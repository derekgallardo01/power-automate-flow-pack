"""Offline simulator of the scheduled-sync Power Automate flow.

Proves the flow logic without a tenant: pull source records, apply a field map,
write rows to a mock "Excel table" (idempotent / deduped), with retry on a
transient failure and a run log — exactly the pattern the real flow implements.

Stdlib-only, deterministic.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class RunLog:
    steps: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.steps.append(msg)

    def __str__(self) -> str:
        return "\n".join(f"  • {s}" for s in self.steps)


def load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def map_entries(entries: list[dict], mapping: dict) -> list[dict]:
    """Apply the field map (target_column -> source_field) and filter approved."""
    rows = []
    for e in entries:
        if mapping.get("only_approved", True) and not e.get("approved", False):
            continue
        row = {col: e.get(src) for col, src in mapping["fields"].items()}
        rows.append(row)
    return rows


def with_retry(action, log: RunLog, attempts: int = 3, label: str = "action"):
    """Call action(); retry on exception up to `attempts`, logging each try."""
    last = None
    for i in range(1, attempts + 1):
        try:
            result = action()
            if i > 1:
                log.add(f"{label}: succeeded on attempt {i}")
            return result
        except Exception as ex:  # noqa: BLE001 - simulated transient failure
            last = ex
            log.add(f"{label}: attempt {i} failed ({ex}); retrying")
    log.add(f"{label}: giving up after {attempts} attempts")
    raise last


def write_table(rows: list[dict], table_path: str, key: str, log: RunLog) -> dict:
    """Idempotently upsert rows into a mock Excel table (JSON), deduped on `key`."""
    existing = load_json(table_path) if os.path.exists(table_path) else []
    by_key = {r[key]: r for r in existing}
    added = 0
    for r in rows:
        if r[key] not in by_key:
            by_key[r[key]] = r
            added += 1
    merged = list(by_key.values())
    os.makedirs(os.path.dirname(table_path), exist_ok=True)
    with open(table_path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
    log.add(f"wrote table: {added} new rows, {len(merged)} total "
            f"({len(rows) - added} duplicates skipped)")
    return {"added": added, "total": len(merged), "skipped": len(rows) - added}


def run_sync(source_path: str, mapping_path: str, table_path: str,
             fail_writes: int = 1) -> tuple[RunLog, dict]:
    """The scheduled-sync flow: trigger → pull → map → write (with retry) → log.

    `fail_writes` simulates that many transient write failures before success, to
    exercise the retry + run-log pattern.
    """
    log = RunLog()
    log.add("trigger: scheduled run started")
    entries = load_json(source_path)
    log.add(f"pull: {len(entries)} entries from source")
    mapping = load_json(mapping_path)
    rows = map_entries(entries, mapping)
    log.add(f"map: {len(rows)} approved rows after field mapping")

    state = {"n": 0}

    def write_action():
        state["n"] += 1
        if state["n"] <= fail_writes:
            raise RuntimeError("transient connector timeout")
        return write_table(rows, table_path, mapping["key"], log)

    result = with_retry(write_action, log, attempts=3, label="write to Excel table")
    log.add("notify: success notification sent")
    return log, result
