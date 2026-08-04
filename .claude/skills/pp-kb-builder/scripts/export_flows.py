"""export_flows.py — capture Power Automate flow definitions to kb/_raw/flows/.

Source: Dataverse `workflow` table, category=5 (Modern Flow).
Verified facts (docs/skill-implementation-plan.md §4.3):
  - `connectionreferences` is a dedicated Memo column -> preferred connector source
  - `clientdataiscompressed` flags gzip+base64 clientdata
  - clientdata inner JSON has NO official schema -> defensive parsing
  - `$authentication` etc. are stripped at capture time (sanitization happens HERE,
    so kb/_raw/ is already safe to commit)

Filters (config "filters"):
  solutions: [uniqueName, ...] -> solutioncomponents componenttype 29 (fallback: full + warn)
  flows:     [pattern, ...]    -> display name, fnmatch wildcards
"""

from __future__ import annotations

import argparse
import base64
import datetime
import fnmatch
import gzip
import json
import os
import sys
import urllib.parse
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pp_common as pp

FLOW_SELECT = "workflowid,name,clientdata,clientdataiscompressed,connectionreferences,statecode,description,modifiedon,_solutionid_value"
COMPONENTTYPE_WORKFLOW = 29


def q(params: dict) -> str:
    return urllib.parse.urlencode(params, safe=",$()=' ")


def parse_embedded_json(value):
    """clientdata / connectionreferences arrive as JSON *strings*; parse defensively."""
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def decompress_clientdata(record: dict):
    """Return the clientdata JSON string, transparently handling compression.

    Compressed form is base64(gzip(json)); be tolerant of zlib/plain too."""
    raw = record.get("clientdata") or ""
    if not record.get("clientdataiscompressed"):
        return raw
    try:
        blob = base64.b64decode(raw)
    except Exception:
        return raw  # not base64 -> treat as plain text
    for decompress in (gzip.decompress, zlib.decompress):
        try:
            return decompress(blob).decode("utf-8")
        except Exception:
            continue
    return raw


def sanitize_flow_record(record: dict) -> tuple[dict, list]:
    """Redact a workflow row. The sensitive parts hide INSIDE JSON strings,
    so plain dict redaction is not enough — parse, redact, re-serialize."""
    findings: list = []
    out = dict(record)

    cd_text = decompress_clientdata(record)
    cd_obj = parse_embedded_json(cd_text)
    if cd_obj:
        cd_clean, f1 = pp.redact(cd_obj, "/clientdata")
        findings += f1
        out["clientdata"] = json.dumps(cd_clean, ensure_ascii=False)
    else:
        out["clientdata"] = cd_text

    cr_obj = parse_embedded_json(record.get("connectionreferences"))
    if cr_obj:
        cr_clean, f2 = pp.redact(cr_obj, "/connectionreferences")
        findings += f2
        # keep connector identity, mask instance GUIDs
        refs = cr_clean.get("connectionReferences", cr_clean)
        if isinstance(refs, dict):
            for ref in refs.values() if all(isinstance(v, dict) for v in refs.values()) else []:
                for key in ("connectionName", "id", "connectionId"):
                    if key in ref:
                        ref[key] = "<redacted-instance>"
                        findings.append(f"/connectionreferences/{key}")
        out["connectionreferences"] = json.dumps(cr_clean, ensure_ascii=False)

    clean, f3 = pp.redact(out)
    findings += f3
    return clean, findings


def match_flows(records: list, patterns: list) -> tuple[list, list]:
    """Display-name matching with fnmatch wildcards. Returns (matched, warnings)."""
    if not patterns:
        return records, []
    matched, warnings = [], []
    for pat in patterns:
        hits = [r for r in records if fnmatch.fnmatchcase((r.get("name") or "").lower(), pat.lower())]
        if hits:
            matched.extend(h for h in hits if h not in matched)
        else:
            warnings.append(f"[filter] flow pattern '{pat}' matched nothing")
    return matched, warnings


def resolve_solution_flows(cfg: dict, token: str, solution_names: list) -> set | None:
    """solution unique names -> set of workflowids (componenttype 29).
    For workflows the component _objectid_value IS the workflowid."""
    wanted: set = set()
    for name in solution_names:
        try:
            sol = pp.api_get(cfg, token, "solutions?" + q({
                "$filter": f"uniquename eq '{name}'", "$select": "solutionid,uniquename"}))
            rows = sol.get("value", [])
            if not rows:
                pp.log(f"[filter] solution '{name}' not found — falling back to FULL capture")
                return None
            comps = pp.api_get(cfg, token, "solutioncomponents?" + q({
                "$filter": f"_solutionid_value eq {rows[0]['solutionid']} and componenttype eq {COMPONENTTYPE_WORKFLOW}",
                "$select": "_objectid_value"}))
            wanted |= {c["_objectid_value"] for c in comps.get("value", [])}
            pp.log(f"[filter] solution '{name}' -> {len(wanted)} flow(s) so far")
        except Exception as e:
            pp.log(f"[filter] solution lookup failed for '{name}': {e} — falling back to FULL capture")
            return None
    return wanted


def main() -> None:
    ap = argparse.ArgumentParser(description="Export modern flows (workflow category=5) to kb/_raw/flows/")
    ap.add_argument("--config", help="path to pp-kb.config.json")
    args = ap.parse_args()

    cfg = pp.load_config(args.config)
    out_dir = os.path.join(cfg["outputDir"], "_raw", "flows")
    filters = cfg.get("filters", {})

    token = pp.get_token(cfg)
    resp = pp.api_get(cfg, token, "workflows?" + q({
        "$filter": "category eq 5", "$select": FLOW_SELECT}))
    records = resp.get("value", [])
    pp.log(f"[export] {len(records)} modern flow(s) in environment")

    sol_names = filters.get("solutions") or []
    if sol_names:
        scope = resolve_solution_flows(cfg, token, sol_names)
        if scope is not None:
            records = [r for r in records if r.get("workflowid") in scope]
    records, warnings = match_flows(records, filters.get("flows") or [])
    for w in warnings:
        pp.log(w)
    pp.log(f"[export] capturing {len(records)} flow(s)")

    redaction_log = []
    for r in records:
        clean, findings = sanitize_flow_record(r)
        redaction_log.extend(findings)
        pp.write_json(os.path.join(out_dir, f"{r['workflowid']}.json"), clean)
        pp.log(f"[export]   {r.get('name')} ({r['workflowid'][:8]}…)")

    index = {
        "capturedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "environment": cfg["dataverseUrl"],
        "filters": filters,
        "flows": sorted((r.get("name") or r["workflowid"]) for r in records),
        "note": "Raw workflow rows. clientdata/connectionreferences sanitized at capture.",
    }
    pp.write_json(os.path.join(out_dir, "_index.json"), index)
    if redaction_log:
        log_path = os.path.join(cfg["outputDir"], "_raw", "REDACTION-LOG.md")
        existing = ""
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8") as f:
                existing = f.read() + "\n"
        pp.write_text(log_path, existing + "# Flow capture redactions\n\n"
                      + "\n".join(f"- `{x}`" for x in redaction_log) + "\n")
    pp.log(f"[export] done -> {out_dir}")


if __name__ == "__main__":
    try:
        main()
    except pp.ConfigError as e:
        pp.die(str(e))
