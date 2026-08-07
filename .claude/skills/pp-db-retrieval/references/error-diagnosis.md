# Error Diagnosis (Dataverse Web API)

Decision tree for the four common failures. Resolve names from the local kb
(`kb/dataverse/tables/*.md`) before concluding anything is missing server-side.

## 400 Bad Request — query shape is wrong

| Likely cause | Check |
|---|---|
| `$expand` used logical name / wrong case | Navigation property name is case-sensitive; look it up in the kb Relationships section |
| Navigation property in `$select` | Move it to `$expand`; select its columns inside the expand |
| Choice compared by label | Compare by integer value (kb doc's choice table) |
| Bad literal quoting | Strings single-quoted, quotes doubled; GUIDs unquoted; ISO dates |
| `$apply` syntax | `groupby((a,b),aggregate(x with sum as total))` — parentheses balanced |
| SQL beyond the subset | See tsql-subset.md (no `SELECT *`, no subqueries, no functions) |

## 401 Unauthorized — token problem

- SPN env vars set? (`PP_TENANT_ID/PP_CLIENT_ID/PP_CLIENT_SECRET/PP_DATAVERSE_URL`)
- Secret expired or wrong tenant?
- Proxy intercepting? (`HTTPS_PROXY`)
- Token audience must be `<dataverseUrl>/.default` — pp_common handles this.

## 403 Forbidden — permission problem

- SPN registered as **Application User** in the environment?
- Security role grants read on this table? (Table-level privileges are enforced
  for SPNs exactly as for users.)
- Note: metadata read and data read are separate privileges.

## 404 Not Found — name problem (usually NOT "table missing")

| Likely cause | Check |
|---|---|
| Wrong entity set name | Read the kb doc's `Entity set` row — never hand-pluralize (`im_category` → `im_categories`, not `im_categorys`) |
| Typo in logical name | kb file names are exact logical names |
| Wrong environment | `PP_DATAVERSE_URL` pointing at the intended org? |

## Escalation

If a query keeps failing after these checks: capture the exact URL (params
visible, token redacted) and the response body's `error.message` — that pair
diagnoses nearly everything.
