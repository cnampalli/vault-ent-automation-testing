#!/usr/bin/env bash
# Run on the INTERNET-CONNECTED webhost. Produces wheelhouse.tar.gz to publish for the air-gapped agent.
# Usage: ./scripts/build-wheelhouse.sh [PYVER] [ABI] [PLATFORM]
#   defaults match a typical CloudBees Linux agent on CPython 3.11 x86_64.
set -euo pipefail

PYVER="${1:-311}"
ABI="${2:-cp311}"
PLATFORM="${3:-manylinux2014_x86_64}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

rm -rf "$HERE/wheelhouse" && mkdir -p "$HERE/wheelhouse"

# Try a plain download first (works when this host matches the agent platform);
# fall back to forcing the agent's platform for the compiled 'cryptography' wheel.
if ! python3 -m pip download -r "$HERE/requirements.txt" -d "$HERE/wheelhouse"; then
  python3 -m pip download -r "$HERE/requirements.txt" -d "$HERE/wheelhouse" \
    --only-binary=:all: --implementation cp \
    --python-version "$PYVER" --abi "$ABI" --platform "$PLATFORM"
fi

tar czf "$HERE/wheelhouse.tar.gz" -C "$HERE" wheelhouse
echo "Created $HERE/wheelhouse.tar.gz -- publish this on the webhost HTTP path."
