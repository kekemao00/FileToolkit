"""压缩解压工作台 — ZIP / 7Z / TAR.GZ 压缩，批量解压（ZIP / 7Z / RAR / TAR）"""
from pathlib import Path

import flet as ft

from core.archive.handler import compress, extract_many
from ui.components.workbench import Workbench, WorkbenchFunction
from ui.palette import c

_ARCHIVES = ("zip", "7z", "rar", "tar", "gz", "tgz", "bz2", "xz")
_ANY = ("*",)


def _hint(text: str) -> ft.Text:
    return ft.Text(text, size=11, color=c("ink-3", "fg"))


class ArchivePage(Workbench):
    TITLE = "压缩解压"
    SUBTITLE = "打包文件和文件夹，或批量解压压缩包"
    MODULE = "archive"
    PICK_LABEL = "点击选择文件"
    PICK_ICON = ft.Icons.UPLOAD_FILE_OUTLINED
    FILE_ICON = ft.Icons.INSERT_DRIVE_FILE_OUTLINED
    FUNCTIONS = [
        WorkbenchFunction("compress_zip", "ZIP 压缩", "通用格式，各系统都能直接打开", ft.Icons.FOLDER_ZIP_OUTLINED,
                          _ANY, accepts_folders=True, show_size=True),
        WorkbenchFunction("compress_7z", "7Z 压缩", "压缩率更高，可设密码", ft.Icons.INVENTORY_2_OUTLINED,
                          _ANY, accepts_folders=True, show_size=True),
        WorkbenchFunction("compress_targz", "TAR.GZ", "Linux / macOS 常用", ft.Icons.ARCHIVE_OUTLINED,
                          _ANY, accepts_folders=True, show_size=True),
        WorkbenchFunction("extract", "解压", "ZIP / 7Z / RAR / TAR，每个包解到单独文件夹",
                          ft.Icons.UNARCHIVE_OUTLINED, _ARCHIVES),
    ]

    def __init__(self, page: ft.Page, initial_func: str | None = None) -> None:
        self._name = self.text_field("", "默认用第一个文件名")
        self._password = self.text_field("", "留空则不加密", password=True, can_reveal_password=True)
        self._extract_password = self.text_field("", "压缩包没有密码时留空", password=True,
                                                 can_reveal_password=True)
        super().__init__(page, initial_func)

    def build_params(self, key: str) -> list[ft.Control]:
        if key == "extract":
            return [
                self.section("解压密码", self._extract_password),
                _hint("RAR 需要本机装有 unrar 或 7-Zip"),
            ]
        controls = [self.section("压缩包名称", self._name)]
        if key == "compress_7z":
            controls.append(self.section("打开密码", ft.Column(controls=[
                self._password, _hint("文件名也会一起加密，忘记密码将无法打开"),
            ], spacing=6)))
        else:
            controls.append(_hint("需要设置密码请选「7Z 压缩」"))
        return controls

    def build_task(self, key: str, files: list[Path], out_dir: Path):
        if key == "extract":
            return extract_many, {"input_files": files, "output_dir": out_dir,
                                  "password": self._extract_password.value or ""}
        fmt = {"compress_zip": "zip", "compress_7z": "7z", "compress_targz": "tar.gz"}[key]
        kwargs = {"input_files": files, "output_dir": out_dir, "format": fmt}
        if key == "compress_7z" and self._password.value:
            kwargs["password"] = self._password.value
        name = (self._name.value or "").strip()
        if name:
            kwargs["archive_name"] = name
        return compress, kwargs
