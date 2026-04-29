#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

arch="${MACOS_ARCH:-arm64}"
if [ "$arch" = "x64" ]; then
  arch="x86_64"
fi

arch_args=()
if [ "$arch" != "universal" ]; then
  arch_args=(--arch "$arch")
fi

icon_args=()
if [ -f "assets/icons/app_icon.png" ]; then
  icon_args=(--icon assets/icons/app_icon.png)
elif [ -f "assets/icons/app_icon.icns" ]; then
  icon_args=(--icon assets/icons/app_icon.icns)
fi

flet build macos \
  "${arch_args[@]}" \
  --product "File Toolkit" \
  --artifact "File Toolkit" \
  --project "file_toolkit" \
  --bundle-id "com.kekemao00.filetoolkit" \
  --company "FileToolkit" \
  --copyright "MIT License" \
  "${icon_args[@]}"
