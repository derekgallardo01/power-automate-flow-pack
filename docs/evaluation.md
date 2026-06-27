# Evaluation

Unit tests in [sim/tests/](../sim/tests/) check the pieces in isolation. The
eval set in [evals/golden.json](../evals/golden.json) tests end-to-end
**scenarios** — what the run does with a specific input shape — so a future
refactor that breaks behaviour without breaking the units gets caught.

## What it does

[evals/run.py](../evals/run.py) loads `golden.json`, sets up each scenario in a
fresh temp directory (optionally seeding an existing table or pre-existing
rows), runs `run_sync`, and checks the returned `added` / `total` / `skipped` /
`dlq_count` against expectations, plus that the run log contains specific
substrings. Exit code is 0 if all pass — suitable for CI gating.

```text
Eval: 9/9 passed (100%)
```

On failure you get the specific mismatch:

```text
Eval: 8/9 passed (89%)

1 failed:
  [dry-run] Dry-run reports what would happen but writes nothing.
      table_exists=True expected=False
```

## Case format

Each case in `golden.json`:

```json
{
  "id": "permanent-failure-to-dlq",
  "scenario": {
    "description": "One row is permanently rejected; lands in DLQ, run still succeeds.",
    "permanent_fail_ids": ["t1"]
  },
  "expect": {
    "added": 3,
    "total": 3,
    "skipped": 0,
    "dlq_count": 1,
    "log_contains": ["dlq: recorded 1 failed row", "notify: success notification sent"]
  }
}
```

| Scenario knob | Meaning |
|---------------|---------|
| `seed_run` | Run `run_sync` once before the test to populate the table (for idempotency cases). |
| `preseed_ids` | Pre-write specific rows into the table before the test (for partial-dedup cases). |
| `fail_writes` | Number of transient write failures to simulate before success. |
| `permanent_fail_ids` | Source ids that should be rejected as permanent failures (→ DLQ). |
| `dry_run` | Run in dry-run mode (no disk writes). |

| Expect field | Meaning |
|--------------|---------|
| `added` / `total` / `skipped` / `dlq_count` | Numeric assertions on the `run_sync` result dict. |
| `log_contains` | List of substrings the run log must contain (order-independent). |
| `table_exists` / `dlq_exists` | Whether the file exists after the run (key for dry-run assertions). |

## Adding cases

Three patterns:

**1. Capture every real-world failure as a scenario.** When a deployment hits a
weird input shape that broke the flow, copy the row(s) into a tiny fixture and
write the scenario before changing code. The eval set is your regression net.

**2. Add throughput edge cases.** Empty source, single row, every row deduped,
every row in DLQ. Each surfaces a different boundary.

**3. Add cross-feature interactions.** Dry-run + permanent failure, idempotent
rerun after a partial DLQ, etc. These are where most subtle bugs hide.

## Workflow when tuning

1. Add the failing scenario(s) to `golden.json` (or copy an existing one and
   tweak the input).
2. Run `python evals/run.py` and see them fail.
3. Change the connector mapping, retry config, or DLQ routing.
4. Re-run. Iterate until the pass rate is back to 100% and existing scenarios
   didn't regress.

This is the same loop that scales to a real tenant — the only difference is
runtime per case (a few seconds per scenario instead of milliseconds).

## What an eval set is not

- **Not a replacement for end-to-end tenant tests.** The eval set proves
  *logic*; the import-guide checklist proves *integration* (connector auth,
  approvals, throttling).
- **Not a substitute for a DLQ review process.** Tests can prove a row went
  to DLQ; only humans can decide what to do about it.
- **Not exhaustive.** 9 cases here are illustrative. A serious deployment runs
  with 30–50 scenarios across every error class the connector can produce.
