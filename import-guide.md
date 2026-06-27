# Import / build guide — Power Automate flow pack

How to recreate these flows in a client tenant. The `sim/` simulator proves the
logic offline; this builds the real flows.

## Prerequisites
- Power Automate license; access to the source (e.g. Asana) and destination
  (Excel table in SharePoint/OneDrive).
- The destination Excel file with a **formatted Table** (Insert > Table) and named
  columns matching `flows/mapping-config.example.json`.

## Build steps
1. **Trigger** — add a **Recurrence** trigger (e.g. daily 06:00, client's time zone).
2. **Pull** — add the source action (Asana "list time entries", or HTTP to the
   Asana API if the connector is insufficient); filter to approved entries.
3. **Map** — add a **Select** action to map source fields → table columns per the
   mapping config.
4. **Upsert** — for each row, check the table for the key (`EntryId`) and **Add a
   row** only if missing (idempotent — avoids duplicates on re-runs).
5. **Error handling** — wrap the write in the try/catch scope from
   `flows/error-handling.subpattern.yaml`; set the action's **Retry Policy** to
   exponential, count 3.
6. **Notify** — send a success email; in the catch scope, log to an Error Log table
   and notify the owner.

## Test with sample data first (the Asana client asked for this)
- [ ] Point at a **test** Asana workspace and a **test** Excel table.
- [ ] Run manually; confirm only approved rows land, with correct columns.
- [ ] Re-run; confirm **no duplicates** are created.
- [ ] Force a failure (rename the table) to confirm the retry + error log + alert fire.
- [ ] Only then switch to the real source/destination.

## Handover
Document in a handover pack: where it lives, how to monitor run
history, and the runbook for common edits.
