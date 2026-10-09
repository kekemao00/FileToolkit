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

# 可执行文件本身不带图标，附上图标和加入应用菜单的脚本（与发布包一致）
cp packaging/linux/file-toolkit.png build/linux/
install -m 755 packaging/linux/install-desktop-entry.sh build/linux/
