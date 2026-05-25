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

## Air-gapped dependency setup (pre-provisioned agent)

The CI agent has no internet. Dependencies are installed ONCE into a stable virtualenv on the
agent, not on every build.

1. **On the webhost (has internet):** build the wheel bundle.
   `./scripts/build-wheelhouse.sh [PYVER] [ABI] [PLATFORM]` -> produces `wheelhouse.tar.gz`.
2. **Transfer + extract** `wheelhouse.tar.gz` onto the agent (or the agent image build).
3. **On the agent:** provision the venv from the pinned `requirements.txt`.
   `WHEELHOUSE_DIR=./wheelhouse VENV_DIR=/opt/vault-ent-suite/venv ./scripts/provision-agent.sh`
   Re-run whenever `requirements.txt` changes. For reproducibility, prefer baking this into the
   agent's base image rather than hand-running it.
4. **CI builds** activate `$VENV_DIR` (Jenkinsfile `VENV_DIR` parameter, default
   `/opt/vault-ent-suite/venv`), verify imports, and run the tests. No per-build install or network.

See the design doc section 8 for the rationale.
