---
name: pp-db-retrieval
description: Read-only Dataverse record retrieval — OData queries, T-SQL subset, FetchXML, and server-side aggregation against a Power Platform environment. Use when the user wants to read/list/filter/count/aggregate/export Dataverse records, build or test a Web API query, convert FetchXML to Web API, or diagnose a 400/401/403/404 from the Dataverse Web API. Never use for create/update/delete — this skill is GET-only by design and by enforcement.
---

# pp-db-retrieval

Read-only record retrieval for Dataverse. Complements pp-kb-builder: that skill
builds the schema knowledge base (`kb/`); this one queries live records, using the
kb as its first schema source.

## Read-only enforcement (four layers — all must stay intact)

1. **HTTP layer**: every request is GET (`pp_common.api_get` has no other verb).
2. **SQL guard**: `--sql` must be a single SELECT — DML/DDL keywords, comments,
   and stacked statements are rejected before sending (`guard_sql`).
3. **FetchXML guard**: mutating elements (`<insert>/<update>/<delete>/...`) are
   rejected before sending (`guard_fetchxml`).
4. **No write helpers**: the skill ships no create/update/delete code paths at all.

If a user asks for a write: refuse and point them at the Dataverse connector /
maker portal. Do not improvise one.

## Schema resolution order (never invent a logical name)

1. **Local kb first**: `kb/dataverse/tables/<logical>.md` — columns, types,
   choice values, lookup targets, entity set name. Zero network, zero guessing.
2. **Live metadata**: `EntityDefinitions(LogicalName='...')` — and tell the user
   the table isn't in the kb (suggest refreshing it).
3. **Still unsure → ask the user.** Guessing names is the #1 cause of failed queries.

Critical name rules (see references/odata-rules.md for the full list):
- `$select`/`$filter` use **all-lowercase LogicalName**; `$expand` uses the
  **case-sensitive navigation property name** — wrong case → 400.
- Read a lookup as `_<lookup>_value` (GUID); the navigation property itself only
  appears inside `$expand`.
- Choice/status display text needs
  `Prefer: odata.include-annotations="OData.Community.Display.V1.FormattedValue"`.

## Query shape routing

| User intent | How |
|---|---|
| Simple list/filter | `--table --filter --select --orderby --top` |
| Count | `--sql "SELECT COUNT(*) AS n FROM <t> WHERE ..."` (server-side, no rows downloaded) |
| Single-table aggregation | `--table <t> --apply "groupby((col),aggregate(metric with sum as total))"` (≤50K source rows) or SQL GROUP BY |
| Cross-table query/aggregation | `--sql` INNER/LEFT JOIN; or `--fetchxml` with link-entity |
| Fast read of <5K rows | `--sql` (single request) — **beware the silent ~5000-row cap** |
| Large result set | OData mode paginates via `@odata.nextLink` (`--max-pages` guard) |
| Export | `--format csv -o out.csv` |

T-SQL subset limits and FetchXML mapping: see references/tsql-subset.md and
references/fetchxml-mapping.md. Error diagnosis: references/error-diagnosis.md.

## Usage

```bash
PY=<pythonPath from pp-kb.config.json>   # same config as pp-kb-builder

$PY .claude/skills/pp-db-retrieval/scripts/dv_query.py \
    --table contoso_salesorder \
    --select contoso_name,contoso_totalamount \
    --filter "contoso_status eq 100000002" --orderby "contoso_orderdate desc" --top 50

$PY .../dv_query.py --sql "SELECT contoso_status, COUNT(*) AS n FROM contoso_salesorder GROUP BY contoso_status"

$PY .../dv_query.py --fetchxml-file query.xml --entityset contoso_salesorders --format csv -o orders.csv
```

Config & credentials: identical to pp-kb-builder (`pp-kb.config.json` +
`PP_TENANT_ID/PP_CLIENT_ID/PP_CLIENT_SECRET/PP_DATAVERSE_URL`, proxy via
`HTTPS_PROXY`). First-time setup: follow SETUP.md.

## Testing

```bash
cd .claude/skills/pp-db-retrieval && python -m unittest discover -s tests -v
```

Tests never touch the network: guards, URL building, entity-set resolution
against a fixture kb, pagination over canned pages, and output formatting.
