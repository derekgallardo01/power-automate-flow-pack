# Flow templates

Documented Power Automate flow definitions you recreate/import in the designer.
They version the *design* in git; the live flows are built in the tenant
(see `../import-guide.md`).

| File | What it is |
|------|------------|
| `scheduled-sync.flow.json` | Hero flow: schedule → pull source → map fields → upsert to an Excel table → notify. |
| `approval.flow.json` | Approval gate: route an item for approval, act on the outcome. |
| `error-handling.subpattern.yaml` | Reusable try/catch/retry + run-log + notify scope to wrap any fragile action. |
| `mapping-config.example.json` | Example field map (Employee/Date/Project/Hours/Cost Center/Approved). |

The `../sim/` simulator implements the same logic offline so you can demonstrate
and test it without a tenant.
