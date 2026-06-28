"""End-to-end scheduled sync run — demonstrates every safety pattern.

The full production loop for a M365 sync flow:

  1. Pull (trigger) - bring data in
  2. Map - normalise field shapes
  3. Write with retry (transient failures handled)
  4. Idempotent dedupe (re-running same item doesn't double-insert)
  5. Dead-letter queue for permanent failures
  6. Dry-run mode for safe rehearsal

This script runs FOUR scenarios in sequence:

  A) Happy path - clean run, no failures
  B) Transient failures - retry succeeds on the 2nd attempt
  C) Permanent failure - row pushed to DLQ, rest of batch continues
  D) Dry-run - same as A but no actual writes

Shows the same flow handling all four cases without code changes.

Usage:
    python examples/sync_run_demo.py
    python examples/sync_run_demo.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim.flow import run_sync  # noqa: E402


SOURCE_PATH = "sim/data/asana_export.json"
MAPPING_PATH = "sim/data/mapping-config.json"


def run_scenario(name: str, narration: str, *, table_path: str, dlq_path: str,
                 fail_writes: int = 0, permanent_fail_ids: list[str] | None = None,
                 dry_run: bool = False) -> dict:
    log, summary = run_sync(
        source_path=SOURCE_PATH,
        mapping_path=MAPPING_PATH,
        table_path=table_path,
        fail_writes=fail_writes,
        permanent_fail_ids=permanent_fail_ids,
        dry_run=dry_run,
        on_failure="dlq",
        dlq_path=dlq_path,
    )
    return {
        "scenario": name, "narration": narration,
        "summary": summary,
        "log_steps": len(log.steps),
        "log_final": log.steps[-1] if log.steps else None,
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scheduled sync run demo across 4 scenarios.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    # Use a temp dir so we don't pollute the repo's out/
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        scenarios = [
            run_scenario(
                "A: Happy path",
                "Clean run, no failures",
                table_path=str(tmp / "happy.json"),
                dlq_path=str(tmp / "happy-dlq.json"),
            ),
            run_scenario(
                "B: Transient failures",
                "Two transient write failures — retry succeeds on 3rd attempt",
                table_path=str(tmp / "transient.json"),
                dlq_path=str(tmp / "transient-dlq.json"),
                fail_writes=2,
            ),
            run_scenario(
                "C: Permanent failure",
                "Row 't2' permanently rejected — DLQ catches it, batch continues",
                table_path=str(tmp / "perm.json"),
                dlq_path=str(tmp / "perm-dlq.json"),
                permanent_fail_ids=["t2"],
            ),
            run_scenario(
                "D: Dry-run",
                "Same as A but no actual writes — useful for rehearsal",
                table_path=str(tmp / "dry.json"),
                dlq_path=str(tmp / "dry-dlq.json"),
                dry_run=True,
            ),
        ]

    if args.json:
        print(json.dumps(scenarios, indent=2, default=str))
        return 0

    for s in scenarios:
        print(f"\n{'=' * 70}")
        print(f"[{s['scenario']}] {s['narration']}")
        print(f"{'=' * 70}")
        summary = s["summary"]
        print(f"  Rows in:       {summary.get('total', '?')}")
        print(f"  Rows added:    {summary.get('added', '?')}")
        print(f"  Rows skipped:  {summary.get('skipped', '?')} (already present, dedupe path)")
        print(f"  Rows DLQ'd:    {summary.get('dlq_count', '?')}")
        print(f"  Steps logged:  {s['log_steps']}")
        if s['dry_run']:
            print(f"  DRY RUN:       (no actual writes occurred)")

    print(f"\n{'=' * 70}")
    print(f"Same flow code, four scenarios: happy / transient / permanent / dry-run.")
    print(f"This is what production-safe Power Automate looks like.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
