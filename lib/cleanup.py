import logging

from lib.vault_client import VaultClient

_log = logging.getLogger(__name__)

_PROTECTED = {
    "system", "identity", "cubbyhole", "token",
    "ns_system", "ns_identity", "ns_token", "ns_cubbyhole",
}


def destroy_namespace(client: VaultClient, parent: str, child: str) -> None:
    """Best-effort: clear the child namespace's mounts/auth, then delete it.

    Always attempts the namespace delete even if listing/disabling fails.
    Swallowed errors are logged (WARNING for whole-list failures, DEBUG for
    individual mount/auth disable failures) so teardown problems are diagnosable
    in CI without making the build noisy in the happy path.
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
            except Exception as exc:
                _log.debug("cleanup: failed to disable secrets engine %s in %s: %s", path, full, exc)
    except Exception as exc:
        _log.warning("cleanup: failed to list secrets engines in %s: %s", full, exc)

    try:
        methods = client.hvac.sys.list_auth_methods()["data"]
        for path, info in methods.items():
            if info.get("type") in _PROTECTED:
                continue
            try:
                client.hvac.sys.disable_auth_method(path=path.rstrip("/"))
            except Exception as exc:
                _log.debug("cleanup: failed to disable auth method %s in %s: %s", path, full, exc)
    except Exception as exc:
        _log.warning("cleanup: failed to list auth methods in %s: %s", full, exc)

    client.namespace = parent
    client.hvac.sys.delete_namespace(path=child)
