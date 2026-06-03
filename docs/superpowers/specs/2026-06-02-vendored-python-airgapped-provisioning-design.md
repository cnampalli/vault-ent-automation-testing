# Design: Vendored Standalone Python + Wheels for the Air-Gapped CI Agent

**Date:** 2026-06-02
**Status:** Approved (pending spec review)
**Supersedes:** the webhost wheelhouse-transfer model in `scripts/build-wheelhouse.sh` / `scripts/provision-agent.sh` (those scripts are repurposed, see below)

## Problem

The CloudBees CI agent is fully locked down: it **cannot install binaries and cannot download anything**. Its only interpreter is the RHEL 8 system **Python 3.6.8 with pip 9.0.3** (glibc 2.28, x86_64).

This blocks the suite two ways:

1. **Dependency floors.** Every current pin requires a newer Python — `hvac>=3.8`, `pytest>=3.10`, `pytest-html>=3.9`, `PyJWT>=3.9`, `cryptography>=3.7`. None run on 3.6.
2. **Toolchain age.** pip 9.0.3 (2018) cannot read modern `manylinux2014` wheel tags, so even correct wheels are rejected at install time.

We must make the suite run on this agent **without downloading or installing anything at build time.**

## Decision

**Vendor a relocatable standalone CPython 3.11 build and the dependency wheels directly into the repo.** The air-gapped agent builds a venv from the vendored interpreter and installs the vendored wheels offline. Modern dependency versions are kept; the agent's ancient system Python is never used for the suite.

This was chosen over the alternative of downgrading all dependencies to the last 3.6-compatible releases. Running five EOL/unmaintained security libraries against a security product (Vault) is a worse risk than carrying one vendored interpreter blob. The tradeoff accepted: ~35 MB of binaries committed to git.

## Constraints & Target Environment

| Property | Value |
|---|---|
| Agent CPU arch | x86_64 |
| Agent libc | glibc 2.28 |
| Agent system Python | 3.6.8 (unused by suite after this change) |
| Agent network | none (air-gapped) |
| Agent privileges | cannot install packages or binaries |
| Connected build host | a developer machine / webhost with internet (used only to refresh vendored artifacts) |

## Architecture

Two phases, cleanly separated:

- **Vendor/refresh (connected host, occasional):** download + verify the interpreter, build + hash-lock + CVE-scan the wheelhouse, commit the artifacts.
- **Provision (air-gapped agent, once per agent or per requirements change):** verify checksums, extract interpreter, create venv, install wheels offline with hash enforcement.

