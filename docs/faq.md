# FAQ

## What's the difference between transient and permanent failures?

A **transient** failure is a plain `Exception` raised inside the write
action — typically a connector timeout, 5xx, throttle 429. `with_retry`
retries up to 3 times with progressive logging. A **permanent** failure
is a `PermanentError` (the kit's own exception type) — typically a 4xx
that won't succeed on retry (bad row, schema mismatch, auth invalid for
that specific row). It's not retried; the row goes to the DLQ.

## Why a dead-letter queue (DLQ) instead of just aborting the run?

A naive flow that aborts on the first bad row creates an operational
nightmare: nothing lands until the bad row is fixed, re-running doesn't
help, and you can't tell whether the rest of the data would have been
fine. The DLQ lets the good rows land, isolates the bad ones for human
review, and lets the run report success-with-caveats rather than total
failure.

## When should I use `on_failure="raise"` instead of `"dlq"`?

In tests where you want to assert the propagation path, or in genuinely
all-or-nothing downstream consumers (rare). Production deployments
should default to `"dlq"`.

## Why is `dry_run` part of the engine and not a CLI flag wrapper?

Because dry-run needs to thread through every write decision —
`write_table`, `write_dlq`, the file existence checks. A wrapper that
swallowed file writes after the fact would be lying about the run log
(it'd say "wrote table" then not have written). Threading `dry_run` into
the engine means the run log says `[DRY RUN] wrote table: N new rows`
explicitly, and `table_exists` on disk is the ground truth.

## Why does the dedup key come from `mapping["key"]`?

So you can swap data sources without touching code. The Asana sample uses
`EntryId`; the Forms sample uses `RequestId`. The simulator doesn't know
or care — it just dedups on whatever column the mapping calls "key".

## How do I add a new source connector?

Edit `mapping-config.json` (or write a new one) to map the connector's
field names to your destination columns. The connector ITSELF lives in
Power Automate / the simulator only ever sees a list of dicts. As long
as your connector produces JSON that matches the mapping, the simulator
runs against it unchanged. See [customization.md §1](customization.md#1-swap-the-source-connector).

## What about a webhook trigger instead of a scheduled trigger?

In Power Automate, swap the recurrence trigger for the relevant webhook
trigger — the rest of the flow doesn't change. The simulator only models
the scheduled-pull path; webhook delivery is its own pattern (the kit
doesn't simulate it because it's hard to make deterministic in a test).

## How do I send notifications to Teams instead of email?

In Power Automate, swap the "Send email" action for "Post message in a
chat or channel". Or wrap both behind an environment variable so the
choice is per-tenant. The simulator currently logs "notify: success
notification sent" as a placeholder — replace with the real channel in
production.
