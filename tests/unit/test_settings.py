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
