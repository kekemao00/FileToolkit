#!/bin/sh
# 把 File Toolkit 加进桌面应用菜单（带图标），只影响当前用户。
# 用法：解压后在 FileToolkit/ 目录里运行 ./install-desktop-entry.sh
# 卸载：rm ~/.local/share/applications/com.kekemao00.filetoolkit.desktop \
#          ~/.local/share/icons/hicolor/256x256/apps/com.kekemao00.filetoolkit.png
set -eu

dir=$(cd "$(dirname "$0")" && pwd)
app_id=com.kekemao00.filetoolkit

exe=""
for f in "$dir"/*; do
    case "$(basename "$f")" in *.sh) continue ;; esac
    if [ -f "$f" ] && [ -x "$f" ]; then exe=$f; break; fi
done
[ -n "$exe" ] || { echo "在 $dir 下没找到可执行文件" >&2; exit 1; }

data=${XDG_DATA_HOME:-$HOME/.local/share}
icon_dir="$data/icons/hicolor/256x256/apps"
mkdir -p "$data/applications" "$icon_dir"
cp "$dir/file-toolkit.png" "$icon_dir/$app_id.png"

cat > "$data/applications/$app_id.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=File Toolkit
Name[zh_CN]=文件全能王
Comment=Local file processing toolkit
Exec="$exe" %F
Path=$dir
Icon=$app_id
Terminal=false
Categories=Utility;
StartupWMClass=$(basename "$exe")
EOF

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$data/applications" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q "$data/icons/hicolor" 2>/dev/null || true
echo "已添加到应用菜单：$data/applications/$app_id.desktop"
