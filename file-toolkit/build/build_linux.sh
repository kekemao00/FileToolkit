#!/usr/bin/env bash
# File Toolkit — Linux build (run on Linux; needs GTK3 dev headers, clang, cmake, ninja).
# Put an ffmpeg binary at assets/bin/ffmpeg first to bundle it into the app.
set -euo pipefail

cd "$(dirname "$0")/.."

args=(build linux --yes)
if [ -n "${BUILD_NUMBER:-}" ]; then
  args+=(--build-number "$BUILD_NUMBER")
fi

uv run --group build -- flet "${args[@]}" "$@"
