import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from flow import PermanentError, RunLog, map_entries, run_sync, with_retry  # noqa: E402

DATA = os.path.join(os.path.dirname(HERE), "data")
SRC = os.path.join(DATA, "asana_export.json")
MAP = os.path.join(DATA, "mapping-config.json")


def _table():
    return os.path.join(tempfile.mkdtemp(), "table.json")


def test_field_mapping_and_approved_filter():
    entries = json.load(open(SRC))
    mapping = json.load(open(MAP))
    rows = map_entries(entries, mapping)
    assert len(rows) == 4
    r = rows[0]
    assert set(r) == {"EntryId", "Employee", "Date", "Project", "Hours",
                      "CostCenter", "Approved"}
    assert r["Employee"] == "Alex Kim"


def test_idempotent_dedupe():
    table = _table()
    _, r1 = run_sync(SRC, MAP, table, fail_writes=0)
    assert r1["added"] == 4
    _, r2 = run_sync(SRC, MAP, table, fail_writes=0)
    assert r2["added"] == 0 and r2["skipped"] == 4 and r2["total"] == 4


def test_retry_on_transient_failure_is_logged():
    table = _table()
    log, result = run_sync(SRC, MAP, table, fail_writes=1)
    text = str(log)
    assert "attempt 1 failed" in text
    assert "succeeded on attempt 2" in text
    assert result["added"] == 4


def test_retry_gives_up_and_raises():
    log = RunLog()
    def always_fail():
        raise RuntimeError("nope")
    try:
        with_retry(always_fail, log, attempts=2, label="x")
        assert False, "expected failure"
    except RuntimeError:
        assert "giving up after 2 attempts" in str(log)


def test_permanent_error_is_not_retried():
    log = RunLog()
    calls = {"n": 0}
    def perm_fail():
        calls["n"] += 1
        raise PermanentError("bad row")
    try:
        with_retry(perm_fail, log, attempts=3, label="x")
        assert False, "expected PermanentError"
    except PermanentError:
        assert calls["n"] == 1
        assert "permanent failure" in str(log)


def test_dlq_routes_permanently_failed_rows():
    tmp = tempfile.mkdtemp()
    table = os.path.join(tmp, "table.json")
    dlq = os.path.join(tmp, "dlq.json")
    log, result = run_sync(SRC, MAP, table, fail_writes=0,
                           permanent_fail_ids=["t1"], dlq_path=dlq)
    assert result["added"] == 3
    assert result["dlq_count"] == 1
    assert result["total"] == 3
    assert os.path.exists(dlq)
    rows = json.load(open(dlq))
    assert len(rows) == 1
    assert rows[0]["row"]["EntryId"] == "t1"
    assert rows[0]["reason"].startswith("permanent")
    assert "timestamp" in rows[0]
    assert "dlq: recorded 1 failed row" in str(log)


def test_dlq_run_still_succeeds_overall():
    tmp = tempfile.mkdtemp()
    table = os.path.join(tmp, "table.json")
    dlq = os.path.join(tmp, "dlq.json")
    _, result = run_sync(SRC, MAP, table, fail_writes=0,
                         permanent_fail_ids=["t1", "t2"], dlq_path=dlq)
    written = json.load(open(table))
    assert len(written) == 2
    assert {r["EntryId"] for r in written} == {"t3", "t5"}
    assert result["dlq_count"] == 2


def test_on_failure_raise_restores_old_behavior():
    tmp = tempfile.mkdtemp()
    table = os.path.join(tmp, "table.json")
    try:
        run_sync(SRC, MAP, table, permanent_fail_ids=["t1"],
                 on_failure="raise")
        assert False, "expected PermanentError"
    except PermanentError:
        assert not os.path.exists(table)


def test_dry_run_does_not_touch_table_or_dlq():
    tmp = tempfile.mkdtemp()
    table = os.path.join(tmp, "table.json")
    dlq = os.path.join(tmp, "dlq.json")
    log, result = run_sync(SRC, MAP, table, fail_writes=0,
                           permanent_fail_ids=["t1"], dlq_path=dlq,
                           dry_run=True)
    assert not os.path.exists(table)
    assert not os.path.exists(dlq)
    assert result["added"] == 3
    assert result["dlq_count"] == 1
    text = str(log)
    assert "[DRY RUN]" in text
    assert "[DRY RUN] wrote table" in text
    assert "[DRY RUN] dlq:" in text


def test_dry_run_preserves_existing_table():
    tmp = tempfile.mkdtemp()
    table = os.path.join(tmp, "table.json")
    run_sync(SRC, MAP, table, fail_writes=0)
    before = open(table).read()
    run_sync(SRC, MAP, table, fail_writes=0,
             permanent_fail_ids=["t1"], dry_run=True)
    after = open(table).read()
    assert before == after
