from lib.preconditions import missing_env, requires_env


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


def test_requires_env_marker_true_when_absent(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    marker = requires_env("MISSING_VAR")
    assert marker.mark.args[0] is True
    assert "MISSING_VAR" in marker.mark.kwargs["reason"]


def test_requires_env_marker_false_when_present(monkeypatch):
    monkeypatch.setenv("PRESENT_VAR", "value")
    marker = requires_env("PRESENT_VAR")
    assert marker.mark.args[0] is False
