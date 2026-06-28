# Getting started

A 5-minute walkthrough — no Power Platform tenant required, no `pip
install` other than pytest.

## 1. Clone and run the demo

```bash
git clone https://github.com/derekgallardo01/power-automate-flow-pack.git
cd power-automate-flow-pack
python sim/run.py
```

You should see two runs. Run 1 has a forced transient failure recovered
on retry → 4 rows written. Run 2 is idempotent — same source, 0 new rows
written (4 duplicates skipped).

## 2. Run the eval set

```bash
python evals/run.py
```

`Eval (golden.json): 9/9 passed (100%)`. Scenarios: clean run, transient
recovery, multi-retry recovery, idempotent rerun, partial dedup, DLQ,
multi-row DLQ, dry-run, dry-run + DLQ.

There's also a second source (Microsoft Forms responses):

```bash
python evals/run.py golden-forms.json sim/data/forms-responses.json sim/data/mapping-config-forms.json
```

`Eval (golden-forms.json): 5/5 passed (100%)`.

## 3. Try the CLI flags

```bash
python sim/cli.py --dry-run
python sim/cli.py --fail-writes 2 --reset
python sim/cli.py --source sim/data/forms-responses.json \
                  --mapping sim/data/mapping-config-forms.json
```

`--dry-run` logs every step but writes nothing.
`--fail-writes N` injects N transient failures before success.
`--reset` deletes the output table + DLQ before running.

## 4. Run in Docker (optional)

```bash
docker build -t power-automate-flow-pack .
docker run --rm power-automate-flow-pack
```

## What to read next

- [Architecture](architecture.md) · [Customization](customization.md) ·
  [Evaluation](evaluation.md) · [Diagrams](diagrams.md) · [FAQ](faq.md)

## Bringing it to a real tenant

The simulator proves the **logic**. The matching Power Automate flow
exports in `flows/` are what you actually build in the tenant. Walk
[`import-guide.md`](../import-guide.md) for the tenant build.
