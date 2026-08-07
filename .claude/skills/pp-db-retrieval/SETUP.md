# pp-db-retrieval — Setup Guide (for Claude)

This skill shares its configuration and credentials with pp-kb-builder.
If pp-kb-builder is already set up in this project, verify only (Steps 1–2)
and go straight to Step 3.

## Step 1 — Python + PyYAML

Read `pythonPath` from `pp-kb.config.json` (env `PP_PYTHON` overrides). If the
project has no config yet, ask the user which Python to use — offer what
`python --version` / `py -0p` / `where python` find — then verify:

```bash
<PY> --version                      # >= 3.10
<PY> -c "import yaml" 2>/dev/null || <PY> -m pip install pyyaml
```

Run every script as `<PY> <script>` — never bare `python`.

## Step 2 — Credentials (env vars, never echo values)

```bash
python - <<'EOF'
import os
for v in ("PP_TENANT_ID","PP_CLIENT_ID","PP_CLIENT_SECRET","PP_DATAVERSE_URL"):
    print(v, "SET" if os.environ.get(v) else "MISSING")
EOF
```

All four must be SET. The SPN needs **data read** on the queried tables
(metadata read alone is not enough) plus Application User registration.
Proxy environments: `HTTPS_PROXY` must be set.

## Step 3 — Self-test (offline)

```bash
cd .claude/skills/pp-db-retrieval && <PY> -m unittest discover -s tests
```

Must end with `OK`.

## Step 4 — Smoke queries (live)

```bash
S=.claude/skills/pp-db-retrieval/scripts
<PY> $S/dv_query.py --sql "SELECT TOP 1 name FROM account" --entityset accounts
<PY> $S/dv_query.py --table <a-table-from-the-kb> --top 3
```

- 401/403 → Application User registration / security-role read privilege
- 404 on `--table` → check `kb/dataverse/tables/` for the exact logical name and
  entity set (never hand-pluralize); if the kb is stale, suggest a rebuild
- The `--sql` entityset default is `accounts`; pass `--entityset` matching any
  real entity set when the tenant renames or lacks `account`

## Notes

- This skill is GET-only. If the user asks to create/update/delete records,
  refuse and point them to the Dataverse connector or maker portal.
- SQL results are silently capped at ~5000 rows server-side; the CLI warns when
  the cap is hit. For larger reads use `--table` mode (paginates) or `--format csv`.
