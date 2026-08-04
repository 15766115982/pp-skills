# Screen: OrderDetailScreen (SalesHub)

## Control tree (4 controls)

```
frmOrder (Form/Edit)
  txtNotes (TextInput)
btnSubmit (Button)
btnBack (Button)
```

## Formulas by property

| Control.Property | Formula |
|---|---|
| (screen).Fill | `RGBA(255, 255, 255, 1)` |
| frmOrder.DataSource | `'Sales Orders'` |
| frmOrder.Item | `selectedOrder` |
| txtNotes.Default | `selectedOrder.contoso_notes` |
| txtNotes.MaxLength | `2000` |
| btnSubmit.Text | `"Submit for approval"` |
| btnSubmit.OnSelect | `Patch('Sales Orders', selectedOrder, ↵     {contoso_status: 'contoso_status'.Submitted, ↵      contoso_notes: txtNotes.Text}); ↵ Notify("Submitted", NotificationType.Success)` |
| btnBack.Text | `"Back"` |
| btnBack.OnSelect | `Back()` |

## Data references on this screen

- Collections: none
- Data sources: `Sales Orders`
- Navigation out:  · Back()

---
*Snapshot: SalesHub | commit testcommit | schema v3.0 | Source: `tests/fixtures/canvas-src/SalesHub/Src` (read-only)*
