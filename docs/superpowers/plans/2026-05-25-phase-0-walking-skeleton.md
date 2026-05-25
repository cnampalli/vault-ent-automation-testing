# Vault Ent Automation Suite — Phase 0 (Walking Skeleton) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a runnable Python/pytest functional-test harness that, in CloudBees CI, installs deps offline, logs into Vault Enterprise with a scoped JWT identity, creates and tears down an ephemeral namespace, runs one real KV v2 test inside it, and reports passed/failed/skipped three ways (JUnit XML, self-contained HTML, console summary).

**Architecture:** Pure, unit-testable helpers (`config`, `lib/*`) are built with TDD against mocks. The Vault-integration layer (session fixtures + the KV test) is validated by running against the real Enterprise cluster in CI — that end-to-end run is the whole point of Phase 0. A single `pytest` invocation produces all three report formats. A Jenkinsfile wires triggers, the air-gapped wheelhouse install, the scoped login, and result publishing.

**Tech Stack:** Python 3.11, pytest, pytest-html, hvac (Vault API client), PyJWT[crypto], cryptography; CloudBees CI (Jenkins declarative pipeline); Vault Enterprise (namespaces, JWT auth, KV v2).

---

## File Structure

| File | Responsibility |
|---|---|
| `requirements.txt` | Pinned dependency list for the offline wheelhouse + install. |
| `pyproject.toml` | pytest config, `area` marker registration, report flags. |
| `.gitignore` | Exclude `.venv/`, `reports/`, `wheelhouse/`, `__pycache__/`. |
| `config/settings.py` | Parse all runtime config from env vars into a frozen `Settings`. |
| `lib/naming.py` | Pure helper: derive a safe single-segment ephemeral namespace name. |
| `lib/vault_client.py` | Namespace-aware thin wrapper over `hvac` (login, namespace switch, ns CRUD). |
| `lib/preconditions.py` | `missing_env()` + `requires_env()` skip-gating for external-dep areas. |
| `lib/cleanup.py` | Best-effort recursive teardown of an ephemeral namespace. |
| `lib/reporting.py` | Pure `format_summary()` producing the grouped console block. |
| `conftest.py` | Session fixtures (scoped auth, ephemeral namespace) + terminal-summary plugin. |
| `tests/secrets/test_kv_v2.py` | The walking-skeleton functional test (write/read a secret). |
| `tests/unit/…` | Unit tests for the pure helpers (TDD). |
| `scripts/build-wheelhouse.sh` | One-time webhost step: download matching wheels. |
| `Jenkinsfile` | CI pipeline: triggers, offline setup, scoped login, test, publish. |
| `README.md` | How to run locally + the air-gapped install procedure. |

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`, `pyproject.toml`, `.gitignore`, `README.md`
- Create dirs: `config/`, `lib/`, `tests/unit/`, `tests/secrets/`, `reports/`, `scripts/`

- [ ] **Step 1: Initialize git**

Run:
```bash
cd /Users/cnampalli/Desktop/Projects/vault-ent-automation-testing
git init
```
Expected: `Initialized empty Git repository`.

- [ ] **Step 2: Create `requirements.txt`**

```
hvac==2.3.0
pytest==8.3.4
pytest-html==4.1.1
PyJWT[crypto]==2.10.1
cryptography==44.0.0
```
(If the webhost resolves different latest versions, pin to whatever it downloads — the wheelhouse is the lock.)

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = "-ra -q"
markers = [
    "area(name): functional area this test belongs to (used for the console summary)",
]

[tool.pytest.ini_options.env]
# placeholder section; env is provided by CI, not here
```

- [ ] **Step 4: Create `.gitignore`**

```
.venv/
reports/
wheelhouse/
wheelhouse.tar.gz
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 5: Create `README.md`**

```markdown
# Vault Enterprise Automation Test Suite

Functional tests for Vault Enterprise auth methods and secret engines, run in CloudBees CI
against a pre-existing cluster. The suite creates an ephemeral namespace per run, tests inside it,
and tears it down.

## Design
See `docs/superpowers/specs/2026-05-25-vault-ent-automation-testing-design.md`.

