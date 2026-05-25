from unittest.mock import MagicMock
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


def test_continues_after_individual_disable_failure():
    vc = _client_with(
        mounts={"kv-first/": {"type": "kv"}, "kv-second/": {"type": "kv"}},
        auths={},
    )
    vc.hvac.sys.disable_secrets_engine.side_effect = [Exception("nope"), None]

    destroy_namespace(vc, parent="automation", child="ci-test-x")

    assert vc.hvac.sys.disable_secrets_engine.call_count == 2
    vc.hvac.sys.delete_namespace.assert_called_once_with(path="ci-test-x")
