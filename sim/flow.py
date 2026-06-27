"""Offline simulator of the scheduled-sync Power Automate flow.

Proves the flow logic without a tenant: pull source records, apply a field map,
write rows to a mock "Excel table" (idempotent / deduped), with retry on
transient failures, a dead-letter queue for permanent failures, dry-run mode,
and a run log -- exactly the pattern the real flow implements.

Stdlib-only, deterministic.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone


class PermanentError(Exception):
    """Non-retryable failure: row is bad, connector rejected it for cause."""


@dataclass
class RunLog:
    steps: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.steps.append(msg)

    def __str__(self) -> str:
        return "\n".join(f"  - {s}" for s in self.steps)


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
    """Call action(); retry on transient exceptions up to `attempts`.

    `PermanentError` is not retried -- it propagates immediately so the caller
    can route the row to the DLQ.
    """
    last = None
    for i in range(1, attempts + 1):
        try:
            result = action()
            if i > 1:
                log.add(f"{label}: succeeded on attempt {i}")
            return result
        except PermanentError as ex:
            log.add(f"{label}: permanent failure ({ex}); not retrying")
            raise
        except Exception as ex:  # noqa: BLE001 - treated as transient
            last = ex
            log.add(f"{label}: attempt {i} failed ({ex}); retrying")
    log.add(f"{label}: giving up after {attempts} attempts")
    raise last


def write_table(rows: list[dict], table_path: str, key: str, log: RunLog,
                dry_run: bool = False) -> dict:
    """Idempotently upsert rows into a mock Excel table (JSON), deduped on `key`."""
    existing = load_json(table_path) if os.path.exists(table_path) else []
    by_key = {r[key]: r for r in existing}
    added = 0
    for r in rows:
        if r[key] not in by_key:
            by_key[r[key]] = r
            added += 1
    merged = list(by_key.values())
    if dry_run:
        log.add(f"[DRY RUN] wrote table: {added} new rows, {len(merged)} total "
                f"({len(rows) - added} duplicates skipped)")
    else:
        os.makedirs(os.path.dirname(table_path) or ".", exist_ok=True)
        with open(table_path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
        log.add(f"wrote table: {added} new rows, {len(merged)} total "
                f"({len(rows) - added} duplicates skipped)")
    return {"added": added, "total": len(merged), "skipped": len(rows) - added}


def write_dlq(failed: list[dict], dlq_path: str, log: RunLog,
              dry_run: bool = False) -> int:
    """Append failed rows to the DLQ file with a reason + UTC timestamp."""
    if not failed:
        return 0
    existing = load_json(dlq_path) if os.path.exists(dlq_path) else []
    existing.extend(failed)
    if dry_run:
        log.add(f"[DRY RUN] dlq: would record {len(failed)} failed row(s) "
                f"({len(existing)} total in DLQ)")
    else:
        os.makedirs(os.path.dirname(dlq_path) or ".", exist_ok=True)
        with open(dlq_path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)
        log.add(f"dlq: recorded {len(failed)} failed row(s) for review "
                f"({len(existing)} total in DLQ)")
    return len(failed)


def run_sync(source_path: str, mapping_path: str, table_path: str,
             fail_writes: int = 0, dry_run: bool = False,
             on_failure: str = "dlq",
             dlq_path: str | None = None,
             permanent_fail_ids: list[str] | None = None
             ) -> tuple[RunLog, dict]:
    """The scheduled-sync flow: trigger -> pull -> map -> write (with retry) -> log.

    `fail_writes` simulates that many transient write failures before success,
    exercising the retry + run-log pattern.

    `permanent_fail_ids` simulates the connector rejecting specific row ids as
    permanent failures -- those rows land in the DLQ instead of aborting the run
    (when `on_failure="dlq"`, the default).

    `on_failure="raise"` restores the pre-DLQ behaviour: a permanent failure
    aborts the whole run. Use this in tests that want to assert on the raise.

    `dry_run=True` performs every step except the actual writes; the run log
    marks the would-be writes with `[DRY RUN]`.
    """
    if on_failure not in ("dlq", "raise"):
        raise ValueError(f"on_failure must be 'dlq' or 'raise', got {on_failure!r}")

    if dlq_path is None:
        dlq_path = os.path.join(os.path.dirname(table_path) or ".", "dlq.json")

    log = RunLog()
    log.add("trigger: scheduled run started" + (" [DRY RUN]" if dry_run else ""))
    entries = load_json(source_path)
    log.add(f"pull: {len(entries)} entries from source")
    mapping = load_json(mapping_path)
    rows = map_entries(entries, mapping)
    log.add(f"map: {len(rows)} approved rows after field mapping")

    key = mapping["key"]
    bad_ids = set(permanent_fail_ids or [])
    good_rows = [r for r in rows if r[key] not in bad_ids]
    failed_rows = [
        {
            "row": r,
            "reason": "permanent: connector rejected row",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for r in rows if r[key] in bad_ids
    ]

    if failed_rows and on_failure == "raise":
        raise PermanentError(
            f"{len(failed_rows)} row(s) permanently failed and on_failure='raise'"
        )

    state = {"n": 0}

    def write_action():
        state["n"] += 1
        if state["n"] <= fail_writes:
            raise RuntimeError("transient connector timeout")
        return write_table(good_rows, table_path, key, log, dry_run=dry_run)

    result = with_retry(write_action, log, attempts=3, label="write to Excel table")

    dlq_count = write_dlq(failed_rows, dlq_path, log, dry_run=dry_run)
    result["dlq_count"] = dlq_count
    log.add("notify: success notification sent")
    return log, result
