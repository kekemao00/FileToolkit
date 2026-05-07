"""图片万能编辑器 — 基于 Figma 设计稿 1:1 还原

布局：左侧主内容区（标题+拖拽区+文件列表） + 右侧参数面板
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import flet as ft

from core.image.compressor import compress_images
from core.image.converter import convert_image
from core.image.resizer import resize_images
from core.image.watermark import add_text_watermark
from services import history_service, settings_service
from services.task_service import run_task

_FUNCTIONS = [
    {"label": "压缩", "desc": "图片压缩与优化", "icon": ft.Icons.COMPRESS, "key": "compress",
     "color": "#005f98", "bg": "#d5e3ff"},
    {"label": "格式转换", "desc": "PNG/JPG/WebP 互转", "icon": ft.Icons.TRANSFORM, "key": "convert",
     "color": "#d97706", "bg": "#fef3c7"},
    {"label": "尺寸调整", "desc": "按比例或固定尺寸", "icon": ft.Icons.PHOTO_SIZE_SELECT_LARGE, "key": "resize",
     "color": "#059669", "bg": "#d1fae5"},
    {"label": "水印", "desc": "添加文字/图片水印", "icon": ft.Icons.WATER_DROP_OUTLINED, "key": "watermark",
     "color": "#7c3aed", "bg": "#ede9fe"},
]

# 水印位置 3×3 网格 → watermark 模块位置标识
_WATERMARK_POS_MAP = {
    "tl": "top_left", "tc": "top_center", "tr": "top_right",
    "cl": "center_left", "cc": "center", "cr": "center_right",
    "bl": "bottom_left", "bc": "bottom_center", "br": "bottom_right",
}


class ImagePage(ft.Column):
    """图片万能编辑器 — 工作台布局"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._files: list[Path] = []
        self._selected_func = "compress"
        self._task: asyncio.Task | None = None
        self._output_dir: Path | None = None

        # 处理中状态组件
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

        # 质量滑块
        self._quality_value = ft.Text("85%", size=12, weight=ft.FontWeight.BOLD, color="#005f98")
        self._quality_slider = ft.Slider(
            min=0, max=100, value=85, divisions=20,
            active_color="#005f98", inactive_color="#d5e3ff",
            on_change=self._on_quality_change,
            width=270,
        )

        # 格式选择（3 个并排按钮）
        self._format_value = "webp"
        self._format_btns: list[ft.Container] = []
        for fmt_key, fmt_label in [("png", "PNG"), ("jpg", "JPG"), ("webp", "WebP")]:
            self._format_btns.append(self._make_format_btn(fmt_key, fmt_label))

        # 水印位置（3×3 网格，值为 tl/tc/tr/cl/cc/cr/bl/bc/br）
        self._watermark_pos = "br"
        self._watermark_pos_btns: dict[str, ft.Container] = {}
        for pos_key in ["tl", "tc", "tr", "cl", "cc", "cr", "bl", "bc", "br"]:
            self._watermark_pos_btns[pos_key] = self._make_pos_btn(pos_key)

        # 尺寸输入
        self._width_field = ft.TextField(
            value="1920", label="宽度 (px)",
            border_radius=12, bgcolor="#d5e3ff", border_color="transparent",
            text_size=14, expand=True,
        )
        self._height_field = ft.TextField(
            value="1080", label="高度 (px)",
            border_radius=12, bgcolor="#d5e3ff", border_color="transparent",
            text_size=14, expand=True,
        )
        self._keep_ratio = ft.Switch(value=True, active_color="#005f98",
                                     inactive_thumb_color="#ffffff", inactive_track_color="#cbdeff")

        # 水印文字
        self._watermark_field = ft.TextField(
            value="FileToolkit",
            border_radius=12, bgcolor="#d5e3ff", border_color="transparent",
            text_size=14, expand=True,
        )

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
                    ft.Text("立即处理 (0张图片)", size=18, color="#ffffff", font_family="42dot Sans"),
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
                                    "图片万能编辑器", size=30,
                                    weight=ft.FontWeight.W_500,
                                    color="#005f98",
                                    font_family="42dot Sans",
                                ),
                                ft.Text(
                                    "批量压缩、格式转换、尺寸调整与水印处理",
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
                        content=ft.Icon(ft.Icons.IMAGE, color="#005f98", size=40),
                        width=72, height=72,
                        bgcolor=ft.Colors.with_opacity(0.12, "#005f98"),
                        border_radius=9999,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "拖拽图片文件到此处",
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
                    self._section("目标格式 (转换)", ft.Row(
                        controls=self._format_btns, spacing=8,
                    )),
                    self._section("尺寸调整", ft.Column(controls=[
                        ft.Row(controls=[self._width_field, self._height_field], spacing=8),
                        ft.Row(controls=[
                            ft.Icon(ft.Icons.ASPECT_RATIO, color="#162f50", size=16),
                            ft.Text("保持比例", size=14, color="#162f50", font_family="42dot Sans"),
                            ft.Container(expand=True),
                            self._keep_ratio,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], spacing=8)),
                    self._section("水印文字", self._watermark_field),
                    self._section("水印位置", ft.Column(controls=[
                        ft.Row(
                            controls=[
                                self._watermark_pos_btns["tl"],
                                self._watermark_pos_btns["tc"],
                                self._watermark_pos_btns["tr"],
                            ],
                            spacing=8,
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        ft.Row(
                            controls=[
                                self._watermark_pos_btns["cl"],
                                self._watermark_pos_btns["cc"],
                                self._watermark_pos_btns["cr"],
                            ],
                            spacing=8,
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        ft.Row(
                            controls=[
                                self._watermark_pos_btns["bl"],
                                self._watermark_pos_btns["bc"],
                                self._watermark_pos_btns["br"],
                            ],
                            spacing=8,
                            alignment=ft.MainAxisAlignment.START,
                        ),
                    ], spacing=8)),
                    self._run_btn,
                    ft.Text("预计耗时: 8秒 • 隐私保护已开启", size=10, color="#455c7f",
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
        return self._param_panel

    def _section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(controls=[
            ft.Text(label.upper(), size=12, color="#455c7f", font_family="42dot Sans"),
            content,
        ], spacing=12)

    def _make_format_btn(self, key: str, label: str) -> ft.Container:
        active = key == getattr(self, "_format_value", "webp")
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
            padding=ft.padding.symmetric(vertical=10),
            on_click=lambda _, k=key: self._select_format(k),
            ink=True,
            data=key,
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

    def _select_format(self, key: str) -> None:
        self._format_value = key
        for btn in self._format_btns:
            active = btn.data == key
            btn.bgcolor = "#005f98" if active else "#ffffff"
            btn.border = ft.border.all(1, "#005f98" if active else "#e2e8f0")
            btn.content.color = "#ffffff" if active else "#162f50"
        self.update()

    def _make_pos_btn(self, key: str) -> ft.Container:
        active = key == getattr(self, "_watermark_pos", "br")
        return ft.Container(
            content=ft.Container(
                width=6, height=6, bgcolor="#ffffff" if active else "#94a3b8",
                border_radius=9999,
            ),
            width=40, height=40,
            bgcolor="#005f98" if active else "#ffffff",
            border=ft.border.all(1, "#005f98" if active else "#e2e8f0"),
            border_radius=8,
            on_click=lambda _, k=key: self._select_pos(k),
            ink=True,
            data=key,
            alignment=ft.Alignment(0, 0),
        )

    def _select_pos(self, key: str) -> None:
        self._watermark_pos = key
        for pk, btn in self._watermark_pos_btns.items():
            active = pk == key
            btn.bgcolor = "#005f98" if active else "#ffffff"
            btn.border = ft.border.all(1, "#005f98" if active else "#e2e8f0")
            btn.content.bgcolor = "#ffffff" if active else "#94a3b8"
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
        if self._files:
            self._run_btn.content.controls[1].value = f"立即处理 ({len(self._files)}张图片)"
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
                dialog_title="选择图片文件",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "heic"],
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
        # 空态显示大拖拽区；有文件时拖拽区收缩到顶部
        self._drop_zone_wrapper.height = 140 if has_files else 260
        for f in self._files:
            try:
                size = f.stat().st_size
                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            except OSError:
                size_str = "?"
            ext = f.suffix.lower().lstrip(".")
            tag_color_map = {
                "png": "#16a34a", "jpg": "#dc2626", "jpeg": "#dc2626",
                "webp": "#2563eb", "bmp": "#7c3aed", "heic": "#ea580c",
                "tiff": "#0891b2", "tif": "#0891b2",
            }
            tag_bg_map = {
                "png": "#dcfce7", "jpg": "#fef2f2", "jpeg": "#fef2f2",
                "webp": "#dbeafe", "bmp": "#ede9fe", "heic": "#ffedd5",
                "tiff": "#cffafe", "tif": "#cffafe",
            }
            tag_color = tag_color_map.get(ext, "#475569")
            tag_bg = tag_bg_map.get(ext, "#f1f5f9")
            try:
                thumb = ft.Image(
                    src=str(f), width=48, height=48, fit=ft.ImageFit.COVER,
                    border_radius=8,
                )
            except Exception:
                thumb = ft.Container(
                    content=ft.Icon(ft.Icons.IMAGE, color="#005f98", size=24),
                    width=48, height=48, bgcolor="#eff6ff", border_radius=8,
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
        self._run_btn.content.controls[1].value = f"立即处理 ({len(self._files)}张图片)"
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
            self._page.snack_bar = ft.SnackBar(content=ft.Text("请先选择图片文件"), duration=2000)
            self._page.snack_bar.open = True
            self._page.update()
            return

        out_dir = settings_service.resolve_output_dir(self._files[0])
        quality = int(self._quality_slider.value)
        func = self._selected_func

        if func == "compress":
            level_map = [(range(0, 34), "high"), (range(34, 67), "medium"), (range(67, 101), "low")]
            level = "medium"
            for r, lv in level_map:
                if quality in r:
                    level = lv
                    break
            kwargs = {"input_files": self._files, "output_dir": out_dir, "level": level}
            fn = compress_images
        elif func == "convert":
            kwargs = {
                "input_files": self._files,
                "output_dir": out_dir,
                "target_format": self._format_value,
                "quality": quality,
            }
            fn = convert_image
        elif func == "resize":
            try:
                w_raw = (self._width_field.value or "").strip()
                h_raw = (self._height_field.value or "").strip()
                width = int(w_raw) if w_raw else None
                height = int(h_raw) if h_raw else None
            except ValueError:
                self._page.snack_bar = ft.SnackBar(
                    content=ft.Text("宽度/高度必须为整数"), duration=2000,
                )
                self._page.snack_bar.open = True
                self._page.update()
                return
            if not width and not height:
                self._page.snack_bar = ft.SnackBar(
                    content=ft.Text("请至少填写宽度或高度"), duration=2000,
                )
                self._page.snack_bar.open = True
                self._page.update()
                return
            kwargs = {
                "input_files": self._files,
                "output_dir": out_dir,
                "width": width,
                "height": height,
                "keep_ratio": bool(self._keep_ratio.value),
            }
            fn = resize_images
        elif func == "watermark":
            text = (self._watermark_field.value or "").strip()
            if not text:
                self._page.snack_bar = ft.SnackBar(
                    content=ft.Text("水印文字不能为空"), duration=2000,
                )
                self._page.snack_bar.open = True
                self._page.update()
                return
            kwargs = {
                "input_files": self._files,
                "output_dir": out_dir,
                "text": text,
                "position": _WATERMARK_POS_MAP.get(self._watermark_pos, "bottom_right"),
                # 复用质量 Slider 作为水印透明度（10-100）
                "opacity": max(10, min(100, quality)),
            }
            fn = add_text_watermark
        else:
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text(f"未知功能：{func}"), duration=2000,
            )
            self._page.snack_bar.open = True
            self._page.update()
            return

        self._show_processing(f"{len(self._files)} 张图片")

        async def _run():
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d) -> None:
        self._update_processing_progress(c, t, d)

    def _on_complete(self, result) -> None:
        history_service.save_task(
            "image", self._selected_func, result,
            input_desc=f"{len(self._files)} 张图片",
        )
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
        row_idx = current - 1
        row = ft.Row(
            controls=[
                ft.Icon(ft.Icons.IMAGE, color="#005f98", size=16),
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
            for fp in result.output_files[:8]:
                self._result_file_rows.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.IMAGE, color="#005f98", size=16),
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
