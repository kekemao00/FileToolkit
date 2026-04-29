"""图片水印 — Figma 设计语言统一"""
import asyncio
from pathlib import Path

import flet as ft

from core.image.watermark import add_text_watermark
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.sub_page_header import SubPageHeader
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class ImageWatermarkPage(ft.Column):
    """添加水印：选图片 → 设置水印文字/位置/透明度 → 执行"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._input_files: list[Path] = []
        self._task: asyncio.Task | None = None

        self._drop_zone = DropZone(
            label="拖拽图片文件到此处",
            sublabel="支持 PNG / JPG / WebP，可多选",
            allowed_extensions=["png", "jpg", "jpeg", "webp"],
            on_files_selected=self._on_files,
            allow_multiple=True,
            icon=ft.Icons.BRANDING_WATERMARK,
        )
        self._drop_zone.set_page(page)

        self._text_field = ft.TextField(
            value="",
            label="水印文字",
            hint_text="输入水印内容",
            border_radius=12,
            bgcolor="#f8fafc",
            border_color="transparent",
            expand=True,
        )
        self._position = ft.Dropdown(
            value="bottom_right",
            options=[
                ft.dropdown.Option("top_left", "左上角"),
                ft.dropdown.Option("top_right", "右上角"),
                ft.dropdown.Option("bottom_left", "左下角"),
                ft.dropdown.Option("bottom_right", "右下角"),
                ft.dropdown.Option("center", "居中"),
                ft.dropdown.Option("tile", "平铺"),
            ],
            width=160, border_radius=12, label="位置",
        )
        self._opacity = ft.Slider(min=10, max=100, value=30, divisions=9, label="{value}%", width=250)
        self._font_size = ft.TextField(
            value="24", label="字号", width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=12, bgcolor="#f8fafc", border_color="transparent",
        )

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)
        self._run_btn = self._build_run_button("添加水印", ft.Icons.BRANDING_WATERMARK)

        self.controls = [
            SubPageHeader(
                title="添加水印",
                icon=ft.Icons.BRANDING_WATERMARK,
                icon_color="#9333ea",
                icon_bg="#faf5ff",
                on_back=lambda: self._page.go("/image"),
            ),
            self._build_body(),
        ]

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择图片", self._drop_zone),
                    self._section("水印设置", ft.Column(controls=[
                        self._text_field,
                        ft.Row(controls=[self._position, self._font_size], spacing=16),
                        ft.Row(controls=[
                            ft.Text("透明度", size=13, color="#455c7f"),
                            self._opacity,
                        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], spacing=12)),
                    self._progress,
                    self._result,
                    ft.Container(
                        content=self._run_btn,
                        padding=ft.padding.symmetric(vertical=8),
                    ),
                ],
                spacing=16,
            ),
            padding=ft.padding.symmetric(horizontal=40, vertical=8),
        )

    def _section(self, title: str, content: ft.Control) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        title, size=14, weight=ft.FontWeight.W_600,
                        color="#162f50", font_family="Manrope",
                    ),
                    content,
                ],
                spacing=10,
            ),
            bgcolor="#ffffff",
            border_radius=16,
            padding=ft.padding.all(20),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
        )

    def _build_run_button(self, label: str, icon: str) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color="#ffffff", size=18),
                    ft.Text(
                        label, size=16, color="#ffffff",
                        font_family="Manrope", weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#005f98",
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=["#005f98", "#2aa7ff"],
            ),
            border_radius=16,
            padding=ft.padding.symmetric(vertical=14),
            shadow=ft.BoxShadow(
                blur_radius=20, spread_radius=-5,
                color=ft.Colors.with_opacity(0.2, "#005f98"),
                offset=ft.Offset(0, 10),
            ),
            on_click=self._start,
            ink=True,
            opacity=0.5,
        )

    # ── 交互 ─────────────────────────────────────────────
    def _on_files(self, paths):
        self._input_files = paths
        self._run_btn.opacity = 1.0 if paths else 0.5
        self._run_btn.update()

    def _start(self, _):
        if not self._input_files or not self._text_field.value:
            if not self._text_field.value:
                self._text_field.error_text = "请输入水印文字"
                self._text_field.update()
            return
        self._text_field.error_text = None
        out_dir = settings_service.resolve_output_dir(self._input_files[0])
        try:
            font_size = max(8, int(self._font_size.value or "24"))
        except ValueError:
            font_size = 24
        kwargs = {
            "input_files": self._input_files,
            "output_dir": out_dir,
            "text": self._text_field.value,
            "position": self._position.value,
            "opacity": int(self._opacity.value),
            "font_size": font_size,
        }
        self._run_btn.opacity = 0.5
        self._run_btn.update()
        self._result.hide()
        self._progress.show(f"{len(self._input_files)} 张图片", "正在添加水印...")

        async def _run():
            await run_task(add_text_watermark, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d):
        self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "水印添加完成！")
        self._run_btn.opacity = 1.0
        self._run_btn.update()
        history_service.save_task("image", "watermark", result, input_desc=f"{len(self._input_files)} 张图片")

    def _cancel(self):
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress.hide()
        self._run_btn.opacity = 1.0
        self._run_btn.update()

    def _reset(self):
        self._input_files.clear()
        self._drop_zone.clear()
        self._drop_zone.update()
        self._run_btn.opacity = 0.5
        self._run_btn.update()