## Required environment variables
| Var | Meaning |
|---|---|
| `VAULT_ADDR` | Cluster URL |
| `CI_OIDC_TOKEN` | The CloudBees CI OIDC/JWT token presented at login |
| `VAULT_PARENT_NAMESPACE` | Delegated parent namespace (default `automation`) |
| `VAULT_JWT_MOUNT` | JWT auth mount path inside the parent ns (default `jwt`) |
| `VAULT_JWT_ROLE` | Scoped role name (default `test-runner`) |
| `STRICT_MODE` | `true` => missing external deps fail instead of skip (default `false`) |
| `BUILD_TAG` | CI build identifier (used to name the ephemeral namespace) |

## Air-gapped install
See "Offline wheelhouse" section below and `scripts/build-wheelhouse.sh`.
```

- [ ] **Step 6: Create empty package markers**

Run:
```bash
touch config/__init__.py lib/__init__.py tests/__init__.py tests/unit/__init__.py tests/secrets/__init__.py
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold vault ent automation test suite (phase 0)"
```

---

## Task 2: Config module (TDD)

**Files:**
- Create: `config/settings.py`
- Test: `tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_settings.py
import pytest
from config.settings import Settings


def test_from_env_parses_required_and_defaults(monkeypatch):
    monkeypatch.setenv("VAULT_ADDR", "https://vault.example:8200")
    monkeypatch.setenv("CI_OIDC_TOKEN", "tok123")
    monkeypatch.delenv("VAULT_PARENT_NAMESPACE", raising=False)
    monkeypatch.delenv("STRICT_MODE", raising=False)

    s = Settings.from_env()

    assert s.vault_addr == "https://vault.example:8200"
    assert s.ci_oidc_token == "tok123"
    assert s.parent_namespace == "automation"   # default
    assert s.jwt_mount == "jwt"                  # default
    assert s.jwt_role == "test-runner"           # default
    assert s.strict_mode is False                # default


def test_strict_mode_truthy(monkeypatch):
    monkeypatch.setenv("VAULT_ADDR", "x")
    monkeypatch.setenv("CI_OIDC_TOKEN", "y")
    monkeypatch.setenv("STRICT_MODE", "true")
    assert Settings.from_env().strict_mode is True


def test_missing_required_raises(monkeypatch):
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.setenv("CI_OIDC_TOKEN", "y")
    with pytest.raises(RuntimeError, match="VAULT_ADDR"):
        Settings.from_env()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config.settings'` (or import error).

- [ ] **Step 3: Write minimal implementation**

```python
# config/settings.py
import os
from dataclasses import dataclass


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return val


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    vault_addr: str
    ci_oidc_token: str
    parent_namespace: str
    jwt_mount: str
    jwt_role: str
    strict_mode: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            vault_addr=_require("VAULT_ADDR"),
            ci_oidc_token=_require("CI_OIDC_TOKEN"),
            parent_namespace=os.environ.get("VAULT_PARENT_NAMESPACE", "automation"),
            jwt_mount=os.environ.get("VAULT_JWT_MOUNT", "jwt"),
            jwt_role=os.environ.get("VAULT_JWT_ROLE", "test-runner"),
            strict_mode=_truthy(os.environ.get("STRICT_MODE")),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_settings.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add config/settings.py tests/unit/test_settings.py
git commit -m "feat: env-driven Settings config with defaults and validation"
```

---

## Task 3: Ephemeral namespace name helper (TDD)

**Files:**
- Create: `lib/naming.py`
- Test: `tests/unit/test_naming.py`

The scoped policy allows `sys/namespaces/ci-test-*` and `ci-test-+/...`, where `+` is a **single path
segment**. So the name MUST be `ci-test-<slug>` with no slashes and a bounded length.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_naming.py
import re
from lib.naming import ephemeral_namespace_name


def test_uses_build_tag_sanitized():
    name = ephemeral_namespace_name("jenkins-MyFolder/Vault Job #123")
    assert name.startswith("ci-test-")
    assert "/" not in name and " " not in name
    assert re.fullmatch(r"ci-test-[a-z0-9-]+", name)


def test_length_capped():
    name = ephemeral_namespace_name("x" * 200)
    assert len(name) <= 48  # "ci-test-" (8) + up to 40


