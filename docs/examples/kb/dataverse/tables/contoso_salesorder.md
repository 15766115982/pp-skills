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
| Solution | ContosoSales 1.4.2 |

## Columns (12)

| Logical name | Display name | Type | Required | Notes |
|---|---|---|---|---|
| `contoso_salesorderid` | Sales Order ID | Uniqueidentifier | System | Primary key |
| `contoso_name` | Order Number | String (64) | Required | |
| `contoso_customer` | Customer | Lookup | Required | → `account` |
| `contoso_orderdate` | Order Date | DateTime (DateOnly) | Required | |
| `contoso_status` | Status | Picklist | Required | → choices below |
| `contoso_totalamount` | Total Amount | Money | None | Min 0, precision 2 |
| `contoso_notes` | Notes | Memo (2000) | None | |
| `statecode` / `statuscode` | Status (system) | State / Status | System | 0 Active / 1 Inactive |
| `ownerid` | Owner | Lookup | System | → `systemuser` |
| `createdon` / `modifiedon` | Created / Modified | DateTime | System | |

## Choice: contoso_status

| Value | Label (1033) |
|---|---|
| 100 000 000 | Draft |
| 100 000 001 | Submitted |
| 100 000 002 | Approved |
| 100 000 003 | Rejected |

## Relationships

| Type | Related table | Schema name | Notes |
|---|---|---|---|
| 1:N | `contoso_orderline` | `contoso_salesorder_orderline` | Parental (cascade delete) |
| N:1 | `account` | `contoso_salesorder_customer` | via `contoso_customer` |

## Used by

- **Apps**: SalesHub → [overview](../../apps/SalesHub/overview.md)
- **Flows**: Contoso Order Approval → [flow doc](../../flows/contoso-order-approval.md)

---
*Snapshot: org12345.crm5.dynamics.com | 2026-08-04 | Raw: `_raw/metadata/contoso_salesorder.json`*
