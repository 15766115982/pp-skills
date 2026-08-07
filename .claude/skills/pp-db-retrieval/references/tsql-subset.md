# T-SQL Subset (`?sql=`)

Extracted from microsoft/Dataverse-skills `dv-query` (MIT). The Web API accepts a
T-SQL subset as a GET parameter: `GET /api/data/v9.2/<entityset>?sql=<query>`.

## Supported

- `SELECT` / `SELECT DISTINCT` / `SELECT TOP N` (0–5000)
- `INNER JOIN` / `LEFT JOIN`
- `WHERE`, `GROUP BY`, `ORDER BY`, `OFFSET`/`FETCH`
- Aggregates: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`

## NOT supported

`SELECT *` · subqueries · CTEs · `HAVING` · `UNION` · `RIGHT`/`FULL`/`CROSS JOIN` ·
`CASE` · string/date/math functions

## ⚠️ The silent 5000-row cap

Results are truncated at ~5000 rows **without an error**. dv_query.py warns when
the row count hits the cap; for anything larger use OData pagination
(`@odata.nextLink`) instead.

## When to use

Single-request reads of small/medium tables (<5K rows): ~2–6s, one HTTP call.
Counting and GROUP BY run server-side — never download rows to count them.

## Column naming

Same as OData: all-lowercase LogicalName in SELECT/WHERE/ORDER BY/JOIN.
Table names in FROM/JOIN are logical names, not entity sets.

## Example

```sql
SELECT contoso_status, COUNT(*) AS n
FROM contoso_salesorder
WHERE contoso_orderdate >= '2026-01-01'
GROUP BY contoso_status
ORDER BY n DESC
```