def test_fallback_when_no_tag(monkeypatch):
    monkeypatch.delenv("BUILD_TAG", raising=False)
    name = ephemeral_namespace_name(None)
    assert name.startswith("ci-test-local-")


def test_reads_build_tag_env(monkeypatch):
    monkeypatch.setenv("BUILD_TAG", "build-42")
    assert ephemeral_namespace_name() == "ci-test-build-42"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_naming.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.naming'`.

- [ ] **Step 3: Write minimal implementation**

```python
# lib/naming.py
import os
import re
import uuid


def ephemeral_namespace_name(build_tag: str | None = None) -> str:
    raw = build_tag or os.environ.get("BUILD_TAG") or f"local-{uuid.uuid4().hex[:8]}"
    slug = re.sub(r"[^a-z0-9-]+", "-", raw.lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")[:40].strip("-")
    return f"ci-test-{slug}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_naming.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add lib/naming.py tests/unit/test_naming.py
git commit -m "feat: safe single-segment ephemeral namespace naming"
```

---

## Task 4: Namespace-aware Vault client wrapper (TDD with mocked hvac)

**Files:**
- Create: `lib/vault_client.py`
- Test: `tests/unit/test_vault_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_vault_client.py
from unittest.mock import MagicMock, patch
from lib.vault_client import VaultClient, authenticate
from config.settings import Settings


@patch("lib.vault_client.hvac.Client")
def test_jwt_login_sets_token(mock_client_cls):
    inner = MagicMock()
    inner.auth.jwt.jwt_login.return_value = {"auth": {"client_token": "s.scoped"}}
    mock_client_cls.return_value = inner

    vc = VaultClient(url="https://v:8200", namespace="automation")
    token = vc.jwt_login(role="test-runner", jwt="ci-tok", mount="jwt")

    assert token == "s.scoped"
    inner.auth.jwt.jwt_login.assert_called_once_with(role="test-runner", jwt="ci-tok", path="jwt")
    assert inner.token == "s.scoped"


@patch("lib.vault_client.hvac.Client")
def test_namespace_switch(mock_client_cls):
    inner = MagicMock()
    mock_client_cls.return_value = inner
    vc = VaultClient(url="https://v:8200", namespace="automation")
    vc.namespace = "automation/ci-test-x"
    assert inner.adapter.namespace == "automation/ci-test-x"


@patch("lib.vault_client.hvac.Client")
def test_authenticate_factory(mock_client_cls):
    inner = MagicMock()
    inner.auth.jwt.jwt_login.return_value = {"auth": {"client_token": "s.s"}}
    mock_client_cls.return_value = inner
    s = Settings(vault_addr="https://v:8200", ci_oidc_token="ci",
                 parent_namespace="automation", jwt_mount="jwt",
                 jwt_role="test-runner", strict_mode=False)
    vc = authenticate(s)
    mock_client_cls.assert_called_once_with(url="https://v:8200", namespace="automation", token=None)
    inner.auth.jwt.jwt_login.assert_called_once_with(role="test-runner", jwt="ci", path="jwt")
    assert vc.hvac is inner
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_vault_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.vault_client'`.

- [ ] **Step 3: Write minimal implementation**

```python
# lib/vault_client.py
import hvac
from config.settings import Settings


class VaultClient:
    """Thin, namespace-aware wrapper over hvac.Client."""

    def __init__(self, url: str, namespace: str | None = None, token: str | None = None):
        self._client = hvac.Client(url=url, namespace=namespace, token=token)

    @property
    def hvac(self) -> hvac.Client:
        return self._client

    @property
    def namespace(self) -> str | None:
        return self._client.adapter.namespace

    @namespace.setter
    def namespace(self, ns: str | None) -> None:
        self._client.adapter.namespace = ns

    def jwt_login(self, role: str, jwt: str, mount: str = "jwt") -> str:
        resp = self._client.auth.jwt.jwt_login(role=role, jwt=jwt, path=mount)
        token = resp["auth"]["client_token"]
        self._client.token = token
        return token

    def create_namespace(self, path: str):
        return self._client.sys.create_namespace(path=path)

    def delete_namespace(self, path: str):
        return self._client.sys.delete_namespace(path=path)


def authenticate(settings: Settings) -> VaultClient:
    client = VaultClient(url=settings.vault_addr, namespace=settings.parent_namespace, token=None)
    client.jwt_login(role=settings.jwt_role, jwt=settings.ci_oidc_token, mount=settings.jwt_mount)
    return client
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_vault_client.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add lib/vault_client.py tests/unit/test_vault_client.py
git commit -m "feat: namespace-aware hvac client wrapper + scoped JWT authenticate()"
```

