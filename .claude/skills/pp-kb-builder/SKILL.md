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

- Python >= 3.10 with `pyyaml` (`pip install pyyaml`)
- Env vars: `PP_TENANT_ID`, `PP_CLIENT_ID`, `PP_CLIENT_SECRET`, `PP_DATAVERSE_URL`,
  `HTTPS_PROXY`/`HTTP_PROXY` (if the environment requires a proxy)
- `pp-kb.config.json` in the project root (see `pp-kb.config.example.json`)

## Pipeline (run from project root)

```bash
# phase 1 — Dataverse metadata (implemented)
python .claude/skills/pp-kb-builder/scripts/export_metadata.py
python .claude/skills/pp-kb-builder/scripts/parse_metadata.py

# phase 2 — Power Automate flows (export_flows.py / parse_flows.py)  [planned]
# phase 3 — Canvas apps (parse_canvas.py)                            [planned]
# phase 4 — cross references + index (build_crossrefs.py, build_index.py) [planned]
```

Each export step is network-bound and separate from parsing: raw JSON lands in
`kb/_raw/` (sanitized), and parsers rebuild the docs deterministically from it.

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
