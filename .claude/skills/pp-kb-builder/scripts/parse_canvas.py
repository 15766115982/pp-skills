"""parse_canvas.py — canvas .pa.yaml sources (read-only) -> kb/apps/ Markdown.

Input: any tree containing Src/*.pa.yaml (Git Integration repo or legacy pac
unpack output). All .pa.yaml files under Src/ are loaded and their five top-level
sections (App / Screens / ComponentDefinitions / DataSources / EditorState) are
merged — this works for both the multi-file and single-file layouts.

Format facts verified against awesome-copilot instructions + official
pa.schema.yaml v3.0 (docs/skill-implementation-plan.md §4.1):
  - formulas are scalars prefixed with '='; multi-line via block scalars
  - Children: array of single-key maps {ControlName: {Control, Properties, ...}}
  - control versioning via Control: Type@x.y.z
  - DataSources entries: Type: Table (Parameters.TableLogicalName) | Actions (ConnectorId)

Two-tier parsing (filters.screens wildcards):
  matched screens  -> full doc under screens/
  unmatched / >1MB -> shallow index row in overview.md only
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pp_common as pp

SECTIONS = ("App", "Screens", "ComponentDefinitions", "DataSources", "EditorState")
LARGE_FILE_BYTES = 1_000_000
MAX_FORMULA_LEN = 500

NAVIGATE_RE = re.compile(r"\bNavigate\(\s*([A-Za-z0-9_]+)")
BACK_RE = re.compile(r"\bBack\(\s*\)")
COLLECT_RE = re.compile(r"\b(?:ClearCollect|Collect)\(\s*([A-Za-z0-9_]+)")
PATCH_RE = re.compile(r"\b(?:Patch|LookUp|Filter|SortByColumns|Search|AddColumns|GroupBy|Sum|CountRows|Remove)\(\s*(?:'([^']+)'|([A-Za-z0-9_]+))")
QUOTED_RE = re.compile(r"'([^']+)'")


class PaLoader(yaml.SafeLoader):
    """SafeLoader without YAML-1.1 bool coercion (On/Off/Yes/No stay strings)."""


PaLoader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:bool"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


# ------------------------------------------------------------------ loading

def find_apps(canvas_root: str) -> list:
    """Return [(app_name, src_dir)]. Accepts root being an app dir itself."""
    if os.path.isdir(os.path.join(canvas_root, "Src")):
        return [(os.path.basename(os.path.normpath(canvas_root)), os.path.join(canvas_root, "Src"))]
    apps = []
    for entry in sorted(os.listdir(canvas_root)) if os.path.isdir(canvas_root) else []:
        src = os.path.join(canvas_root, entry, "Src")
        if os.path.isdir(src):
            apps.append((entry, src))
    return apps


def load_app(src_dir: str) -> tuple[dict, dict]:
    """Merge all .pa.yaml under Src/. Returns (merged_sections, provenance).

    provenance: {("Screens"|"ComponentDefinitions", name): file_path}"""
    merged: dict = {s: {} for s in SECTIONS}
    provenance: dict = {}
    for dirpath, _dirs, files in os.walk(src_dir):
        for fn in sorted(files):
            if not fn.endswith(".pa.yaml"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as f:
                    doc = yaml.load(f, Loader=PaLoader)
            except yaml.YAMLError as e:
                pp.log(f"[warn] YAML parse failed for {path}: {e} — skipping file")
                continue
            if not isinstance(doc, dict):
                continue
            for section in SECTIONS:
                part = doc.get(section)
                if isinstance(part, dict):
                    for name, body in part.items():
                        merged[section][str(name)] = body
                        provenance[(section, str(name))] = path
                elif part is not None:
                    merged[section] = part  # scalar sections (unlikely, defensive)
    return merged, provenance


# ------------------------------------------------------------------ analysis

def walk_controls(children, depth, rows):
    """children: [{Name: {Control, Properties, Children, Variant, ...}}]"""
    if not isinstance(children, list):
        return
    for item in children:
        if not isinstance(item, dict) or len(item) != 1:
            continue
        name, body = next(iter(item.items()))
        if not isinstance(body, dict):
            continue
        ctype = str(body.get("Control", "?"))
        variant = body.get("Variant")
        props = body.get("Properties") or {}
        rows.append({
            "name": str(name), "type": ctype, "variant": str(variant) if variant else "",
            "depth": depth, "properties": props if isinstance(props, dict) else {},
        })
        walk_controls(body.get("Children"), depth + 1, rows)


def control_label(row) -> str:
    label = f"{row['name']} ({row['type']}"
    if row["variant"]:
        label += f"/{row['variant']}"
    return label + ")"


def formulas_of(rows, owner: str) -> list:
    """[(control_path, property, formula_text)]"""
    out = []
    for r in rows:
        for prop, val in (r["properties"] or {}).items():
            if isinstance(val, str) and val.startswith("="):
                out.append((r["name"], str(prop), val))
    return out


def nav_edges(formulas) -> list:
    edges = []
    for ctrl, prop, fx in formulas:
        for m in NAVIGATE_RE.finditer(fx):
            edges.append((ctrl, prop, m.group(1)))
    return edges


def collection_names(formulas) -> set:
    names = set()
    for _c, _p, fx in formulas:
        names |= set(COLLECT_RE.findall(fx))
    return names


def table_refs(formulas, ds_names: set) -> set:
    """Table/data-source references: known data-source names (quoted or bare)
    plus Patch/LookUp/Filter/... first args that match a data source."""
    refs = set()
    for _c, _p, fx in formulas:
        for m in PATCH_RE.finditer(fx):
            cand = m.group(1) or m.group(2)
            if cand in ds_names:
                refs.add(cand)
        for q in QUOTED_RE.findall(fx):
            if q in ds_names:
                refs.add(q)
        for name in ds_names:
            if re.fullmatch(r"[A-Za-z0-9_]+", name) and re.search(rf"\b{re.escape(name)}\b", fx):
                refs.add(name)
    return refs


def screen_rows(screen_body: dict) -> list:
    rows: list = []
    walk_controls((screen_body or {}).get("Children"), 0, rows)
    return rows


def match_screens(names: list, patterns: list) -> set:
    if not patterns:
        return set(names)
    return {n for n in names if any(fnmatch.fnmatchcase(n.lower(), p.lower()) for p in patterns)}


# ------------------------------------------------------------------ rendering

def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ↵ ")


def render_screen_doc(app: str, screen: str, body: dict, ds_names: set, footer: str,
                      kind: str = "Screen") -> str:
    rows = screen_rows(body)
    formulas = formulas_of(rows, screen)
    props = (body or {}).get("Properties") or {}
    screen_fx = [(f"({kind.lower()})", k, v) for k, v in props.items() if isinstance(v, str) and v.startswith("=")]
    all_fx = screen_fx + formulas

    L = [f"# {kind}: {screen} ({app})", ""]
    L += [f"## Control tree ({len(rows)} controls)", "", "```"]
    for r in rows:
        L.append("  " * r["depth"] + control_label(r))
    L += ["```", "", "## Formulas by property", "",
          "| Control.Property | Formula |", "|---|---|"]
    for ctrl, prop, fx in all_fx:
        text = fx[1:].rstrip()  # strip '=' and block-scalar trailing newline
        if len(text) > MAX_FORMULA_LEN:
            text = text[:MAX_FORMULA_LEN] + " …"
        L.append(f"| {ctrl}.{prop} | `{md_escape(text)}` |")
    if not all_fx:
        L.append("| _(none)_ | |")

    cols = collection_names(all_fx)
    tables = table_refs(all_fx, ds_names)
    navs = sorted({t for _c, _p, t in nav_edges(all_fx)})
    backs = any(BACK_RE.search(fx) for _c, _p, fx in all_fx)
    L += ["", "## Data references on this screen", ""]
    L.append("- Collections: " + (", ".join(f"`{c}`" for c in sorted(cols)) if cols else "none"))
    L.append("- Data sources: " + (", ".join(f"`{t}`" for t in sorted(tables)) if tables else "none"))
    L.append("- Navigation out: " + (", ".join(f"→ {n}" for n in navs) + (" · Back()" if backs else "") if navs or backs else "none"))
    L += ["", "---", f"*{footer}*", ""]
    return "\n".join(L)


def render_overview(app: str, merged: dict, provenance: dict, full_screens: set,
                    shallow: dict, src_dir: str, footer: str) -> str:
    app_props = ((merged.get("App") or {}).get("Properties") or {})
    screens = merged.get("Screens") or {}
    comps = merged.get("ComponentDefinitions") or {}
    datasources = merged.get("DataSources") or {}

    L = [f"# App: {app} (Canvas)", "", "| | |", "|---|---|",
         f"| Source | `{disp_path(src_dir)}` |",
         f"| Screens | {len(screens)} ({len(full_screens)} fully parsed, {len(shallow)} shallow) |",
         f"| Components | {len(comps)} |", ""]

    L += ["## App-level (App.pa.yaml)", ""]
    if app_props:
        L += ["| Property | Formula |", "|---|---|"]
        for k, v in app_props.items():
            if isinstance(v, str) and v.startswith("="):
                text = v[1:].rstrip()
                if len(text) > MAX_FORMULA_LEN:
                    text = text[:MAX_FORMULA_LEN] + " …"
                L.append(f"| {k} | `{md_escape(text)}` |")
            else:
                L.append(f"| {k} | {v} |")
    else:
        L.append("_(no app properties)_")

    L += ["", "## Data sources", "", "| Name | Type | Details |", "|---|---|---|"]
    for name, ds in datasources.items():
        ds = ds or {}
        dtype = ds.get("Type", "?")
        params = ds.get("Parameters") or {}
        detail = params.get("TableLogicalName", "") or ds.get("ConnectorId", "") or ""
        L.append(f"| `{name}` | {dtype} | {detail} |")
    if not datasources:
        L.append("| _(none declared)_ | |")

    # navigation graph across ALL screens (full + shallow)
    all_edges, backs = [], set()
    for sname, body in screens.items():
        rows = screen_rows(body)
        fx = formulas_of(rows, sname)
        fx += [("(screen)", k, v) for k, v in ((body or {}).get("Properties") or {}).items()
               if isinstance(v, str) and v.startswith("=")]
        for _c, _p, target in nav_edges(fx):
            all_edges.append((sname, target))
        if any(BACK_RE.search(f) for _c, _p, f in fx):
            backs.add(sname)
    L += ["", "## Screen navigation", "", "```mermaid", "flowchart LR"]
    start = app_props.get("StartScreen", "")
    if isinstance(start, str) and start.startswith("="):
        start = start[1:]
    for s in sorted(screens):
        marker = '(["' + s + '"])' if s == start else '["' + s + '"]'
        L.append(f"    {s}{marker}")
    for src, dst in sorted(set(all_edges)):
        if dst in screens:
            L.append(f"    {src} -- Navigate --> {dst}")
    L += ["```"]
    note = "_Oval node = StartScreen."
    if backs:
        note += " Screens calling Back(): " + ", ".join(sorted(backs)) + "._"
    L += [note]

    L += ["", "## Screens", "", "| Screen | Parse tier | Controls | Data sources | Doc |", "|---|---|---|---|---|"]
    ds_names = set(datasources)
    for s in sorted(screens):
        rows = screen_rows(screens[s])
        fx = formulas_of(rows, s)
        tables = table_refs(fx, ds_names)
        if s in full_screens:
            L.append(f"| {s} | full | {len(rows)} | {', '.join(sorted(tables)) or '—'} | [screens/{s}.md](screens/{s}.md) |")
        else:
            reason = shallow.get(s, "not matched by filters.screens")
            L.append(f"| {s} | shallow ({reason}) | {len(rows)} | {', '.join(sorted(tables)) or '—'} | — |")

    if comps:
        L += ["", "## Components", "", "| Component | Controls | Doc |", "|---|---|---|"]
        for c in sorted(comps):
            rows = screen_rows(comps[c])
            L.append(f"| {c} | {len(rows)} | [components/{c}.md](components/{c}.md) |")

    L += ["", "---", f"*{footer}*", ""]
    return "\n".join(L)


def disp_path(p: str) -> str:
    """Portable path display: relative to cwd when possible, forward slashes."""
    p = os.path.normpath(p)
    try:
        rel = os.path.relpath(p, os.getcwd())
        if not rel.startswith(".."):
            p = rel
    except ValueError:
        pass
    return p.replace(os.sep, "/")


def git_commit_of(path: str) -> str:
    if os.environ.get("PP_CANVAS_COMMIT"):  # test/CI override for deterministic output
        return os.environ["PP_CANVAS_COMMIT"]
    try:
        r = subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown (not a git repo)"


# ------------------------------------------------------------------ main

def main() -> None:
    ap = argparse.ArgumentParser(description="Parse canvas .pa.yaml sources to kb/apps/ Markdown")
    ap.add_argument("--config", help="path to pp-kb.config.json")
    args = ap.parse_args()

    cfg = pp.load_config(args.config)
    canvas_root = cfg["canvasSourcePath"]
    apps = find_apps(canvas_root)
    if not apps:
        pp.die(f"no canvas apps found under {canvas_root} (expected <app>/Src/*.pa.yaml)")

    screen_patterns = cfg.get("filters", {}).get("screens") or []
    out_root = os.path.join(cfg["outputDir"], "apps")

    for app_name, src_dir in apps:
        merged, provenance = load_app(src_dir)
        screens = merged.get("Screens") or {}
        ds_names = set(merged.get("DataSources") or {})
        commit = git_commit_of(canvas_root)
        footer = f"Snapshot: {app_name} | commit {commit} | schema v3.0 | Source: `{disp_path(src_dir)}` (read-only)"

        # two-tier decision
        matched = match_screens(list(screens), screen_patterns)
        full_screens, shallow = set(), {}
        for s in screens:
            src_file = provenance.get(("Screens", s), "")
            size = os.path.getsize(src_file) if src_file and os.path.exists(src_file) else 0
            if s not in matched:
                shallow[s] = "not matched by filters.screens"
            elif size > LARGE_FILE_BYTES:
                shallow[s] = f"large file ({size // 1000} KB > {LARGE_FILE_BYTES // 1000} KB)"
            else:
                full_screens.add(s)

        app_dir = os.path.join(out_root, app_name)
        for s in sorted(full_screens):
            doc = render_screen_doc(app_name, s, screens[s], ds_names, footer)
            pp.write_text(os.path.join(app_dir, "screens", f"{s}.md"), doc)
        comps = merged.get("ComponentDefinitions") or {}
        for c in sorted(comps):
            doc = render_screen_doc(app_name, c, comps[c], ds_names, footer, kind="Component")
            pp.write_text(os.path.join(app_dir, "components", f"{c}.md"), doc)
        overview = render_overview(app_name, merged, provenance, full_screens, shallow, src_dir, footer)
        pp.write_text(os.path.join(app_dir, "overview.md"), overview)
        pp.log(f"[parse] {app_name}: {len(full_screens)} full + {len(shallow)} shallow screens, "
               f"{len(comps)} components -> {app_dir}")

    hits = pp.redaction_scan_dir(cfg["outputDir"])
    if hits:
        pp.die("redaction scan FAILED:\n" + "\n".join(hits))
    pp.log("[parse] redaction scan: PASS")


if __name__ == "__main__":
    main()
