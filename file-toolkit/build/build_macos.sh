#!/usr/bin/env bash
# File Toolkit — macOS build (run on macOS; product name, bundle id, etc. come from
# [tool.flet] in pyproject.toml, version from [project].version).
#   MACOS_ARCH=arm64|x86_64|universal (default: arm64)
set -euo pipefail

cd "$(dirname "$0")/.."

arch="${MACOS_ARCH:-arm64}"
[ "$arch" = "x64" ] && arch="x86_64"

args=(build macos --yes)
if [ "$arch" != "universal" ]; then
  args+=(--arch "$arch")
fi
if [ -n "${BUILD_NUMBER:-}" ]; then
  args+=(--build-number "$BUILD_NUMBER")
fi

uv run --group build -- flet "${args[@]}" "$@"
