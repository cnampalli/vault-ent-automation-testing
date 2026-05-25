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

## Air-gapped install
See `scripts/build-wheelhouse.sh` and the design doc §8.
