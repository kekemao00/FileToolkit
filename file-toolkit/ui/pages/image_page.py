"""图片万能编辑器 — 基于 Figma 设计稿 1:1 还原

布局：左侧主内容区（标题+拖拽区+功能卡片+文件列表） + 右侧参数面板
"""
import asyncio
import time
from pathlib import Path

import flet as ft

from core.image.compressor import compress_images
from core.image.converter import convert_image
from core.image.resizer import resize_images
from core.image.watermark import add_text_watermark
from core.models import TaskResult
from services import history_service, settings_service
from services.task_service import run_task

_FUNCTIONS = [
    {"label": "压缩", "desc": "图片压缩与优化", "icon": ft.Icons.COMPRESS, "key": "compress",
     "color": "#005f98", "bg": "#d5e3ff"},
    {"label": "格式转换", "desc": "PNG / JPG / WebP", "icon": ft.Icons.SWAP_HORIZ, "key": "convert",
     "color": "#059669", "bg": "#d1fae5"},
    {"label": "尺寸调整", "desc": "按比例或固定尺寸", "icon": ft.Icons.PHOTO_SIZE_SELECT_LARGE,
     "key": "resize", "color": "#d97706", "bg": "#fef3c7"},
    {"label": "水印", "desc": "添加文字水印", "icon": ft.Icons.WATER_DROP_OUTLINED, "key": "watermark",
     "color": "#7c3aed", "bg": "#ede9fe"},
]

# slider 0-100 → compress_images level 枚举
def _quality_level(v: float) -> str:
    if v >= 70:
        return "low"   # 质量高 → 低压缩
    if v >= 40:
        return "medium"
    return "high"      # 质量低 → 高压缩


