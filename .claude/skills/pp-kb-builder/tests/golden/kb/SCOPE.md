# Coverage Manifest

> This file declares **what this KB does and does not cover**.
> If something is absent here, it is intentionally out of scope — do not assume generation failure.

## In scope (fully parsed)

- **Tables (2)**: `contoso_orderline`, `contoso_salesorder`
- **Flows (2)**: Contoso Order Approval, Daily Order Digest
- **Canvas screens — full parse (2)**: SalesHub/OrderDetailScreen, SalesHub/OrderListScreen

## Shallow index only (structure known, details not parsed)

- **Canvas screens (1)**:
  - SalesHub/SettingsScreen — not matched by filters.screens

## External / boundary references (referenced but intentionally not in KB)

- **Tables**: `contoso_invoiceline`
  (marked `(external — not in KB)` in REFERENCES.md and diagrams)

## Filters applied at capture

```json
{
  "screens": [
    "Order*"
  ],
  "solutions": [
    "ContosoSales"
  ]
}
```
