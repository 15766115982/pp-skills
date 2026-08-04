# Cross-Artifact References

## Table → Apps

| Table (logical) | Display name | Used by apps |
|---|---|---|
| `contoso_orderline` | Order Line | SalesHub |
| `contoso_salesorder` | Sales Order | SalesHub |

## Table → Flows

| Table (logical) | Display name | Used by flows |
|---|---|---|
| `contoso_orderline` | Order Line | Contoso Order Approval |
| `contoso_salesorder` | Sales Order | Contoso Order Approval, Daily Order Digest |
| contoso_invoiceline (external — not in KB) | — | Daily Order Digest |

## Connector → Artifacts

| Connector | Artifacts |
|---|---|
| `shared_commondataserviceforapps` | Contoso Order Approval, Daily Order Digest |
| `shared_office365` | Contoso Order Approval, SalesHub |

## Reference graph

```mermaid
flowchart LR
    subgraph Apps
        A0["SalesHub"]
    end
    subgraph Flows
        F0["Contoso Order Approval"]
        F1["Daily Order Digest"]
    end
    subgraph Tables
        T0[("contoso_orderline")]
        T1[("contoso_salesorder")]
        X0["contoso_invoiceline<br/>(external — not in KB)"]
    end
    A0 --> T0
    A0 --> T1
    F0 --> T0
    F0 --> T1
    F1 --> X0
    F1 --> T1
```

---
*Snapshot: org12345.crm5.dynamics.com | cross-reference build*
