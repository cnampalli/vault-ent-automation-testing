import os
from dataclasses import dataclass


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not (val and val.strip()):
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
    # TLS trust config (mirrors the Vault CLI's VAULT_CACERT / VAULT_SKIP_VERIFY).
    vault_cacert: str | None = None
    vault_skip_verify: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            vault_addr=_require("VAULT_ADDR"),
            ci_oidc_token=_require("CI_OIDC_TOKEN"),
            parent_namespace=os.environ.get("VAULT_PARENT_NAMESPACE", "automation"),
            jwt_mount=os.environ.get("VAULT_JWT_MOUNT", "jwt"),
            jwt_role=os.environ.get("VAULT_JWT_ROLE", "test-runner"),
            strict_mode=_truthy(os.environ.get("STRICT_MODE")),
            vault_cacert=os.environ.get("VAULT_CACERT") or None,
            vault_skip_verify=_truthy(os.environ.get("VAULT_SKIP_VERIFY")),
        )

    def tls_verify(self) -> bool | str:
        """The 'verify' value for hvac/requests: a CA bundle path if provided, else False to
        skip verification, else True (verify against the system trust store)."""
        if self.vault_cacert:
            return self.vault_cacert
        if self.vault_skip_verify:
            return False
        return True