---

## Task 5: Preconditions / skip-gating (TDD)

**Files:**
- Create: `lib/preconditions.py`
- Test: `tests/unit/test_preconditions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_preconditions.py
from lib.preconditions import missing_env


def test_missing_env_reports_absent(monkeypatch):
    monkeypatch.delenv("LDAP_URL", raising=False)
    monkeypatch.setenv("LDAP_BINDDN", "cn=admin")
    assert missing_env("LDAP_URL", "LDAP_BINDDN") == ["LDAP_URL"]


def test_missing_env_empty_when_all_present(monkeypatch):
    monkeypatch.setenv("DB_URL", "postgres://x")
    assert missing_env("DB_URL") == []


def test_missing_env_treats_blank_as_absent(monkeypatch):
    monkeypatch.setenv("VENAFI_URL", "   ")
    assert missing_env("VENAFI_URL") == ["VENAFI_URL"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_preconditions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.preconditions'`.

- [ ] **Step 3: Write minimal implementation**

```python
# lib/preconditions.py
import os
import pytest


def missing_env(*env_vars: str) -> list[str]:
    """Return the env vars that are unset or blank."""
    return [v for v in env_vars if not (os.environ.get(v) or "").strip()]


def requires_env(*env_vars: str):
    """pytest marker: skip the test when any required env var is missing.

    In STRICT_MODE the suite-level conftest converts skips to failures; here we
    always express the dependency as a skipif so non-strict runs stay green.
    """
    absent = missing_env(*env_vars)
    return pytest.mark.skipif(
        bool(absent),
        reason=f"missing required env: {', '.join(absent)}" if absent else "",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_preconditions.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add lib/preconditions.py tests/unit/test_preconditions.py
git commit -m "feat: precondition skip-gating for external-dependency areas"
```

---

## Task 6: Recursive namespace teardown (TDD with mocked client)

**Files:**
- Create: `lib/cleanup.py`
- Test: `tests/unit/test_cleanup.py`

Vault refuses to delete a non-empty namespace, so we must disable secret engines and auth methods
(which also revokes their leases) **before** deleting the namespace.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cleanup.py
from unittest.mock import MagicMock, call
from lib.cleanup import destroy_namespace
from lib.vault_client import VaultClient


def _client_with(mounts, auths):
    vc = MagicMock(spec=VaultClient)
    vc.hvac = MagicMock()
    vc.hvac.sys.list_mounted_secrets_engines.return_value = {"data": mounts}
    vc.hvac.sys.list_auth_methods.return_value = {"data": auths}
    return vc


def test_disables_user_mounts_and_auth_then_deletes():
    vc = _client_with(
        mounts={"kv-abc/": {"type": "kv"}, "cubbyhole/": {"type": "cubbyhole"},
                "sys/": {"type": "system"}, "identity/": {"type": "identity"}},
        auths={"approle-x/": {"type": "approle"}, "token/": {"type": "token"}},
    )

    destroy_namespace(vc, parent="automation", child="ci-test-x")

    vc.hvac.sys.disable_secrets_engine.assert_called_once_with(path="kv-abc")
    vc.hvac.sys.disable_auth_method.assert_called_once_with(path="approle-x")
    vc.hvac.sys.delete_namespace.assert_called_once_with(path="ci-test-x")
    # namespace was set to the child for cleanup, then back to parent for delete
    assert vc.namespace == "automation"


