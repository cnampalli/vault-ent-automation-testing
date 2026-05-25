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
| `CI_OIDC_TOKEN` | The CloudBees CI OIDC/JWT token presented at login |
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

## Air-gapped dependency setup (pre-provisioned agent)

The CI agent has no internet. Dependencies are installed ONCE into a stable virtualenv on the
agent, not on every build.

1. **On the webhost (has internet):** build the wheel bundle.
   `./scripts/build-wheelhouse.sh [PYVER] [ABI] [PLATFORM]` -> produces `wheelhouse.tar.gz`.
2. **Transfer + extract** `wheelhouse.tar.gz` onto the agent (or the agent image build).
3. **On the agent:** provision the venv from the pinned `requirements.txt`.
   `WHEELHOUSE_DIR=./wheelhouse VENV_DIR=/opt/vault-ent-suite/venv bash scripts/provision-agent.sh`
   Re-run whenever `requirements.txt` changes. For reproducibility, prefer baking this into the
   agent's base image rather than hand-running it.
4. **CI builds** activate `$VENV_DIR` (Jenkinsfile `VENV_DIR` parameter, default
   `/opt/vault-ent-suite/venv`), verify imports, and run the tests. No per-build install or network.

See the design doc section 8 for the rationale.
