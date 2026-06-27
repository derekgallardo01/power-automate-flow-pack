import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from flow import RunLog, map_entries, run_sync, with_retry  # noqa: E402

DATA = os.path.join(os.path.dirname(HERE), "data")
SRC = os.path.join(DATA, "asana_export.json")
MAP = os.path.join(DATA, "mapping-config.json")


def _table():
    return os.path.join(tempfile.mkdtemp(), "table.json")


def test_field_mapping_and_approved_filter():
    import json
    entries = json.load(open(SRC))
    mapping = json.load(open(MAP))
    rows = map_entries(entries, mapping)
    # 4 of 5 entries are approved
    assert len(rows) == 4
    r = rows[0]
    assert set(r) == {"EntryId", "Employee", "Date", "Project", "Hours",
                      "CostCenter", "Approved"}
    assert r["Employee"] == "Alex Kim"


def test_idempotent_dedupe():
    table = _table()
    _, r1 = run_sync(SRC, MAP, table, fail_writes=0)
    assert r1["added"] == 4
    _, r2 = run_sync(SRC, MAP, table, fail_writes=0)  # second run
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
