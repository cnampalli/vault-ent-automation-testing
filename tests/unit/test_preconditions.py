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
