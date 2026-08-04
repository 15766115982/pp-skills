# Table: contoso_orderline (Order Line)

| | |
|---|---|
| Logical name | `contoso_orderline` |
| Display name | Order Line |
| Schema name | `contoso_OrderLine` |
| Entity set | `contoso_orderlines` |
| Primary ID | `contoso_orderlineid` |
| Primary name | `contoso_name` |
| Ownership | UserOwned |

## Columns (6)

| Logical name | Display name | Type | Required | Notes |
|---|---|---|---|---|
| `contoso_orderlineid` | Order Line ID | Uniqueidentifier | System | Primary key |
| `contoso_name` | Line Description | String (100) | None | Primary name |
| `contoso_product` | Product | Lookup | None | → `product` |
| `contoso_quantity` | Quantity | Integer [1..10000] | Required |  |
| `contoso_salesorder` | Sales Order | Lookup | Required | → `contoso_salesorder` |
| `contoso_unitprice` | Unit Price | Money (prec 2) | None |  |

## Relationships

| Type | Related table | Schema name | Notes |
|---|---|---|---|
| N:1 | `contoso_salesorder` | `contoso_salesorder_orderline` | via `contoso_salesorder` |
| N:1 | `product` | `contoso_orderline_product` | via `contoso_product` |
| N:N | `contoso_tag` | `contoso_orderline_tag` | intersect `contoso_orderline_tag` |

## Used by

_(populated by build_crossrefs — phase 4)_

---
*Snapshot: org12345.crm5.dynamics.com | 2026-08-04T09:31:00+00:00 | Raw: `_raw/metadata/`*
