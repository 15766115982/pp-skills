"""parse_flows.py — kb/_raw/flows/*.json -> kb/flows/<flowname>.md.

Renders per flow: trigger config, action table with runAfter, mermaid dependency
graph (conditions as rhombi, true/false branches), connector list (from the
dedicated connectionreferences column first), tables touched, boundary marking.

clientdata inner JSON has NO official schema — every access is defensive:
missing fields degrade to empty output with a note, never a crash.
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
from export_flows import decompress_clientdata, parse_embedded_json

SAFE_ID = re.compile(r"[^A-Za-z0-9_]")
TABLE_PATH = re.compile(r"/tables/([^/\"']+)")
TABLE_KEYS = {"table", "entityname", "entity", "tablename"}


def slug(name: str) -> str:
    return SAFE_ID.sub("_", name)


def runafter_of(action: dict) -> dict:
    """Normalize runAfter: {prev_name: [statuses]} handling old list format."""
    out = {}
    ra = action.get("runAfter") or {}
    if isinstance(ra, dict):
        for prev, val in ra.items():
            if isinstance(val, list):
                out[prev] = [s.get("actionStatus", "Succeeded") if isinstance(s, dict) else str(s) for s in val]
            elif isinstance(val, dict):
                out[prev] = [val.get("actionStatus", "Succeeded")]
    return out


def walk_actions(actions: dict, rows: list, edges: list, parent_labels: dict | None = None,
                 branch: str | None = None) -> None:
    """Recursively collect action rows + runAfter edges.

    rows:  (name, type, operation, runafter_text, branch)
    edges: (src, dst, label)
    """
    if not isinstance(actions, dict):
        return
    prev_by_branch: dict = parent_labels if parent_labels is not None else {}
    for name, action in actions.items():
        if not isinstance(action, dict):
            continue
        atype = action.get("type", "?")
        host = (action.get("inputs") or {}).get("host") or {}
        operation = host.get("operationId", "")
        ra = runafter_of(action)
        ra_text = ", ".join(f"{p} ({'/'.join(ss)})" if ss != ["Succeeded"] else p
                            for p, ss in ra.items()) or "—"
        rows.append({"name": name, "type": atype, "operation": operation,
                     "runafter": ra_text, "branch": branch or "",
                     "action": action, "incoming": ra})
        # nested structures
        if isinstance(action.get("actions"), dict):
            walk_actions(action["actions"], rows, edges, {}, branch="true")
        else_branch = (action.get("else") or {})
        if isinstance(else_branch.get("actions"), dict):
            walk_actions(else_branch["actions"], rows, edges, {}, branch="false")
        for case in ((action.get("cases") or {}).values() if isinstance(action.get("cases"), dict) else []):
            if isinstance(case, dict) and isinstance(case.get("actions"), dict):
                walk_actions(case["actions"], rows, edges, {}, branch=f"case {case.get('value','?')}")
        default_case = action.get("default") or {}
        if isinstance(default_case, dict) and isinstance(default_case.get("actions"), dict):
            walk_actions(default_case["actions"], rows, edges, {}, branch="default")


def build_graph(trigger_name: str, rows: list) -> str:
    """Mermaid flowchart from collected rows (top-level edges only where resolvable)."""
    lines = ["```mermaid", "flowchart TD"]
    trig_id = "TRIG"
    lines.append(f'    {trig_id}(["Trigger: {trigger_name}"])')

    def node_line(row) -> str:
        nid = slug(row["name"])
        label = row["name"] + (f"<br/>{row['operation']}" if row["operation"] else "")
        if row["type"] in ("If", "Switch"):
            return f'    {nid}{{"{label}"}}'
        if row["type"] == "Terminate":
            return f'    {nid}(["{label}"])'
        return f'    {nid}["{label}"]'

    top = [r for r in rows if not r["branch"]]
    nested = [r for r in rows if r["branch"]]
    for r in top + nested:
        lines.append(node_line(r))

    names = {r["name"] for r in rows}
    by_name = {r["name"]: r for r in rows}
    starters = [r for r in top if not r["incoming"]]
    for r in starters:
        lines.append(f"    {trig_id} --> {slug(r['name'])}")
    for r in rows:
        for prev, statuses in r["incoming"].items():
            if prev not in names:
                continue
            label = ""
            if statuses != ["Succeeded"]:
                label = "|" + "/".join(statuses) + "|"
            lines.append(f"    {slug(prev)} -->{label} {slug(r['name'])}")
    # branch edges from conditions to nested actions
    nested_by_branch: dict = {}
    for r in nested:
        nested_by_branch.setdefault(r["branch"], []).append(r)
    cond_rows = [r for r in rows if r["type"] in ("If", "Switch")]
    for cond in cond_rows:
        a = cond["action"]
        if isinstance(a.get("actions"), dict):
            for child in a["actions"]:
                lines.append(f'    {slug(cond["name"])} -- "true" --> {slug(child)}')
        if isinstance((a.get("else") or {}).get("actions"), dict):
            for child in (a.get("else") or {})["actions"]:
                lines.append(f'    {slug(cond["name"])} -- "false" --> {slug(child)}')
        if isinstance(a.get("cases"), dict):
            for case in a["cases"].values():
                for child in (case.get("actions") or {}):
                    lines.append(f'    {slug(cond["name"])} -- "{case.get("value","case")}" --> {slug(child)}')
    lines.append("```")
    return "\n".join(lines)


def find_tables(obj, found: set) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                if k.lower() in TABLE_KEYS and re.fullmatch(r"[A-Za-z0-9_]+", v):
                    found.add(v)
                for m in TABLE_PATH.finditer(v):
                    found.add(m.group(1))
            else:
                find_tables(v, found)
    elif isinstance(obj, list):
        for v in obj:
            find_tables(v, found)


def connector_summary(record: dict, cd: dict) -> list:
    """Prefer the dedicated connectionreferences column; fall back to clientdata."""
    rows, seen = [], set()
    sources = [parse_embedded_json(record.get("connectionreferences")),
               cd.get("connectionReferences") or {}]
    for src in sources:
        refs = src.get("connectionReferences", src) if isinstance(src, dict) else {}
        if not isinstance(refs, dict):
            continue
        for logical, ref in refs.items():
            if not isinstance(ref, dict) or logical in seen:
                continue
            seen.add(logical)
            api = (ref.get("apiId") or ref.get("api", {}).get("id", "") if isinstance(ref.get("api"), dict) else ref.get("apiId") or "")
            short = api.rstrip("/").split("/")[-1] if api else "?"
            rows.append((logical, short, api))
    return rows


def render_flow(record: dict, footer: str) -> str:
    name = record.get("name") or record.get("workflowid", "?")
    cd_text = decompress_clientdata(record)
    cd = parse_embedded_json(cd_text)
    definition = cd.get("definition") or {}
    state = {1: "Activated", 2: "Suspended"}.get(record.get("statecode"), str(record.get("statecode", "?")))

    L = [f"# Flow: {name}", "", "| | |", "|---|---|",
         f"| Workflow ID | `{record.get('workflowid','')}` |",
         f"| State | {state} (statecode {record.get('statecode','?')}) |",
         "| Category | 5 (Modern Flow) |",
         f"| Modified | {record.get('modifiedon','?')} |"]
    if record.get("description"):
        L.append(f"| Description | {record['description']} |")

    # trigger
    triggers = definition.get("triggers") or {}
    L += ["", "## Trigger", ""]
    if triggers:
        L += ["| Name | Type | Kind | Configuration |", "|---|---|---|---|"]
        for tname, t in triggers.items():
            inputs = json.dumps(t.get("inputs", {}), ensure_ascii=False)
            if len(inputs) > 120:
                inputs = inputs[:117] + "..."
            L.append(f"| {tname} | `{t.get('type','?')}` | {t.get('kind','')} | {inputs} |")
    else:
        L.append("_(no triggers found in clientdata — defensive note)_")

    # actions
    rows: list = []
    edges: list = []
    walk_actions(definition.get("actions") or {}, rows, edges)
    L += ["", f"## Actions ({len(rows)}) & dependency graph", "",
          "| Action | Type | Operation | runAfter | Branch |", "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {r['type']} | {r['operation'] or '—'} | {r['runafter']} | {r['branch'] or '—'} |")

    first_trigger = next(iter(triggers), "unknown")
    L += ["", build_graph(first_trigger, rows)]

    # connectors
    conns = connector_summary(record, cd)
    L += ["", "## Connectors used", "", "| Connection reference | Connector | apiId |", "|---|---|---|"]
    for logical, short, api in conns:
        L.append(f"| `{logical}` | {short} | `{api}` |")
    if not conns:
        L.append("| _(none declared)_ | | |")

    # tables
    found: set = set()
    find_tables(definition, found)
    in_kb = set()
    L += ["", "## Tables touched", ""]
    if found:
        L.append(" · ".join(f"`{t}`" for t in sorted(found)))
    else:
        L.append("_(no Dataverse table references detected)_")

    L += ["", "---", f"*{footer}*", ""]
    return "\n".join(L), rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Render kb/_raw/flows/ to kb/flows/ Markdown")
    ap.add_argument("--config", help="path to pp-kb.config.json")
    args = ap.parse_args()

    cfg = pp.load_config(args.config)
    raw_dir = os.path.join(cfg["outputDir"], "_raw", "flows")
    out_dir = os.path.join(cfg["outputDir"], "flows")
    files = sorted(p for p in glob.glob(os.path.join(raw_dir, "*.json"))
                   if not os.path.basename(p).startswith("_"))
    if not files:
        pp.die(f"no raw flows found in {raw_dir} — run export_flows.py first")
    index = {}
    index_path = os.path.join(raw_dir, "_index.json")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
    footer = "Snapshot: {} | {} | Raw: `_raw/flows/` (clientdata sanitized)".format(
        index.get("environment", cfg.get("dataverseUrl", "?")), index.get("capturedAt", "?"))

    os.makedirs(out_dir, exist_ok=True)
    for path in files:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
        text, _rows = render_flow(record, footer)
        fname = re.sub(r"[^A-Za-z0-9_.-]+", "-", (record.get("name") or record["workflowid"])).strip("-").lower()
        pp.write_text(os.path.join(out_dir, f"{fname}.md"), text)
        pp.log(f"[parse]   {record.get('name')} -> {fname}.md")

    hits = pp.redaction_scan_dir(cfg["outputDir"])
    if hits:
        pp.die("redaction scan FAILED:\n" + "\n".join(hits))
    pp.log("[parse] redaction scan: PASS")


if __name__ == "__main__":
    main()
