# Changelog

Notable changes to the Power Automate flow pack. Dates are when the change
landed on `main`.

## 2026-06-27 — Docker support
- Dockerfile so the simulator runs via `docker run` without a Python install
- README "Run in Docker" section

## 2026-06-27 — Second scenario set (Microsoft Forms)
- `sim/data/forms-responses.json` + `sim/data/mapping-config-forms.json` —
  a second source dataset (Forms responses, no approval filter)
- `evals/golden-forms.json` — 5 end-to-end scenarios
- `evals/run.py` now accepts positional args for golden file + source + mapping
- CI runs both scenario sets on every push

## 2026-06-27 — GitHub Actions CI
- `.github/workflows/ci.yml` running pytest + eval + smoke-test on Python 3.11
- CI status badge added to README

## 2026-06-27 — Build-out: DLQ, dry-run, evals, CLI
- `PermanentError` type for non-retryable failures
- `write_dlq()` with reason + UTC timestamp; `run_sync` grows
  `permanent_fail_ids` / `dry_run` / `dlq_path` / `on_failure` parameters
- `sim/cli.py` argparse wrapper with `--source / --mapping / --table /
  --fail-writes / --dry-run / --reset` flags
- `evals/golden.json` (9 scenarios) + `evals/run.py` with CI-gating exit code
- 5 new tests covering DLQ + dry-run + permanent vs transient distinction
- `docs/architecture.md`, `customization.md`, `evaluation.md`
- `docs/sample-run.txt` (captured normal / idempotent / dry-run / DLQ outputs)
- README expanded with architecture, sample, eval, customization sections

## 2026-06-27 — Initial public release
- Offline simulator of the scheduled-sync flow (pull → map → write → retry)
- Idempotent upserts deduped on a configurable key
- Power Automate `.flow.json` exports for the live tenant build
- `import-guide.md` for the tenant build
- 5 unit tests
