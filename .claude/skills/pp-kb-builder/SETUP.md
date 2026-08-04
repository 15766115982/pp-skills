# pp-kb-builder — Setup Guide (for Claude)

Follow this guide when the user asks to **set up / install / configure** this skill
in a new environment. Work interactively: ask the questions below, verify each
answer by running the check, and only then move on. Never print secret values.

## Step 0 — Detect what's already there

```bash
ls pp-kb.config.json 2>/dev/null
ls ./canvas-src 2>/dev/null
```

If a config exists, read it and skip questions whose answers are already present
(confirm with the user rather than re-asking).

## Step 1 — Python interpreter (ALWAYS ASK)

Ask the user which Python to use, offering what you find:

```bash
python --version 2>&1; py -0p 2>/dev/null; where python 2>/dev/null
ls ./venv/Scripts/python.exe ./.venv/Scripts/python.exe 2>/dev/null
```

Present the discovered interpreters and ask, e.g.:

> Which Python should run the pipeline?
> 1. `python` (system, 3.11.9)
> 2. `py -3.11`
> 3. a venv/conda interpreter — give me the path

Then verify the chosen one (`<PY>` = the user's choice, exactly as typed):

```bash
<PY> --version                      # must be >= 3.10
<PY> -c "import yaml; print(yaml.__version__)" || <PY> -m pip install pyyaml
```

Record it in `pp-kb.config.json`:

```jsonc
{ "pythonPath": "python" }   // or "py -3.11", "C:/venvs/ppkb/Scripts/python.exe", ...
```

**From now on, run every pipeline script as `<PY> <script>`, never bare `python`.**
(Alternatively the user may set env var `PP_PYTHON`, which overrides the config.)

## Step 2 — Credentials (env vars, never the config file)

Ask the user to set these, then verify presence WITHOUT echoing values:

```bash
python - <<'EOF'
import os
for v in ("PP_TENANT_ID","PP_CLIENT_ID","PP_CLIENT_SECRET","PP_DATAVERSE_URL"):
    print(v, "SET" if os.environ.get(v) else "MISSING")
print("HTTPS_PROXY", "SET" if os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") else "not set")
EOF
```

If anything is MISSING, guide the user to set it (Windows: System env vars or
`setx`, new shell needed) and re-check. Do not proceed to exports until all four
are SET. Proxy: if the intranet requires one, `HTTPS_PROXY` must be set too.

## Step 3 — Config file

Create/complete `pp-kb.config.json` in the project root (see
`pp-kb.config.example.json`). Ask about:

- `canvasSourcePath` — where the canvas source tree lives (needs `<App>/Src/*.pa.yaml`)
- `filters.solutions` — solution unique names to scope capture
- `filters.tables` / `filters.flows` / `filters.screens` — optional narrowing
  (screens supports `*` wildcards; unmatched screens become shallow index rows)
- `outputDir` — default `./kb`

## Step 4 — Self-test

```bash
cd .claude/skills/pp-kb-builder && <PY> -m unittest discover -s tests
```

Must end with `OK`. If PyYAML is missing this fails — go back to Step 1.

## Step 5 — First capture (watch these known failure modes)

```bash
<PY> .claude/skills/pp-kb-builder/scripts/export_metadata.py
<PY> .claude/skills/pp-kb-builder/scripts/export_flows.py
```

| Symptom | Meaning / action |
|---|---|
| 401/403 on token or API | SPN not registered as Application User, or role lacks metadata/workflow read |
| `solution lookup failed` / `falling back to FULL capture` | solutioncomponents association didn't work in this environment — report the error verbatim |
| `cast failed for <table>` warnings | OptionSet enrichment blocked; output still usable, choices will be incomplete |
| proxy/timeout errors | check `HTTPS_PROXY`; confirm outbound 443 to login.microsoftonline.com + *.dynamics.com |

## Step 6 — Render + verify

```bash
S=.claude/skills/pp-kb-builder/scripts
<PY> $S/parse_metadata.py && <PY> $S/parse_flows.py && <PY> $S/parse_canvas.py \
  && <PY> $S/build_crossrefs.py && <PY> $S/build_index.py
```

Then verify with the user:

- every stage ends with `redaction scan: PASS`
- spot-check 2–3 tables against Maker Portal (columns, choices, relationships)
- spot-check 1–2 flows against the designer (trigger, action chain)
- skim `kb/_raw/` + `kb/_raw/REDACTION-LOG.md` before committing `kb/` to Git
- `kb/CLAUDE.md` + `kb/SCOPE.md` exist and reflect the intended coverage

Done — from here on the user just asks questions; rebuilding is re-running the
same pipeline with the same `<PY>`.
