"""parse_metadata.py — kb/_raw/metadata/*.json -> kb/dataverse/ Markdown.

Outputs (deterministic; rebuild produces byte-identical files from same _raw):
  dataverse/tables/<logicalname>.md   one per table
  dataverse/optionsets.md             global option sets (if any)
  dataverse/er-overview.md            mermaid erDiagram, boundary nodes for out-of-scope tables
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pp_common as pp

SYSTEM_ATTRS_NOTE = "statecode / statuscode"
ER_MAX_COLS = 8


def load_raw(raw_dir: str) -> dict:
    entities = {}
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        name = os.path.basename(path)
        if name.startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            e = json.load(f)
        entities[e["LogicalName"]] = e
    index_path = os.path.join(raw_dir, "_index.json")
    index = {}
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
    return entities, index


def fmt_type(attr: dict) -> str:
    t = attr.get("AttributeType", "?")
    if t == "String":
        return f"String ({attr.get('MaxLength', '?')})"
    if t == "Memo":
        return f"Memo ({attr.get('MaxLength', '?')})"
    if t == "Integer":
        lo, hi = attr.get("MinValue"), attr.get("MaxValue")
        return f"Integer [{lo}..{hi}]" if lo is not None else "Integer"
    if t == "Money":
        return f"Money (prec {attr.get('Precision', 2)})"
    if t == "DateTime":
        beh = (attr.get("DateTimeBehavior") or {}).get("Value", "")
        return f"DateTime ({beh})" if beh else "DateTime"
    if t == "Lookup":
        return "Lookup"
    if t == "Picklist":
        return "Picklist"
    return t


def fmt_required(attr: dict) -> str:
    v = (attr.get("RequiredLevel") or {}).get("Value", "None")
    return {"ApplicationRequired": "Required", "SystemRequired": "System"}.get(v, "None")


def attr_notes(attr: dict, lang: int) -> str:
    notes = []
    if attr.get("AttributeType") == "Lookup" and attr.get("Targets"):
        notes.append("→ " + ", ".join(f"`{t}`" for t in attr["Targets"]))
    if attr.get("AttributeType") in ("Picklist", "State", "Status") and attr.get("OptionSet"):
        notes.append("→ choices below" if not attr["OptionSet"].get("IsGlobal") else f"→ global set `{attr['OptionSet'].get('Name','')}`")
    if attr.get("IsPrimaryId"):
        notes.append("Primary key")
    if attr.get("IsPrimaryName"):
        notes.append("Primary name")
    return "; ".join(notes)


def render_choices(attr: dict, lang: int) -> str:
    os_ = attr.get("OptionSet") or {}
    options = os_.get("Options") or []
    if not options:
        return ""
    lines = [f"\n## Choice: {attr['LogicalName']}", "", "| Value | Label |", "|---|---|"]
    for o in sorted(options, key=lambda x: (x.get("Value") is None, x.get("Value"))):
        lines.append(f"| {o.get('Value', '—')} | {pp.label_of(o.get('Label'), lang)} |")
    return "\n".join(lines) + "\n"


def render_table(e: dict, lang: int, footer: str, used_by: dict | None = None) -> str:
    logical = e["LogicalName"]
    disp = pp.label_of(e.get("DisplayName"), lang)
    L = [f"# Table: {logical} ({disp})", "", "| | |", "|---|---|"]
    rows = [
        ("Logical name", f"`{logical}`"),
        ("Display name", disp),
        ("Schema name", f"`{e.get('SchemaName','')}`"),
        ("Entity set", f"`{e.get('EntitySetName','')}`"),
        ("Primary ID", f"`{e.get('PrimaryIdAttribute','')}`"),
        ("Primary name", f"`{e.get('PrimaryNameAttribute','')}`"),
        ("Ownership", e.get("OwnershipType", "")),
    ]
    L += [f"| {k} | {v} |" for k, v in rows]

    attrs = sorted(e.get("Attributes", []), key=lambda a: (not a.get("IsPrimaryId"), not a.get("IsPrimaryName"), a.get("LogicalName", "")))
    L += ["", f"## Columns ({len(attrs)})", "", "| Logical name | Display name | Type | Required | Notes |", "|---|---|---|---|---|"]
    for a in attrs:
        L.append("| `{}` | {} | {} | {} | {} |".format(
            a.get("LogicalName", ""), pp.label_of(a.get("DisplayName"), lang),
            fmt_type(a), fmt_required(a), attr_notes(a, lang)))

    body = "\n".join(L) + "\n"
    for a in attrs:
        if a.get("AttributeType") in ("Picklist", "State", "Status") and (a.get("OptionSet") or {}).get("Options"):
            body += render_choices(a, lang)

    rels = []
    for r in e.get("OneToManyRelationships", []):
        cc = (r.get("CascadeConfiguration") or {}).get("Delete", "")
        extra = "Parental (cascade delete)" if cc == "Cascade" else ""
        rels.append(("1:N", r.get("ReferencingEntity", ""), r.get("SchemaName", ""), extra))
    for r in e.get("ManyToOneRelationships", []):
        rels.append(("N:1", r.get("ReferencedEntity", ""), r.get("SchemaName", ""), f"via `{r.get('ReferencingAttribute','')}`"))
    for r in e.get("ManyToManyRelationships", []):
        rels.append(("N:N", r.get("Entity2LogicalName", ""), r.get("SchemaName", ""), f"intersect `{r.get('IntersectTableName','')}`"))
    if rels:
        body += "\n## Relationships\n\n| Type | Related table | Schema name | Notes |\n|---|---|---|---|\n"
        for t, target, schema, note in sorted(rels):
            body += f"| {t} | `{target}` | `{schema}` | {note} |\n"

    body += "\n## Used by\n\n_(populated by build_crossrefs — phase 4)_\n"
    body += f"\n---\n*{footer}*\n"
    return body


def render_er(entities: dict, footer: str) -> str:
    lines = ["# Dataverse ER Overview", ""]
    rel_lines, seen_rels = [], set()
    for logical in sorted(entities):
        e = entities[logical]
        for r in e.get("OneToManyRelationships", []):
            child = r.get("ReferencingEntity", "")
            key = (logical, child)
            if key in seen_rels:
                continue
            seen_rels.add(key)
            comment = (r.get("SchemaName") or "").split("_")[-1] or "1:N"
            lines_rel = f'    {logical} ||--o{{ {child} : "{comment}"'
            rel_lines.append((logical, child, lines_rel))
        for r in e.get("ManyToManyRelationships", []):
            other = r.get("Entity2LogicalName", "")
            key = tuple(sorted([logical, other]))
            if key in seen_rels:
                continue
            seen_rels.add(key)
            rel_lines.append((logical, other, f'    {logical} }}o--o{{ {other} : "{r.get("IntersectTableName","")}"'))

    lines.append(f"{len(entities)} tables in scope. Out-of-scope tables appear as boundary nodes without column detail.")
    lines += ["", "```mermaid", "erDiagram"]
    for _p, _c, rl in sorted(rel_lines, key=lambda x: x[2]):
        lines.append(rl)
    lines.append("")
    for logical in sorted(entities):
        e = entities[logical]
        lines.append(f"    {logical} {{")
        shown = 0
        attrs = sorted(e.get("Attributes", []), key=lambda a: (not a.get("IsPrimaryId"), a.get("AttributeType") != "Lookup", a.get("LogicalName", "")))
        for a in attrs:
            if shown >= ER_MAX_COLS:
                break
            t = (a.get("AttributeType") or "?").lower()
            name = a.get("LogicalName", "")
            suffix = " PK" if a.get("IsPrimaryId") else (" FK" if a.get("AttributeType") == "Lookup" else "")
            disp = pp.label_of(a.get("DisplayName"), 1033)
            comment = f' "{disp}"' if disp else ""
            lines.append(f"        {t} {name}{suffix}{comment}")
            shown += 1
        lines.append("    }")
    lines += ["```", "", "> Tables out of scope appear as boundary nodes without column detail.", "> Rule: >40 tables → split into sub-diagrams by publisher prefix.", "", f"---", f"*{footer}*", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render kb/_raw/metadata/ to kb/dataverse/ Markdown")
    ap.add_argument("--config", help="path to pp-kb.config.json")
    args = ap.parse_args()

    cfg = pp.load_config(args.config)
    raw_dir = os.path.join(cfg["outputDir"], "_raw", "metadata")
    out_dir = os.path.join(cfg["outputDir"], "dataverse")
    entities, index = load_raw(raw_dir)
    if not entities:
        pp.die(f"no raw metadata found in {raw_dir} — run export_metadata.py first")
    lang = index.get("labelLanguage", cfg["labelLanguage"])
    footer = "Snapshot: {} | {} | Raw: `_raw/metadata/`".format(
        index.get("environment", cfg.get("dataverseUrl", "?")), index.get("capturedAt", "?"))

    os.makedirs(os.path.join(out_dir, "tables"), exist_ok=True)
    for logical in sorted(entities):
        pp.write_text(os.path.join(out_dir, "tables", f"{logical}.md"), render_table(entities[logical], lang, footer))
    pp.log(f"[parse] {len(entities)} table docs -> {out_dir}/tables/")

    pp.write_text(os.path.join(out_dir, "er-overview.md"), render_er(entities, footer))
    pp.log("[parse] er-overview.md")

    # final safety net
    hits = pp.redaction_scan_dir(cfg["outputDir"])
    if hits:
        pp.die("redaction scan FAILED:\n" + "\n".join(hits))
    pp.log("[parse] redaction scan: PASS")


if __name__ == "__main__":
    main()
