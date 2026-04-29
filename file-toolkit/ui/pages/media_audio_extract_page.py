"""音频提取操作页"""
import asyncio
from pathlib import Path

import flet as ft

from core.media.audio import extract_audio
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
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
            width=160, border_radius=8, label="输出格式",
        )

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)
        self._run_btn = ft.FilledButton("提取音频", icon=ft.Icons.MUSIC_NOTE, on_click=self._start, disabled=True)

        self.controls = [self._build_header(), self._build_body()]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: self._page.go("/media"), icon_color="#455c7f"),
                    ft.Container(
                        content=ft.Icon(ft.Icons.MUSIC_NOTE, color="#dc2626", size=20),
                        width=40, height=40, bgcolor="#fef2f2", border_radius=10, alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text("提取音频", size=20, weight=ft.FontWeight.W_600, color="#162f50", font_family="Manrope"),
                ],
                spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=28, top=24, right=40, bottom=16),
        )

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择视频", self._drop_zone),
                    self._section("输出格式", self._format),
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

    def _on_file(self, paths):
        self._input_file = paths[0] if paths else None
        self._run_btn.disabled = self._input_file is None
        self._run_btn.update()

    def _start(self, _):
        if not self._input_file:
            return
        out_dir = settings_service.resolve_output_dir(self._input_file)
        kwargs = {"input_file": self._input_file, "output_dir": out_dir, "audio_format": self._format.value}
        self._run_btn.disabled = True
        self._result.hide()
        self._progress.show(self._input_file.name, "正在提取音频...")
        async def _run():
            await run_task(extract_audio, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d): self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "音频提取完成！")
        self._run_btn.disabled = False
        self._run_btn.update()
        history_service.save_task("media", "audio_extract", result, input_desc=self._input_file.name if self._input_file else "")

    def _cancel(self):
        if self._task and not self._task.done(): self._task.cancel()
        self._progress.hide()
        self._run_btn.disabled = False
        self._run_btn.update()

    def _reset(self):
        self._input_file = None
        self._drop_zone.clear()
        self._drop_zone.update()
        self._run_btn.disabled = True
        self._run_btn.update()
