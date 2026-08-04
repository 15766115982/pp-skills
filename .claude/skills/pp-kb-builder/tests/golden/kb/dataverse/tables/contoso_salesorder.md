# Table: contoso_salesorder (Sales Order)

| | |
|---|---|
| Logical name | `contoso_salesorder` |
| Display name | Sales Order |
| Schema name | `contoso_SalesOrder` |
| Entity set | `contoso_salesorders` |
| Primary ID | `contoso_salesorderid` |
| Primary name | `contoso_name` |
| Ownership | UserOwned |

## Columns (10)

| Logical name | Display name | Type | Required | Notes |
|---|---|---|---|---|
| `contoso_salesorderid` | Sales Order ID | Uniqueidentifier | System | Primary key |
| `contoso_name` | Order Number | String (64) | Required | Primary name |
| `contoso_customer` | Customer | Lookup | Required | → `account` |
| `contoso_isrush` | Rush Order | Boolean | None |  |
| `contoso_notes` | Notes | Memo (2000) | None |  |
| `contoso_orderdate` | Order Date | DateTime (DateOnly) | Required |  |
| `contoso_priority` | Priority | Integer [1..5] | None |  |
| `contoso_status` | Status | Picklist | Required | → choices below |
| `contoso_totalamount` | Total Amount | Money (prec 2) | None |  |
| `statecode` | Status | State | System | → choices below |

## Choice: contoso_status

| Value | Label |
|---|---|
| 100000000 | Draft |
| 100000001 | Submitted |
| 100000002 | Approved |
| 100000003 | Rejected |

## Choice: statecode

| Value | Label |
|---|---|
| 0 | Active |
| 1 | Inactive |

## Relationships

| Type | Related table | Schema name | Notes |
|---|---|---|---|
| 1:N | `contoso_orderline` | `contoso_salesorder_orderline` | Parental (cascade delete) |
| N:1 | `account` | `contoso_salesorder_customer` | via `contoso_customer` |

## Used by

- **Apps**: [SalesHub](../../apps/SalesHub/overview.md)
- **Flows**: [Contoso Order Approval](../../flows/contoso-order-approval.md), [Daily Order Digest](../../flows/daily-order-digest.md)

---
*Snapshot: org12345.crm5.dynamics.com | 2026-08-04T09:31:00+00:00 | Raw: `_raw/metadata/`*
