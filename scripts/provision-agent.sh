#!/usr/bin/env bash
# Run ONCE on the air-gapped CI agent (or bake into the agent image) to install the suite's
# pinned dependencies into a stable virtualenv. Re-run whenever requirements.txt changes.
#
# Prereq: the wheelhouse built by scripts/build-wheelhouse.sh on the webhost has been transferred
# and extracted on this agent (so a directory of .whl files exists).
#
# Inputs (env vars):
#   WHEELHOUSE_DIR : directory containing the downloaded wheels (default: ./wheelhouse)
#   VENV_DIR       : where to create the venv (default: /opt/vault-ent-suite/venv)
# Usage:
#   WHEELHOUSE_DIR=./wheelhouse VENV_DIR=/opt/vault-ent-suite/venv ./scripts/provision-agent.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
WHEELHOUSE_DIR="${WHEELHOUSE_DIR:-$HERE/wheelhouse}"
VENV_DIR="${VENV_DIR:-/opt/vault-ent-suite/venv}"

if [ ! -d "$WHEELHOUSE_DIR" ]; then
  echo "ERROR: wheelhouse directory not found: $WHEELHOUSE_DIR" >&2
  echo "Build it on the webhost (scripts/build-wheelhouse.sh), transfer + extract it here, then re-run." >&2
  exit 1
fi

echo "Provisioning virtualenv at $VENV_DIR from wheelhouse $WHEELHOUSE_DIR"
rm -rf "$VENV_DIR"
python3 -m venv "$VENV_DIR"
# shellcheck source=/dev/null
. "$VENV_DIR/bin/activate"
python3 -m pip install --no-index --find-links="$WHEELHOUSE_DIR" -r "$HERE/requirements.txt"
python3 -m pip check
python3 -c "import hvac, jwt, cryptography, pytest; print('agent provisioned OK')"
echo "Done. Configure CI builds with VENV_DIR=$VENV_DIR"
