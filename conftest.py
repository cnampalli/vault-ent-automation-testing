import os
import pytest

from config.settings import Settings
from lib.vault_client import authenticate
from lib.naming import ephemeral_namespace_name
from lib.cleanup import destroy_namespace
from lib.reporting import format_summary

# ---- result aggregation (pure, unit-tested) -------------------------------

def aggregate_outcomes(records):
    """records: iterable of (area, outcome, reason). Returns area -> counts dict."""
    agg = {}
    for area, outcome, reason in records:
        row = agg.setdefault(area, {"passed": 0, "failed": 0, "skipped": 0, "reason": None})
        if outcome in row:
            row[outcome] += 1
        if outcome == "skipped" and reason and not row["reason"]:
            row["reason"] = reason
    # normalize reason text (strip pytest's "Skipped: " prefix) before returning
    for row in agg.values():
        if row["reason"]:
            row["reason"] = row["reason"].replace("Skipped: ", "").strip()
    return agg


# ---- collect area marker per test id --------------------------------------

_AREA_BY_ID = {}
_RECORDS = []


def pytest_collection_modifyitems(items):
    for item in items:
        marker = item.get_closest_marker("area")
        area = marker.args[0] if marker and marker.args else item.module.__name__.split(".")[-1]
        _AREA_BY_ID[item.nodeid] = area


def pytest_runtest_logreport(report):
    # record once per test: prefer the 'call' phase; capture setup-time skips too
    if report.when == "call" or (report.when == "setup" and report.skipped):
        area = _AREA_BY_ID.get(report.nodeid, "uncategorized")
        outcome = "passed" if report.passed else "failed" if report.failed else "skipped"
        reason = ""
        if report.skipped and isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
            reason = report.longrepr[2]
        _RECORDS.append((area, outcome, reason))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    agg = aggregate_outcomes(_RECORDS)
    terminalreporter.write_line("")
    terminalreporter.write_line(format_summary(agg))


# ---- session fixtures (live Vault; validated in CI) -----------------------

@pytest.fixture(scope="session")
def settings():
    return Settings.from_env()


@pytest.fixture(scope="session")
def admin_client(settings):
    """Scoped client logged into the parent namespace via JWT."""
    return authenticate(settings)


@pytest.fixture(scope="session")
def ephemeral_namespace(settings, admin_client):
    """Create automation/ci-test-<build-id>, yield its full path, tear it down after."""
    child = ephemeral_namespace_name()
    parent = settings.parent_namespace

    admin_client.namespace = parent
    admin_client.create_namespace(path=child)

    full = f"{parent}/{child}"
    try:
        yield full
    finally:
        destroy_namespace(admin_client, parent=parent, child=child)


@pytest.fixture()
def ns_client(settings, ephemeral_namespace, admin_client):
    """A client scoped to the ephemeral namespace for use inside tests."""
    admin_client.namespace = ephemeral_namespace
    return admin_client
