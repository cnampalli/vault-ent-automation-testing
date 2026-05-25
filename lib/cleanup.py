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