def test_delete_runs_even_if_listing_fails():
    vc = MagicMock(spec=VaultClient)
    vc.hvac = MagicMock()
    vc.hvac.sys.list_mounted_secrets_engines.side_effect = Exception("boom")
    vc.hvac.sys.list_auth_methods.side_effect = Exception("boom")

    destroy_namespace(vc, parent="automation", child="ci-test-x")

    vc.hvac.sys.delete_namespace.assert_called_once_with(path="ci-test-x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_cleanup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.cleanup'`.

- [ ] **Step 3: Write minimal implementation**

```python
# lib/cleanup.py
from lib.vault_client import VaultClient

_PROTECTED = {"system", "identity", "cubbyhole", "token", "ns_system", "ns_identity", "ns_token"}


def destroy_namespace(client: VaultClient, parent: str, child: str) -> None:
    """Best-effort: clear the child namespace's mounts/auth, then delete it.

    Always attempts the namespace delete even if listing/disabling fails.
    """
    full = f"{parent}/{child}"

    client.namespace = full
    try:
        mounts = client.hvac.sys.list_mounted_secrets_engines()["data"]
        for path, info in mounts.items():
            if info.get("type") in _PROTECTED:
                continue
            try:
                client.hvac.sys.disable_secrets_engine(path=path.rstrip("/"))
            except Exception:
                pass
    except Exception:
        pass

    try:
        methods = client.hvac.sys.list_auth_methods()["data"]
        for path, info in methods.items():
            if info.get("type") in _PROTECTED:
                continue
            try:
                client.hvac.sys.disable_auth_method(path=path.rstrip("/"))
            except Exception:
                pass
    except Exception:
        pass

    client.namespace = parent
    client.hvac.sys.delete_namespace(path=child)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_cleanup.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add lib/cleanup.py tests/unit/test_cleanup.py
git commit -m "feat: best-effort recursive ephemeral-namespace teardown"
```

---

## Task 7: Console summary formatter (TDD)

**Files:**
- Create: `lib/reporting.py`
- Test: `tests/unit/test_reporting.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_reporting.py
from lib.reporting import format_summary


def test_format_summary_renders_counts_and_total():
    results = {
        "KV v2": {"passed": 3, "failed": 0, "skipped": 0, "reason": None},
        "LDAP": {"passed": 0, "failed": 0, "skipped": 2, "reason": "LDAP_URL not set"},
        "Transit": {"passed": 2, "failed": 1, "skipped": 0, "reason": None},
    }
    out = format_summary(results)

    assert "Vault Ent Functional Suite" in out
    assert "KV v2" in out and "3 passed" in out
    assert "SKIPPED (LDAP_URL not set)" in out
    assert "Transit" in out and "2 passed, 1 failed" in out
    assert "TOTAL: 5 passed, 1 failed, 2 skipped" in out


def test_empty_results():
    out = format_summary({})
    assert "TOTAL: 0 passed, 0 failed, 0 skipped" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_reporting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.reporting'`.

- [ ] **Step 3: Write minimal implementation**

```python
# lib/reporting.py
HEADER = "===== Vault Ent Functional Suite ====="


def _area_line(area: str, r: dict) -> str:
    passed, failed, skipped = r.get("passed", 0), r.get("failed", 0), r.get("skipped", 0)
    if skipped and not passed and not failed:
        status = f"SKIPPED ({r.get('reason') or 'precondition not met'})"
    else:
        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if failed:
            parts.append(f"{failed} failed")
        if skipped:
            parts.append(f"{skipped} skipped")
        status = ", ".join(parts) or "0 passed"
    dots = "." * max(2, 22 - len(area))
    return f"{area} {dots} {status}"


def format_summary(area_results: dict) -> str:
    lines = [HEADER]
    totals = {"passed": 0, "failed": 0, "skipped": 0}
    for area, r in area_results.items():
        for k in totals:
            totals[k] += r.get(k, 0)
        lines.append(_area_line(area, r))
    lines.append("-" * len(HEADER))
    lines.append(
        f"TOTAL: {totals['passed']} passed, {totals['failed']} failed, {totals['skipped']} skipped"
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_reporting.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add lib/reporting.py tests/unit/test_reporting.py
git commit -m "feat: grouped console summary formatter"
```

---

## Task 8: conftest — fixtures + terminal-summary plugin

**Files:**
- Create: `conftest.py`
- Test (unit, for the aggregation helper): `tests/unit/test_summary_aggregation.py`

The session fixtures talk to live Vault (validated in CI). The result-aggregation logic that feeds
`format_summary` is factored into a pure function so it can be unit-tested without Vault.

- [ ] **Step 1: Write the failing test for the aggregation helper**

```python
# tests/unit/test_summary_aggregation.py
from conftest import aggregate_outcomes


def test_aggregate_groups_by_area():
    # (area, outcome, reason)
    records = [
        ("KV v2", "passed", None),
        ("KV v2", "passed", None),
        ("LDAP", "skipped", "LDAP_URL not set"),
        ("Transit", "failed", None),
    ]
    agg = aggregate_outcomes(records)
    assert agg["KV v2"]["passed"] == 2
    assert agg["LDAP"]["skipped"] == 1
    assert agg["LDAP"]["reason"] == "LDAP_URL not set"
    assert agg["Transit"]["failed"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_summary_aggregation.py -v`
Expected: FAIL — `ImportError: cannot import name 'aggregate_outcomes' from 'conftest'`.

- [ ] **Step 3: Write `conftest.py`**

```python
# conftest.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_summary_aggregation.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run the full unit suite to confirm nothing regressed**

Run: `pytest tests/unit -v`
Expected: PASS (all unit tests green); the terminal summary block prints at the end.

- [ ] **Step 6: Commit**

```bash
git add conftest.py tests/unit/test_summary_aggregation.py
git commit -m "feat: session fixtures + terminal-summary plugin with area grouping"
```

---

## Task 9: Walking-skeleton KV v2 test (live Vault — validated in CI)

**Files:**
- Create: `tests/secrets/test_kv_v2.py`

This is an integration test against the real cluster; it cannot fail-first locally without Vault
Enterprise. It is the proof that the whole loop (login → namespace → engine → I/O → teardown) works.

- [ ] **Step 1: Write the test**

```python
# tests/secrets/test_kv_v2.py
import uuid
import pytest

pytestmark = pytest.mark.area("KV v2")


def test_kv_v2_write_then_read(ns_client):
    mount = f"kv-{uuid.uuid4().hex[:8]}"
    ns_client.hvac.sys.enable_secrets_engine(
        backend_type="kv", path=mount, options={"version": "2"}
    )

    ns_client.hvac.secrets.kv.v2.create_or_update_secret(
        path="smoke", secret={"hello": "world"}, mount_point=mount
    )
    read = ns_client.hvac.secrets.kv.v2.read_secret_version(
        path="smoke", mount_point=mount
    )

    assert read["data"]["data"] == {"hello": "world"}
```

- [ ] **Step 2: (Local optional) Confirm it is collected and skips cleanly without Vault**

Run: `pytest tests/secrets/test_kv_v2.py -v`
Expected (no `VAULT_ADDR`/`CI_OIDC_TOKEN` set locally): the `settings` fixture raises and the test
**errors/skips** — that is acceptable locally. Real verification happens in CI (Task 12).

- [ ] **Step 3: Commit**

```bash
git add tests/secrets/test_kv_v2.py
git commit -m "test: walking-skeleton KV v2 write/read inside ephemeral namespace"
```

---

## Task 10: Webhost wheelhouse build script

**Files:**
- Create: `scripts/build-wheelhouse.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Run on the INTERNET-CONNECTED webhost. Produces wheelhouse.tar.gz to publish for the air-gapped agent.
# Usage: ./scripts/build-wheelhouse.sh [PYVER] [ABI] [PLATFORM]
#   defaults match a typical CloudBees Linux agent on CPython 3.11 x86_64.
set -euo pipefail

PYVER="${1:-311}"
ABI="${2:-cp311}"
PLATFORM="${3:-manylinux2014_x86_64}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

rm -rf "$HERE/wheelhouse" && mkdir -p "$HERE/wheelhouse"

# Try a plain download first (works when this host matches the agent platform);
# fall back to forcing the agent's platform for the compiled 'cryptography' wheel.
if ! pip download -r "$HERE/requirements.txt" -d "$HERE/wheelhouse"; then
  pip download -r "$HERE/requirements.txt" -d "$HERE/wheelhouse" \
    --only-binary=:all: --implementation cp \
    --python-version "$PYVER" --abi "$ABI" --platform "$PLATFORM"
fi

tar czf "$HERE/wheelhouse.tar.gz" -C "$HERE" wheelhouse
echo "Created $HERE/wheelhouse.tar.gz -- publish this on the webhost HTTP path."
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x scripts/build-wheelhouse.sh
git add scripts/build-wheelhouse.sh
git commit -m "build: webhost wheelhouse builder for air-gapped install"
```

---

## Task 11: Jenkinsfile

**Files:**
- Create: `Jenkinsfile`

- [ ] **Step 1: Write the Jenkinsfile**

```groovy
pipeline {
  agent any

  triggers {
    // PR/merge handled by webhook (SCM) + nightly drift check
    cron('H 2 * * *')
  }

  parameters {
    string(name: 'VAULT_ADDR_OVERRIDE', defaultValue: '', description: 'Override VAULT_ADDR')
    booleanParam(name: 'STRICT_MODE', defaultValue: false, description: 'Fail (not skip) on missing external deps')
    string(name: 'VENV_DIR', defaultValue: '/opt/vault-ent-suite/venv', description: 'Path to the pre-provisioned venv on the agent')
    string(name: 'AREAS', defaultValue: '', description: 'Comma-separated area filter (case-insensitive substring); empty = all')
  }

  environment {
    VAULT_ADDR            = "${params.VAULT_ADDR_OVERRIDE ?: env.VAULT_ADDR}"
    STRICT_MODE           = "${params.STRICT_MODE}"
    VAULT_PARENT_NAMESPACE = 'automation'
    VAULT_JWT_MOUNT       = 'jwt'
    VAULT_JWT_ROLE        = 'test-runner'
    // CI_OIDC_TOKEN is injected by the platform's OIDC step/credential (open item in spec §3)
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Setup') {
      steps {
        sh '''
          set -e
          # Verify the pre-provisioned venv exists (provisioned once via scripts/provision-agent.sh)
          test -f "${VENV_DIR}/bin/activate" || { echo "ERROR: venv not found at ${VENV_DIR}"; exit 1; }
          . "${VENV_DIR}/bin/activate"
          python -c "import hvac, jwt, cryptography, pytest; print('deps OK')"
        '''
      }
    }

    stage('Test') {
      steps {
        sh '''
          set -e
          . "${VENV_DIR}/bin/activate"
          mkdir -p reports
          pytest \
            ${AREAS:+--areas "$AREAS"} \
            --junitxml=reports/junit.xml \
            --html=reports/report.html --self-contained-html
        '''
      }
    }
  }

  post {
    always {
      junit allowEmptyResults: false, testResults: 'reports/junit.xml'
      archiveArtifacts artifacts: 'reports/report.html', allowEmptyArchive: true
      // Optional in-UI HTML (requires HTML Publisher plugin):
      // publishHTML(target: [reportDir: 'reports', reportFiles: 'report.html', reportName: 'Vault Suite'])
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add Jenkinsfile
git commit -m "ci: CloudBees pipeline with offline setup, scoped test run, and result publishing"
```

---

## Task 12: End-to-end validation in CloudBCI (user-driven)

This task is run by the user (CI access + back-end is the source of truth; output is not shared back).

- [ ] **Step 1: One-time admin setup on the cluster**

Apply the §4 commands from the spec: create `automation` namespace, write the `test-runner` policy,
enable the JWT auth mount inside `automation`, and create the `test-runner` role bound to the pipeline
claim (open item A — substitute the real claim name/value).

- [ ] **Step 2: Build the wheelhouse on the webhost and provision the agent**

On the internet-connected webhost, run `scripts/build-wheelhouse.sh` (pass the agent's PYVER/ABI/PLATFORM
if they differ from defaults) to produce `wheelhouse.tar.gz`. Transfer and extract the bundle onto the CI
agent, then run the one-time provisioning step:

```bash
# On the CI agent (once, or whenever dependencies change):
WHEELHOUSE_DIR=/path/to/extracted/wheelhouse \
VENV_DIR=/opt/vault-ent-suite/venv \
bash scripts/provision-agent.sh
```

This wipes and recreates the stable venv, installs from the pinned `requirements.txt` using the local
wheelhouse, and runs `pip check`. Set the Jenkins `VENV_DIR` parameter to match `VENV_DIR` above
(default `/opt/vault-ent-suite/venv`). The pipeline performs **no install** at build time.

- [ ] **Step 3: Confirm the agent toolchain**

On the CI agent: `python3 --version` (matches the wheelhouse) and `uname -s -m`. Confirm
`${VENV_DIR}/bin/activate` exists after provisioning.

- [ ] **Step 4: Run the pipeline**

Trigger the job with `VENV_DIR` set to the provisioned venv path. Optionally set `AREAS=KV v2` to
run only the walking-skeleton test. Expected build result: the **Setup** stage verifies the venv and
smoke-checks imports; the **Test** stage runs, JUnit shows **1 passed** (the KV test) with
**0 failed**, the HTML report is archived, and the console log shows the summary block:
```
KV v2 ................ 1 passed
--------------------------------------
TOTAL: 1 passed, 0 failed, 0 skipped
```

- [ ] **Step 5: Confirm teardown**

Verify the `automation/ci-test-<build-id>` namespace no longer exists after the run
(`vault namespace list -namespace=automation`). Report any deviation back; the suite's inputs are
taken as truth.

---

---

## Post-Plan Enhancements (landed after original task list)

Two improvements were implemented beyond the original Phase 0 scope:

1. **Pre-provisioned agent model** (`scripts/provision-agent.sh` + slimmed Jenkinsfile): instead of
   fetching and installing the wheelhouse tarball on every build via a `WHEELHOUSE_URL` parameter,
   the agent is provisioned once (or on dependency change) into a stable venv at `VENV_DIR`
   (default `/opt/vault-ent-suite/venv`). The Jenkinsfile Setup stage now verifies the venv exists,
   activates it, and smoke-checks imports — no per-build install.

2. **AREAS selection** (`--areas` CLI option + `AREAS` Jenkins parameter): implemented in
   `conftest.py` via `parse_areas`/`select_areas`. Passing a comma-separated list runs only tests
   whose `area` marker matches (case-insensitive substring); empty means all. An all-miss filter
   fails fast with a `UsageError` listing available areas. Reflects the `AREAS` parameter added to
   the Jenkinsfile in Task 11.

---

## Self-Review

**Spec coverage (Phase 0 scope):**
- §3 config / env → Task 2 ✅
- §4 scoped JWT login → Task 4 + Task 8 fixtures ✅; admin setup → Task 12 ✅
- §4 ephemeral namespace + teardown → Task 3, Task 6, Task 8 ✅
- §6 KV v2 (no-dep) walking-skeleton → Task 9 ✅
- §7 three report formats → Task 7 (console), Task 8 (hook), Task 11 (JUnit + HTML) ✅
- §8 air-gapped wheelhouse → Task 10 + Task 11 Setup stage + Task 12 ✅
- §9 Jenkinsfile triggers/stages/publish → Task 11 ✅
- §10 Phase 0 = walking skeleton → entire plan ✅
- Out of Phase 0 (deferred to later plans): full auth-method/secret-engine coverage, precondition-gated
  areas beyond the `requires_env` primitive (built in Task 5, exercised in Phase 2), deep
  lifecycle/policy depth. `lib/preconditions.py` is built now so Phase 1/2 can use it immediately.

**Placeholder scan:** No TBD/TODO. `WEBHOST`/claim values are explicit user-supplied parameters tracked
as open items in spec §3, not plan placeholders.

**Type consistency:** `VaultClient(.hvac, .namespace, jwt_login, create_namespace, delete_namespace)`,
`authenticate(settings)`, `destroy_namespace(client, parent, child)`, `missing_env(*vars)`,
`format_summary(area_results)`, `aggregate_outcomes(records)` — names/signatures match across Tasks 4,
6, 7, 8, 9.

**Note on TDD boundary:** pure helpers (Tasks 2–8) are strict red→green TDD with mocks. The live-Vault
integration (Task 9 + fixtures) is validated by the CI run in Task 12, consistent with the spec's
"the suite is the validation" constraint.
```