CI builds then just activate the prepared venv and run pytest (unchanged from today's pre-provisioned-agent model).

### Repository layout (new)

```
vendor/
  python/
    cpython-3.11.15+20260510-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz
    SHA256SUMS                # upstream sums file, committed for provenance
  wheelhouse/
    *.whl                     # all runtime deps + transitive, cp311 manylinux2014_x86_64
requirements.txt              # human-edited direct deps (clean pins, see below)
requirements.lock            # fully-resolved, hash-pinned (--require-hashes input)
scripts/
  build-wheelhouse.sh         # repurposed: fetch+verify interpreter, build+lock+audit wheelhouse
  provision-agent.sh          # repurposed: verify+extract interpreter, venv, offline hashed install
```

`vendor/` is committed (removed from `.gitignore`). Stored as plain git blobs — **not git-LFS**, which would require the agent to fetch objects over the network and defeat the air-gap goal. Total growth ≈ 35 MB (interpreter ≈ 29 MB + wheels ≈ 6–10 MB).

## Vendored Artifacts

### Interpreter

- **Source:** `astral-sh/python-build-standalone`, release tag `20260510`.
- **Asset:** `cpython-3.11.15+20260510-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`
  - Baseline `x86_64` variant (no AVX/SSE4 CPU-baseline requirement — runs on any x86_64).
  - `install_only_stripped` — relocatable (rpath set to run from any path), stripped to ≈ 29.4 MB.
  - Bundles pip, enabling modern dependency versions.
- **Expected SHA256:** `171dffd8c0f66e8a0725364a7428015b22fc18dd298b24f541392e17dd0e561f`
- **Upstream URL:** `https://github.com/astral-sh/python-build-standalone/releases/download/20260510/cpython-3.11.15%2B20260510-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`

### Dependencies (clean pins)

Verified against the OSV database on 2026-06-02; all chosen versions have **no known advisories**.

| Package | Pin | Note |
|---|---|---|
| hvac | 2.4.0 | already clean |
| pytest | 9.0.3 | up from 8.3.4 (was `GHSA-6w46-j5rx-g56g`) |
| pytest-html | 4.2.0 | up from 4.1.1 |
| PyJWT[crypto] | 2.13.0 | up from 2.10.1 (was 3 advisories) |
| cryptography | 48.0.0 | up from 44.0.0 (was 4 advisories incl. `PYSEC-2026-35`) |

Transitive dependencies resolve to their latest clean releases (e.g. `requests 2.34.2`, `urllib3 2.7.0`, `idna 3.17`, `jinja2 3.1.6`, `certifi`, `cffi`, `pycparser`, `markupsafe`, `pluggy`, `iniconfig`, `packaging`). The exact set is frozen in `requirements.lock`.

> Compatibility note: pytest 9.0.3 + pytest-html 4.2.0 must be validated together by the build-time smoke run (see Testing). If pytest-html 4.2.0 is not yet compatible with pytest 9, fall back to the highest mutually-compatible clean pair and record it in `requirements.lock`.

## Security Controls

1. **Verified-clean pins.** Direct deps pinned to the OSV-clean versions above; transitives resolved to latest. The build re-runs an OSV/`pip-audit` scan over `requirements.lock` and **fails** if any advisory is present, so the committed wheelhouse is provably CVE-free at vendoring time.
2. **Hash-locked installs.** `requirements.lock` carries `--hash=sha256:…` for every wheel. The agent installs with `pip install --require-hashes --no-index --find-links=vendor/wheelhouse`. A tampered or swapped `.whl` fails the install — the primary supply-chain guard for vendored binaries.
3. **Interpreter integrity.** `provision-agent.sh` computes the SHA256 of the vendored tarball and compares it to the pinned expected value before extraction; mismatch aborts loudly. The upstream `SHA256SUMS` file is committed for provenance. Optionally, the connected host runs `gh attestation verify` against the asset when refreshing.
4. **Upgrade bundled tooling.** After venv creation, pip and setuptools are upgraded to clean latest (`pip 26.1.2`, `setuptools 82.0.1`) from vendored wheels, since standalone builds ship older ones carrying advisories. Done offline via `--no-index`.
5. **Drift gate.** A CI/documented `pip-audit` step re-scans `requirements.lock` on a schedule (or each build) so a CVE disclosed *after* vendoring is caught and triggers a refresh. Prevents silent rot of vendored binaries.

## Build / Refresh Flow (connected host)

`scripts/build-wheelhouse.sh` (repurposed) performs, idempotently:

1. Download the pinned interpreter asset; verify SHA256 against the pinned value (and `SHA256SUMS`); write into `vendor/python/`.
2. `pip download` the deps for the agent target (`--only-binary=:all: --implementation cp --python-version 3.11 --abi cp311 --platform manylinux2014_x86_64`) into `vendor/wheelhouse/`. Fail loudly if any wheel is unavailable for the target (no host-platform fallback).
3. Generate `requirements.lock` with full resolution + `--hash` entries.
4. Run `pip-audit` (OSV) over `requirements.lock`; abort on any advisory.
5. Print a summary; the developer commits `vendor/`, `requirements.txt`, `requirements.lock`.

This is the *only* step that needs internet, and it runs on a developer/webhost machine — never on the agent.

## Provisioning Flow (air-gapped agent)

`scripts/provision-agent.sh` (repurposed) performs, idempotently:

1. Verify the vendored interpreter tarball's SHA256 against the pinned value; abort on mismatch.
2. Extract the interpreter to a stable path (e.g. `/opt/vault-ent-suite/python`); the build is relocatable.
3. Create the venv from the vendored interpreter: `"$PY/bin/python3" -m venv "$VENV_DIR"` (wiping any stale venv first for determinism).
4. Offline-upgrade pip/setuptools from `vendor/wheelhouse` (`--no-index --find-links`).
5. `pip install --require-hashes --no-index --find-links=vendor/wheelhouse -r requirements.lock`.
6. `pip check`, then an import smoke test: `python -c "import hvac, jwt, cryptography, pytest"`.
7. Print the `VENV_DIR` for CI builds to activate.

No network calls anywhere in this flow. The venv is created from the vendored interpreter directly; the agent's system Python 3.6.8 is never involved.

## CI Integration (Jenkinsfile)

Unchanged model: builds activate `$VENV_DIR` and run pytest with the existing `AREAS` selection. The only addition is an optional guard step that asserts `$VENV_DIR` exists and was provisioned from the vendored interpreter (fail with a clear message pointing at `provision-agent.sh` otherwise). No new per-build downloads.

## Testing

- **Unit tests** (existing 42) continue to run; no code changes expected to `lib/`, `config/`, `conftest.py`.
- **Build-time smoke run:** after `provision-agent.sh` on a glibc-2.28 x86_64 environment (or a matching container), run `pytest tests/unit` to confirm the vendored interpreter + wheels resolve and the suite collects/passes. This validates the pytest 9 / pytest-html 4.2 pairing.
- **Integrity negative test:** corrupt a byte in the vendored tarball and confirm `provision-agent.sh` aborts; swap a wheel and confirm `--require-hashes` rejects it.
- **CVE gate test:** confirm `pip-audit` over `requirements.lock` exits non-zero when fed a known-vulnerable pin.

## Tradeoffs & Risks

- **Repo size (+~35 MB).** Accepted; plain git blobs. Acceptable for a private CI repo. Mitigation if it grows painful: a future move to an internal artifact store the agent *can* reach.
- **Single target platform.** Vendored wheels + interpreter are pinned to cp311 / glibc-2.28 / x86_64. A different agent arch/libc requires a re-vendor. Documented in README.
- **Refresh discipline.** Vendored artifacts don't auto-update; the drift gate (control 5) is what keeps them honest.
- **pytest 9 plugin compatibility.** Mitigated by the build-time smoke run and the documented fallback pin pair.

## Out of Scope

- Replacing the agent's system Python or changing the agent image.
- Git-LFS or an internal package mirror (possible future evolution).
- Phase 1 auth-method/secret-engine test expansion (separate spec).
