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
    mock_client_cls.assert_called_once_with(
        url="https://v:8200", namespace="automation", token=None, verify=True)
    inner.auth.jwt.jwt_login.assert_called_once_with(role="test-runner", jwt="ci", path="jwt")
    assert vc.hvac is inner


@patch("lib.vault_client.hvac.Client")
def test_authenticate_passes_tls_verify(mock_client_cls):
    inner = MagicMock()
    inner.auth.jwt.jwt_login.return_value = {"auth": {"client_token": "s.s"}}
    mock_client_cls.return_value = inner
    s = Settings(vault_addr="https://v:8200", ci_oidc_token="ci",
                 parent_namespace="automation", jwt_mount="jwt",
                 jwt_role="test-runner", strict_mode=False,
                 vault_cacert="/etc/ssl/vault-ca.pem")
    authenticate(s)
    assert mock_client_cls.call_args.kwargs["verify"] == "/etc/ssl/vault-ca.pem"


@patch("lib.vault_client.hvac.Client")
def test_vault_client_forwards_verify(mock_client_cls):
    mock_client_cls.return_value = MagicMock()
    VaultClient(url="https://v:8200", verify=False)
    assert mock_client_cls.call_args.kwargs["verify"] is False
