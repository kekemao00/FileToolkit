"""视频压缩 — Figma 设计语言统一"""
import asyncio
from pathlib import Path

import flet as ft

from core.media.video import compress_video
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.sub_page_header import SubPageHeader
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class VideoCompressPage(ft.Column):
    """视频压缩：选文件 → 选压缩级别/分辨率 → 执行"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._input_files: list[Path] = []
        self._task: asyncio.Task | None = None

        self._drop_zone = DropZone(
            label="拖拽视频文件到此处",
            sublabel="支持 MP4 / AVI / MKV / MOV",
            allowed_extensions=["mp4", "avi", "mkv", "mov", "flv", "wmv", "webm"],
            on_files_selected=self._on_files,
            allow_multiple=True,
            icon=ft.Icons.COMPRESS,
        )
        self._drop_zone.set_page(page)

        self._quality = ft.RadioGroup(
            value="medium",
            content=ft.Row(controls=[
                ft.Radio(value="low", label="轻度（质量优先）"),
                ft.Radio(value="medium", label="标准"),
                ft.Radio(value="high", label="极限（体积优先）"),
            ], spacing=16),
        )
        self._resolution = ft.Dropdown(
            value="original",
            options=[
                ft.dropdown.Option("original", "保持原始"),
                ft.dropdown.Option("1080p", "1080p"),
                ft.dropdown.Option("720p", "720p"),
                ft.dropdown.Option("480p", "480p"),
            ],
            width=160, border_radius=12, label="分辨率",
        )

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)
        self._run_btn = self._build_run_button("开始压缩", ft.Icons.COMPRESS)

        self.controls = [
            SubPageHeader(
                title="视频压缩",
                icon=ft.Icons.COMPRESS,
                icon_color="#2563eb",
                icon_bg="#eff6ff",
                on_back=lambda: self._page.go("/media"),
            ),
            self._build_body(),
        ]

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择视频", self._drop_zone),
                    self._section("压缩设置", ft.Column(controls=[self._quality, self._resolution], spacing=12)),
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
        kwargs = {"input_files": self._input_files, "output_dir": out_dir, "quality": self._quality.value, "resolution": self._resolution.value}
        self._run_btn.opacity = 0.5
        self._run_btn.update()
        self._result.hide()
        self._progress.show(f"{len(self._input_files)} 个视频", "正在压缩...")

        async def _run():
            await run_task(compress_video, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d):
        self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "压缩完成！")
        self._run_btn.opacity = 1.0
        self._run_btn.update()
        history_service.save_task("media", "video_compress", result, input_desc=f"{len(self._input_files)} 个视频")

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
