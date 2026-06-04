import pytest
from config.settings import Settings


def test_from_env_parses_required_and_defaults(monkeypatch):
    monkeypatch.setenv("VAULT_ADDR", "https://vault.example:8200")
    monkeypatch.setenv("CI_OIDC_TOKEN", "tok123")
    # Clear every optional var this test asserts a default for, so an ambient CI value
    # (e.g. VAULT_JWT_MOUNT=jwt-jenkins-ci on the agent) can't leak in and fail the assertion.
    for var in ("VAULT_PARENT_NAMESPACE", "STRICT_MODE", "VAULT_JWT_MOUNT",
                "VAULT_JWT_ROLE", "VAULT_CACERT", "VAULT_SKIP_VERIFY"):
        monkeypatch.delenv(var, raising=False)

    s = Settings.from_env()

    assert s.vault_addr == "https://vault.example:8200"
    assert s.ci_oidc_token == "tok123"
    assert s.parent_namespace == "automation"   # default
    assert s.jwt_mount == "jwt"                  # default
    assert s.jwt_role == "test-runner"           # default
    assert s.strict_mode is False                # default
    assert s.vault_cacert is None                # default
    assert s.vault_skip_verify is False          # default
    assert s.tls_verify() is True                # default: verify with system trust store


def test_from_env_tls_options(monkeypatch):
    monkeypatch.setenv("VAULT_ADDR", "x")
    monkeypatch.setenv("CI_OIDC_TOKEN", "y")
    monkeypatch.setenv("VAULT_CACERT", "/etc/ssl/vault-ca.pem")
    monkeypatch.setenv("VAULT_SKIP_VERIFY", "true")
    s = Settings.from_env()
    assert s.vault_cacert == "/etc/ssl/vault-ca.pem"
    assert s.vault_skip_verify is True


@pytest.mark.parametrize("cacert,skip,expected", [
    (None, False, True),                                       # default: verify
    (None, True, False),                                       # explicit skip
    ("/etc/ssl/vault-ca.pem", False, "/etc/ssl/vault-ca.pem"),  # CA bundle path
    ("/etc/ssl/vault-ca.pem", True, "/etc/ssl/vault-ca.pem"),   # CA bundle wins over skip
])
def test_tls_verify_resolution(cacert, skip, expected):
    s = Settings(vault_addr="x", ci_oidc_token="y", parent_namespace="automation",
                 jwt_mount="jwt", jwt_role="test-runner", strict_mode=False,
                 vault_cacert=cacert, vault_skip_verify=skip)
    assert s.tls_verify() == expected


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


@pytest.mark.parametrize("val", ["1", "true", "yes", "on", "TRUE", "YES"])
def test_strict_mode_truthy_variants(monkeypatch, val):
    monkeypatch.setenv("VAULT_ADDR", "x")
    monkeypatch.setenv("CI_OIDC_TOKEN", "y")
    monkeypatch.setenv("STRICT_MODE", val)
    assert Settings.from_env().strict_mode is True


@pytest.mark.parametrize("missing,present", [("VAULT_ADDR", "CI_OIDC_TOKEN"), ("CI_OIDC_TOKEN", "VAULT_ADDR")])
def test_each_required_var_raises_with_its_name(monkeypatch, missing, present):
    monkeypatch.delenv(missing, raising=False)
    monkeypatch.setenv(present, "value")
    with pytest.raises(RuntimeError, match=missing):
        Settings.from_env()


def test_whitespace_required_var_raises(monkeypatch):
    monkeypatch.setenv("VAULT_ADDR", "   ")
    monkeypatch.setenv("CI_OIDC_TOKEN", "y")
    with pytest.raises(RuntimeError, match="VAULT_ADDR"):
        Settings.from_env()
