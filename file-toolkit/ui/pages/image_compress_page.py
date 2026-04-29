"""图片批量压缩操作页"""
import asyncio
from pathlib import Path

import flet as ft

from core.image.compressor import compress_images
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class ImageCompressPage(ft.Column):
    """图片压缩：选文件 → 选压缩级别 → 执行"""

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
            icon=ft.Icons.COMPRESS,
        )
        self._drop_zone.set_page(page)

        self._level = ft.RadioGroup(
            value="medium",
            content=ft.Row(controls=[
                ft.Radio(value="low", label="轻度（质量优先）"),
                ft.Radio(value="medium", label="标准"),
                ft.Radio(value="high", label="极限（体积优先）"),
            ], spacing=16),
        )

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)
        self._run_btn = ft.FilledButton("开始压缩", icon=ft.Icons.COMPRESS, on_click=self._start, disabled=True)

        self.controls = [self._build_header(), self._build_body()]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: self._page.go("/image"), icon_color="#455c7f"),
                    ft.Container(
                        content=ft.Icon(ft.Icons.COMPRESS, color="#16a34a", size=20),
                        width=40, height=40, bgcolor="#f0fdf4", border_radius=10, alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text("图片压缩", size=20, weight=ft.FontWeight.W_600, color="#162f50", font_family="Manrope"),
                ],
                spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=28, top=24, right=40, bottom=16),
        )

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择图片", self._drop_zone),
                    self._section("压缩级别", self._level),
                    self._progress, self._result,
                    ft.Container(content=self._run_btn, alignment=ft.Alignment(0, 0), padding=ft.padding.symmetric(vertical=8)),
                ],
                spacing=16,
            ),
            padding=ft.padding.symmetric(horizontal=40, vertical=8),
        )

    def _section(self, title, content):
        return ft.Container(
            content=ft.Column(controls=[
                ft.Text(title, size=14, weight=ft.FontWeight.W_600, color="#162f50", font_family="Manrope"), content,
            ], spacing=10),
            bgcolor="#ffffff", border_radius=16, padding=ft.padding.all(20),
            shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.05, "#000000"), offset=ft.Offset(0, 1)),
        )

    def _on_files(self, paths):
        self._input_files = paths
        self._run_btn.disabled = not paths
        self._run_btn.update()

    def _start(self, _):
        if not self._input_files:
            return
        out_dir = settings_service.resolve_output_dir(self._input_files[0])
        kwargs = {"input_files": self._input_files, "output_dir": out_dir, "level": self._level.value}
        self._run_btn.disabled = True
        self._result.hide()
        self._progress.show(f"{len(self._input_files)} 张图片", "正在压缩...")
        async def _run():
            await run_task(compress_images, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d): self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "压缩完成！")
        self._run_btn.disabled = False
        self._run_btn.update()
        history_service.save_task("image", "compress", result, input_desc=f"{len(self._input_files)} 张图片")

    def _cancel(self):
        if self._task and not self._task.done(): self._task.cancel()
        self._progress.hide()
        self._run_btn.disabled = False
        self._run_btn.update()

    def _reset(self):
        self._input_files.clear()
        self._drop_zone.clear()
        self._drop_zone.update()
        self._run_btn.disabled = True
        self._run_btn.update()
