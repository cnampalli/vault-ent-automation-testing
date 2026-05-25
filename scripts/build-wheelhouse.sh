#!/usr/bin/env bash
# Run on the INTERNET-CONNECTED webhost. Produces wheelhouse.tar.gz to publish for the air-gapped agent.
#
# Wheels are downloaded for the AGENT's platform (not this host's), so this works whether or not the
# webhost matches the agent. Pass the agent's values if they differ from the CloudBees Linux / CPython
# 3.11 / x86_64 defaults below. Determine them on the agent with `python3 --version` and `uname -m`.
# If pip reports "no matching distribution" for a package, the platform tag is wrong for it -- adjust
# PLATFORM (e.g. manylinux_2_28_x86_64) or ABI to match the agent.
#
# Usage: ./scripts/build-wheelhouse.sh [PYVER] [ABI] [PLATFORM]
set -euo pipefail

PYVER="${1:-3.11}"
ABI="${2:-cp311}"
PLATFORM="${3:-manylinux2014_x86_64}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

echo "Downloading wheels for target: python=$PYVER abi=$ABI platform=$PLATFORM"
rm -rf "$HERE/wheelhouse" && mkdir -p "$HERE/wheelhouse"

# Always target the agent platform explicitly. --only-binary=:all: prevents host-specific sdists
# from sneaking in. This fails LOUDLY on the webhost if a wheel is unavailable, instead of silently
# bundling wrong-platform wheels that would explode at install time on the air-gapped agent.
python3 -m pip download -r "$HERE/requirements.txt" -d "$HERE/wheelhouse" \
  --only-binary=:all: --implementation cp \
  --python-version "$PYVER" --abi "$ABI" --platform "$PLATFORM"

tar czf "$HERE/wheelhouse.tar.gz" -C "$HERE" wheelhouse
echo "Created $HERE/wheelhouse.tar.gz -- publish this on the webhost HTTP path."
