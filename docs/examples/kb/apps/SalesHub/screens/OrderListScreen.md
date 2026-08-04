# Screen: OrderListScreen (SalesHub)

Source: `canvas-src/SalesHub/Src/OrderListScreen.pa.yaml`

## Control tree (8 controls, non-default props shown)

```
OrderListScreen
├── HeaderBar (component: HeaderBar)            Title: ="Orders"
├── galOrders (gallery, vertical)
│   Items: =Filter(colOrders, ddStatus.Selected.Value = "All" || contoso_status = ddStatus.Selected.Value)
│   ├── lblOrderNumber (label)                  Text: =ThisItem.contoso_name
│   ├── lblStatus (label)                       Text: =Text(ThisItem.contoso_status)
│   │                                           Fill: =If(ThisItem.contoso_status = 'contoso_status'.Approved, Color.Green, Color.Gray)
│   └── icoNext (icon: ChevronRight)
│       OnSelect: =Navigate(OrderDetailScreen, ScreenTransition.Fade, {selectedOrder: ThisItem})
├── ddStatus (dropdown)
│   Items: =["All", "Draft", "Submitted", "Approved", "Rejected"]
│   Default: ="All"
└── btnRefresh (button)
    OnSelect: =ClearCollect(colOrders, SortByColumns('Sales Orders', "contoso_orderdate", Descending))
```

## Formulas by property

| Control.Property | Formula |
|---|---|
| galOrders.Items | `Filter(colOrders, ddStatus.Selected.Value = "All" \|\| contoso_status = ddStatus.Selected.Value)` |
| icoNext.OnSelect | `Navigate(OrderDetailScreen, ScreenTransition.Fade, {selectedOrder: ThisItem})` |
| btnRefresh.OnSelect | `ClearCollect(colOrders, SortByColumns('Sales Orders', "contoso_orderdate", Descending))` |

## Data references on this screen

- Collections: `colOrders` (written here and in App.OnStart)
- Tables: `contoso_salesorder` (via `'Sales Orders'`)
- Navigation out: → OrderDetailScreen

---
*Full formulas: see source file. Large-file policy: >1 MB screens list properties only.*
