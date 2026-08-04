# Dataverse ER Overview

2 tables in scope. Out-of-scope tables appear as boundary nodes without column detail.

```mermaid
erDiagram
    contoso_orderline }o--o{ contoso_tag : "contoso_orderline_tag"
    contoso_salesorder ||--o{ contoso_orderline : "orderline"

    contoso_orderline {
        uniqueidentifier contoso_orderlineid PK "Order Line ID"
        lookup contoso_product FK "Product"
        lookup contoso_salesorder FK "Sales Order"
        string contoso_name "Line Description"
        integer contoso_quantity "Quantity"
        money contoso_unitprice "Unit Price"
    }
    contoso_salesorder {
        uniqueidentifier contoso_salesorderid PK "Sales Order ID"
        lookup contoso_customer FK "Customer"
        boolean contoso_isrush "Rush Order"
        string contoso_name "Order Number"
        memo contoso_notes "Notes"
        datetime contoso_orderdate "Order Date"
        integer contoso_priority "Priority"
        picklist contoso_status "Status"
    }
```

> Tables out of scope appear as boundary nodes without column detail.
> Rule: >40 tables → split into sub-diagrams by publisher prefix.

---
*Snapshot: org12345.crm5.dynamics.com | 2026-08-04T09:31:00+00:00 | Raw: `_raw/metadata/`*
