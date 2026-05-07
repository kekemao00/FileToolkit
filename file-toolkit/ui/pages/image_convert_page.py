"""图片格式转换 — Figma 设计语言统一"""
import asyncio
from pathlib import Path

import flet as ft

from core.image.converter import convert_image
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.sub_page_header import SubPageHeader
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class ImageConvertPage(ft.Column):
    """图片格式转换：选文件 → 选目标格式 → 执行"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._input_files: list[Path] = []
        self._task: asyncio.Task | None = None

        self._drop_zone = DropZone(
            label="拖拽图片文件到此处",
            sublabel="支持 PNG / JPG / WebP / BMP / TIFF，可多选",
            allowed_extensions=["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"],
            on_files_selected=self._on_files,
            allow_multiple=True,
            icon=ft.Icons.IMAGE,
        )
        self._drop_zone.set_page(page)

        self._format = ft.Dropdown(
            value="webp",
            options=[
                ft.dropdown.Option("png", "PNG"),
                ft.dropdown.Option("jpg", "JPG"),
                ft.dropdown.Option("webp", "WebP"),
                ft.dropdown.Option("bmp", "BMP"),
            ],
            width=160, border_radius=12, label="目标格式",
        )
        self._quality = ft.Slider(min=10, max=100, value=85, divisions=9, label="{value}%", width=300)

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)
        self._run_btn = self._build_run_button("开始转换", ft.Icons.TRANSFORM)

        self.controls = [
            SubPageHeader(
                title="图片格式转换",
                icon=ft.Icons.TRANSFORM,
                icon_color="#2563eb",
                icon_bg="#eff6ff",
                on_back=lambda: self._page.go("/image"),
            ),
            self._build_body(),
        ]

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择图片", self._drop_zone),
                    self._section("转换设置", ft.Column(controls=[
                        self._format,
                        ft.Row(controls=[
                            ft.Text("质量", size=13, color="#455c7f"),
                            self._quality,
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
                        color="#162f50", font_family="42dot Sans",
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
                        font_family="42dot Sans", weight=ft.FontWeight.W_500,
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
        if not self._input_files:
            return
        out_dir = settings_service.resolve_output_dir(self._input_files[0])
        kwargs = {"input_files": self._input_files, "output_dir": out_dir, "target_format": self._format.value, "quality": int(self._quality.value)}
        self._run_btn.opacity = 0.5
        self._run_btn.update()
        self._result.hide()
        self._progress.show(f"{len(self._input_files)} 张图片", "正在转换...")

        async def _run():
            await run_task(convert_image, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d):
        self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "转换完成！")
        self._run_btn.opacity = 1.0
        self._run_btn.update()
        history_service.save_task("image", "convert", result, input_desc=f"{len(self._input_files)} 张图片")

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
