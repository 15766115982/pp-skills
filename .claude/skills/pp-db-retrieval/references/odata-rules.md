# OData Rules (Dataverse Web API)

Extracted from microsoft/power-cat-skills `dataverse-webapi-query` and
microsoft/Dataverse-skills `dv-query` (both MIT). Names are the #1 failure cause —
resolve them from `kb/dataverse/tables/*.md` before composing a query.

## The 8 iron rules

1. **Entity set name** in the URL path: plural, lowercase (e.g. `contoso_salesorders`).
   Get it from the kb doc's `Entity set` row — never pluralize by hand.
2. **API version**: `/api/data/v9.2/`.
3. **`$select` / `$filter` use all-lowercase LogicalName** of the column.
4. **`$expand` uses the navigation property name** — case-sensitive
   (e.g. `contoso_Customer`). Wrong case → 400. Find it in the kb Relationships
   section or via live metadata.
5. **Lookup read**: `_<lookupLogicalName>_value` returns the GUID.
   The navigation property itself belongs only inside `$expand`, never `$select`.
6. **Formatted values** (choice labels, currency text): request header
   `Prefer: odata.include-annotations="OData.Community.Display.V1.FormattedValue"`,
   then read `@OData.Community.Display.V1.FormattedValue`-suffixed keys.
7. **Literal syntax**: GUIDs without quotes; strings in single quotes with
   internal quotes doubled (`'O''Brien'`); dates ISO 8601 (`2026-08-04T00:00:00Z`);
   choice/status compared by **integer value**, not label.
8. **No server-side aggregation in plain OData** — use `$apply`, `?sql=`,
   or `?fetchXml=` (see sibling references).

## Standard headers

```
Authorization: Bearer <token>          (from SPN env vars — never ask the user for one)
Accept: application/json
OData-MaxVersion: 4.0
OData-Version: 4.0
Prefer: odata.maxpagesize=5000         (optional, large reads)
Prefer: odata.include-annotations="OData.Community.Display.V1.FormattedValue"   (when labels needed)
```

## Common mistakes → symptoms

| Mistake | Symptom |
|---|---|
| `$expand` with logical name instead of navigation property | 400 |
| Navigation property in `$select` | 400 "Could not find a property" |
| Choice compared by label string | 400 / empty results — compare by int value |
| Lowercased navigation property | 400 (case-sensitive) |
| Guessed pluralization (`im_categorys`) | 404 that looks like "table missing" — resolve EntitySetName from kb |
