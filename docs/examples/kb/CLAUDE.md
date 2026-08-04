# Power Platform Knowledge Base — ContosoSales

> Snapshot: environment `org12345.crm5.dynamics.com` | solution `ContosoSales` (v1.4.2)
> Generated: 2026-08-04T09:31:00Z by pp-kb-builder v0.1 | Source commit: `a1b2c3d`

## How to read this KB

1. **Start here, then [SCOPE.md](SCOPE.md)** — the coverage manifest: what is fully parsed vs. shallow-indexed vs. intentionally out of scope. Absence from this KB is deliberate, not a generation failure.
2. Then [REFERENCES.md](REFERENCES.md) — the cross-artifact matrix: which table is used by which app/flow.
3. Drill into the artifact you need:
   - `dataverse/tables/<logicalname>.md` — one file per table (columns, choices, relationships)
   - `flows/<flowname>.md` — one file per flow (trigger, action DAG, connectors)
   - `apps/<AppName>/` — app overview + one file per screen (control tree, formulas)
4. If a summary lacks detail, read the raw capture: `_raw/` holds the sanitized source JSON (metadata, workflow clientdata). Canvas sources stay in `../canvas-src/` (read-only).
5. Prefer `grep`-style search over reading whole directories; files are self-contained.

## Contents

| Area | Files | Count |
|---|---|---|
| Tables | `dataverse/tables/` | 2 |
| Global choices | `dataverse/optionsets.md` | 1 |
| ER overview | `dataverse/er-overview.md` | 1 |
| Flows | `flows/` | 1 |
| Canvas apps | `apps/` | 1 (2 screens) |

## Conventions

- All names use **logical names** for tables/columns; display names in parentheses on first mention.
- Mermaid diagrams render in VS Code (Mermaid extension) / Typora / Git platforms.
- Secrets never appear in this KB: `$authentication`, connection instance IDs and similar are redacted at capture time (see `_raw/REDACTION-LOG.md`).
