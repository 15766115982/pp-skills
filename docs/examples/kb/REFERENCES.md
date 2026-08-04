# Cross-Artifact References — ContosoSales

## Table → Apps

| Table (logical) | Display name | Used by apps |
|---|---|---|
| `contoso_salesorder` | Sales Order | SalesHub |
| `contoso_orderline` | Order Line | SalesHub |

## Table → Flows

| Table (logical) | Display name | Used by flows | Operations |
|---|---|---|---|
| `contoso_salesorder` | Sales Order | Contoso Order Approval | trigger (row created), UpdateRow, GetRow |
| `contoso_orderline` | Order Line | Contoso Order Approval | ListRows |

## Connector → Artifacts

| Connector (apiId) | Artifacts |
|---|---|
| `shared_commondataserviceforapps` (Dataverse) | Contoso Order Approval, SalesHub |
| `shared_office365` (Office 365 Outlook) | Contoso Order Approval |

## Reference graph

```mermaid
flowchart LR
    subgraph Apps
        App1["SalesHub"]
    end
    subgraph Flows
        F1["Contoso Order Approval"]
    end
    subgraph Tables
        T1[("contoso_salesorder")]
        T2[("contoso_orderline")]
    end
    subgraph Connectors
        C1["Dataverse"]
        C2["Office 365 Outlook"]
    end
    App1 -- "Patch / gallery binding" --> T1
    App1 -- "gallery binding" --> T2
    F1 -- "trigger + UpdateRow" --> T1
    F1 -- "ListRows" --> T2
    App1 --> C1
    F1 --> C1
    F1 --> C2
```
