#!/usr/bin/env bash
# Runs on a CONNECTED host (developer machine / webhost) -- the ONLY step that needs internet.
# Refreshes the vendored air-gapped artifacts committed to the repo:
#   vendor/python/   : the pinned standalone CPython interpreter + upstream SHA256SUMS
#   vendor/wheelhouse: dependency + tooling wheels for the agent target (cp311/manylinux2014_x86_64)
#   requirements.lock: fully-resolved, hash-pinned install input, OSV-scanned clean
# The air-gapped agent then provisions offline via scripts/provision-agent.sh (downloads nothing).
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"

# --- Pinned interpreter (astral-sh/python-build-standalone) --------------------------------
PBS_TAG="20260510"
PBS_ASSET="cpython-3.11.15+20260510-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PBS_SHA256="171dffd8c0f66e8a0725364a7428015b22fc18dd298b24f541392e17dd0e561f"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/cpython-3.11.15%2B20260510-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
SUMS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/SHA256SUMS"

# --- Wheel target (MUST match the air-gapped agent) ---------------------------------------
PYVER="3.11"; ABI="cp311"; PLATFORM="manylinux2014_x86_64"
PIP_PIN="26.1.2"; SETUPTOOLS_PIN="82.0.1"

PY_DIR="$HERE/vendor/python"
WH_DIR="$HERE/vendor/wheelhouse"
LOCK="$HERE/requirements.lock"

mkdir -p "$PY_DIR" "$WH_DIR"

echo "==> Fetching interpreter $PBS_ASSET"
curl -fSL "$PBS_URL" -o "$PY_DIR/$PBS_ASSET"
curl -fSL "$SUMS_URL" -o "$PY_DIR/SHA256SUMS"

echo "==> Verifying interpreter checksum"
python3 - "$PY_DIR/$PBS_ASSET" "$PBS_SHA256" <<'PY'
import hashlib, sys
path, expected = sys.argv[1], sys.argv[2]
h = hashlib.sha256()
with open(path, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
got = h.hexdigest()
if got != expected:
    sys.exit(f"CHECKSUM MISMATCH: {got} != {expected}")
print("checksum OK")
PY

echo "==> Downloading wheels for cp${PYVER}/${PLATFORM}"
rm -f "$WH_DIR"/*.whl
python3 -m pip download -r "$HERE/requirements.txt" -d "$WH_DIR" \
  --only-binary=:all: --implementation cp \
  --python-version "$PYVER" --abi "$ABI" --platform "$PLATFORM"
# Tooling wheels for the offline pip/setuptools upgrade (pure-python; platform-agnostic).
python3 -m pip download "pip==$PIP_PIN" "setuptools==$SETUPTOOLS_PIN" -d "$WH_DIR" --only-binary=:all:

echo "==> Generating hash-locked $LOCK"
python3 "$HERE/scripts/_gen_lock.py" "$WH_DIR" > "$LOCK"

echo "==> CVE scan (OSV) over $LOCK"
python3 "$HERE/scripts/_osv_audit.py" "$LOCK"

echo "==> Done. Review and commit: vendor/ requirements.txt requirements.lock"