class ImagePage(ft.Column):
    """图片万能编辑器 — 工作台布局"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._files: list[Path] = []
        self._selected_func = "compress"
        self._task: asyncio.Task | None = None
        self._current_result: TaskResult | None = None
        self._output_dir: Path | None = None

        # ── 处理中状态组件 ──────────────────────────────
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

        # ── 完成状态组件 ────────────────────────────────
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

        # ── 压缩 / 格式转换 通用：质量滑块 ───────────────
        self._quality_value = ft.Text("85%", size=12, weight=ft.FontWeight.BOLD, color="#005f98")
        self._quality_slider = ft.Slider(
            min=0, max=100, value=85, divisions=20,
            active_color="#005f98", inactive_color="#d5e3ff",
            on_change=self._on_quality_change,
            width=270,
        )

        # ── 格式转换：目标格式 ───────────────────────────
        self._format_dropdown = ft.Dropdown(
            value="webp",
            options=[
                ft.dropdown.Option("png", "PNG"),
                ft.dropdown.Option("jpg", "JPG"),
                ft.dropdown.Option("webp", "WebP"),
                ft.dropdown.Option("bmp", "BMP"),
            ],
            border_radius=12,
            bgcolor="#d5e3ff",
            border_color="transparent",
            text_size=14,
            expand=True,
        )

        # ── 尺寸调整：宽高 + 保持比例 ────────────────────
        self._width_field = ft.TextField(
            value="1920", label="宽(px)",
            border_radius=12, bgcolor="#d5e3ff", border_color="transparent",
            text_size=14, label_style=ft.TextStyle(size=11, color="#455c7f"),
            expand=True,
        )
        self._height_field = ft.TextField(
            value="1080", label="高(px)",
            border_radius=12, bgcolor="#d5e3ff", border_color="transparent",
            text_size=14, label_style=ft.TextStyle(size=11, color="#455c7f"),
            expand=True,
        )
        self._keep_ratio_switch = ft.Switch(
            value=True, active_color="#005f98",
            inactive_thumb_color="#ffffff", inactive_track_color="#cbdeff",
        )

        # ── 水印：文字 + 位置 ────────────────────────────
        self._watermark_text = ft.TextField(
            value="© FileToolkit",
            border_radius=12, bgcolor="#d5e3ff", border_color="transparent",
            text_size=14, expand=True,
        )
        self._watermark_position = ft.Dropdown(
            value="bottom_right",
            options=[
                ft.dropdown.Option("top_left", "左上"),
                ft.dropdown.Option("top_right", "右上"),
                ft.dropdown.Option("bottom_left", "左下"),
                ft.dropdown.Option("bottom_right", "右下"),
                ft.dropdown.Option("center", "居中"),
                ft.dropdown.Option("tile", "平铺"),
            ],
            border_radius=12, bgcolor="#d5e3ff", border_color="transparent",
            text_size=14, expand=True,
        )

        # ── 文件列表 ────────────────────────────────────
        self._file_list = ft.Column(spacing=0)
        self._file_count = ft.Text(
            "待处理文件 (0)", size=18, color="#162f50", font_family="42dot Sans",
        )

        # ── 运行按钮 ────────────────────────────────────
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

        # ── 功能卡片（2×2 网格）─────────────────────────
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

        # ── 动态参数容器 ────────────────────────────────
        self._param_sections_container = ft.Column(spacing=24)
        self._update_param_sections()

        self._main_content = self._build_main_content()
        self._build_param_panel()

        # 响应式断点
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

    # ── 顶部栏 ──────────────────────────────────────────
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
                                    tooltip="搜索功能即将上线",
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                                    icon_color="#475569", icon_size=20,
                                    disabled=True,
                                    opacity=0.45,
                                    tooltip="通知功能即将上线",
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
                blur_radius=2, color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
            padding=ft.padding.symmetric(horizontal=32),
        )

    # ── 主内容区（工作台 / 处理中 / 完成 三视图切换）────
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
                                            "图片万能编辑器", size=30,
                                            weight=ft.FontWeight.W_500,
                                            color="#005f98",
                                            font_family="42dot Sans",
                                        ),
                                        ft.Text(
                                            "压缩、格式转换与尺寸调整，一站式完成",
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
                                            tooltip="网格视图即将上线",
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
                                            tooltip="列表视图即将上线",
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
            width=16, height=2, bgcolor=dash_color, border_radius=9999,
        )
        dash_column = lambda: ft.Container(  # noqa: E731
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
                            ft.TextButton("清空全部", style=ft.ButtonStyle(color="#005f98"),
                                          on_click=self._clear_files),
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

    # ── 参数面板 ────────────────────────────────────────
    def _build_param_panel(self) -> ft.Control:
        self._param_panel = ft.Container(
            content=ft.Column(
                controls=[
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
                    # 动态参数区（随功能切换）
                    self._param_sections_container,
                    # 处理按钮
                    self._run_btn,
                    ft.Text(
                        "预计耗时: 8秒 • 隐私保护已开启",
                        size=10, color="#455c7f", font_family="42dot Sans",
                        text_align=ft.TextAlign.CENTER,
                    ),
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

    def _update_param_sections(self) -> None:
        """根据所选功能刷新参数区域。"""
        sections: list[ft.Control] = []
        if self._selected_func == "compress":
            sections.append(self._section("压缩质量", ft.Column(controls=[
                ft.Row(controls=[ft.Container(expand=True), self._quality_value]),
                self._quality_slider,
                ft.Row(controls=[
                    ft.Text("体积优先", size=10, color="#455c7f"),
                    ft.Container(expand=True),
                    ft.Text("均衡", size=10, color="#455c7f"),
                    ft.Container(expand=True),
                    ft.Text("画质优先", size=10, color="#455c7f"),
                ]),
            ], spacing=8)))
        elif self._selected_func == "convert":
            sections.append(self._section("目标格式", self._format_dropdown))
            sections.append(self._section("输出质量", ft.Column(controls=[
                ft.Row(controls=[ft.Container(expand=True), self._quality_value]),
                self._quality_slider,
            ], spacing=8)))
        elif self._selected_func == "resize":
            sections.append(self._section("目标尺寸", ft.Column(controls=[
                ft.Row(controls=[self._width_field, self._height_field], spacing=8),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LINK, color="#162f50", size=16),
                            ft.Text("保持宽高比", size=14, color="#162f50", font_family="42dot Sans"),
                            ft.Container(expand=True),
                            self._keep_ratio_switch,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor="#ffffff",
                    border_radius=12,
                    padding=ft.padding.all(12),
                ),
            ], spacing=12)))
        elif self._selected_func == "watermark":
            sections.append(self._section("水印文字", self._watermark_text))
            sections.append(self._section("水印位置", self._watermark_position))

        self._param_sections_container.controls = sections

    def _section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(controls=[
            ft.Text(label.upper(), size=12, color="#455c7f", font_family="42dot Sans"),
            content,
        ], spacing=12)

    # ── 功能切换 / 滑块变化 ──────────────────────────────
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
            icon_block.bgcolor = f["color"] if active else f["bg"]
            icon_block.content.color = "#ffffff" if active else f["color"]
            badge.bgcolor = "#ffffff" if active else "#005f98"
            badge.content.color = f["color"] if active else "#ffffff"
            col.controls[1].color = "#ffffff" if active else "#162f50"
            col.controls[2].color = ft.Colors.with_opacity(0.7, "#ffffff") if active else "#455c7f"
        self._update_param_sections()
        if self._files:
            self._run_btn.content.controls[1].value = f"立即处理 ({len(self._files)}个文件)"
        self.update()

    def _on_quality_change(self, e) -> None:
        self._quality_value.value = f"{int(e.control.value)}%"
        self._quality_value.update()

    # ── 文件选择 / 列表维护 ─────────────────────────────
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
        for idx, f in enumerate(self._files):
            try:
                size = f.stat().st_size
                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
            except OSError:
                size_str = "?"
            is_last = idx == len(self._files) - 1
            ext = f.suffix.lower().lstrip(".")
            color_map = {
                "png": ("#059669", "#d1fae5"),
                "jpg": ("#dc2626", "#fee2e2"),
                "jpeg": ("#dc2626", "#fee2e2"),
                "webp": ("#2563eb", "#dbeafe"),
                "bmp": ("#7c3aed", "#ede9fe"),
                "heic": ("#d97706", "#fef3c7"),
            }
            fg, bg = color_map.get(ext, ("#005f98", "#d5e3ff"))
            item = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.IMAGE, color=fg, size=16),
                            width=32, height=32, bgcolor=bg, border_radius=6,
                            alignment=ft.Alignment(0, 0),
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
        row.controls[1].value = f"立即处理 ({len(self._files)}个文件)"
        self._run_btn.opacity = 1.0 if self._files else 0.4
        self.update()

    def _clear_files(self, _) -> None:
        self._files.clear()
        self._rebuild_file_list()

    def _remove_file(self, path: Path) -> None:
        if path in self._files:
            self._files.remove(path)
        self._rebuild_file_list()
        self._page.update()

    # ── 任务执行 ────────────────────────────────────────
    def _start_task(self, _) -> None:
        if not self._files:
            self._page.snack_bar = ft.SnackBar(content=ft.Text("请先选择文件"), duration=2000)
            self._page.snack_bar.open = True
            self._page.update()
            return

        out_dir = settings_service.resolve_output_dir(self._files[0])
        quality = int(self._quality_slider.value)

        if self._selected_func == "compress":
            kwargs = {
                "input_files": self._files,
                "output_dir": out_dir,
                "level": _quality_level(quality),
            }
            fn = compress_images
        elif self._selected_func == "convert":
            kwargs = {
                "input_files": self._files,
                "output_dir": out_dir,
                "target_format": self._format_dropdown.value,
                "quality": quality,
            }
            fn = convert_image
        elif self._selected_func == "resize":
            try:
                width = int(self._width_field.value) if self._width_field.value else None
                height = int(self._height_field.value) if self._height_field.value else None
            except ValueError:
                self._page.snack_bar = ft.SnackBar(content=ft.Text("宽/高必须为整数"), duration=2000)
                self._page.snack_bar.open = True
                self._page.update()
                return
            kwargs = {
                "input_files": self._files,
                "output_dir": out_dir,
                "width": width,
                "height": height,
                "keep_ratio": self._keep_ratio_switch.value,
            }
            fn = resize_images
        else:  # watermark
            kwargs = {
                "input_files": self._files,
                "output_dir": out_dir,
                "text": self._watermark_text.value or "",
                "position": self._watermark_position.value or "bottom_right",
            }
            fn = add_text_watermark

        self._show_processing(f"{len(self._files)} 个文件")

        async def _run():
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d):
        self._update_processing_progress(c, t, d)

    def _on_complete(self, result):
        history_service.save_task(
            "image", self._selected_func, result,
            input_desc=f"{len(self._files)} 个文件",
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

    # ── 响应式 ──────────────────────────────────────────
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

    # ── 处理中状态视图 ──────────────────────────────────
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
            for fp in result.output_files[:5]:
                self._result_file_rows.controls.append(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE, color="#005f98", size=14),
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
        import subprocess, sys
        if self._output_dir and self._output_dir.exists():
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(self._output_dir)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self._output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(self._output_dir)])
