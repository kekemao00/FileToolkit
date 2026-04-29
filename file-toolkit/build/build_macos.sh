#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

arch="${MACOS_ARCH:-arm64}"
if [ "$arch" = "x64" ]; then
  arch="x86_64"
fi

set -- build macos

if [ "$arch" != "universal" ]; then
  set -- "$@" --arch "$arch"
fi

set -- "$@" \
  --product "File Toolkit" \
  --artifact "File Toolkit" \
  --project "file_toolkit" \
  --bundle-id "com.kekemao00.filetoolkit" \
  --company "FileToolkit" \
  --copyright "MIT License"

if [ -f "assets/icons/app_icon.png" ]; then
  set -- "$@" --icon assets/icons/app_icon.png
elif [ -f "assets/icons/app_icon.icns" ]; then
  set -- "$@" --icon assets/icons/app_icon.icns
fi

flet "$@"
