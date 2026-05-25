import os


def missing_env(*env_vars: str) -> list[str]:
    """Return the env vars that are unset or blank."""
    return [v for v in env_vars if not (os.environ.get(v) or "").strip()]


def requires_env(*env_vars: str):
    """pytest marker: skip the test when any required env var is missing.

    Env vars are read at collection time (module import), so they must be set
    in the process environment before pytest starts -- not inside fixtures.

    Note: a STRICT_MODE that converts these skips into failures is planned for a
    later phase and is NOT yet enforced; today, missing deps always skip.
    """
    import pytest  # lazy: keeps lib/ free of a hard pytest runtime dependency

    absent = missing_env(*env_vars)
    return pytest.mark.skipif(
        bool(absent),
        reason=f"missing required env: {', '.join(absent)}",
    )
