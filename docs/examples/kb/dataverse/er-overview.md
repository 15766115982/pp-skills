# Dataverse ER Overview — ContosoSales

2 tables in scope. Relationship metadata from `RelationshipDefinitions` (see `_raw/metadata/`).

```mermaid
erDiagram
    account ||--o{ contoso_salesorder : "customer (N:1)"
    contoso_salesorder ||--o{ contoso_orderline : "order lines (1:N, parental)"

    contoso_salesorder {
        uniqueidentifier contoso_salesorderid PK
        string contoso_name "Order Number, req"
        lookup contoso_customer FK
        datetime contoso_orderdate
        picklist contoso_status "Draft/Submitted/Approved/Rejected"
        money contoso_totalamount
    }
    contoso_orderline {
        uniqueidentifier contoso_orderlineid PK
        lookup contoso_salesorder FK
        lookup contoso_product "→ product"
        int contoso_quantity
        money contoso_unitprice
    }
```

> Tables out of solution scope (`account`, `product`) appear as boundary nodes without column detail.
> Rule: >40 tables → split into sub-diagrams by publisher prefix.
