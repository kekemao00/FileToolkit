"""音频提取 — Figma 设计语言统一"""
import asyncio
from pathlib import Path

import flet as ft

from core.media.audio import extract_audio
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.sub_page_header import SubPageHeader
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class AudioExtractPage(ft.Column):
    """从视频中提取音频轨道"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._input_file: Path | None = None
        self._task: asyncio.Task | None = None

        self._drop_zone = DropZone(
            label="拖拽视频文件到此处",
            sublabel="支持 MP4 / AVI / MKV / MOV / FLV",
            allowed_extensions=["mp4", "avi", "mkv", "mov", "flv", "wmv", "webm"],
            on_files_selected=self._on_file,
            allow_multiple=False,
            icon=ft.Icons.MUSIC_NOTE,
        )
        self._drop_zone.set_page(page)

        self._format = ft.Dropdown(
            value="mp3",
            options=[
                ft.dropdown.Option("mp3", "MP3"),
                ft.dropdown.Option("wav", "WAV"),
                ft.dropdown.Option("flac", "FLAC"),
                ft.dropdown.Option("aac", "AAC"),
            ],
            width=160, border_radius=12, label="输出格式",
        )

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)
        self._run_btn = self._build_run_button("提取音频", ft.Icons.MUSIC_NOTE)

        self.controls = [
            SubPageHeader(
                title="提取音频",
                icon=ft.Icons.MUSIC_NOTE,
                icon_color="#dc2626",
                icon_bg="#fef2f2",
                on_back=lambda: self._page.go("/media"),
            ),
            self._build_body(),
        ]

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择视频", self._drop_zone),
                    self._section("输出格式", self._format),
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
    def _on_file(self, paths):
        self._input_file = paths[0] if paths else None
        self._run_btn.opacity = 1.0 if self._input_file else 0.5
        self._run_btn.update()

    def _start(self, _):
        if not self._input_file:
            return
        out_dir = settings_service.resolve_output_dir(self._input_file)
        kwargs = {"input_file": self._input_file, "output_dir": out_dir, "audio_format": self._format.value}
        self._run_btn.opacity = 0.5
        self._run_btn.update()
        self._result.hide()
        self._progress.show(self._input_file.name, "正在提取音频...")

        async def _run():
            await run_task(extract_audio, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d):
        self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "音频提取完成！")
        self._run_btn.opacity = 1.0
        self._run_btn.update()
        history_service.save_task("media", "audio_extract", result, input_desc=self._input_file.name if self._input_file else "")

    def _cancel(self):
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress.hide()
        self._run_btn.opacity = 1.0
        self._run_btn.update()

    def _reset(self):
        self._input_file = None
        self._drop_zone.clear()
        self._drop_zone.update()
        self._run_btn.opacity = 0.5
        self._run_btn.update()
