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

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            vault_addr=_require("VAULT_ADDR"),
            ci_oidc_token=_require("CI_OIDC_TOKEN"),
            parent_namespace=os.environ.get("VAULT_PARENT_NAMESPACE", "automation"),
            jwt_mount=os.environ.get("VAULT_JWT_MOUNT", "jwt"),
            jwt_role=os.environ.get("VAULT_JWT_ROLE", "test-runner"),
            strict_mode=_truthy(os.environ.get("STRICT_MODE")),
        )
