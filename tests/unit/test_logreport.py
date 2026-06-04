import pytest
import conftest


class Rep:
    """Minimal stand-in for a pytest TestReport."""
    def __init__(self, nodeid, when, passed=False, failed=False, skipped=False, longrepr=None):
        self.nodeid = nodeid
        self.when = when
        self.passed = passed
        self.failed = failed
        self.skipped = skipped
        self.longrepr = longrepr


@pytest.fixture(autouse=True)
def _isolate_conftest_state():
    """Snapshot/restore conftest's module-level collectors so these tests don't pollute the
    live session summary."""
    outcomes, areas = dict(conftest._OUTCOMES), dict(conftest._AREA_BY_ID)
    conftest._OUTCOMES.clear()
    conftest._AREA_BY_ID.clear()
    yield
    conftest._OUTCOMES.clear(); conftest._OUTCOMES.update(outcomes)
    conftest._AREA_BY_ID.clear(); conftest._AREA_BY_ID.update(areas)


def test_setup_error_recorded_as_failed():
    # A fixture/setup failure (e.g. Vault TLS error) must surface as a failure, not vanish.
    conftest._AREA_BY_ID["kv::t"] = "KV v2"
    conftest.pytest_runtest_logreport(Rep("kv::t", "setup", failed=True))
    conftest.pytest_runtest_logreport(Rep("kv::t", "teardown", passed=True))
    assert ("KV v2", "failed", "") in conftest.collected_records()


def test_passing_test_recorded_once():
    conftest._AREA_BY_ID["u::t"] = "unit"
    conftest.pytest_runtest_logreport(Rep("u::t", "setup", passed=True))
    conftest.pytest_runtest_logreport(Rep("u::t", "call", passed=True))
    conftest.pytest_runtest_logreport(Rep("u::t", "teardown", passed=True))
    assert conftest.collected_records().count(("unit", "passed", "")) == 1


def test_teardown_error_overrides_pass():
    # Namespace cleanup failing in teardown is a real problem -> the test must read as failed.
    conftest._AREA_BY_ID["u::t"] = "KV v2"
    conftest.pytest_runtest_logreport(Rep("u::t", "call", passed=True))
    conftest.pytest_runtest_logreport(Rep("u::t", "teardown", failed=True))
    recs = conftest.collected_records()
    assert ("KV v2", "failed", "") in recs
    assert ("KV v2", "passed", "") not in recs


def test_setup_skip_recorded_with_reason():
    conftest._AREA_BY_ID["l::t"] = "LDAP"
    conftest.pytest_runtest_logreport(
        Rep("l::t", "setup", skipped=True, longrepr=("f", 1, "Skipped: no url")))
    assert conftest.collected_records() == [("LDAP", "skipped", "Skipped: no url")]


def test_merge_outcome_severity():
    assert conftest.merge_outcome(None, ("passed", "")) == ("passed", "")
    assert conftest.merge_outcome(("passed", ""), ("failed", "")) == ("failed", "")
    assert conftest.merge_outcome(("failed", ""), ("passed", "")) == ("failed", "")
    assert conftest.merge_outcome(("skipped", "a"), ("skipped", "b")) == ("skipped", "a")
