"""压缩解压页 — Tab 切换布局"""
import asyncio
from pathlib import Path

import flet as ft

from core.archive.handler import compress, extract
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class ArchivePage(ft.Column):
    """压缩解压页：Tab 切换压缩/解压两种模式"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._task: asyncio.Task | None = None

        # ── 压缩 Tab 组件 ──
        self._compress_drop = DropZone(
            label="拖拽文件或文件夹到此处",
            sublabel="支持多选，点击选择文件",
            on_files_selected=self._on_compress_files,
            allow_multiple=True,
            icon=ft.Icons.FOLDER_ZIP,
        )
        self._compress_drop.set_page(page)

        self._compress_format = ft.Dropdown(
            value="zip",
            options=[
                ft.dropdown.Option("zip", "ZIP"),
                ft.dropdown.Option("7z", "7Z"),
                ft.dropdown.Option("tar.gz", "TAR.GZ"),
            ],
            width=160,
            border_radius=8,
            label="压缩格式",
        )
        self._compress_level = ft.Dropdown(
            value="normal",
            options=[
                ft.dropdown.Option("fast", "快速（体积较大）"),
                ft.dropdown.Option("normal", "标准"),
                ft.dropdown.Option("max", "最大压缩（较慢）"),
            ],
            width=200,
            border_radius=8,
            label="压缩级别",
        )
        self._compress_progress = ProgressCard(on_cancel=self._cancel)
        self._compress_result = ResultCard(on_reset=self._reset_compress)
        self._compress_btn = ft.FilledButton(
            "开始压缩", icon=ft.Icons.COMPRESS, on_click=self._start_compress, disabled=True,
        )
        self._compress_files: list[Path] = []

        # ── 解压 Tab 组件 ──
        self._extract_drop = DropZone(
            label="拖拽压缩包到此处",
            sublabel="支持 ZIP / 7Z / RAR / TAR.GZ",
            allowed_extensions=["zip", "7z", "rar", "tar", "gz", "bz2", "xz"],
            on_files_selected=self._on_extract_file,
            allow_multiple=False,
            icon=ft.Icons.UNARCHIVE,
        )
        self._extract_drop.set_page(page)

        self._extract_progress = ProgressCard(on_cancel=self._cancel)
        self._extract_result = ResultCard(on_reset=self._reset_extract)
        self._extract_btn = ft.FilledButton(
            "开始解压", icon=ft.Icons.UNARCHIVE, on_click=self._start_extract, disabled=True,
        )
        self._extract_file: Path | None = None

        # ── Tab 切换 ──
        self._tab_index = 0
        self._tab_content = ft.Column(spacing=16)
        self._update_tab_content()

        self.controls = [
            self._build_header(),
            self._build_tabs(),
            ft.Container(
                content=self._tab_content,
                padding=ft.padding.symmetric(horizontal=40, vertical=8),
            ),
        ]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.FOLDER_ZIP, color="#2563eb", size=24),
                        width=48,
                        height=48,
                        bgcolor="#eff6ff",
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "压缩解压",
                                size=24,
                                weight=ft.FontWeight.W_600,
                                color="#162f50",
                                font_family="Manrope",
                            ),
                            ft.Text(
                                "极速打包与安全解压文件",
                                size=14,
                                color="#455c7f",
                                font_family="Manrope",
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=40, top=32, right=40, bottom=16),
        )

    def _build_tabs(self) -> ft.Control:
        def _on_tab(idx):
            def handler(_):
                self._tab_index = idx
                self._update_tab_content()
                self._update_tab_style()
                self.update()
            return handler

        self._tab_btns = []
        for i, (label, icon) in enumerate([("压缩", ft.Icons.COMPRESS), ("解压", ft.Icons.UNARCHIVE)]):
            btn = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=18, color="#005f98" if i == 0 else "#455c7f"),
                        ft.Text(label, size=14, color="#005f98" if i == 0 else "#455c7f", font_family="Manrope", weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                bgcolor="#dee9ff" if i == 0 else "transparent",
                border_radius=10,
                padding=ft.padding.symmetric(horizontal=24, vertical=10),
                on_click=_on_tab(i),
                ink=True,
                animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            )
            self._tab_btns.append(btn)

        return ft.Container(
            content=ft.Row(controls=self._tab_btns, spacing=8),
            bgcolor="#f1f5f9",
            border_radius=12,
            padding=ft.padding.all(4),
            margin=ft.margin.symmetric(horizontal=40),
        )

    def _update_tab_style(self) -> None:
        for i, btn in enumerate(self._tab_btns):
            active = i == self._tab_index
            btn.bgcolor = "#dee9ff" if active else "transparent"
            row = btn.content
            row.controls[0].color = "#005f98" if active else "#455c7f"
            row.controls[1].color = "#005f98" if active else "#455c7f"

    def _update_tab_content(self) -> None:
        if self._tab_index == 0:
            self._tab_content.controls = [
                self._section("选择文件", self._compress_drop),
                self._section("压缩设置", ft.Row(controls=[self._compress_format, self._compress_level], spacing=16)),
                self._compress_progress,
                self._compress_result,
                ft.Container(content=self._compress_btn, alignment=ft.Alignment(0, 0), padding=ft.padding.symmetric(vertical=8)),
            ]
        else:
            self._tab_content.controls = [
                self._section("选择压缩包", self._extract_drop),
                self._extract_progress,
                self._extract_result,
                ft.Container(content=self._extract_btn, alignment=ft.Alignment(0, 0), padding=ft.padding.symmetric(vertical=8)),
            ]

    def _section(self, title: str, content: ft.Control) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(title, size=14, weight=ft.FontWeight.W_600, color="#162f50", font_family="Manrope"),
                    content,
                ],
                spacing=10,
            ),
            bgcolor="#ffffff",
            border_radius=16,
            padding=ft.padding.all(20),
            shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.05, "#000000"), offset=ft.Offset(0, 1)),
        )

    # ── 压缩交互 ──
    def _on_compress_files(self, paths: list[Path]) -> None:
        self._compress_files = paths
        self._compress_btn.disabled = not paths
        self._compress_btn.update()

    def _start_compress(self, _) -> None:
        if not self._compress_files:
            return
        out_dir = settings_service.resolve_output_dir(self._compress_files[0])
        kwargs = {
            "input_files": self._compress_files,
            "output_dir": out_dir,
            "format": self._compress_format.value,
            "level": self._compress_level.value,
        }
        self._compress_btn.disabled = True
        self._compress_result.hide()
        self._compress_progress.show(f"{len(self._compress_files)} 个文件", "正在压缩...")

        async def _run():
            await run_task(compress, kwargs, self._on_progress_compress, self._on_complete_compress)
        self._task = self._page.run_task(_run)

    def _on_progress_compress(self, current, total, desc):
        self._compress_progress.update_progress(current, total, desc)

    def _on_complete_compress(self, result):
        self._compress_progress.hide()
        self._compress_result.show(result, "压缩完成！")
        self._compress_btn.disabled = False
        self._compress_btn.update()
        history_service.save_task("archive", "compress", result, input_desc=f"{len(self._compress_files)} 个文件")

    def _reset_compress(self) -> None:
        self._compress_files.clear()
        self._compress_drop.clear()
        self._compress_drop.update()
        self._compress_btn.disabled = True
        self._compress_btn.update()

    # ── 解压交互 ──
    def _on_extract_file(self, paths: list[Path]) -> None:
        self._extract_file = paths[0] if paths else None
        self._extract_btn.disabled = self._extract_file is None
        self._extract_btn.update()

    def _start_extract(self, _) -> None:
        if not self._extract_file:
            return
        out_dir = settings_service.resolve_output_dir(self._extract_file)
        kwargs = {"input_file": self._extract_file, "output_dir": out_dir}
        self._extract_btn.disabled = True
        self._extract_result.hide()
        self._extract_progress.show(self._extract_file.name, "正在解压...")

        async def _run():
            await run_task(extract, kwargs, self._on_progress_extract, self._on_complete_extract)
        self._task = self._page.run_task(_run)

    def _on_progress_extract(self, current, total, desc):
        self._extract_progress.update_progress(current, total, desc)

    def _on_complete_extract(self, result):
        self._extract_progress.hide()
        self._extract_result.show(result, "解压完成！")
        self._extract_btn.disabled = False
        self._extract_btn.update()
        history_service.save_task("archive", "extract", result, input_desc=self._extract_file.name if self._extract_file else "")

    def _reset_extract(self) -> None:
        self._extract_file = None
        self._extract_drop.clear()
        self._extract_drop.update()
        self._extract_btn.disabled = True
        self._extract_btn.update()

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._compress_progress.hide()
        self._extract_progress.hide()
        self._compress_btn.disabled = False
        self._extract_btn.disabled = False
        self._compress_btn.update()
        self._extract_btn.update()
