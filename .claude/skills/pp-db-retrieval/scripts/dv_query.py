"""dv_query.py — read-only Dataverse retrieval CLI (pp-db-retrieval).

Four query shapes:
  --table + --select/--filter/--orderby/--top/--expand      OData entity-set query
  --sql "SELECT ..."                                        T-SQL subset via ?sql= (GET)
  --fetchxml "<fetch>..." / --fetchxml-file q.xml           FetchXML via ?fetchXml= (GET)
  --table + --apply "groupby(...)"                          server-side aggregation

Read-only guarantees (layered):
  1. All HTTP is GET (enforced in pp_common.api_get).
  2. SQL is validated read-only before sending (SELECT-only, no DML/DDL/multiple
     statements/comments).
  3. FetchXML is validated read-only before sending (no <insert>/<update>/<delete>,
     and no custom actions that mutate).
  4. --table entity set is resolved from the LOCAL kb first (kb/dataverse/tables),
     falling back to a live EntityDefinitions lookup.

Output: --format table|csv|json (table prints to stdout; csv/json need -o).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pp_common as pp

MAX_PAGES_DEFAULT = 200          # hard stop against runaway pagination
SQL_ROW_CAP = 5000               # server silently truncates at ~5000 rows

# ------------------------------------------------------------------ guards

_SQL_FORBIDDEN_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|UPSERT|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|"
    r"EXEC|EXECUTE|INTO)\s|xp_|sp_", re.IGNORECASE)
_SQL_FORBIDDEN_TOKENS = re.compile(r"--|/\*|\*/|;\s*\S")


def guard_sql(sql: str) -> str:
    """Raise unless `sql` is a single read-only SELECT."""
    s = sql.strip()
    if not re.match(r"(?is)^\s*SELECT\b", s):
        raise ValueError("SQL must start with SELECT (read-only skill)")
    m = _SQL_FORBIDDEN_WORDS.search(s) or _SQL_FORBIDDEN_TOKENS.search(s)
    if m:
        raise ValueError(f"SQL rejected (write/forbidden token near '{m.group(0).strip()}')")
    return s


_FETCHXML_FORBIDDEN = re.compile(r"<(insert|update|delete|upsert|merge)\b", re.IGNORECASE)


def guard_fetchxml(fx: str) -> str:
    s = fx.strip()
    if not re.match(r"(?is)^\s*<fetch\b", s):
        raise ValueError("FetchXML must start with <fetch>")
    if _FETCHXML_FORBIDDEN.search(s):
        raise ValueError("FetchXML rejected (contains a mutating element)")
    return s


# ------------------------------------------------------------- entity set

def resolve_entity_set(table: str, cfg: dict, token: str | None) -> tuple[str, str]:
    """(entity_set_name, source). Local kb first, then live metadata."""
    kb_dir = os.path.join(cfg["outputDir"], "dataverse", "tables")
    # exact logical-name file
    for cand in (table, table.lower()):
        p = os.path.join(kb_dir, f"{cand}.md")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    m = re.match(r"\| Entity set \| `([^`]+)` \|", line)
                    if m:
                        return m.group(1), "local kb"
    # scan all table docs for display/logical match
    if os.path.isdir(kb_dir):
        for fn in sorted(os.listdir(kb_dir)):
            if not fn.endswith(".md"):
                continue
            with open(os.path.join(kb_dir, fn), encoding="utf-8") as f:
                head = f.read(4000)
            logical = re.search(r"\| Logical name \| `([^`]+)` \|", head)
            display = re.search(r"\| Display name \| ([^|]+) \|", head)
            eset = re.search(r"\| Entity set \| `([^`]+)` \|", head)
            names = {x.strip().lower() for x in (logical.group(1) if logical else "",
                                                 display.group(1) if display else "") if x}
            if table.lower() in names and eset:
                return eset.group(1), "local kb"
    if token is None:
        raise ValueError(
            f"'{table}' not found in local kb ({kb_dir}) and no token for live lookup. "
            "Refresh the knowledge base or check the table name.")
    resp = pp.api_get(cfg, token,
        "EntityDefinitions?" + urllib.parse.urlencode(
            {"$filter": f"LogicalName eq '{table.lower()}'", "$select": "EntitySetName"},
            safe="$ '"))
    rows = resp.get("value", [])
    if not rows:
        raise ValueError(f"'{table}' not found as a Dataverse logical name either — refusing to guess.")
    return rows[0]["EntitySetName"], "live EntityDefinitions"


# ------------------------------------------------------------------ request

def paged_get(cfg: dict, token: str, path_and_query: str, max_pages: int) -> tuple[list, int]:
    """Follow @odata.nextLink. Returns (rows, page_count)."""
    rows, pages = [], 0
    url_path: str | None = path_and_query
    while url_path:
        resp = pp.api_get(cfg, token, url_path)
        rows.extend(resp.get("value", []))
        pages += 1
        nxt = resp.get("@odata.nextLink")
        if not nxt or pages >= max_pages:
            if nxt and pages >= max_pages:
                pp.log(f"[warn] stopped at max-pages={max_pages}; result may be incomplete")
            break
        # nextLink is absolute; strip back to path after /api/data/vX/
        m = re.search(r"/api/data/v[\d.]+/(.+)$", nxt)
        url_path = m.group(1) if m else None
    return rows, pages


def build_odata_query(args) -> str:
    params = {}
    if args.select:
        params["$select"] = args.select
    if args.filter:
        params["$filter"] = args.filter
    if args.orderby:
        params["$orderby"] = args.orderby
    if args.top:
        params["$top"] = str(args.top)
    if args.expand:
        params["$expand"] = args.expand
    if args.apply:
        params["$apply"] = args.apply
    if args.count:
        params["$count"] = "true"
    return urllib.parse.urlencode(params, safe=",$()'= ")


# ------------------------------------------------------------------ output

def format_rows(rows: list, fmt: str, out_path: str | None) -> None:
    if fmt == "json":
        text = json.dumps(rows, ensure_ascii=False, indent=2)
        if out_path:
            pp.write_text(out_path, text + "\n")
        else:
            print(text)
        return
    cols = sorted({k for r in rows for k in r.keys() if not k.startswith("@")})
    if fmt == "csv":
        if not out_path:
            pp.die("--format csv requires -o <file>")
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        return
    # table
    if not rows:
        print("(0 rows)")
        return
    widths = {c: min(max(len(c), *(len(str(r.get(c, ""))) for r in rows[:100])), 40) for c in cols}
    print(" | ".join(c.ljust(widths[c]) for c in cols))
    print("-+-".join("-" * widths[c] for c in cols))
    for r in rows:
        print(" | ".join(str(r.get(c, ""))[:widths[c]].ljust(widths[c]) for c in cols))


# ------------------------------------------------------------------ main

def _rows_from_entityset(resp: dict) -> list:
    """Extract row list from a ?sql= / ?fetchXml= response (defensive: the
    response wraps rows in 'value' for both)."""
    return resp.get("value", [])


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only Dataverse query (GET only)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--table", help="logical/display name (resolved via local kb first)")
    src.add_argument("--sql", help="T-SQL subset (SELECT only, enforced)")
    src.add_argument("--fetchxml", help="FetchXML string (read-only, enforced)")
    src.add_argument("--fetchxml-file", help="path to FetchXML file")
    src.add_argument("--entityset", help="explicit entity set to prefix for --sql/--fetchxml (default 'accounts')")
    ap.add_argument("--select"); ap.add_argument("--filter"); ap.add_argument("--orderby")
    ap.add_argument("--expand"); ap.add_argument("--apply")
    ap.add_argument("--top", type=int); ap.add_argument("--count", action="store_true")
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES_DEFAULT)
    ap.add_argument("--format", choices=["table", "csv", "json"], default="table")
    ap.add_argument("-o", "--out", help="output file (csv/json)")
    ap.add_argument("--config", help="path to pp-kb.config.json")
    args = ap.parse_args()

    cfg = pp.load_config(args.config)
    token = pp.get_token(cfg)

    if args.sql is not None:
        sql = guard_sql(args.sql)
        entity_set = args.entityset or "accounts"
        path = f"{entity_set}?" + urllib.parse.urlencode({"sql": sql})
        pp.log(f"[query] SQL mode via {entity_set}?sql= (server caps at ~5000 rows)")
        resp = pp.api_get(cfg, token, path)
        rows = _rows_from_entityset(resp)
        if len(rows) >= SQL_ROW_CAP:
            pp.log(f"[warn] {len(rows)} rows returned — at/over the silent 5000-row cap; narrow the query")
        format_rows(rows, args.format, args.out)
        pp.log(f"[query] {len(rows)} row(s)")
        return

    if args.fetchxml is not None or args.fetchxml_file is not None:
        fx = args.fetchxml
        if args.fetchxml_file:
            with open(args.fetchxml_file, encoding="utf-8") as f:
                fx = f.read()
        fx = guard_fetchxml(fx)
        entity_set = args.entityset or "accounts"
        path = f"{entity_set}?" + urllib.parse.urlencode({"fetchXml": fx})
        resp = pp.api_get(cfg, token, path)
        rows = _rows_from_entityset(resp)
        format_rows(rows, args.format, args.out)
        pp.log(f"[query] {len(rows)} row(s) via FetchXML")
        return

    # OData table mode
    entity_set, source = resolve_entity_set(args.table, cfg, token)
    pp.log(f"[query] '{args.table}' -> {entity_set} (via {source})")
    query = build_odata_query(args)
    path = entity_set + ("?" + query if query else "")
    rows, pages = paged_get(cfg, token, path, args.max_pages)
    format_rows(rows, args.format, args.out)
    pp.log(f"[query] {len(rows)} row(s) in {pages} page(s)")


if __name__ == "__main__":
    try:
        main()
    except pp.ConfigError as e:
        pp.die(str(e))
    except ValueError as e:
        pp.die(f"rejected: {e}")
