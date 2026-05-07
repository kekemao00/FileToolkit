"""音视频处理中心 — 基于 Figma 设计稿 1:1 还原

布局：左侧主内容区（标题+拖拽区+文件缩略卡片网格） + 右侧参数面板
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import flet as ft

from core.media.audio import convert_audio, extract_audio
from core.media.video import compress_video, convert_video
from services import history_service, settings_service
from services.task_service import run_task

_FUNCTIONS = [
    {"label": "视频转换", "desc": "MP4/AVI/MOV/MKV 互转", "icon": ft.Icons.SWAP_HORIZ,
     "key": "video_convert", "color": "#005f98", "bg": "#d5e3ff"},
    {"label": "视频压缩", "desc": "码率/分辨率压缩", "icon": ft.Icons.COMPRESS,
     "key": "video_compress", "color": "#d97706", "bg": "#fef3c7"},
    {"label": "音频提取", "desc": "从视频提取音频", "icon": ft.Icons.MUSIC_NOTE,
     "key": "audio_extract", "color": "#059669", "bg": "#d1fae5"},
    {"label": "音频转换", "desc": "MP3/WAV/AAC/FLAC", "icon": ft.Icons.GRAPHIC_EQ,
     "key": "audio_convert", "color": "#7c3aed", "bg": "#ede9fe"},
]

_VIDEO_EXTS = {"mp4", "avi", "mkv", "mov", "flv", "wmv", "webm", "m4v"}
_AUDIO_EXTS = {"mp3", "wav", "flac", "aac", "ogg", "wma", "m4a"}


class MediaPage(ft.Column):
    """音视频处理中心 — 工作台布局"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._files: list[Path] = []
        self._selected_func = "video_convert"
        self._task: asyncio.Task | None = None
        self._output_dir: Path | None = None

        # 处理中状态组件
        self._progress_title = ft.Text(
            "", size=30, weight=ft.FontWeight.W_600, color="#162f50",
            font_family="42dot Sans",
        )
        self._progress_pct = ft.Text(
            "0%", size=30, weight=ft.FontWeight.BOLD, color="#005f98",
            font_family="42dot Sans",
        )
        self._progress_bar = ft.ProgressBar(
            value=0, color="#005f98", bgcolor="#d5e3ff", bar_height=10,
            border_radius=5,
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
        self._result_file_rows = ft.Column(spacing=8)
        self._result_open_btn = ft.FilledButton(
            "打开文件夹",
            style=ft.ButtonStyle(bgcolor="#005f98", color="#ffffff"),
            on_click=self._open_output_folder,
        )
        self._result_reset_btn = ft.TextButton(
            "继续处理",
            style=ft.ButtonStyle(color="#455c7f"),
            on_click=lambda _: self._reset(),
        )

        # 视频压缩：质量滑块（code: 0-33 high质量 / 34-66 medium / 67-100 low）
        self._quality_value = ft.Text("75%", size=12, weight=ft.FontWeight.BOLD, color="#005f98")
        self._quality_slider = ft.Slider(
            min=0, max=100, value=75, divisions=20,
            active_color="#005f98", inactive_color="#d5e3ff",
            on_change=self._on_quality_change,
            width=270,
        )

        # 视频转换：目标格式（3 并排按钮，共 4 个 -> Row wrap=True）
        self._video_format_value = "mp4"
        self._video_format_btns: list[ft.Container] = []
        for fmt_key, fmt_label in [("mp4", "MP4"), ("avi", "AVI"), ("mov", "MOV"), ("mkv", "MKV")]:
            self._video_format_btns.append(self._make_format_btn(
                "_video_format_value", fmt_key, fmt_label,
                lambda _, k=fmt_key: self._select_video_format(k),
            ))

        # 音频转换：目标格式
        self._audio_format_value = "mp3"
        self._audio_format_btns: list[ft.Container] = []
        for fmt_key, fmt_label in [("mp3", "MP3"), ("wav", "WAV"), ("aac", "AAC"), ("flac", "FLAC")]:
            self._audio_format_btns.append(self._make_format_btn(
                "_audio_format_value", fmt_key, fmt_label,
                lambda _, k=fmt_key: self._select_audio_format(k),
            ))

        # 音频提取：输出格式
        self._extract_format_value = "mp3"
        self._extract_format_btns: list[ft.Container] = []
        for fmt_key, fmt_label in [("mp3", "MP3"), ("wav", "WAV")]:
            self._extract_format_btns.append(self._make_format_btn(
                "_extract_format_value", fmt_key, fmt_label,
                lambda _, k=fmt_key: self._select_extract_format(k),
            ))

        # 视频压缩：分辨率选择
        self._resolution_value = "original"
        self._resolution_btns: list[ft.Container] = []
        for res_key, res_label in [("original", "原始"), ("1080p", "1080p"),
                                    ("720p", "720p"), ("480p", "480p")]:
            self._resolution_btns.append(self._make_format_btn(
                "_resolution_value", res_key, res_label,
                lambda _, k=res_key: self._select_resolution(k),
            ))

        # 文件列表（缩略图卡片网格）
        self._file_list = ft.Row(
            controls=[],
            wrap=True,
            spacing=12,
            run_spacing=12,
        )
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
            opacity=0.4,
        )

        # 功能卡片（2×2 网格）
        self._func_btns = []
        for idx, f in enumerate(_FUNCTIONS):
            active = f["key"] == self._selected_func
            icon_block = ft.Container(
                content=ft.Icon(f["icon"], color="#ffffff" if active else f["color"], size=28),
                width=56, height=56,
                bgcolor="#005f98" if active else f["bg"],
                border_radius=14,
                alignment=ft.Alignment(0, 0),
            )
            badge = ft.Container(
                content=ft.Text(
                    str(idx + 1), size=10, color="#005f98" if active else "#ffffff",
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

        self._NARROW_BREAKPOINT = 800
        self._is_narrow = None
        self._body_container: ft.Control = ft.Container()
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
                                    disabled=True, opacity=0.45,
                                    tooltip="通知",
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SETTINGS_OUTLINED,
                                    icon_color="#475569", icon_size=20,
                                    on_click=lambda _: self._page.go("/settings"),
                                ),
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
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "音视频处理中心", size=30,
                                    weight=ft.FontWeight.W_500,
                                    color="#005f98",
                                    font_family="42dot Sans",
                                ),
                                ft.Text(
                                    "视频转换、视频压缩、音频提取与音频转换",
                                    size=16, color="#455c7f",
                                    font_family="42dot Sans",
                                ),
                            ],
                            spacing=4,
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

        def dash_segment() -> ft.Container:
            return ft.Container(
                width=16, height=2, bgcolor=dash_color, border_radius=9999,
            )

        def dash_column() -> ft.Container:
            return ft.Container(
                width=2, height=16, bgcolor=dash_color, border_radius=9999,
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
                        content=ft.Icon(ft.Icons.MOVIE, color="#005f98", size=40),
                        width=72, height=72,
                        bgcolor=ft.Colors.with_opacity(0.12, "#005f98"),
                        border_radius=9999,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "拖拽音视频文件到此处",
                        size=18, color="#005f98",
                        font_family="42dot Sans",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "或点击选择文件",
                        size=14, color="#455c7f",
                        font_family="42dot Sans",
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=36, horizontal=24),
            expand=True,
            on_click=self._pick_files,
            ink=True,
        )
        self._drop_zone_body = ft.Container(
            content=ft.Stack(
                controls=[
                    ft.Container(content=body, expand=True, padding=ft.padding.all(0)),
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
                ],
            ),
            border_radius=20,
            bgcolor="#F4F6FF",
            on_hover=self._on_drop_zone_hover,
            ink=False,
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        self._drop_zone_wrapper = ft.Container(
            content=self._drop_zone_body,
            padding=ft.padding.symmetric(horizontal=32),
            height=260,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )
        return self._drop_zone_wrapper

    def _on_drop_zone_hover(self, e: ft.ControlEvent) -> None:
        self._drop_zone_body.bgcolor = (
            ft.Colors.with_opacity(0.06, "#005f98") if e.data == "true" else "#F4F6FF"
        )
        self._drop_zone_body.update()

    def _build_file_list(self) -> ft.Control:
        self._file_list_container = ft.Container(
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
                spacing=12,
            ),
            padding=ft.padding.symmetric(horizontal=32),
            visible=False,
        )
        return self._file_list_container

    def _build_param_panel(self) -> ft.Control:
        # 视频压缩参数组（质量滑块 + 分辨率）
        self._compress_section = self._section("视频压缩", ft.Column(controls=[
            ft.Row(controls=[
                ft.Text("输出质量", size=13, color="#162f50"),
                ft.Container(expand=True),
                self._quality_value,
            ]),
            self._quality_slider,
            ft.Row(controls=[
                ft.Text("体积优先", size=10, color="#455c7f"),
                ft.Container(expand=True),
                ft.Text("均衡", size=10, color="#455c7f"),
                ft.Container(expand=True),
                ft.Text("画质优先", size=10, color="#455c7f"),
            ]),
            ft.Container(height=8),
            ft.Text("分辨率", size=13, color="#162f50"),
            ft.Row(controls=self._resolution_btns, spacing=8, wrap=True, run_spacing=8),
        ], spacing=8))

        self._video_format_section = self._section("视频目标格式", ft.Row(
            controls=self._video_format_btns, spacing=8, wrap=True, run_spacing=8,
        ))
        self._audio_format_section = self._section("音频目标格式", ft.Row(
            controls=self._audio_format_btns, spacing=8, wrap=True, run_spacing=8,
        ))
        self._extract_format_section = self._section("提取输出格式", ft.Row(
            controls=self._extract_format_btns, spacing=8,
        ))

        self._param_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "参数设置", size=20, weight=ft.FontWeight.W_500,
                        color="#005f98", font_family="42dot Sans",
                    ),
                    self._section("选择功能", ft.Column(
                        controls=[
                            ft.Row(controls=[self._func_btns[0], self._func_btns[1]], spacing=8),
                            ft.Row(controls=[self._func_btns[2], self._func_btns[3]], spacing=8),
                        ],
                        spacing=8,
                    )),
                    self._video_format_section,
                    self._compress_section,
                    self._extract_format_section,
                    self._audio_format_section,
                    self._run_btn,
                    ft.Text("本地处理 • 隐私保护已开启", size=10, color="#455c7f",
                            font_family="42dot Sans", text_align=ft.TextAlign.CENTER),
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
        self._update_param_sections()
        return self._param_panel

    def _section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(controls=[
            ft.Text(label.upper(), size=12, color="#455c7f", font_family="42dot Sans"),
            content,
        ], spacing=12)

    def _make_format_btn(self, attr_name: str, key: str, label: str, on_click) -> ft.Container:
        active = key == getattr(self, attr_name, "")
        return ft.Container(
            content=ft.Text(
                label, size=13, weight=ft.FontWeight.W_600,
                color="#ffffff" if active else "#162f50",
                text_align=ft.TextAlign.CENTER,
                font_family="42dot Sans",
            ),
            bgcolor="#005f98" if active else "#ffffff",
            border=ft.border.all(1, "#005f98" if active else "#e2e8f0"),
            border_radius=10,
            padding=ft.padding.symmetric(vertical=10, horizontal=16),
            on_click=on_click,
            ink=True,
            data=key,
            alignment=ft.Alignment(0, 0),
            width=72,
        )

    def _apply_btn_active(self, btns: list[ft.Container], key: str) -> None:
        for btn in btns:
            active = btn.data == key
            btn.bgcolor = "#005f98" if active else "#ffffff"
            btn.border = ft.border.all(1, "#005f98" if active else "#e2e8f0")
            btn.content.color = "#ffffff" if active else "#162f50"

    def _select_video_format(self, key: str) -> None:
        self._video_format_value = key
        self._apply_btn_active(self._video_format_btns, key)
        self.update()

    def _select_audio_format(self, key: str) -> None:
        self._audio_format_value = key
        self._apply_btn_active(self._audio_format_btns, key)
        self.update()

    def _select_extract_format(self, key: str) -> None:
        self._extract_format_value = key
        self._apply_btn_active(self._extract_format_btns, key)
        self.update()

    def _select_resolution(self, key: str) -> None:
        self._resolution_value = key
        self._apply_btn_active(self._resolution_btns, key)
        self.update()

    def _build_processing_view(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
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
                    self._progress_bar,
                    self._progress_file_rows,
                    ft.Row(controls=[ft.Container(expand=True), self._progress_cancel_btn]),
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
                    self._result_file_rows,
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

    def _update_param_sections(self) -> None:
        # 按选中的功能控制参数子区显示
        key = self._selected_func
        self._video_format_section.visible = key == "video_convert"
        self._compress_section.visible = key == "video_compress"
        self._extract_format_section.visible = key == "audio_extract"
        self._audio_format_section.visible = key == "audio_convert"

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
            icon_stack = col.controls[0]
            icon_block = icon_stack.controls[0]
            badge = icon_stack.controls[1]
            icon_block.bgcolor = "#005f98" if active else f["bg"]
            icon_block.content.color = "#ffffff" if active else f["color"]
            badge.bgcolor = "#ffffff" if active else "#005f98"
            badge.content.color = "#005f98" if active else "#ffffff"
            col.controls[1].color = "#ffffff" if active else "#162f50"
            col.controls[2].color = ft.Colors.with_opacity(0.7, "#ffffff") if active else "#455c7f"
        self._update_param_sections()
        if self._files:
            self._run_btn.content.controls[1].value = f"立即处理 ({len(self._files)}个文件)"
        self.update()

    def _on_quality_change(self, e) -> None:
        self._quality_value.value = f"{int(e.control.value)}%"
        self._quality_value.update()

    def _pick_files(self, _) -> None:
        self._page.run_task(self._pick_files_async)

    async def _pick_files_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        try:
            files = await picker.pick_files(
                dialog_title="选择音视频文件",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=[
                    "mp4", "avi", "mkv", "mov", "flv", "wmv", "webm", "m4v",
                    "mp3", "wav", "flac", "aac", "ogg", "wma", "m4a",
                ],
                allow_multiple=True,
            )
        except RuntimeError:
            self._page.snack_bar = ft.SnackBar(content=ft.Text("无法打开文件选择器，请检查系统环境"), duration=3000)
            self._page.snack_bar.open = True
            self._page.update()
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
        has_files = bool(self._files)
        self._file_list_container.visible = has_files
        self._drop_zone_wrapper.height = 140 if has_files else 260
        for f in self._files:
            try:
                size = f.stat().st_size
                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            except OSError:
                size_str = "?"
            ext = f.suffix.lower().lstrip(".")
            is_audio = ext in _AUDIO_EXTS
            tag_color = "#7c3aed" if is_audio else "#005f98"
            tag_bg = "#ede9fe" if is_audio else "#d5e3ff"
            thumb_icon = ft.Icons.AUDIO_FILE if is_audio else ft.Icons.VIDEO_FILE
            thumb = ft.Container(
                content=ft.Icon(thumb_icon, color=tag_color, size=24),
                width=48, height=48, bgcolor=tag_bg, border_radius=8,
                alignment=ft.Alignment(0, 0),
            )
            card = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                thumb,
                                ft.Container(
                                    content=ft.Text(
                                        ext.upper() or "?", size=10, weight=ft.FontWeight.BOLD,
                                        color=tag_color, font_family="Plus Jakarta Sans",
                                    ),
                                    bgcolor=tag_bg,
                                    border_radius=6,
                                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                ),
                                ft.Container(expand=True),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_color="#94a3b8",
                                    icon_size=14,
                                    tooltip="移除",
                                    on_click=lambda _, path=f: self._remove_file(path),
                                    style=ft.ButtonStyle(
                                        overlay_color=ft.Colors.with_opacity(0.08, "#dc2626"),
                                        padding=ft.padding.all(4),
                                    ),
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        ft.Text(
                            f.name, size=13, color="#162f50", font_family="42dot Sans",
                            weight=ft.FontWeight.W_500,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(size_str, size=11, color="#455c7f", font_family="Plus Jakarta Sans"),
                    ],
                    spacing=6,
                ),
                bgcolor="#ffffff",
                border=ft.border.all(1, "#e2e8f0"),
                border_radius=12,
                padding=ft.padding.all(12),
                width=220,
            )
            self._file_list.controls.append(card)
        self._run_btn.content.controls[1].value = f"立即处理 ({len(self._files)}个文件)"
        self._run_btn.opacity = 1.0 if has_files else 0.4
        self.update()

    def _clear_files(self, _) -> None:
        self._files.clear()
        self._rebuild_file_list()

    def _remove_file(self, path: Path) -> None:
        if path in self._files:
            self._files.remove(path)
        self._rebuild_file_list()
        self._page.update()

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
                expand=True, spacing=0, scroll=ft.ScrollMode.AUTO,
            )
        else:
            self._param_panel.width = 320
            self._param_panel.border_radius = 16
            self._param_panel.border = ft.border.only(left=ft.BorderSide(1, "#d5e3ff"))
            new_body = ft.Row(
                controls=[self._main_content, self._param_panel],
                expand=True, spacing=0,
            )
        self._body_container = new_body
        self.controls[1] = new_body
        if update:
            self.update()

    def _on_page_resized(self, e) -> None:
        self._apply_responsive_layout()

    def _start_task(self, _) -> None:
        if not self._files:
            self._page.snack_bar = ft.SnackBar(content=ft.Text("请先选择音视频文件"), duration=2000)
            self._page.snack_bar.open = True
            self._page.update()
            return

        out_dir = settings_service.resolve_output_dir(self._files[0])
        func = self._selected_func
        quality = int(self._quality_slider.value)

        # 按功能过滤文件类型
        if func in ("video_convert", "video_compress", "audio_extract"):
            files = [p for p in self._files if p.suffix.lower().lstrip(".") in _VIDEO_EXTS]
            need = "视频"
        elif func == "audio_convert":
            files = [p for p in self._files if p.suffix.lower().lstrip(".") in _AUDIO_EXTS]
            need = "音频"
        else:
            files = self._files
            need = "音视频"

        if not files:
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text(f"所选功能需要{need}文件，当前无符合条件的文件"),
                duration=2500,
            )
            self._page.snack_bar.open = True
            self._page.update()
            return

        if func == "video_convert":
            kwargs = {
                "input_files": files,
                "output_dir": out_dir,
                "target_format": self._video_format_value,
            }
            fn = convert_video
        elif func == "video_compress":
            # quality slider：左(低值)=体积优先=low(CRF28)，右(高值)=画质优先=high(CRF18)
            if quality < 34:
                q_level = "low"
            elif quality < 67:
                q_level = "medium"
            else:
                q_level = "high"
            kwargs = {
                "input_files": files,
                "output_dir": out_dir,
                "quality": q_level,
                "resolution": self._resolution_value,
            }
            fn = compress_video
        elif func == "audio_extract":
            # 后端 extract_audio 单文件；包装成批处理
            fmt = self._extract_format_value
            fn = _batch_extract_audio
            kwargs = {
                "input_files": files,
                "output_dir": out_dir,
                "audio_format": fmt,
            }
        elif func == "audio_convert":
            kwargs = {
                "input_files": files,
                "output_dir": out_dir,
                "target_format": self._audio_format_value,
                "bitrate": "192",
            }
            fn = convert_audio
        else:
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text(f"未知功能：{func}"), duration=2000,
            )
            self._page.snack_bar.open = True
            self._page.update()
            return

        self._show_processing(f"{len(files)} 个文件")

        async def _run():
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d) -> None:
        self._update_processing_progress(c, t, d)

    def _on_complete(self, result) -> None:
        history_service.save_task(
            "media", self._selected_func, result,
            input_desc=f"{len(self._files)} 个文件",
        )
        self._output_dir = result.output_dir if result.output_dir else (
            result.output_files[0].parent if result.output_files else None
        )
        self._show_complete(result)

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._reset_to_workspace()

    def _reset(self) -> None:
        self._files.clear()
        self._rebuild_file_list()
        self._reset_to_workspace()

    def _reset_to_workspace(self) -> None:
        self._workspace_view.visible = True
        self._processing_view.visible = False
        self._complete_view.visible = False
        self.update()

    def _show_processing(self, file_count_label: str) -> None:
        self._progress_title.value = "正在处理…"
        self._progress_pct.value = "0%"
        self._progress_bar.value = 0
        self._progress_file_rows.controls.clear()
        self._workspace_view.visible = False
        self._processing_view.visible = True
        self._complete_view.visible = False
        self.update()

    def _update_processing_progress(self, current: int, total: int, desc: str) -> None:
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_pct.value = f"{pct}%"
        self._progress_bar.value = current / total if total > 0 else 0
        row_idx = current - 1
        row = ft.Row(
            controls=[
                ft.Icon(ft.Icons.MOVIE, color="#005f98", size=16),
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
        # 隐藏处理中视图并回到工作台
        self._reset_to_workspace()

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
            for fp in result.output_files[:8]:
                fp_ext = fp.suffix.lower().lstrip(".")
                fp_is_audio = fp_ext in _AUDIO_EXTS
                fp_icon = ft.Icons.AUDIO_FILE if fp_is_audio else ft.Icons.VIDEO_FILE
                fp_color = "#7c3aed" if fp_is_audio else "#005f98"
                self._result_file_rows.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(fp_icon, color=fp_color, size=16),
                                ft.Text(
                                    fp.name, size=13, color="#162f50",
                                    expand=True, max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        "已完成", size=10, color="#16a34a",
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    bgcolor="#dcfce7",
                                    border_radius=6,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FOLDER_OPEN,
                                    icon_color="#005f98",
                                    icon_size=16,
                                    tooltip="打开所在文件夹",
                                    on_click=lambda _, p=fp: self._open_file_location(p),
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor="#f8fafc",
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    )
                )
            if len(result.output_files) > 8:
                self._result_file_rows.controls.append(
                    ft.Text(f"…共 {len(result.output_files)} 个文件", size=12, color="#455c7f")
                )

        self._workspace_view.visible = False
        self._processing_view.visible = False
        self._complete_view.visible = True
        self.update()

    def _hide_complete(self) -> None:
        # 从完成视图回到工作台
        self._reset_to_workspace()

    def _open_output_folder(self, _) -> None:
        if self._output_dir and self._output_dir.exists():
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(self._output_dir)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self._output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(self._output_dir)])

    def _open_file_location(self, path: Path) -> None:
        folder = path.parent
        if not folder.exists():
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])


def _batch_extract_audio(
    input_files: list[Path],
    output_dir: Path,
    audio_format: str = "mp3",
    progress_callback=None,
):
    """音频提取的批处理包装：遍历调用 extract_audio 单文件版本。"""
    import time

    from core.models import TaskResult, TaskStatus

    t0 = time.time()
    if not input_files:
        return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")
    output_files: list[Path] = []
    total = len(input_files)
    try:
        for i, path in enumerate(input_files, start=1):
            res = extract_audio(path, output_dir, audio_format=audio_format)
            if res.status == TaskStatus.FAILED:
                return TaskResult(
                    status=TaskStatus.FAILED,
                    error_message=res.error_message,
                    output_files=output_files,
                    output_dir=output_dir,
                    duration_seconds=time.time() - t0,
                )
            output_files.extend(res.output_files or [])
            if progress_callback:
                progress_callback(i, total, f"已提取：{path.name} ({i}/{total})")
        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=output_files,
            output_dir=output_dir,
            duration_seconds=time.time() - t0,
        )
    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )
