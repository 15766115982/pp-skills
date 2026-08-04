"""export_metadata.py — capture Dataverse table metadata to kb/_raw/metadata/.

Strategy (verified against MS Learn, see docs/skill-implementation-plan.md §4.2):
  1. Entity list via EntityDefinitions?$select=... (light).
  2. Per entity: base $expand=Attributes + three relationship collections.
  3. Per entity: type-cast requests to enrich Picklist/State/Status attributes
     with their OptionSet (one $expand can only cast one type).
  4. Redact, write one JSON per table + _index.json snapshot.

Filters (config "filters"):
  solutions: [uniqueName, ...]  -> via solutioncomponents (fallback: full + warn)
  tables:    [name, ...]        -> dual match on LogicalName / DisplayName (case-insensitive)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pp_common as pp

ENTITY_SELECT = "LogicalName,DisplayName,SchemaName,EntitySetName,PrimaryIdAttribute,PrimaryNameAttribute,OwnershipType,MetadataId,IsCustomEntity"
REL_SELECT_1N = "SchemaName,ReferencedEntity,ReferencingEntity,ReferencingAttribute,CascadeConfiguration"
REL_SELECT_N1 = "SchemaName,ReferencedEntity,ReferencingEntity,ReferencedAttribute,ReferencingAttribute"
REL_SELECT_NN = "SchemaName,Entity1LogicalName,Entity2LogicalName,IntersectTableName"
CASTS = ["Picklist", "State", "Status"]  # AttributeMetadata derived types needing OptionSet


def q(params: dict) -> str:
    return urllib.parse.urlencode(params, safe=",$()=' ")


def fetch_entity_list(cfg: dict, token: str) -> list:
    resp = pp.api_get(cfg, token, "EntityDefinitions?" + q({"$select": ENTITY_SELECT}))
    return resp.get("value", [])


def resolve_solution_entities(cfg: dict, token: str, solution_names: list) -> set | None:
    """Map solution unique names -> set of entity LogicalNames via solutioncomponents.
    Returns None (caller falls back to full capture) if anything is unclear."""
    wanted: set = set()
    for name in solution_names:
        try:
            sol = pp.api_get(cfg, token, "solutions?" + q({
                "$filter": f"uniquename eq '{name}'",
                "$select": "solutionid,uniquename,friendlyname,version",
            }))
            rows = sol.get("value", [])
            if not rows:
                pp.log(f"[filter] solution '{name}' not found — falling back to FULL capture")
                return None
            sid = rows[0]["solutionid"]
            comps = pp.api_get(cfg, token, "solutioncomponents?" + q({
                "$filter": f"_solutionid_value eq {sid} and componenttype eq 1",
                "$select": "_objectid_value",
            }))
            meta_ids = {c["_objectid_value"] for c in comps.get("value", [])}
            if not meta_ids:
                pp.log(f"[filter] solution '{name}' contains no entities")
                continue
            # Map MetadataId -> LogicalName
            listing = pp.api_get(cfg, token, "EntityDefinitions?" + q({"$select": "LogicalName,MetadataId"}))
            for e in listing.get("value", []):
                if e.get("MetadataId") in meta_ids:
                    wanted.add(e["LogicalName"])
            pp.log(f"[filter] solution '{name}' -> {len(wanted)} entities so far")
        except Exception as e:  # association shape may vary; degrade loudly, never silently
            pp.log(f"[filter] solution lookup failed for '{name}': {e} — falling back to FULL capture")
            return None
    return wanted


def match_tables(entity_list: list, name_filters: list, lang: int) -> tuple[list, list]:
    """Dual-channel match: LogicalName exact (ci), then DisplayName (ci). Returns (matched, warnings)."""
    by_logical = {e["LogicalName"].lower(): e for e in entity_list}
    by_display = {}
    for e in entity_list:
        disp = pp.label_of(e.get("DisplayName"), lang)
        if disp:
            by_display.setdefault(disp.lower(), e)
    matched, warnings, seen = [], [], set()
    for name in name_filters:
        key = name.lower()
        hit = by_logical.get(key) or by_display.get(key)
        if hit:
            if hit["LogicalName"] not in seen:
                matched.append(hit)
                seen.add(hit["LogicalName"])
        else:
            warnings.append(f"[filter] table '{name}' matched nothing (tried logical + display name)")
    return matched, warnings


def fetch_entity_detail(cfg: dict, token: str, logical: str) -> dict:
    detail = pp.api_get(cfg, token, f"EntityDefinitions(LogicalName='{logical}')?" + q({
        "$expand": (
            f"Attributes,"
            f"OneToManyRelationships($select={REL_SELECT_1N}),"
            f"ManyToOneRelationships($select={REL_SELECT_N1}),"
            f"ManyToManyRelationships($select={REL_SELECT_NN})"
        )
    }))
    # Enrich enum-ish attributes with OptionSet via per-type casts.
    options_by_attr: dict = {}
    for cast in CASTS:
        try:
            resp = pp.api_get(cfg, token,
                f"EntityDefinitions(LogicalName='{logical}')/Attributes/Microsoft.Dynamics.CRM.{cast}AttributeMetadata?"
                + q({"$select": "LogicalName", "$expand": "OptionSet"}))
            for attr in resp.get("value", []):
                if attr.get("OptionSet"):
                    options_by_attr[attr["LogicalName"]] = attr["OptionSet"]
        except Exception as e:
            pp.log(f"[warn] {cast} cast failed for {logical}: {e}")
    for attr in detail.get("Attributes", []):
        if attr.get("LogicalName") in options_by_attr:
            attr["OptionSet"] = options_by_attr[attr["LogicalName"]]
    return detail


def main() -> None:
    ap = argparse.ArgumentParser(description="Export Dataverse metadata to kb/_raw/metadata/")
    ap.add_argument("--config", help="path to pp-kb.config.json")
    args = ap.parse_args()

    cfg = pp.load_config(args.config)
    out_dir = os.path.join(cfg["outputDir"], "_raw", "metadata")
    filters = cfg.get("filters", {})
    lang = cfg["labelLanguage"]

    token = pp.get_token(cfg)
    entity_list = fetch_entity_list(cfg, token)
    pp.log(f"[export] {len(entity_list)} entities in environment")

    # --- resolve scope -----------------------------------------------------
    sol_names = filters.get("solutions") or []
    table_names = filters.get("tables") or []
    scope: set | None = None
    if sol_names:
        scope = resolve_solution_entities(cfg, token, sol_names)
    if table_names:
        matched, warnings = match_tables(entity_list, table_names, lang)
        for w in warnings:
            pp.log(w)
        name_scope = {e["LogicalName"] for e in matched}
        scope = name_scope if scope is None else (scope & name_scope)
    targets = [e for e in entity_list if scope is None or e["LogicalName"] in scope]
    pp.log(f"[export] capturing {len(targets)} table(s)")

    # --- capture -----------------------------------------------------------
    redaction_log = []
    for e in targets:
        logical = e["LogicalName"]
        detail = fetch_entity_detail(cfg, token, logical)
        clean, findings = pp.redact(detail)
        redaction_log.extend(findings)
        pp.write_json(os.path.join(out_dir, f"{logical}.json"), clean)
        pp.log(f"[export]   {logical}: {len(detail.get('Attributes', []))} attributes")

    index = {
        "capturedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "environment": cfg["dataverseUrl"],
        "labelLanguage": lang,
        "filters": filters,
        "tables": sorted(t["LogicalName"] for t in targets),
        "note": "Raw metadata snapshots. Sanitized. Knowledge base is fully rebuildable from these files.",
    }
    pp.write_json(os.path.join(out_dir, "_index.json"), index)
    if redaction_log:
        pp.write_text(os.path.join(cfg["outputDir"], "_raw", "REDACTION-LOG.md"),
                      "# Redaction log\n\n" + "\n".join(f"- `{f}`" for f in redaction_log) + "\n")
    pp.log(f"[export] done -> {out_dir}")


if __name__ == "__main__":
    try:
        main()
    except pp.ConfigError as e:
        pp.die(str(e))
