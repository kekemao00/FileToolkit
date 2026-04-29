"""视频剪切操作页"""
import asyncio
from pathlib import Path

import flet as ft

from core.media.video import cut_video
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class VideoCutPage(ft.Column):
    """视频剪辑：选文件 → 设置起止时间 → 执行"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._input_file: Path | None = None
        self._task: asyncio.Task | None = None

        self._drop_zone = DropZone(
            label="拖拽视频文件到此处",
            sublabel="支持 MP4 / AVI / MKV / MOV",
            allowed_extensions=["mp4", "avi", "mkv", "mov", "flv", "wmv", "webm"],
            on_files_selected=self._on_file,
            allow_multiple=False,
            icon=ft.Icons.CONTENT_CUT,
        )
        self._drop_zone.set_page(page)

        self._start_time = ft.TextField(
            value="00:00:00",
            label="开始时间",
            hint_text="HH:MM:SS",
            width=140,
            border_radius=8,
        )
        self._end_time = ft.TextField(
            value="00:01:00",
            label="结束时间",
            hint_text="HH:MM:SS",
            width=140,
            border_radius=8,
        )

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)
        self._run_btn = ft.FilledButton("开始剪辑", icon=ft.Icons.CONTENT_CUT, on_click=self._start, disabled=True)

        self.controls = [self._build_header(), self._build_body()]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: self._page.go("/media"), icon_color="#455c7f"),
                    ft.Container(
                        content=ft.Icon(ft.Icons.CONTENT_CUT, color="#16a34a", size=20),
                        width=40, height=40, bgcolor="#f0fdf4", border_radius=10, alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text("视频剪辑", size=20, weight=ft.FontWeight.W_600, color="#162f50", font_family="Manrope"),
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
                    self._section("剪辑范围", ft.Column(controls=[
                        ft.Row(controls=[self._start_time, ft.Text("→", size=16, color="#455c7f"), self._end_time], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text("格式：HH:MM:SS（如 00:01:30 表示 1 分 30 秒）", size=11, color="#94a3b8", font_family="Manrope"),
                    ], spacing=8)),
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
        kwargs = {
            "input_file": self._input_file,
            "output_dir": out_dir,
            "start_time": self._start_time.value or "00:00:00",
            "end_time": self._end_time.value or "00:01:00",
        }
        self._run_btn.disabled = True
        self._result.hide()
        self._progress.show(self._input_file.name, "正在剪辑...")
        async def _run():
            await run_task(cut_video, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d): self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "剪辑完成！")
        self._run_btn.disabled = False
        self._run_btn.update()
        history_service.save_task("media", "video_cut", result, input_desc=self._input_file.name if self._input_file else "")

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
