import os
import pytest


def missing_env(*env_vars: str) -> list[str]:
    """Return the env vars that are unset or blank."""
    return [v for v in env_vars if not (os.environ.get(v) or "").strip()]


def requires_env(*env_vars: str):
    """pytest marker: skip the test when any required env var is missing.

    In STRICT_MODE the suite-level conftest converts skips to failures; here we
    always express the dependency as a skipif so non-strict runs stay green.
    """
    absent = missing_env(*env_vars)
    return pytest.mark.skipif(
        bool(absent),
        reason=f"missing required env: {', '.join(absent)}" if absent else "",
    )
