# Vault Enterprise Automation Test Suite

Functional tests for Vault Enterprise auth methods and secret engines, run in CloudBees CI
against a pre-existing cluster. The suite creates an ephemeral namespace per run, tests inside it,
and tears it down.

## Design
See `docs/superpowers/specs/2026-05-25-vault-ent-automation-testing-design.md`.

## Required environment variables
| Var | Meaning |
|---|---|
| `VAULT_ADDR` | Cluster URL |
| `CI_OIDC_TOKEN` | Vault login JWT. In CI it is bound automatically from the CloudBees OpenID Connect provider credential `oidc-jwt-provider` (audience = `VAULT_ADDR`); the Vault `test-runner` role must set `bound_audiences=$VAULT_ADDR` to accept it |
| `VAULT_PARENT_NAMESPACE` | Delegated parent namespace (default `automation`) |
| `VAULT_JWT_MOUNT` | JWT auth mount path inside the parent ns (default `jwt`) |
| `VAULT_JWT_ROLE` | Scoped role name (default `test-runner`) |
| `STRICT_MODE` | `true` => missing external deps fail instead of skip (default `false`) |
| `BUILD_TAG` | CI build identifier (used to name the ephemeral namespace) |

## Selecting which areas to run

By default the full suite runs. To scope a run to specific auth methods or secret engines set
`AREAS` (env var or Jenkins parameter) or pass `--areas` on the command line. The value is a
comma-separated list of case-insensitive substrings matched against each test's `area` marker.

```bash
# Run only KV v2, Transit, and AppRole tests
AREAS="kv,transit,approle" pytest

# Equivalent via CLI flag
pytest --areas="kv,transit,approle"

# Exclude Kubernetes by listing only the engines/methods you want
AREAS="kv,transit,approle,pki,ssh,ldap" pytest
```

- Empty / unset `AREAS` runs everything (no filtering).
- A filter that matches no area at all causes a fast-fail `UsageError` that lists the available
  areas — useful for catching typos before a long run.
- Substring matching lets short tokens like `pki` match both `PKI (built-in)` and `PKI (Venafi)`.
- In Jenkins, set the `AREAS` build parameter; the conftest reads it automatically as an env var.

## Air-gapped dependency setup (vendored runtime + wheels)

The CI agent has no internet and cannot install or download anything. The Python runtime and all
dependencies are **vendored into this repo** under `vendor/` and installed offline.

**Refreshing the vendored artifacts** (on any machine WITH internet — the only networked step):

```bash
bash scripts/build-wheelhouse.sh
```

This downloads + checksum-verifies the pinned standalone CPython 3.11 (`vendor/python/`), downloads
the dependency + tooling wheels for the agent target `cp311 / manylinux2014_x86_64`
(`vendor/wheelhouse/`), regenerates the hash-pinned `requirements.lock`, and **fails if any pin has
a known OSV advisory**. Commit `vendor/`, `requirements.txt`, and `requirements.lock`.

**Provisioning the agent** (offline — downloads nothing, ignores the agent's system Python):

```bash
bash scripts/provision-agent.sh
```

This verifies the interpreter SHA256, extracts it to `/opt/vault-ent-suite/python`, builds a venv at
`/opt/vault-ent-suite/venv`, and installs the wheels with `pip install --require-hashes --no-index`.
Re-run whenever `vendor/` or `requirements.lock` changes; for reproducibility, prefer baking it into
the agent image. Override paths via `VENV_DIR` / `PY_BASE`.

**CI builds** activate `$VENV_DIR` (Jenkinsfile `VENV_DIR` parameter, default
`/opt/vault-ent-suite/venv`), assert Python 3.11 + import the deps, and run the tests — no per-build
install or network.

> Target is pinned to glibc-2.28 x86_64 / CPython 3.11. A different agent arch or libc requires
> re-vendoring with the matching `python-build-standalone` asset and wheel platform tag.

See `docs/superpowers/specs/2026-06-02-vendored-python-airgapped-provisioning-design.md` for rationale.
