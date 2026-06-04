import os
import warnings
from typing import Iterable

import pytest

from config.settings import Settings
from lib.vault_client import authenticate
from lib.naming import ephemeral_namespace_name
from lib.cleanup import destroy_namespace
from lib.reporting import format_summary

# ---- result aggregation (pure, unit-tested) -------------------------------

def aggregate_outcomes(
    records: Iterable[tuple[str, str, str | None]],
) -> dict[str, dict]:
    """records: iterable of (area, outcome, reason). Returns area -> counts dict."""
    agg: dict[str, dict] = {}
    for area, outcome, reason in records:
        row = agg.setdefault(area, {"passed": 0, "failed": 0, "skipped": 0, "reason": None})
        if outcome in row:
            row[outcome] += 1
        if outcome == "skipped" and reason and not row["reason"]:
            row["reason"] = reason
    # normalize reason text (strip pytest's "Skipped: " prefix) before returning
    for row in agg.values():
        if row["reason"]:
            row["reason"] = row["reason"].removeprefix("Skipped: ").strip()
    return agg


def parse_areas(raw: str | None) -> list[str]:
    """Parse a comma-separated AREAS string into normalized lowercase filters."""
    return [a.strip().lower() for a in (raw or "").split(",") if a.strip()]


def select_areas(
    area_by_id: dict[str, str | None],
    filters: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Given {nodeid: area} and lowercase filters, return (keep_ids, drop_ids, unmatched_filters).

    A test is kept if any filter is a case-insensitive substring of its area name.
    With no filters, everything is kept. unmatched_filters are filters that matched no area
    (likely typos), useful for warning the operator.

    Note for contributors: matching is substring-based, so when adding a new area name,
    check it does not unintentionally collide as a substring with an existing area name.
    """
    if not filters:
        return list(area_by_id.keys()), [], []
    keep, drop, matched = [], [], set()
    for nodeid, area in area_by_id.items():
        area_l = (area or "").lower()
        hit = next((f for f in filters if f in area_l), None)
        if hit:
            matched.add(hit)
            keep.append(nodeid)
        else:
            drop.append(nodeid)
    unmatched = [f for f in filters if f not in matched]
    return keep, drop, unmatched


# ---- collect area marker per test id --------------------------------------
# NOTE: the module-level state below is NOT pytest-xdist safe (each worker would
# get its own copy). Single-process runs only; revisit if xdist is ever added.
_AREA_BY_ID = {}
_OUTCOMES = {}  # nodeid -> (outcome, reason); one row per test, worst phase wins

_SEVERITY = {"passed": 0, "skipped": 1, "failed": 2}


def merge_outcome(old, new):
    """Pick the more severe of two (outcome, reason) tuples; on a tie keep the first.

    Severity order: failed > skipped > passed. This collapses a test's setup/call/teardown
    phases into a single row, so a setup or teardown error (e.g. Vault auth/TLS failure, or a
    namespace cleanup failure) surfaces as a failure instead of being dropped.
    """
    if old is None or _SEVERITY[new[0]] > _SEVERITY[old[0]]:
        return new
    return old


def collected_records():
    """Flatten the per-test outcomes into (area, outcome, reason) records for aggregation."""
    return [
        (_AREA_BY_ID.get(nodeid, "uncategorized"), outcome, reason)
        for nodeid, (outcome, reason) in _OUTCOMES.items()
    ]


def pytest_addoption(parser):
    parser.addoption(
        "--areas",
        action="store",
        default=None,
        help="Comma-separated area filters; run only tests whose area marker matches "
             "(case-insensitive substring). Also read from the AREAS environment variable.",
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        marker = item.get_closest_marker("area")
        if marker and marker.args:
            area = marker.args[0]
        else:
            area = item.module.__name__.split(".")[-1] if item.module else "uncategorized"
        _AREA_BY_ID[item.nodeid] = area

    raw = config.getoption("--areas") or os.environ.get("AREAS")
    filters = parse_areas(raw)
    if not filters:
        return

    keep_ids, _drop_ids, unmatched = select_areas(_AREA_BY_ID, filters)
    if not keep_ids:
        raise pytest.UsageError(
            f"AREAS={raw!r} selected no tests (unrecognised filters: {unmatched}). "
            f"Available areas: {sorted(set(_AREA_BY_ID.values()))}"
        )
    if unmatched:
        warnings.warn(
            f"AREAS filter(s) matched no area and were ignored: {unmatched}",
            stacklevel=1,
        )

    keep = set(keep_ids)
    deselected = [it for it in items if it.nodeid not in keep]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = [it for it in items if it.nodeid in keep]


def pytest_runtest_logreport(report):
    # Collapse every phase into one row per test. Crucially, setup/teardown FAILURES (errors in
    # fixtures -- Vault auth, TLS, namespace cleanup) are captured here; the old code only looked
    # at the 'call' phase and so silently dropped them from the summary.
    if report.when == "call":
        outcome = "passed" if report.passed else "failed" if report.failed else "skipped"
    elif report.skipped:            # setup-time skip
        outcome = "skipped"
    elif report.failed:             # setup or teardown error
        outcome = "failed"
    else:
        return                      # setup/teardown that passed -> nothing to record
    reason = ""
    if report.skipped and isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
        reason = report.longrepr[2]
    _OUTCOMES[report.nodeid] = merge_outcome(_OUTCOMES.get(report.nodeid), (outcome, reason))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    agg = aggregate_outcomes(collected_records())
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
    """A client scoped to the ephemeral namespace for the duration of one test.

    Snapshots and restores the shared session client's namespace so multiple
    tests using this fixture don't create a test-order dependency.
    """
    original = admin_client.namespace
    admin_client.namespace = ephemeral_namespace
    yield admin_client
    admin_client.namespace = original
