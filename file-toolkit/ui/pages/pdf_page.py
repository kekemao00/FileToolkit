"""PDF 万能编辑器 — 基于 Figma 设计稿 1:1 还原

布局：左侧主内容区（标题+拖拽区+文件列表） + 右侧参数面板
"""
import asyncio
import subprocess
import sys
import time
from pathlib import Path

import flet as ft

from core.models import TaskResult
from core.pdf.compressor import compress_pdf
from core.pdf.converter import pdf_to_docx
from core.pdf.merger import merge_pdf
from core.pdf.splitter import split_pdf
from services import history_service, settings_service
from services.task_service import run_task
from ui.utils import show_toast

_FUNCTIONS = [
    {"label": "合并", "desc": "PDF 合并与优化", "icon": ft.Icons.MERGE, "key": "merge",
     "color": "#005f98", "bg": "#d5e3ff"},
    {"label": "拆分", "desc": "按页码范围拆分", "icon": ft.Icons.CONTENT_CUT, "key": "split",
     "color": "#d97706", "bg": "#fef3c7"},
    {"label": "压缩", "desc": "输出质量 85%", "icon": ft.Icons.COMPRESS, "key": "compress",
     "color": "#059669", "bg": "#d1fae5"},
    {"label": "转Office", "desc": "PDF 转 Office", "icon": ft.Icons.SWAP_HORIZ, "key": "to_word",
     "color": "#7c3aed", "bg": "#ede9fe"},
]

# slider 0-100 → compress_pdf quality 枚举
def _quality_level(v: float) -> str:
    if v >= 70:
        return "high"
    if v >= 40:
        return "medium"
    return "low"

# "1-5, 6-10" → ["1-5", "6-10"]
def _parse_ranges(text: str) -> list[str]:
    return [s.strip() for s in text.split(",") if s.strip()]


