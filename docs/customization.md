# Customization

Six things you'll typically tune per client. Each is a small, localized change.

## 1. Swap the source connector

The simulator reads JSON from disk; the real flow reads from a connector
(Asana, ServiceNow, a SQL view, a webhook). Either way the downstream contract
is the same: a list of dicts, each representing a record.

Change `mapping-config.json` to match the new source's field names:

```json
{
  "key": "TicketId",
  "only_approved": false,
  "fields": {
    "TicketId":   "id",
    "Subject":    "title",
    "Assignee":   "owner.email",
    "ClosedAt":   "closed_at"
  }
}
```

`map_entries` in [sim/flow.py](../sim/flow.py) is the join point — it only sees
the mapping config + a list of source dicts, so it doesn't care which connector
they came from.

## 2. Change the dedup key

`mapping["key"]` is the column used for idempotent upserts. Picking the wrong
key is the #1 cause of duplicate-row bugs:

- **A natural key from the source** (record id, ticket number) is best.
- A composite key isn't supported directly; build one as a derived field in
  `map_entries` before `write_table` sees it: e.g. `"BookingKey": f"{date}-{room}"`.
- **Avoid generated keys** (`uuid4`, timestamp) — they break idempotency.

## 3. Tune retry count + what counts as transient

Default: 3 attempts, plain `Exception` is treated as transient (retried),
`PermanentError` is not.

```python
with_retry(write_action, log, attempts=5, label="write to Excel table")
```

If the connector exposes specific exception types (e.g. `HTTPError(429)` for
throttling, `HTTPError(400)` for bad data), translate them at the boundary:

```python
def write_action():
    try:
        return connector.write(rows)
    except HTTPError as e:
        if 400 <= e.code < 500 and e.code != 429:
            raise PermanentError(f"connector rejected: {e.code}") from e
        raise  # 429 / 5xx → transient
```

## 4. DLQ destination

Default: `dlq.json` next to the output table. For production, route the DLQ
somewhere a human will actually see it:

- **A SharePoint list** — easy to triage, supports columns + filters.
- **A Teams notification** — for low-volume DLQs where one bad row should
  ping a channel.
- **A ticket** in ServiceNow / Jira — for when a DLQ entry needs SLAs.

The seam is `write_dlq` in [sim/flow.py](../sim/flow.py); replace the JSON
append with a `requests.post(...)` to your destination of choice.

## 5. Schedule cadence

The simulator runs once per `run_sync` invocation. The real cadence lives in
`flows/scheduled-sync.flow.json` under the trigger node — adjust the
`recurrence` interval there. Common patterns:

- Hourly for time entries (this repo's example).
- Every 15 min for inboxes / queues.
- Nightly at low-traffic hours for snapshot-style syncs.

Heavy syncs at peak hours starve other connectors; check throttling limits in
your tenant before going under hourly.

## 6. Notifications

Default: a single `notify: success notification sent` log line. In production:

- **Always notify on success** with a one-line summary (`added=N, dlq=K`); silent
  success is indistinguishable from "the flow stopped running".
- **Page on DLQ > 0** with the DLQ entries inline. This is what makes the
  difference between "the flow handled it" and "the flow ignored it".
- **Page on failed run** (rare since most failures are caught) with the run log.

Hook these into the existing success notification step in
`flows/scheduled-sync.flow.json`.

## Validating any change

After any of the above:

```bash
python -m pytest sim/tests/ -q
python evals/run.py
python sim/run.py
```

If you changed `map_entries` or `write_table` semantics, add scenarios to
[evals/golden.json](../evals/golden.json) **before** the code change so the
regression net captures the new behaviour.
