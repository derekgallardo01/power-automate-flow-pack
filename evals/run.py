"""Run the scheduled-sync simulator against a golden scenario set.

    python evals/run.py
    python evals/run.py golden-forms.json sim/data/forms-responses.json sim/data/mapping-config-forms.json

Exit code is 0 if every scenario passes, 1 otherwise - suitable for CI gating.
Two scenario sets ship in the repo: the Asana-time-entries one
(`golden.json` + `sim/data/asana_export.json`) and the Microsoft-Forms one
(`golden-forms.json` + `sim/data/forms-responses.json`). Each pairs with
its own mapping config.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))

from flow import run_sync  # noqa: E402

# Defaults (Asana scenario). Overridden by CLI args.
DEFAULT_GOLDEN = "golden.json"
DEFAULT_SRC = os.path.join("sim", "data", "asana_export.json")
DEFAULT_MAP = os.path.join("sim", "data", "mapping-config.json")


def _setup(scenario: dict, src: str, mapping: str) -> tuple[str, str]:
    tmp = tempfile.mkdtemp(prefix="flowpack-eval-")
    table = os.path.join(tmp, "excel_table.json")
    dlq = os.path.join(tmp, "dlq.json")

    if scenario.get("seed_run"):
        run_sync(src, mapping, table, fail_writes=0, dlq_path=dlq)

    preseed = scenario.get("preseed_ids")
    if preseed:
        with open(mapping, encoding="utf-8") as fh:
            mp = json.load(fh)
        with open(src, encoding="utf-8") as fh:
            entries = json.load(fh)
        keep = [e for e in entries if e.get("id") in preseed]
        rows = [
            {col: e.get(k) for col, k in mp["fields"].items()}
            for e in keep
        ]
        with open(table, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)

    return table, dlq


def _run_case(case: dict, src: str, mapping: str) -> tuple[bool, list[str], dict, str]:
    scenario = case.get("scenario", {})
    table, dlq = _setup(scenario, src, mapping)
    log, result = run_sync(
        src, mapping, table,
        fail_writes=scenario.get("fail_writes", _default_fail_writes(case["id"])),
        dry_run=scenario.get("dry_run", False),
        permanent_fail_ids=scenario.get("permanent_fail_ids"),
        dlq_path=dlq,
    )
    log_text = str(log)

    expect = case["expect"]
    details: list[str] = []
    for k in ("added", "total", "skipped", "dlq_count"):
        if k in expect and result.get(k) != expect[k]:
            details.append(f"{k}={result.get(k)} expected={expect[k]}")
    for substr in expect.get("log_contains", []):
        if substr not in log_text:
            details.append(f"log missing substring {substr!r}")
    if "table_exists" in expect and os.path.exists(table) != expect["table_exists"]:
        details.append(f"table_exists={os.path.exists(table)} expected={expect['table_exists']}")
    if "dlq_exists" in expect and os.path.exists(dlq) != expect["dlq_exists"]:
        details.append(f"dlq_exists={os.path.exists(dlq)} expected={expect['dlq_exists']}")

    return (len(details) == 0, details, result, log_text)


def _default_fail_writes(case_id: str) -> int:
    if case_id == "transient-recovered":
        return 1
    if case_id == "transient-recovered-on-third":
        return 2
    return 0


def evaluate(cases: list[dict], src: str, mapping: str) -> dict:
    passed, failed = [], []
    for case in cases:
        ok, details, result, _ = _run_case(case, src, mapping)
        record = {
            "id": case.get("id", "?"),
            "description": case.get("scenario", {}).get("description", ""),
            "details": details,
            "result": result,
        }
        (passed if ok else failed).append(record)
    return {"passed": passed, "failed": failed}


def _resolve(p: str, base: str) -> str:
    return p if os.path.isabs(p) else os.path.join(base, p)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    golden_name = argv[0] if len(argv) > 0 else DEFAULT_GOLDEN
    src_rel = argv[1] if len(argv) > 1 else DEFAULT_SRC
    mapping_rel = argv[2] if len(argv) > 2 else DEFAULT_MAP

    golden_path = _resolve(golden_name, HERE)
    src_path = _resolve(src_rel, ROOT)
    mapping_path = _resolve(mapping_rel, ROOT)

    with open(golden_path, encoding="utf-8") as fh:
        cases = json.load(fh)
    result = evaluate(cases, src_path, mapping_path)

    total = len(cases)
    n_pass = len(result["passed"])
    n_fail = len(result["failed"])
    rate = (n_pass / total * 100) if total else 0.0
    label = os.path.basename(golden_path)
    print(f"Eval ({label}): {n_pass}/{total} passed ({rate:.0f}%)")
    if n_fail:
        print(f"\n{n_fail} failed:")
        for f in result["failed"]:
            print(f"  [{f['id']}] {f['description']}")
            for d in f["details"]:
                print(f"      {d}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
