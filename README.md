# Power Automate flow pack

[![CI](https://github.com/derekgallardo01/power-automate-flow-pack/actions/workflows/ci.yml/badge.svg)](https://github.com/derekgallardo01/power-automate-flow-pack/actions/workflows/ci.yml)

Reusable Power Automate patterns for Microsoft 365 automation — pull data on a
schedule, map fields, write it to an Excel table in SharePoint, with **retry**,
**de-duplication**, a **dead-letter queue**, **dry-run** mode, and a **run log**
baked in.

Includes an offline simulator that proves the logic without a tenant — run it
with `python sim/run.py` and watch a transient failure recover and an
idempotent re-run skip everything. The CLI exposes the DLQ + dry-run paths the
canned demo doesn't show.

```bash
python sim/run.py                          # transient failure → retry + idempotent re-run
python sim/cli.py --dry-run                # every step logged, nothing written
python sim/cli.py --fail-writes 1 --reset  # custom run with options
python evals/run.py                        # 9 end-to-end scenarios, CI-gating
python -m pytest sim/tests/ -q             # 10 unit tests
```

Stdlib-only Python, no tenant required to run any of this.

## The problem it solves

A team had approved time entries in Asana but payroll needed them in an Excel
table in SharePoint — and someone was copying rows by hand every week. Naive
automations break in two predictable ways: they duplicate rows on re-runs, and
they fail silently on a transient timeout. **Permanent failures** are worse
still: a single bad row aborts the whole sync, so nothing lands until someone
hand-fixes the data. This pattern handles all three.

```mermaid
flowchart LR
    T["Daily schedule"] --> P["Pull approved entries"]
    P --> M["Map fields"]
    M --> S{"Permanent fail?"}
    S -- "no" --> U["Upsert rows (dedupe on id)"]
    U --> R["Retry transient errors"]
    S -- "yes" --> Q["Dead-letter queue<br/>(reason + timestamp)"]
    R --> N["Success notification"]
    Q --> N
```

## Architecture in one paragraph

`run_sync` runs five steps in order: trigger → `load_json` (source + mapping) →
`map_entries` (field map + approved filter) → `write_table` (idempotent upsert
keyed on `mapping["key"]`, wrapped in `with_retry` which retries plain
`Exception` and propagates `PermanentError` immediately) → `write_dlq` (any
rows in `permanent_fail_ids` get appended to `dlq.json` with reason + UTC
timestamp). `dry_run=True` performs every step but writes nothing, with
`[DRY RUN]` markers on the run-log entries it would change. Full diagrams +
per-component notes: [docs/architecture.md](docs/architecture.md).

## Sample output

```text
=== Normal run with a transient failure recovered on retry ===
  - trigger: scheduled run started
  - pull: 5 entries from source
  - map: 4 approved rows after field mapping
  - write to Excel table: attempt 1 failed (transient connector timeout); retrying
  - wrote table: 4 new rows, 4 total (0 duplicates skipped)
  - write to Excel table: succeeded on attempt 2
  - notify: success notification sent
summary: {'added': 4, 'total': 4, 'skipped': 0, 'dlq_count': 0}
```

Captured run including idempotent re-run, dry-run, and a permanent-failure
→ DLQ example: [docs/sample-run.txt](docs/sample-run.txt).

## Evaluation

Nine end-to-end scenarios in [evals/golden.json](evals/golden.json) cover the
full grid: clean run, transient recovery, multi-retry recovery, idempotent
re-run, partial dedup, permanent failure → DLQ, multi-row DLQ, dry-run, dry-run
+ DLQ combined.

```bash
$ python evals/run.py
Eval: 9/9 passed (100%)
```

How to add scenarios (real-world failure capture, throughput edges,
cross-feature interactions) is in [docs/evaluation.md](docs/evaluation.md).

## Customization

Six typical tuning points — source connector, dedup key, retry semantics
(what's transient vs permanent), DLQ destination, schedule cadence,
notifications — are walked through in
[docs/customization.md](docs/customization.md). Most are one-line edits in
`mapping-config.json` or [sim/flow.py](sim/flow.py).

## What's inside

| Path | Purpose |
|------|---------|
| [flows/](flows/) | Power Automate flow exports: `scheduled-sync`, `approval`, the reusable `error-handling` sub-pattern, and an example field-mapping config. |
| [import-guide.md](import-guide.md) | Build/import steps + a test-with-sample-data-first checklist. |
| [sim/flow.py](sim/flow.py) | The pattern: `run_sync`, `with_retry`, `write_table`, `write_dlq`, `RunLog`, `PermanentError`. |
| [sim/cli.py](sim/cli.py) | argparse wrapper: `--source/--mapping/--table`, `--fail-writes`, `--dry-run`, `--reset`. |
| [sim/run.py](sim/run.py) | Scripted two-run demo (transient failure recovered + idempotent re-run). |
| [sim/tests/](sim/tests/) | 10 pytest unit tests across mapping, retry, DLQ, dry-run. |
| [evals/](evals/) | 9 end-to-end scenarios + CI-gating runner. |
| [docs/](docs/) | Architecture, customization, and evaluation guides. |

## Taking it to a real tenant

Build the flow in Power Automate from the templates in [flows/](flows/),
following [import-guide.md](import-guide.md). Test against a sandbox source and
destination first, using the eval scenarios as your acceptance test list. Same
logic, same guarantees as the simulator.
