#!/usr/bin/env bash
# Runs ONCE on the air-gapped CI agent (or bake into the agent image). Builds a venv from the
# VENDORED standalone interpreter and installs the VENDORED, hash-locked wheels OFFLINE.
# Downloads nothing and does not use the agent's system Python. Re-run when vendor/ or
# requirements.lock changes.
#
# Inputs (env vars):
#   VENV_DIR : where to create the venv      (default: /opt/vault-ent-suite/venv)
#   PY_BASE  : where to extract the runtime   (default: /opt/vault-ent-suite/python)
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${VENV_DIR:-/opt/vault-ent-suite/venv}"
PY_BASE="${PY_BASE:-/opt/vault-ent-suite/python}"

PBS_ASSET="cpython-3.11.15+20260510-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PBS_SHA256="171dffd8c0f66e8a0725364a7428015b22fc18dd298b24f541392e17dd0e561f"
TARBALL="$HERE/vendor/python/$PBS_ASSET"
WH_DIR="$HERE/vendor/wheelhouse"
LOCK="$HERE/requirements.lock"

[ -f "$TARBALL" ] || { echo "ERROR: vendored interpreter missing: $TARBALL" >&2; exit 1; }
[ -d "$WH_DIR" ]  || { echo "ERROR: vendored wheelhouse missing: $WH_DIR" >&2; exit 1; }
[ -f "$LOCK" ]    || { echo "ERROR: lockfile missing: $LOCK" >&2; exit 1; }

echo "==> Verifying interpreter checksum"
echo "${PBS_SHA256}  ${TARBALL}" | sha256sum -c -

echo "==> Extracting interpreter to $PY_BASE"
rm -rf "$PY_BASE"; mkdir -p "$PY_BASE"
tar -xzf "$TARBALL" -C "$PY_BASE"   # creates "$PY_BASE/python/..."
PYBIN="$PY_BASE/python/bin/python3"
[ -x "$PYBIN" ] || { echo "ERROR: interpreter not found after extract: $PYBIN" >&2; exit 1; }

echo "==> Creating venv at $VENV_DIR (from vendored interpreter)"
rm -rf "$VENV_DIR"
"$PYBIN" -m venv "$VENV_DIR"
# shellcheck source=/dev/null
. "$VENV_DIR/bin/activate"

echo "==> Upgrading pip/setuptools offline"
python3 -m pip install --no-index --find-links="$WH_DIR" --upgrade pip setuptools

echo "==> Installing dependencies (hash-enforced, offline)"
python3 -m pip install --no-index --find-links="$WH_DIR" --require-hashes -r "$LOCK"

python3 -m pip check
python3 -c "import hvac, jwt, cryptography, pytest; print('agent provisioned OK')"
echo "Done. Configure CI builds with VENV_DIR=$VENV_DIR"
