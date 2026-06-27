"""Demo the scheduled-sync flow: pull -> map -> write (with retry) -> log.

Run twice to see idempotency: the second run adds 0 rows (all deduped).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flow import run_sync  # noqa: E402


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "data")
    out = os.path.join(here, "out")
    table = os.path.join(out, "excel_table.json")
    dlq = os.path.join(out, "dlq.json")
    for path in (table, dlq):
        if os.path.exists(path):
            os.remove(path)

    print("=== Run 1 (with a simulated transient failure) ===")
    log, result = run_sync(
        os.path.join(data, "asana_export.json"),
        os.path.join(data, "mapping-config.json"),
        table, fail_writes=1,
    )
    print(log)
    print(f"result: {result}")

    print("\n=== Run 2 (idempotent -- nothing new) ===")
    log2, result2 = run_sync(
        os.path.join(data, "asana_export.json"),
        os.path.join(data, "mapping-config.json"),
        table, fail_writes=0,
    )
    print(log2)
    print(f"result: {result2}")
    print(f"\nMock Excel table written to: {table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
