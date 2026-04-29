"""PDF 万能编辑器 — 基于 Figma 设计稿 1:1 还原

布局：左侧主内容区（标题+拖拽区+文件列表） + 右侧参数面板
"""
import asyncio
from pathlib import Path

import flet as ft

from core.pdf.splitter import split_pdf
from core.pdf.merger import merge_pdf
from core.pdf.compressor import compress_pdf
from core.pdf.converter import pdf_to_docx
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


_FUNCTIONS = [
    {"label": "合并", "icon": ft.Icons.MERGE, "key": "merge"},
    {"label": "拆分", "icon": ft.Icons.CONTENT_CUT, "key": "split"},
    {"label": "压缩", "icon": ft.Icons.COMPRESS, "key": "compress"},
    {"label": "转word", "icon": ft.Icons.SWAP_HORIZ, "key": "to_word"},
]


class PdfPage(ft.Column):
    """PDF 万能编辑器 — 工作台布局"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._files: list[Path] = []
        self._selected_func = "merge"
        self._task: asyncio.Task | None = None

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)

        # 质量滑块
        self._quality_value = ft.Text("85%", size=12, weight=ft.FontWeight.BOLD, color="#005f98")
        self._quality_slider = ft.Slider(
            min=0, max=100, value=85, divisions=20,
            active_color="#005f98", inactive_color="#d5e3ff",
            on_change=self._on_quality_change,
            width=270,
        )

        # 页码范围
        self._range_field = ft.TextField(
            value="1-5, 8",
            border_radius=12,
            bgcolor="#d5e3ff",
            border_color="transparent",
            text_size=14,
            expand=True,
        )

        # 增强选项
        self._pwd_switch = ft.Switch(value=False, active_color="#005f98", inactive_thumb_color="#ffffff", inactive_track_color="#cbdeff")
        self._watermark_switch = ft.Switch(value=True, active_color="#005f98", inactive_thumb_color="#ffffff", inactive_track_color="#cbdeff")

        # 文件列表
        self._file_list = ft.Column(spacing=12)
        self._file_count = ft.Text("待处理文件 (0)", size=18, color="#162f50", font_family="Manrope")

        # 运行按钮
        self._run_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PLAY_ARROW, color="#ffffff", size=20),
                    ft.Text("立即处理 (0个文件)", size=18, color="#ffffff", font_family="Manrope"),
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
            padding=ft.padding.symmetric(vertical=16),
            shadow=ft.BoxShadow(
                blur_radius=25, spread_radius=-5,
                color=ft.Colors.with_opacity(0.2, "#005f98"),
                offset=ft.Offset(0, 20),
            ),
            on_click=self._start_task,
            ink=True,
        )

        # 功能按钮
        self._func_btns = []
        for f in _FUNCTIONS:
            active = f["key"] == self._selected_func
            btn = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(f["icon"], color="#ffffff" if active else "#455c7f", size=16),
                        ft.Text(f["label"], size=12, color="#ffffff" if active else "#455c7f", font_family="Manrope", text_align=ft.TextAlign.CENTER),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#005f98" if active else "#d5e3ff",
                border_radius=12,
                padding=ft.padding.symmetric(vertical=12, horizontal=20),
                on_click=lambda _, k=f["key"]: self._select_func(k),
                ink=True,
                data=f["key"],
                width=130,
                height=68,
                alignment=ft.Alignment(0, 0),
            )
            self._func_btns.append(btn)

        self.controls = [
            self._build_topbar(),
            ft.Row(
                controls=[
                    self._build_main_content(),
                    self._build_param_panel(),
                ],
                expand=True,
                spacing=0,
            ),
        ]

    def _build_topbar(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.SEARCH, color="#94a3b8", size=15),
                                            ft.Container(
                                                content=ft.Text("搜索功能或指令...", size=13, color="#94a3b8"),
                                                padding=ft.padding.only(left=8),
                                                expand=True,
                                            ),
                                        ],
                                        spacing=0,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    width=288, height=36,
                                    bgcolor=ft.Colors.with_opacity(0.5, "#f8fafc"),
                                    border=ft.border.all(1, ft.Colors.with_opacity(0.6, "#e2e8f0")),
                                    border_radius=9999,
                                    padding=ft.padding.symmetric(horizontal=15),
                                ),
                                ft.IconButton(icon=ft.Icons.NOTIFICATIONS_OUTLINED, icon_color="#475569", icon_size=20),
                                ft.IconButton(icon=ft.Icons.SETTINGS_OUTLINED, icon_color="#475569", icon_size=20,
                                              on_click=lambda _: self._page.go("/settings")),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=80,
            bgcolor=ft.Colors.with_opacity(0.8, "#ffffff"),
            blur=ft.Blur(12, 12),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#e2e8f0"))),
            shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.05, "#000000"), offset=ft.Offset(0, 1)),
            padding=ft.padding.only(left=40, right=24),
        )

    def _build_main_content(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    # 标题区
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text("PDF 万能编辑器", size=30, weight=ft.FontWeight.W_500, color="#005f98", font_family="Manrope"),
                                        ft.Text("处理、转换与加密您的数字化文档", size=16, color="#455c7f", font_family="Manrope"),
                                    ],
                                    spacing=4,
                                ),
                                ft.Container(expand=True),
                                ft.Row(
                                    controls=[
                                        ft.Container(
                                            content=ft.Icon(ft.Icons.GRID_VIEW, color="#005f98", size=16),
                                            bgcolor="#d5e3ff", border_radius=12,
                                            padding=ft.padding.all(8),
                                        ),
                                        ft.Container(
                                            content=ft.Icon(ft.Icons.VIEW_LIST, color="#005f98", size=16),
                                            bgcolor="#d5e3ff", border_radius=12,
                                            padding=ft.padding.all(8),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                        padding=ft.padding.only(left=32, right=32, top=32),
                    ),
                    # 拖拽区
                    self._build_drop_zone(),
                    # 文件列表
                    self._build_file_list(),
                    # 进度/结果
                    ft.Container(
                        content=ft.Column(controls=[self._progress, self._result], spacing=8),
                        padding=ft.padding.symmetric(horizontal=32),
                    ),
                ],
                spacing=24,
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
        )

    def _build_drop_zone(self) -> ft.Control:
        return ft.Container(
            content=ft.Stack(
                controls=[
                    # 渐变发光边框
                    ft.Container(
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                            colors=["#005f98", "#6b1ef3"],
                        ),
                        border_radius=16,
                        opacity=0.1,
                        blur=ft.Blur(4, 4),
                        expand=True,
                    ),
                    # 主体
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(ft.Icons.UPLOAD_FILE, color="#2aa7ff", size=30),
                                    width=64, height=64,
                                    bgcolor=ft.Colors.with_opacity(0.2, "#2aa7ff"),
                                    border_radius=9999,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Text("点击或将 PDF 文件拖拽至此处", size=20, color="#005f98", font_family="Manrope", text_align=ft.TextAlign.CENTER),
                                ft.Text("支持多文件合并，最大单文件限制 200MB", size=14, color="#455c7f", font_family="Manrope", text_align=ft.TextAlign.CENTER),
                                ft.Container(
                                    content=ft.Container(
                                        content=ft.Text("选择本地文件", size=16, color="#ffffff", font_family="Manrope", text_align=ft.TextAlign.CENTER),
                                        bgcolor="#005f98",
                                        border_radius=9999,
                                        padding=ft.padding.symmetric(horizontal=24, vertical=8),
                                        shadow=ft.BoxShadow(blur_radius=15, spread_radius=-3, color=ft.Colors.with_opacity(0.3, "#005f98"), offset=ft.Offset(0, 10)),
                                    ),
                                    padding=ft.padding.only(top=8),
                                    on_click=self._pick_files,
                                ),
                            ],
                            spacing=16,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor="#ffffff",
                        border=ft.border.all(2, "#2aa7ff"),
                        border_radius=16,
                        padding=ft.padding.symmetric(vertical=40, horizontal=2),
                        expand=True,
                    ),
                ],
            ),
            padding=ft.padding.symmetric(horizontal=32),
            height=220,
        )

    def _build_file_list(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self._file_count,
                            ft.Container(expand=True),
                            ft.TextButton("清空全部", style=ft.ButtonStyle(color="#005f98"), on_click=self._clear_files),
                        ],
                    ),
                    self._file_list,
                ],
                spacing=16,
            ),
            padding=ft.padding.symmetric(horizontal=32),
        )

    def _build_param_panel(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    # 标题
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SETTINGS, color="#005f98", size=18),
                            ft.Text("参数设置", size=20, color="#005f98", font_family="Manrope"),
                        ],
                        spacing=8,
                    ),
                    # 功能选择
                    self._section("选择功能", ft.Row(
                        controls=self._func_btns,
                        wrap=True, spacing=8, run_spacing=8,
                    )),
                    # 输出质量
                    self._section("输出质量", ft.Column(controls=[
                        ft.Row(controls=[ft.Container(expand=True), self._quality_value]),
                        self._quality_slider,
                        ft.Row(controls=[
                            ft.Text("体积优先", size=10, color="#455c7f"),
                            ft.Container(expand=True),
                            ft.Text("均衡", size=10, color="#455c7f"),
                            ft.Container(expand=True),
                            ft.Text("画质优先", size=10, color="#455c7f"),
                        ]),
                    ], spacing=8)),
                    # 页码范围
                    self._section("页码范围", ft.Row(controls=[
                        self._range_field,
                        ft.IconButton(icon=ft.Icons.REFRESH, icon_color="#005f98", icon_size=20),
                    ], spacing=8)),
                    # 增强选项
                    self._section("增强选项", ft.Column(controls=[
                        self._toggle_row("添加密码", ft.Icons.LOCK_OUTLINED, self._pwd_switch),
                        self._toggle_row("添加水印", ft.Icons.WATER_DROP_OUTLINED, self._watermark_switch),
                    ], spacing=12)),
                    # 弹性空间
                    ft.Container(expand=True),
                    # 处理按钮
                    self._run_btn,
                    ft.Text("预计耗时: 12秒 • 隐私保护已开启", size=10, color="#455c7f", font_family="Manrope", text_align=ft.TextAlign.CENTER),
                ],
                spacing=24,
                expand=True,
            ),
            width=320,
            bgcolor=ft.Colors.with_opacity(0.7, "#f4f6ff"),
            blur=ft.Blur(6, 6),
            border=ft.border.only(left=ft.BorderSide(1, "#d5e3ff")),
            padding=ft.padding.all(24),
        )

    def _section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(controls=[
            ft.Text(label.upper(), size=12, color="#455c7f", font_family="Manrope"),
            content,
        ], spacing=12)

    def _toggle_row(self, label: str, icon: str, switch: ft.Switch) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color="#162f50", size=16),
                    ft.Text(label, size=14, color="#162f50", font_family="Manrope"),
                    ft.Container(expand=True),
                    switch,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.5, "#ffffff"),
            border_radius=12,
            padding=ft.padding.all(12),
        )

    def _select_func(self, key: str) -> None:
        self._selected_func = key
        for btn in self._func_btns:
            active = btn.data == key
            btn.bgcolor = "#005f98" if active else "#d5e3ff"
            col = btn.content
            col.controls[0].color = "#ffffff" if active else "#455c7f"
            col.controls[1].color = "#ffffff" if active else "#455c7f"
        self.update()

    def _on_quality_change(self, e) -> None:
        self._quality_value.value = f"{int(e.control.value)}%"
        self._quality_value.update()

    def _pick_files(self, _) -> None:
        self._page.run_task(self._pick_files_async)

    async def _pick_files_async(self) -> None:
        picker = ft.FilePicker()
        self._page.overlay.append(picker)
        self._page.update()
        files = await picker.pick_files(
            dialog_title="选择 PDF 文件",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"],
            allow_multiple=True,
        )
        self._page.overlay.remove(picker)
        if not files:
            self._page.update()
            return
        paths = [Path(f.path) for f in files if f.path]
        if paths:
            self._files.extend(paths)
            self._rebuild_file_list()
        self._page.update()

    def _rebuild_file_list(self) -> None:
        self._file_list.controls.clear()
        self._file_count.value = f"待处理文件 ({len(self._files)})"
        for f in self._files:
            try:
                size = f.stat().st_size
                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            except OSError:
                size_str = "?"
            item = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.PICTURE_AS_PDF, color="#dc2626", size=20),
                            width=48, height=48, bgcolor="#fee2e2", border_radius=8, alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(controls=[
                            ft.Text(f.name, size=16, weight=ft.FontWeight.BOLD, color="#162f50", font_family="Manrope", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(size_str, size=12, color="#455c7f"),
                        ], spacing=2, expand=True),
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#ebf1ff",
                border_radius=12,
                padding=ft.padding.all(16),
                height=80,
            )
            self._file_list.controls.append(item)
        # 更新按钮文字
        row = self._run_btn.content
        row.controls[1].value = f"立即处理 ({len(self._files)}个文件)"
        self.update()

    def _clear_files(self, _) -> None:
        self._files.clear()
        self._rebuild_file_list()

    def _start_task(self, _) -> None:
        if not self._files:
            return
        out_dir = settings_service.resolve_output_dir(self._files[0])
        func_map = {"merge": merge_pdf, "split": split_pdf, "compress": compress_pdf, "to_word": pdf_to_docx}
        fn = func_map.get(self._selected_func, merge_pdf)
        kwargs = {"input_files" if self._selected_func == "merge" else "input_file": self._files if self._selected_func == "merge" else self._files[0], "output_dir": out_dir}
        self._progress.show(f"{len(self._files)} 个文件", f"正在{self._selected_func}...")
        self._result.hide()

        async def _run():
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d):
        self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "处理完成！")
        history_service.save_task("pdf", self._selected_func, result, input_desc=f"{len(self._files)} 个文件")

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress.hide()

    def _reset(self) -> None:
        self._files.clear()
        self._rebuild_file_list()