class PdfPage(ft.Column):
    """PDF 万能编辑器 — 工作台布局"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._files: list[Path] = []
        self._active_files: list[Path] = []
        self._page_count_cache: dict[Path, int | None] = {}
        self._selected_func = "merge"
        self._task: asyncio.Task | None = None
        self._current_result: TaskResult | None = None

        self._progress_title = ft.Text(
            "", size=30, weight=ft.FontWeight.W_600, color="#162f50",
            font_family="42dot Sans",
        )
        self._progress_pct = ft.Text(
            "0%", size=16, weight=ft.FontWeight.BOLD, color="#005f98",
            font_family="42dot Sans",
        )
        self._progress_bar = ft.ProgressBar(
            value=0, color="#005f98", bgcolor="#d5e3ff", bar_height=8,
            border_radius=4,
        )
        self._progress_file_rows = ft.Column(spacing=8)
        self._progress_cancel_btn = ft.FilledButton(
            "全部取消",
            style=ft.ButtonStyle(bgcolor="#be123c", color="#ffffff"),
            on_click=lambda _: self._cancel(),
        )

        # 完成状态组件
        self._result_title = ft.Text(
            "", size=30, weight=ft.FontWeight.W_600, color="#162f50",
            font_family="42dot Sans",
        )
        self._result_pct = ft.Text(
            "100%", size=16, weight=ft.FontWeight.BOLD, color="#007276",
            font_family="42dot Sans",
        )
        self._result_bar = ft.ProgressBar(
            value=1, color="#007276", bgcolor="#d5e3ff", bar_height=8,
            border_radius=4,
        )
        self._result_file_rows = ft.Column(spacing=8)
        self._result_open_btn = ft.FilledButton(
            "打开文件夹",
            style=ft.ButtonStyle(bgcolor="#005f98", color="#ffffff"),
            on_click=self._open_output_folder,
        )
        self._result_retry_btn = ft.TextButton(
            "重试",
            style=ft.ButtonStyle(color="#005f98"),
            on_click=lambda e: self._start_task(e),
        )
        self._result_reset_btn = ft.TextButton(
            "继续处理",
            style=ft.ButtonStyle(color="#455c7f"),
            on_click=lambda _: self._reset(),
        )
        self._result_summary = ft.Text(
            "", size=14, color="#162f50", weight=ft.FontWeight.W_600,
            font_family="42dot Sans",
        )
        self._result_duration = ft.Text(
            "", size=12, color="#455c7f", font_family="42dot Sans",
        )
        self._output_dir: Path | None = None

        # 质量滑块
        self._quality_value = ft.Text("85%", size=12, weight=ft.FontWeight.BOLD, color="#005f98")
        self._quality_slider = ft.Slider(
            min=0, max=100, value=85, divisions=20,
            active_color="#005f98", inactive_color="#d5e3ff",
            on_change=self._on_quality_change,
            width=270,
        )

        # 页码范围（支持 "起始-结束" 和单页码，如 "1-5, 8"）
        self._range_field = ft.TextField(
            value="1-5, 8",
            border_radius=12,
            bgcolor="#d5e3ff",
            border_color="transparent",
            text_size=14,
            expand=True,
        )

        # 增强选项（功能尚未接入，disabled 防止误操作）
        self._pwd_switch = ft.Switch(value=False, active_color="#005f98", inactive_thumb_color="#ffffff", inactive_track_color="#cbdeff", disabled=True)
        self._watermark_switch = ft.Switch(value=True, active_color="#005f98", inactive_thumb_color="#ffffff", inactive_track_color="#cbdeff", disabled=True)

        # 文件列表
        self._file_list = ft.Column(spacing=0)
        self._file_count = ft.Text("待处理文件 (0)", size=18, color="#162f50", font_family="42dot Sans")

        # 运行按钮
        self._run_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PLAY_ARROW, color="#ffffff", size=20),
                    ft.Text("立即处理 (0个文件)", size=18, color="#ffffff", font_family="42dot Sans"),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#005f98",
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=["#005f98", "#00a3ff"],
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
            opacity=0.4,  # 初始无文件时视觉禁用
        )

        # 功能卡片（2×2 网格）
        self._func_btns = []
        for idx, f in enumerate(_FUNCTIONS):
            active = f["key"] == self._selected_func
            icon_block = ft.Container(
                content=ft.Icon(f["icon"], color="#ffffff" if active else f["color"], size=28),
                width=56, height=56,
                bgcolor=f["color"] if active else f["bg"],
                border_radius=14,
                alignment=ft.Alignment(0, 0),
            )
            badge = ft.Container(
                content=ft.Text(
                    str(idx + 1), size=10, color=f["color"] if active else "#ffffff",
                    weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER,
                ),
                width=20, height=20,
                bgcolor="#ffffff" if active else "#005f98",
                border_radius=9999,
                alignment=ft.Alignment(0, 0),
                right=0, top=0,
            )
            icon_stack = ft.Stack(controls=[icon_block, badge], width=60, height=60)
            btn = ft.Container(
                content=ft.Column(
                    controls=[
                        icon_stack,
                        ft.Text(
                            f["label"], size=13, weight=ft.FontWeight.W_600,
                            color="#ffffff" if active else "#162f50",
                            font_family="42dot Sans",
                        ),
                        ft.Text(
                            f["desc"], size=11,
                            color=ft.Colors.with_opacity(0.7, "#ffffff") if active else "#455c7f",
                            font_family="Plus Jakarta Sans",
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                ),
                bgcolor="#005f98" if active else "#ffffff",
                border=ft.border.all(2, "#005f98" if active else "#e2e8f0"),
                border_radius=14,
                padding=ft.padding.all(14),
                on_click=lambda _, k=f["key"]: self._select_func(k),
                ink=True,
                data=f["key"],
                expand=True,
                shadow=ft.BoxShadow(
                    blur_radius=4 if active else 2,
                    color=ft.Colors.with_opacity(0.08 if active else 0.04, "#000000"),
                    offset=ft.Offset(0, 2),
                ),
            )
            self._func_btns.append(btn)

        self._main_content = self._build_main_content()
        self._build_param_panel()

        # 响应式断点
        self._NARROW_BREAKPOINT = 800
        self._is_narrow = None  # 强制首次 _apply_responsive_layout 生效
        self._body_container: ft.Control = ft.Container()  # 占位，立即被替换
        self._topbar = self._build_topbar()

        self.controls = [self._topbar, self._body_container]
        self._apply_responsive_layout(update=False)

        self._prev_on_resize = None

    def did_mount(self) -> None:
        self._prev_on_resize = self._page.on_resize
        self._page.on_resize = self._on_page_resized

    def will_unmount(self) -> None:
        if self._page.on_resize == self._on_page_resized:
            self._page.on_resize = self._prev_on_resize

    def _build_topbar(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                # 搜索框：功能未上线，降低视觉权重
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
                                    width=288, height=54,
                                    bgcolor=ft.Colors.with_opacity(0.5, "#f8fafc"),
                                    border=ft.border.all(1, ft.Colors.with_opacity(0.6, "#e2e8f0")),
                                    border_radius=9999,
                                    padding=ft.padding.symmetric(horizontal=15),
                                    opacity=0.45,
                                    tooltip="搜索",
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                                    icon_color="#475569", icon_size=20,
                                    disabled=True,
                                    opacity=0.45,
                                    tooltip="通知",
                                ),
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
            bgcolor="#ffffff",
            shadow=ft.BoxShadow(
                blur_radius=2, color=ft.Colors.with_opacity(0.05, "#000000"), offset=ft.Offset(0, 1),
            ),
            padding=ft.padding.symmetric(horizontal=32),
        )

    def _build_main_content(self) -> ft.Control:
        self._workspace_view = self._build_workspace_view()
        self._processing_view = self._build_processing_view()
        self._complete_view = self._build_complete_view()
        self._processing_view.visible = False
        self._complete_view.visible = False

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._workspace_view,
                    self._processing_view,
                    self._complete_view,
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )

    def _build_workspace_view(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "PDF 万能编辑器", size=30,
                                            weight=ft.FontWeight.W_500,
                                            color="#005f98",
                                            font_family="42dot Sans",
                                        ),
                                        ft.Text(
                                            "处理、转换与加密您的数字化文档",
                                            size=16, color="#455c7f",
                                            font_family="42dot Sans",
                                        ),
                                    ],
                                    spacing=4,
                                ),
                                ft.Container(expand=True),
                                ft.Row(
                                    controls=[
                                        ft.Container(
                                            content=ft.Icon(
                                                ft.Icons.GRID_VIEW,
                                                color="#005f98",
                                                size=16,
                                            ),
                                            bgcolor="#d5e3ff",
                                            border_radius=12,
                                            padding=ft.padding.all(8),
                                            opacity=0.45,
                                            tooltip="网格视图",
                                        ),
                                        ft.Container(
                                            content=ft.Icon(
                                                ft.Icons.VIEW_LIST,
                                                color="#005f98",
                                                size=16,
                                            ),
                                            bgcolor="#d5e3ff",
                                            border_radius=12,
                                            padding=ft.padding.all(8),
                                            opacity=0.45,
                                            tooltip="列表视图",
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                        padding=ft.padding.only(left=32, right=32, top=32),
                    ),
                    self._build_drop_zone(),
                    self._build_file_list(),
                ],
                spacing=24,
            ),
        )

    def _build_drop_zone(self) -> ft.Control:
        dash_color = ft.Colors.with_opacity(0.3, "#005f98")
        dash_segment = lambda: ft.Container(  # noqa: E731
            width=16,
            height=2,
            bgcolor=dash_color,
            border_radius=9999,
        )
        dash_column = lambda: ft.Container(  # noqa: E731
            width=2,
            height=16,
            bgcolor=dash_color,
            border_radius=9999,
        )
        top_dash = ft.Row(
            controls=[dash_segment() for _ in range(30)],
            spacing=8,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        side_dash = ft.Column(
            controls=[dash_column() for _ in range(10)],
            spacing=8,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        body = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.UPLOAD_FILE, color="#005f98", size=40),
                        width=72,
                        height=72,
                        bgcolor=ft.Colors.with_opacity(0.12, "#005f98"),
                        border_radius=9999,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "拖拽 PDF 文件到此处",
                        size=18,
                        color="#005f98",
                        font_family="42dot Sans",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "或点击选择文件",
                        size=14,
                        color="#455c7f",
                        font_family="42dot Sans",
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#F4F6FF",
            padding=ft.padding.symmetric(vertical=36, horizontal=24),
            expand=True,
            on_click=self._pick_files,
            ink=True,
        )
        self._drop_zone_body = ft.Container(
            content=ft.Stack(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                top_dash,
                                ft.Row(
                                    controls=[
                                        side_dash,
                                        ft.Container(expand=True),
                                        side_dash,
                                    ],
                                    expand=True,
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                top_dash,
                            ],
                            spacing=10,
                            expand=True,
                        ),
                        padding=ft.padding.all(12),
                        ignore_interactions=True,
                        expand=True,
                    ),
                    ft.Container(
                        content=body,
                        expand=True,
                        padding=ft.padding.all(0),
                    ),
                ],
            ),
            border_radius=20,
            bgcolor="#F4F6FF",
            on_hover=self._on_drop_zone_hover,
            ink=False,
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        return ft.Container(
            content=self._drop_zone_body,
            padding=ft.padding.symmetric(horizontal=32),
            height=200,
        )

    def _on_drop_zone_hover(self, e: ft.ControlEvent) -> None:
        self._drop_zone_body.bgcolor = (
            ft.Colors.with_opacity(0.06, "#005f98")
            if e.data == "true"
            else "#F4F6FF"
        )
        self._drop_zone_body.update()

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
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(width=32),
                                ft.Text(
                                    "文件名", size=12, color="#94a3b8",
                                    font_family="Plus Jakarta Sans", expand=True,
                                ),
                                ft.Text(
                                    "大小", size=12, color="#94a3b8",
                                    font_family="Plus Jakarta Sans", width=72,
                                ),
                                ft.Text(
                                    "操作", size=12, color="#94a3b8",
                                    font_family="Plus Jakarta Sans", width=40,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            spacing=12,
                        ),
                        bgcolor="#f8fafc",
                        border_radius=ft.border_radius.only(top_left=8, top_right=8),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border=ft.border.only(bottom=ft.BorderSide(1, "#e2e8f0")),
                    ),
                    self._file_list,
                ],
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=32),
        )

    def _build_param_panel(self) -> ft.Control:
        self._param_panel = ft.Container(
            content=ft.Column(
                controls=[
                    # 标题
                    ft.Text(
                        "参数设置", size=20, weight=ft.FontWeight.W_500,
                        color="#005f98", font_family="42dot Sans",
                    ),
                    # 功能选择（2×2 网格）
                    self._section("选择功能", ft.Column(
                        controls=[
                            ft.Row(controls=[self._func_btns[0], self._func_btns[1]], spacing=8),
                            ft.Row(controls=[self._func_btns[2], self._func_btns[3]], spacing=8),
                        ],
                        spacing=8,
                    )),
                    # 输出质量
                    self._section("输出质量 (压缩)", ft.Column(controls=[
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
                    self._section("页码范围 (拆分)", ft.Row(controls=[
                        self._range_field,
                        ft.IconButton(icon=ft.Icons.REFRESH, icon_color="#005f98", icon_size=20,
                                      on_click=lambda _: self._reset_range()),
                    ], spacing=8)),
                    # 增强选项（规划中）
                    self._section("增强选项", ft.Column(controls=[
                        self._toggle_row("添加密码", ft.Icons.LOCK_OUTLINED, self._pwd_switch),
                        self._toggle_row("添加水印", ft.Icons.WATER_DROP_OUTLINED, self._watermark_switch),
                    ], spacing=12)),
                    # 处理按钮
                    self._run_btn,
                    ft.Text("预计耗时: 12秒 • 隐私保护已开启", size=10, color="#455c7f", font_family="42dot Sans", text_align=ft.TextAlign.CENTER),
                ],
                spacing=24,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            width=320,
            bgcolor="#f4f6ff",
            border_radius=16,
            border=ft.border.only(left=ft.BorderSide(1, "#d5e3ff")),
            padding=ft.padding.all(24),
        )
        return self._param_panel

    def _section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(controls=[
            ft.Text(label.upper(), size=12, color="#455c7f", font_family="42dot Sans"),
            content,
        ], spacing=12)

    def _toggle_row(self, label: str, icon: str, switch: ft.Switch) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color="#162f50", size=16),
                    ft.Text(label, size=14, color="#162f50", font_family="42dot Sans"),
                    ft.Container(expand=True),
                    switch,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#ffffff",
            border_radius=12,
            padding=ft.padding.all(12),
            opacity=0.5,
            tooltip="暂未启用",
        )

    def _select_func(self, key: str) -> None:
        self._selected_func = key
        for i, btn in enumerate(self._func_btns):
            f = _FUNCTIONS[i]
            active = btn.data == key
            btn.bgcolor = "#005f98" if active else "#ffffff"
            btn.border = ft.border.all(2, "#005f98" if active else "#e2e8f0")
            btn.shadow = ft.BoxShadow(
                blur_radius=4 if active else 2,
                color=ft.Colors.with_opacity(0.08 if active else 0.04, "#000000"),
                offset=ft.Offset(0, 2),
            )
            col = btn.content
            # controls[0] 是 Stack(icon_block, badge)
            icon_stack = col.controls[0]
            icon_block = icon_stack.controls[0]
            badge = icon_stack.controls[1]
            icon_block.bgcolor = f["color"] if active else f["bg"]
            icon_block.content.color = "#ffffff" if active else f["color"]
            badge.bgcolor = "#ffffff" if active else "#005f98"
            badge.content.color = f["color"] if active else "#ffffff"
            col.controls[1].color = "#ffffff" if active else "#162f50"
            col.controls[2].color = ft.Colors.with_opacity(0.7, "#ffffff") if active else "#455c7f"
        if self._files:
            single_func = key in ("split", "compress", "to_word")
            count_label = "1个文件" if (single_func and len(self._files) > 1) else f"{len(self._files)}个文件"
            self._run_btn.content.controls[1].value = f"立即处理 ({count_label})"
        self.update()

    def _on_quality_change(self, e) -> None:
        self._quality_value.value = f"{int(e.control.value)}%"
        self._quality_value.update()

    def _reset_range(self) -> None:
        self._range_field.value = "1-5, 8"
        self._range_field.update()

    def _pick_files(self, _) -> None:
        self._page.run_task(self._pick_files_async)

    async def _pick_files_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        try:
            files = await picker.pick_files(
                dialog_title="选择 PDF 文件",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
                allow_multiple=True,
            )
        except RuntimeError:
            show_toast(self._page, "无法打开文件选择器，请检查系统环境", duration=3000)
            files = None
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
        for idx, f in enumerate(self._files):
            try:
                size = f.stat().st_size
                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            except OSError:
                size_str = "?"
            is_last = idx == len(self._files) - 1
            item = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.PICTURE_AS_PDF, color="#dc2626", size=16),
                            width=32, height=32, bgcolor="#fee2e2", border_radius=6, alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(
                            f.name, size=14, color="#162f50", font_family="42dot Sans",
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True,
                        ),
                        ft.Text(size_str, size=12, color="#455c7f", width=72),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_color="#94a3b8",
                            icon_size=16,
                            tooltip="移除",
                            on_click=lambda _, path=f: self._remove_file(path),
                            style=ft.ButtonStyle(
                                overlay_color=ft.Colors.with_opacity(0.08, "#dc2626"),
                                padding=ft.padding.all(4),
                            ),
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#ffffff",
                padding=ft.padding.symmetric(horizontal=12, vertical=10),
                border=ft.border.only(bottom=ft.BorderSide(1, "#e2e8f0") if not is_last else ft.BorderSide(0)),
            )
            self._file_list.controls.append(item)
        row = self._run_btn.content
        single_func = self._selected_func in ("split", "compress", "to_word")
        count_label = "1个文件" if (single_func and len(self._files) > 1) else f"{len(self._files)}个文件"
        row.controls[1].value = f"立即处理 ({count_label})"
        # 有文件时恢复按钮视觉
        self._run_btn.opacity = 1.0 if self._files else 0.4
        self.update()

    def _clear_files(self, _) -> None:
        self._files.clear()
        self._rebuild_file_list()

    def _start_task(self, _) -> None:
        if not self._files:
            show_toast(self._page, "请先选择文件")
            return

        out_dir = settings_service.resolve_output_dir(self._files[0])
        quality = _quality_level(self._quality_slider.value)
        ranges = _parse_ranges(self._range_field.value)

        if self._selected_func == "merge":
            ts = int(time.time())
            kwargs = {
                "input_files": self._files,
                "output_file": out_dir / f"merged_{ts}.pdf",
            }
            fn = merge_pdf
        elif self._selected_func == "split":
            kwargs = {
                "input_file": self._files[0],
                "output_dir": out_dir,
                "mode": "range" if ranges else "pages",
                "page_ranges": ranges or None,
            }
            fn = split_pdf
        elif self._selected_func == "compress":
            kwargs = {
                "input_file": self._files[0],
                "output_file": out_dir / f"{self._files[0].stem}_compressed.pdf",
                "quality": quality,
            }
            fn = compress_pdf
        else:  # to_word
            kwargs = {
                "input_file": self._files[0],
                "output_dir": out_dir,
            }
            fn = pdf_to_docx

        single_func = self._selected_func in ("split", "compress", "to_word")
        file_count_label = "1 个文件" if (single_func and len(self._files) > 1) else f"{len(self._files)} 个文件"
        self._show_processing(file_count_label)

        async def _run():
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d):
        self._update_processing_progress(c, t, d)

    def _on_complete(self, result):
        single_func = self._selected_func in ("split", "compress", "to_word")
        file_count_label = "1 个文件" if (single_func and len(self._files) > 1) else f"{len(self._files)} 个文件"
        history_service.save_task("pdf", self._selected_func, result, input_desc=file_count_label)
        self._output_dir = result.output_dir if result.output_dir else (
            result.output_files[0].parent if result.output_files else None
        )
        self._show_complete(result)

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._hide_processing()

    def _reset(self) -> None:
        self._files.clear()
        self._rebuild_file_list()
        self._hide_complete()

    def _apply_responsive_layout(self, update: bool = True) -> None:
        width = self._page.width or 1000
        narrow = width < self._NARROW_BREAKPOINT
        if narrow == self._is_narrow:
            return
        self._is_narrow = narrow
        if narrow:
            self._param_panel.width = None
            self._param_panel.border_radius = 0
            self._param_panel.border = ft.border.only(top=ft.BorderSide(1, "#d5e3ff"))
            new_body = ft.Column(
                controls=[self._main_content, self._param_panel],
                expand=True,
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
            )
        else:
            self._param_panel.width = 320
            self._param_panel.border_radius = 16
            self._param_panel.border = ft.border.only(left=ft.BorderSide(1, "#d5e3ff"))
            new_body = ft.Row(
                controls=[self._main_content, self._param_panel],
                expand=True,
                spacing=0,
            )
        self._body_container = new_body
        self.controls[1] = new_body
        if update:
            self.update()

    def _on_page_resized(self, e) -> None:
        self._apply_responsive_layout()

    def _remove_file(self, path: Path) -> None:
        if path in self._files:
            self._files.remove(path)
        self._rebuild_file_list()
        self._page.update()

    # ── 处理中状态视图 ──────────────────────────────────────────────────────

    def _build_processing_view(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    # 顶部：标题 + 百分比
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                self._progress_title,
                                ft.Container(expand=True),
                                self._progress_pct,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.only(bottom=8),
                    ),
                    # 总进度条
                    self._progress_bar,
                    # 逐文件进度行
                    self._progress_file_rows,
                    # 取消按钮
                    ft.Row(
                        controls=[ft.Container(expand=True), self._progress_cancel_btn],
                    ),
                ],
                spacing=12,
            ),
            bgcolor="#ffffff",
            border=ft.border.all(1, "#e2e8f0"),
            border_radius=16,
            padding=ft.padding.all(24),
            margin=ft.margin.symmetric(horizontal=32),
        )

    def _build_complete_view(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    # 顶部：成功图标 + 标题
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.CHECK_CIRCLE, color="#16a34a", size=28),
                                width=44, height=44,
                                bgcolor="#d1fae5",
                                border_radius=9999,
                                alignment=ft.Alignment(0, 0),
                            ),
                            self._result_title,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    # 输出文件列表
                    self._result_file_rows,
                    # 操作按钮
                    ft.Row(
                        controls=[
                            self._result_reset_btn,
                            ft.Container(expand=True),
                            self._result_open_btn,
                        ],
                    ),
                ],
                spacing=16,
            ),
            bgcolor="#ffffff",
            border=ft.border.all(1, "#d1fae5"),
            border_radius=16,
            padding=ft.padding.all(24),
            margin=ft.margin.symmetric(horizontal=32),
        )

    def _show_processing(self, file_count_label: str) -> None:
        self._progress_title.value = "正在处理…"
        self._progress_pct.value = "0%"
        self._progress_bar.value = 0
        self._progress_file_rows.controls.clear()
        self._processing_view.visible = True
        self._complete_view.visible = False
        self.update()

    def _update_processing_progress(self, current: int, total: int, desc: str) -> None:
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_pct.value = f"{pct}%"
        self._progress_bar.value = current / total if total > 0 else 0
        # 更新或追加文件行
        row_idx = current - 1
        row = ft.Row(
            controls=[
                ft.Icon(ft.Icons.PICTURE_AS_PDF, color="#005f98", size=16),
                ft.Text(desc, size=13, color="#162f50", expand=True),
                ft.ProgressBar(
                    value=1.0, color="#005f98", bgcolor="#d5e3ff",
                    height=4, border_radius=2, width=80,
                ),
                ft.Text(f"{current}/{total}", size=12, color="#455c7f", width=40),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        if row_idx < len(self._progress_file_rows.controls):
            self._progress_file_rows.controls[row_idx] = row
        else:
            self._progress_file_rows.controls.append(row)
        self._processing_view.update()

    def _hide_processing(self) -> None:
        self._processing_view.visible = False
        self.update()

    def _show_complete(self, result) -> None:
        from core.models import TaskStatus
        if result.status == TaskStatus.SUCCESS:
            self._result_title.value = "处理完成！"
            self._result_title.color = "#16a34a"
        else:
            self._result_title.value = f"处理失败：{result.error_message or '未知错误'}"
            self._result_title.color = "#dc2626"

        self._result_file_rows.controls.clear()
        if result.output_files:
            for fp in result.output_files[:5]:
                self._result_file_rows.controls.append(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PICTURE_AS_PDF, color="#dc2626", size=14),
                            ft.Text(fp.name, size=13, color="#162f50", expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                        spacing=8,
                    )
                )
            if len(result.output_files) > 5:
                self._result_file_rows.controls.append(
                    ft.Text(f"…共 {len(result.output_files)} 个文件", size=12, color="#455c7f")
                )

        self._processing_view.visible = False
        self._complete_view.visible = True
        self.update()

    def _hide_complete(self) -> None:
        self._complete_view.visible = False
        self.update()

    def _open_output_folder(self, _) -> None:
        if self._output_dir and self._output_dir.exists():
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(self._output_dir)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self._output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(self._output_dir)])
