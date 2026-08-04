# Coverage Manifest — ContosoSales snapshot

> Generated 2026-08-04. This file declares **what this KB does and does not cover**.
> If something is absent here, it is intentionally out of scope — do not assume generation failure.

## In scope (fully parsed)

| Type | Items |
|---|---|
| Tables (2) | `contoso_salesorder`, `contoso_orderline` |
| Flows (1) | Contoso Order Approval |
| Canvas screens — full parse (2) | SalesHub/OrderListScreen, SalesHub/OrderDetailScreen |

## Shallow index only (structure known, details not parsed)

| Type | Items | Granularity |
|---|---|---|
| Canvas screens (6) | SalesHub/SettingsScreen, SalesHub/ReportScreen, SalesHub/AdminScreen, … | name, control names, data-source refs, navigation edges |

## External / boundary references (referenced but intentionally not in KB)

| Type | Items | Referenced from |
|---|---|---|
| Tables | `account`, `product`, `invoice lines (contoso_invoiceline)` | app formulas, flow actions |
| Flows | Invoice Sync (ContosoFinance solution) | — |
| Connectors | SharePoint (`shared_sharepointonline`) | ReportScreen |

## Filters applied at capture

`solutions: ["ContosoSales"]` · `tables: [contoso_salesorder, contoso_orderline]` · `screens: ["Order*"]`
