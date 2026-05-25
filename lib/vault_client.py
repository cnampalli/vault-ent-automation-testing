import hvac
from typing import Any
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

    def create_namespace(self, path: str) -> Any:
        return self._client.sys.create_namespace(path=path)

    def delete_namespace(self, path: str) -> Any:
        return self._client.sys.delete_namespace(path=path)


def authenticate(settings: Settings) -> VaultClient:
    client = VaultClient(url=settings.vault_addr, namespace=settings.parent_namespace, token=None)
    client.jwt_login(role=settings.jwt_role, jwt=settings.ci_oidc_token, mount=settings.jwt_mount)
    return client
