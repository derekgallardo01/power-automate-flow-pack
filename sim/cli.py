"""Command-line wrapper around `run_sync`.

    python sim/cli.py --source sim/data/asana_export.json \
                      --mapping sim/data/mapping-config.json \
                      --table sim/out/excel_table.json \
                      --fail-writes 1 --reset

Use --dry-run to see what would be written without touching disk.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from flow import run_sync  # noqa: E402


def _default(path: str) -> str:
    return os.path.join(HERE, path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Run the scheduled-sync simulator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--source", default=_default("data/asana_export.json"),
                   help="Path to the source records JSON file.")
    p.add_argument("--mapping", default=_default("data/mapping-config.json"),
                   help="Path to the field-mapping config JSON file.")
    p.add_argument("--table", default=_default("out/excel_table.json"),
                   help="Path to the output (mock Excel) table JSON file.")
    p.add_argument("--fail-writes", type=int, default=0,
                   help="Simulate N transient write failures before success.")
    p.add_argument("--dry-run", action="store_true",
                   help="Run every step but do not modify the table or DLQ.")
    p.add_argument("--reset", action="store_true",
                   help="Delete the output table (and DLQ) before running.")
    args = p.parse_args(argv)

    dlq_path = os.path.join(os.path.dirname(args.table) or ".", "dlq.json")

    if args.reset:
        for path in (args.table, dlq_path):
            if os.path.exists(path):
                os.remove(path)

    log, result = run_sync(
        source_path=args.source,
        mapping_path=args.mapping,
        table_path=args.table,
        fail_writes=args.fail_writes,
        dry_run=args.dry_run,
        dlq_path=dlq_path,
    )
    print(log)
    print(
        f"summary: added={result['added']} total={result['total']} "
        f"skipped={result['skipped']} dlq_count={result['dlq_count']}"
        + (" [dry-run]" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
