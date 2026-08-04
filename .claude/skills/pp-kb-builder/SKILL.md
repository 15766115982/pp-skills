---
name: pp-kb-builder
description: Build a Markdown knowledge base from Power Platform assets — Dataverse table metadata, Power Automate flow definitions (workflow table clientdata), and Canvas App .pa.yaml sources. Use when the user asks to build/refresh/regenerate a Power Platform knowledge base, document their environment/solution, or parse canvas app / flow / Dataverse schema into agent-readable docs.
---

# pp-kb-builder

Produces an agent-readable Markdown knowledge base (`kb/`) from three asset classes:
Dataverse metadata (Web API), Power Automate flows (workflow table `clientdata`),
and Canvas App sources (`.pa.yaml`, read-only from a local source tree).

## Behavior rules (non-negotiable)

1. **Preflight before work**: verify config + env vars + proxy/token + canvas source
   presence. If anything is missing, STOP and guide the user to fix it — never
   silently skip a pipeline stage.
2. **Read-only on inputs**: never modify the canvas source tree. All writes go to
   `kb/` (config: `outputDir`).
3. **Credential discipline**: secrets live only in env vars (`PP_CLIENT_SECRET`).
   Never write env values, tokens, or connection instance data to `kb/` or logs.
4. **Idempotent output**: every run fully regenerates `kb/` from `kb/_raw/`.
5. **Redaction scan last**: the pipeline is not done until the scan reports PASS.

## Prerequisites

- Python >= 3.10 with `pyyaml`, interpreter chosen during setup and recorded as
  `pythonPath` in the config (env override: `PP_PYTHON`)
- Env vars: `PP_TENANT_ID`, `PP_CLIENT_ID`, `PP_CLIENT_SECRET`, `PP_DATAVERSE_URL`,
  `HTTPS_PROXY`/`HTTP_PROXY` (if the environment requires a proxy)
- `pp-kb.config.json` in the project root (see `pp-kb.config.example.json`)

**First-time setup: follow [SETUP.md](SETUP.md)** — it walks through interpreter
selection (asks the user which Python), credential checks, config, self-test and
the first capture with known failure modes.

## Pipeline (run from project root, in this order)

Use the configured interpreter for every invocation — read `pythonPath` from
`pp-kb.config.json` (env `PP_PYTHON` overrides) and run `<PY> <script>`;
never assume bare `python` is the right interpreter.

```bash
S=.claude/skills/pp-kb-builder/scripts
PY=<pythonPath from config>   # e.g. python | py -3.11 | C:/venvs/ppkb/Scripts/python.exe

# capture (network, SPN via env vars)
$PY $S/export_metadata.py        # Dataverse metadata -> kb/_raw/metadata/
$PY $S/export_flows.py           # workflow clientdata -> kb/_raw/flows/

# render (offline, deterministic from kb/_raw/ + canvas sources)
$PY $S/parse_metadata.py         # kb/dataverse/ (tables + ER diagram)
$PY $S/parse_flows.py            # kb/flows/ (runAfter mermaid DAGs)
$PY $S/parse_canvas.py           # kb/apps/ (two-tier screens, navigation graph)
$PY $S/build_crossrefs.py        # kb/REFERENCES.md + Used-by rewrites
$PY $S/build_index.py            # kb/CLAUDE.md + kb/SCOPE.md
```

Each export step is network-bound and separate from parsing: raw JSON lands in
`kb/_raw/` (sanitized), and parsers rebuild the docs deterministically from it.
Any subset can be re-run (e.g. flows only); always finish with build_index.py.

## Filters (config "filters")

- `solutions`: unique names; resolved via `solutioncomponents` (falls back to full
  capture with a loud warning if the association lookup fails)
- `tables`: logical OR display names, case-insensitive dual match
- `flows`: display names, `*` wildcard
- `screens`: `*` wildcard; matched screens get full parse, others shallow index

## Testing

```bash
cd .claude/skills/pp-kb-builder
python -m unittest discover -s tests -v
```

Fixtures are synthetic (built from the official pa.schema.yaml and Web API shapes);
no real environment data ever leaves the customer network.
