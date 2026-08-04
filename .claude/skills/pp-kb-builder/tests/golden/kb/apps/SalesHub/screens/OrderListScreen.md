# Screen: OrderListScreen (SalesHub)

## Control tree (7 controls)

```
hdrMain (Component/HeaderBar)
galOrders (Gallery/Vertical)
  lblOrderNumber (Label)
  lblStatus (Label)
  icoNext (Icon/ChevronRight)
ddStatus (Dropdown)
btnRefresh (Button)
```

## Formulas by property

| Control.Property | Formula |
|---|---|
| (screen).Fill | `RGBA(245, 245, 245, 1)` |
| (screen).OnVisible | `Refresh('Sales Orders')` |
| hdrMain.Title | `"Orders"` |
| galOrders.Items | `Filter(colOrders, ↵     ddStatus.Selected.Value = "All" \|\| ↵     Text(contoso_status) = ddStatus.Selected.Value)` |
| galOrders.Layout | `Layout.Vertical` |
| lblOrderNumber.Text | `ThisItem.contoso_name` |
| lblOrderNumber.X | `10` |
| lblOrderNumber.Y | `10` |
| lblStatus.Text | `Text(ThisItem.contoso_status)` |
| lblStatus.Fill | `If(ThisItem.contoso_status = 'contoso_status'.Approved, Color.Green, Color.Gray)` |
| icoNext.OnSelect | `Navigate(OrderDetailScreen, ScreenTransition.Fade, {selectedOrder: ThisItem})` |
| ddStatus.Items | `["All", "Draft", "Submitted", "Approved", "Rejected"]` |
| ddStatus.Default | `"All"` |
| btnRefresh.Text | `"Refresh"` |
| btnRefresh.OnSelect | `ClearCollect(colOrders, SortByColumns('Sales Orders', "contoso_orderdate", Descending))` |

## Data references on this screen

- Collections: `colOrders`
- Data sources: `Sales Orders`
- Navigation out: → OrderDetailScreen

---
*Snapshot: SalesHub | commit testcommit | schema v3.0 | Source: `tests/fixtures/canvas-src/SalesHub/Src` (read-only)*
