"""build_crossrefs.py — cross-artifact reference graph -> kb/REFERENCES.md (+ crossrefs.json).

The differentiator (docs/skill-implementation-plan.md §4.4): "which table is used
by which apps/flows" — no existing tool covers this.

Matching (deterministic, explainable):
  Canvas app -> tables:     DataSources entries with Type=Table -> Parameters.TableLogicalName
  Flow -> tables:           table/entityName keys + /tables/ paths in action inputs,
                            resolved against KB logical names / entity set names / display names
  Connectors:               flow connectionreferences apiId + canvas DataSources Actions ConnectorId
  Boundary rule:            referenced objects not in KB are marked "(external — not in KB)",
                            never dead links

Also rewrites the "## Used by" section of each dataverse/tables/*.md in place
(between the "## Used by" heading and the footer separator) — deterministic.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pp_common as pp
import parse_canvas as pc
from export_flows import decompress_clientdata, parse_embedded_json
from parse_flows import find_tables, connector_summary

EXTERNAL = "(external — not in KB)"


def load_kb_tables(raw_dir: str) -> dict:
    """{logical_lower: {"logical":..., "display":..., "entityset":...}}"""
    tables = {}
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        if os.path.basename(path).startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            e = json.load(f)
        tables[e["LogicalName"].lower()] = {
            "logical": e["LogicalName"],
            "display": pp.label_of(e.get("DisplayName"), 1033),
            "entityset": e.get("EntitySetName", ""),
        }
    return tables


def resolve_table(name: str, kb_tables: dict) -> str | None:
    """Map a raw reference (logical / entity set / display) to a KB logical name."""
    key = name.lower()
    if key in kb_tables:
        return kb_tables[key]["logical"]
    for t in kb_tables.values():
        if key in (t["entityset"].lower(), t["display"].lower()):
            return t["logical"]
    return None


def flow_slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-").lower()


def collect_flow_refs(raw_dir: str, kb_tables: dict) -> tuple[dict, dict]:
    """{flow_name: {"tables": [logical|external], "connectors": [(ref, short, apiId)]}}"""
    flows, externals = {}, set()
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        if os.path.basename(path).startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
        name = rec.get("name") or rec["workflowid"]
        cd = parse_embedded_json(decompress_clientdata(rec))
        raw_names: set = set()
        find_tables(cd.get("definition") or {}, raw_names)
        tables = []
        for rn in sorted(raw_names):
            hit = resolve_table(rn, kb_tables)
            tables.append(hit or f"{rn} {EXTERNAL}")
            if not hit:
                externals.add(rn)
        flows[name] = {"tables": tables, "connectors": connector_summary(rec, cd)}
    return flows, externals


def collect_app_refs(cfg: dict, kb_tables: dict) -> tuple[dict, set]:
    """{app_name: {"tables": [...], "connectors": [connectorId]}}"""
    apps, externals = {}, set()
    for app_name, src_dir in pc.find_apps(cfg["canvasSourcePath"]):
        merged, _prov = pc.load_app(src_dir)
        tables, connectors = [], []
        for ds_name, ds in (merged.get("DataSources") or {}).items():
            ds = ds or {}
            if ds.get("Type") == "Table":
                logical = (ds.get("Parameters") or {}).get("TableLogicalName", "")
                hit = resolve_table(logical, kb_tables) if logical else None
                tables.append(hit or f"{logical or ds_name} {EXTERNAL}")
                if not hit:
                    externals.add(logical or str(ds_name))
            elif ds.get("ConnectorId"):
                connectors.append(ds["ConnectorId"])
        apps[app_name] = {"tables": sorted(set(tables)), "connectors": sorted(set(connectors))}
    return apps, externals


def render_references(apps: dict, flows: dict, kb_tables: dict, footer: str) -> str:
    logicals = sorted(t["logical"] for t in kb_tables.values())

    def apps_of(logical):
        return sorted(a for a, d in apps.items() if logical in d["tables"])

    def flows_of(logical):
        return sorted(f for f, d in flows.items() if logical in d["tables"])

    L = ["# Cross-Artifact References", ""]

    L += ["## Table → Apps", "", "| Table (logical) | Display name | Used by apps |", "|---|---|---|"]
    for t in logicals:
        info = kb_tables[t.lower()]
        used = apps_of(t)
        L.append(f"| `{t}` | {info['display']} | {', '.join(used) or '—'} |")
    ext_in_apps = sorted({x for d in apps.values() for x in d["tables"] if x.endswith(EXTERNAL)})
    for x in ext_in_apps:
        used = sorted(a for a, d in apps.items() if x in d["tables"])
        L.append(f"| {x} | — | {', '.join(used)} |")

    L += ["", "## Table → Flows", "", "| Table (logical) | Display name | Used by flows |", "|---|---|---|"]
    for t in logicals:
        info = kb_tables[t.lower()]
        used = flows_of(t)
        L.append(f"| `{t}` | {info['display']} | {', '.join(used) or '—'} |")
    ext_in_flows = sorted({x for d in flows.values() for x in d["tables"] if x.endswith(EXTERNAL)})
    for x in ext_in_flows:
        used = sorted(f for f, d in flows.items() if x in d["tables"])
        L.append(f"| {x} | — | {', '.join(used)} |")

    # connector -> artifacts
    conn_map: dict = {}
    for a, d in apps.items():
        for cid in d["connectors"]:
            conn_map.setdefault(cid, set()).add(a)
    for f, d in flows.items():
        for _ref, short, _api in d["connectors"]:
            conn_map.setdefault(short, set()).add(f)
    L += ["", "## Connector → Artifacts", "", "| Connector | Artifacts |", "|---|---|"]
    for cid in sorted(conn_map):
        L.append(f"| `{cid}` | {', '.join(sorted(conn_map[cid]))} |")

    # graph
    L += ["", "## Reference graph", "", "```mermaid", "flowchart LR"]
    if apps:
        L.append("    subgraph Apps")
        L += [f'        A{i}["{a}"]' for i, a in enumerate(sorted(apps))]
        L.append("    end")
    if flows:
        L.append("    subgraph Flows")
        L += [f'        F{i}["{f}"]' for i, f in enumerate(sorted(flows))]
        L.append("    end")
    L.append("    subgraph Tables")
    t_ids = {}
    for i, t in enumerate(logicals):
        t_ids[t] = f"T{i}"
        L.append(f'        T{i}[("{t}")]')
    ext_all = sorted(set(ext_in_apps) | set(ext_in_flows))
    for i, x in enumerate(ext_all):
        node = x.replace(f" {EXTERNAL}", "")
        t_ids[x] = f"X{i}"
        L.append(f'        X{i}["{node}<br/>{EXTERNAL}"]')
    L.append("    end")
    a_ids = {a: f"A{i}" for i, a in enumerate(sorted(apps))}
    f_ids = {f: f"F{i}" for i, f in enumerate(sorted(flows))}
    for a in sorted(apps):
        for t in apps[a]["tables"]:
            if t in t_ids:
                L.append(f"    {a_ids[a]} --> {t_ids[t]}")
    for f in sorted(flows):
        for t in flows[f]["tables"]:
            if t in t_ids:
                L.append(f"    {f_ids[f]} --> {t_ids[t]}")
    L += ["```", "", "---", f"*{footer}*", ""]
    return "\n".join(L)


USED_BY_RE = re.compile(r"\n## Used by\n.*?(?=\n---\n\*)", re.DOTALL)


def rewrite_used_by(out_dir: str, apps: dict, flows: dict, kb_tables: dict) -> None:
    tdir = os.path.join(out_dir, "dataverse", "tables")
    for path in sorted(glob.glob(os.path.join(tdir, "*.md"))):
        logical = os.path.splitext(os.path.basename(path))[0]
        used_apps = sorted(a for a, d in apps.items() if logical in d["tables"])
        used_flows = sorted(f for f, d in flows.items() if logical in d["tables"])
        lines = ["\n## Used by", ""]
        if used_apps:
            lines.append("- **Apps**: " + ", ".join(
                f"[{a}](../../apps/{a}/overview.md)" for a in used_apps))
        if used_flows:
            lines.append("- **Flows**: " + ", ".join(
                f"[{f}](../../flows/{flow_slug(f)}.md)" for f in used_flows))
        if not used_apps and not used_flows:
            lines.append("_(no in-KB artifacts reference this table)_")
        lines.append("")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new, n = USED_BY_RE.subn("\n".join(lines), text)
        if n:
            pp.write_text(path, new)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build kb/REFERENCES.md and rewrite Used-by sections")
    ap.add_argument("--config", help="path to pp-kb.config.json")
    args = ap.parse_args()

    cfg = pp.load_config(args.config)
    out_dir = cfg["outputDir"]
    kb_tables = load_kb_tables(os.path.join(out_dir, "_raw", "metadata"))
    if not kb_tables:
        pp.die("no raw metadata — run export_metadata.py + parse_metadata.py first")

    flows, ext_flows = collect_flow_refs(os.path.join(out_dir, "_raw", "flows"), kb_tables)
    apps, ext_apps = collect_app_refs(cfg, kb_tables)

    def _index_env():
        for sub in ("metadata", "flows"):
            p = os.path.join(out_dir, "_raw", sub, "_index.json")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    env = json.load(f).get("environment")
                if env:
                    return env
        return cfg.get("dataverseUrl", os.environ.get("PP_DATAVERSE_URL", "?"))

    footer = f"Snapshot: {_index_env()} | cross-reference build"

    pp.write_text(os.path.join(out_dir, "REFERENCES.md"),
                  render_references(apps, flows, kb_tables, footer))
    rewrite_used_by(out_dir, apps, flows, kb_tables)
    pp.write_json(os.path.join(out_dir, "_raw", "crossrefs.json"), {
        "apps": apps, "flows": {k: v["tables"] for k, v in flows.items()},
        "externalTables": sorted(ext_apps | ext_flows),
        "tables": sorted(t["logical"] for t in kb_tables.values()),
    })
    pp.log(f"[xref] {len(apps)} apps, {len(flows)} flows, {len(kb_tables)} tables, "
           f"{len(ext_apps | ext_flows)} external refs -> REFERENCES.md")

    hits = pp.redaction_scan_dir(out_dir)
    if hits:
        pp.die("redaction scan FAILED:\n" + "\n".join(hits))
    pp.log("[xref] redaction scan: PASS")


if __name__ == "__main__":
    main()
