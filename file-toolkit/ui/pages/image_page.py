"""图片工作台 — 压缩 / 格式转换 / 尺寸调整 / 水印 / 批量重命名"""
from pathlib import Path

import flet as ft

from core.image.compressor import compress_images
from core.image.converter import convert_image
from core.image.renamer import batch_rename, preview_rename
from core.image.resizer import resize_images
from core.image.watermark import add_text_watermark
from core.models import TaskResult, TaskStatus
from ui.components.workbench import ChoiceGroup, Workbench, WorkbenchFunction, is_mounted
from ui.palette import c
from ui.utils import show_toast

_IMAGES = ("png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "heic")

_POSITIONS = [
    ("top_left", "左上"), ("top_center", "上中"), ("top_right", "右上"),
    ("center_left", "左中"), ("center", "居中"), ("center_right", "右中"),
    ("bottom_left", "左下"), ("bottom_center", "下中"), ("bottom_right", "右下"),
    ("tile", "平铺"),
]


def _slider(min_v: int, max_v: int, value: int, divisions: int) -> ft.Slider:
    return ft.Slider(min=min_v, max=max_v, value=value, divisions=divisions, label="{value}",
                     active_color=c("ink", "fg"), inactive_color=c("surface-3"), expand=True)


def _labeled(label: str, control: ft.Control) -> ft.Control:
    return ft.Row(controls=[ft.Text(label, size=12, color=c("ink-2", "fg"), width=56), control],
                  spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)


class ImagePage(Workbench):
    TITLE = "图片工作台"
    SUBTITLE = "批量压缩、格式转换、尺寸调整、水印与重命名"
    MODULE = "image"
    PICK_LABEL = "点击选择图片"
    PICK_ICON = ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED
    FILE_ICON = ft.Icons.IMAGE_OUTLINED
    FILE_NOUN = "张图片"
    FUNCTIONS = [
        WorkbenchFunction("compress", "压缩", "减小图片体积", ft.Icons.COMPRESS_OUTLINED, _IMAGES),
        WorkbenchFunction("convert", "格式转换", "PNG / JPG / WebP / BMP / TIFF", ft.Icons.TRANSFORM_OUTLINED,
                          _IMAGES),
        WorkbenchFunction("resize", "尺寸调整", "按宽高缩放", ft.Icons.PHOTO_SIZE_SELECT_LARGE_OUTLINED,
                          _IMAGES),
        WorkbenchFunction("watermark", "水印", "批量添加文字水印", ft.Icons.WATER_DROP_OUTLINED,
                          _IMAGES),
        WorkbenchFunction("rename", "批量重命名", "按模板原地改名", ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
                          _IMAGES, uses_output_dir=False),
    ]

    def __init__(self, page: ft.Page, initial_func: str | None = None) -> None:
        # 压缩
        self._level = ChoiceGroup([("low", "轻度"), ("medium", "标准"), ("high", "极限")], "medium")
        # 转换
        self._format = ChoiceGroup(
            [("png", "PNG"), ("jpg", "JPG"), ("webp", "WebP"), ("bmp", "BMP"), ("tiff", "TIFF")], "webp")
        self._quality = _slider(10, 100, 85, 18)
        # 尺寸
        self._width = self.text_field("", "宽度 px", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self._height = self.text_field("", "高度 px", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self._keep_ratio = ft.Checkbox(label="保持比例", value=True, active_color=c("ink", "fg"))
        # 水印
        self._wm_text = self.text_field("", "水印文字")
        self._wm_pos = ChoiceGroup(_POSITIONS, "bottom_right")
        self._wm_opacity = _slider(10, 100, 40, 9)
        self._wm_size = _slider(12, 120, 32, 18)
        # 重命名
        self._template = self.text_field("{name}_{n:03d}", "命名模板", on_change=lambda _: self._refresh_preview())
        self._start_num = self.text_field("1", "起始序号", keyboard_type=ft.KeyboardType.NUMBER, expand=True,
                                          on_change=lambda _: self._refresh_preview())
        self._preview = ft.Column(spacing=4)
        super().__init__(page, initial_func)

    def build_params(self, key: str) -> list[ft.Control]:
        if key == "compress":
            return [self.section("压缩强度", ft.Column(controls=[
                self._level,
                ft.Text("轻度几乎看不出差别；极限体积最小，细节会有损失", size=11, color=c("ink-3", "fg")),
            ], spacing=8))]
        if key == "convert":
            return [
                self.section("目标格式", self._format),
                self.section("输出质量（JPG / WebP）", self._quality),
            ]
        if key == "resize":
            return [self.section("目标尺寸", ft.Column(controls=[
                ft.Row(controls=[self._width, ft.Text("×", color=c("ink-2", "fg")), self._height], spacing=8),
                self._keep_ratio,
                ft.Text("保持比例时只填一项即可，另一项自动计算", size=11, color=c("ink-3", "fg")),
            ], spacing=8))]
        if key == "watermark":
            return [
                self.section("水印文字", self._wm_text),
                self.section("位置", self._wm_pos),
                self.section("样式", ft.Column(controls=[
                    _labeled("透明度", self._wm_opacity),
                    _labeled("字号", self._wm_size),
                ], spacing=0)),
            ]
        return [
            self.section("命名规则", ft.Column(controls=[
                self._template,
                ft.Text("{name} 原名　{n} 序号　{n:03d} 补零序号　{date} 日期", size=11, color=c("ink-3", "fg")),
                _labeled("起始序号", self._start_num),
            ], spacing=8)),
            self.section("预览", self._preview),
            ft.Text("重命名直接修改原文件，不会另存副本", size=11, color=c("ink-2", "fg")),
        ]

    def on_files_changed(self) -> None:
        self._refresh_preview(update=False)

    def _start_number(self) -> int:
        try:
            return max(0, int(self._start_num.value or "1"))
        except ValueError:
            return 1

    def _refresh_preview(self, update: bool = True) -> None:
        files = self._applicable()[:4] if hasattr(self, "_files") else []
        if not files:
            self._preview.controls = [ft.Text("选择图片后显示新文件名", size=12, color=c("ink-3", "fg"))]
        else:
            rows = preview_rename(files, self._template.value or "{name}_{n:03d}", self._start_number())
            self._preview.controls = [
                ft.Text(f"{old.name} → {new}", size=12, color=c("ink", "fg"),
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                for old, new in rows
            ]
        if update and is_mounted(self._preview):
            self._preview.update()

    def build_task(self, key: str, files: list[Path], out_dir: Path):
        if key == "compress":
            return compress_images, {"input_files": files, "output_dir": out_dir, "level": self._level.value}
        if key == "convert":
            return convert_image, {"input_files": files, "output_dir": out_dir,
                                   "target_format": self._format.value, "quality": int(self._quality.value)}
        if key == "resize":
            try:
                width = int(self._width.value) if (self._width.value or "").strip() else None
                height = int(self._height.value) if (self._height.value or "").strip() else None
            except ValueError:
                show_toast(self._page, "宽度和高度必须是整数")
                return None
            if not width and not height:
                show_toast(self._page, "请至少填写宽度或高度")
                return None
            return resize_images, {"input_files": files, "output_dir": out_dir, "width": width,
                                   "height": height, "keep_ratio": bool(self._keep_ratio.value)}
        if key == "watermark":
            text = (self._wm_text.value or "").strip()
            if not text:
                show_toast(self._page, "请填写水印文字")
                return None
            return add_text_watermark, {"input_files": files, "output_dir": out_dir, "text": text,
                                        "position": self._wm_pos.value, "opacity": int(self._wm_opacity.value),
                                        "font_size": int(self._wm_size.value)}
        return batch_rename, {"input_files": files, "template": self._template.value or "{name}_{n:03d}",
                              "start_number": self._start_number()}

    def after_task(self, key: str, files: list[Path], result: TaskResult) -> None:
        # 重命名是原地操作，把列表里的旧路径换成新路径
        if key == "rename" and result.status == TaskStatus.SUCCESS:
            mapping = dict(zip(files, result.output_files))
            self._files = [mapping.get(p, p) for p in self._files]
            self._render_files()
