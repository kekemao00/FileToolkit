"""压缩解压中心 — 基于 Figma 设计稿 1:1 还原

布局：左侧主内容区（标题+拖拽区+文件缩略卡片网格） + 右侧参数面板
遵循核心模式：三视图互斥切换、功能卡片、参数面板、文件列表、拖拽区
"""
import asyncio
import subprocess
import sys
import time
from pathlib import Path

import flet as ft

from core.archive.handler import compress, extract
from core.models import TaskResult, TaskStatus
from services import history_service, settings_service
from services.task_service import run_task
from ui.utils import show_toast

_FUNCTIONS = [
    {"label": "ZIP 压缩", "desc": "通用兼容格式", "icon": ft.Icons.FOLDER_ZIP,
     "key": "compress_zip", "color": "#005f98", "bg": "#d5e3ff"},
    {"label": "7Z 压缩", "desc": "高压缩比", "icon": ft.Icons.INVENTORY_2,
     "key": "compress_7z", "color": "#d97706", "bg": "#fef3c7"},
    {"label": "TAR.GZ", "desc": "Linux 常用", "icon": ft.Icons.ARCHIVE,
     "key": "compress_targz", "color": "#059669", "bg": "#d1fae5"},
    {"label": "解压", "desc": "ZIP/7Z/RAR/TAR", "icon": ft.Icons.UNARCHIVE,
     "key": "extract", "color": "#7c3aed", "bg": "#ede9fe"},
]

_ARCHIVE_EXTS = {"zip", "7z", "rar", "tar", "gz", "bz2", "xz", "tgz"}


class ArchivePage(ft.Column):
    """压缩解压中心 — 工作台布局"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._files: list[Path] = []
        self._selected_func = "compress_zip"
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

        # 密码输入（加密可选）
        self._password_field = ft.TextField(
            hint_text="访问密码（可选）",
            border_radius=12, bgcolor="#d5e3ff", border_color="transparent",
            text_size=14, expand=True, password=True, can_reveal_password=True,
        )

        # 分卷大小（MB，可选）
        self._volume_field = ft.TextField(
            hint_text="分卷大小 MB（留空不分卷）",
            border_radius=12, bgcolor="#d5e3ff", border_color="transparent",
            text_size=14, expand=True, keyboard_type=ft.KeyboardType.NUMBER,
        )

        # 固实压缩开关（仅视觉占位，当前后端未实现）
        self._solid_enabled = ft.Switch(
            value=False, active_color="#005f98",
            inactive_thumb_color="#ffffff", inactive_track_color="#cbdeff",
            tooltip="固实压缩暂未开启",
        )

        # 文件列表（缩略图卡片网格）
        self._file_list = ft.Row(
            controls=[],
            wrap=True,
            spacing=12,
            run_spacing=12,
        )
        self._file_count = ft.Text("待处理文件 (0)", size=18, color="#162f50",
                                   font_family="42dot Sans")

        # 运行按钮
        self._run_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PLAY_ARROW, color="#ffffff", size=20),
                    ft.Text("立即处理 (0个文件)", size=18, color="#ffffff",
                            font_family="42dot Sans"),
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
                content=ft.Icon(f["icon"],
                                color="#ffffff" if active else f["color"], size=28),
                width=56, height=56,
                bgcolor="#005f98" if active else f["bg"],
                border_radius=14,
                alignment=ft.Alignment(0, 0),
            )
            badge = ft.Container(
                content=ft.Text(
                    str(idx + 1), size=10,
                    color="#005f98" if active else "#ffffff",
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
                blur_radius=2, color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
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
                                    "压缩解压中心", size=30,
                                    weight=ft.FontWeight.W_500,
                                    color="#005f98",
                                    font_family="42dot Sans",
                                ),
                                ft.Text(
                                    "极速无损压缩，主流格式一键互转",
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
                        content=ft.Icon(ft.Icons.FOLDER_ZIP, color="#005f98", size=40),
                        width=72, height=72,
                        bgcolor=ft.Colors.with_opacity(0.12, "#005f98"),
                        border_radius=9999,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "拖拽文件到此处",
                        size=18, color="#005f98",
                        font_family="42dot Sans",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "或点击选择文件 / 文件夹",
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
                            ft.TextButton(
                                "清空全部",
                                style=ft.ButtonStyle(color="#005f98"),
                                on_click=self._clear_files,
                            ),
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
        self._password_section = self._section("访问密码 (可选)", self._password_field)
        self._volume_section = self._section("分卷大小", self._volume_field)
        self._solid_section = self._section("固实压缩", ft.Row(
            controls=[
                ft.Icon(ft.Icons.LAYERS, color="#162f50", size=16),
                ft.Text("启用固实", size=14, color="#162f50",
                        font_family="42dot Sans"),
                ft.Container(expand=True),
                self._solid_enabled,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
                            ft.Row(controls=[self._func_btns[0], self._func_btns[1]],
                                   spacing=8),
                            ft.Row(controls=[self._func_btns[2], self._func_btns[3]],
                                   spacing=8),
                        ],
                        spacing=8,
                    )),
                    self._password_section,
                    self._volume_section,
                    self._solid_section,
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
            ft.Text(label.upper(), size=12, color="#455c7f",
                    font_family="42dot Sans"),
            content,
        ], spacing=12)

    def _update_param_sections(self) -> None:
        """按功能控制参数子区显示：解压时隐藏密码/分卷/固实。"""
        is_compress = self._selected_func != "extract"
        self._password_section.visible = is_compress
        self._volume_section.visible = is_compress
        self._solid_section.visible = is_compress

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
                    ft.Row(controls=[ft.Container(expand=True),
                                     self._progress_cancel_btn]),
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
                                content=ft.Icon(ft.Icons.CHECK_CIRCLE,
                                                color="#16a34a", size=28),
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
            col.controls[2].color = (
                ft.Colors.with_opacity(0.7, "#ffffff") if active else "#455c7f"
            )
        self._update_param_sections()
        if self._files:
            self._run_btn.content.controls[1].value = (
                f"立即处理 ({len(self._files)}个文件)"
            )
        self.update()

    def _pick_files(self, _) -> None:
        self._page.run_task(self._pick_files_async)

    async def _pick_files_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        is_extract = self._selected_func == "extract"
        try:
            if is_extract:
                files = await picker.pick_files(
                    dialog_title="选择压缩包",
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=list(_ARCHIVE_EXTS),
                    allow_multiple=False,
                )
            else:
                files = await picker.pick_files(
                    dialog_title="选择要压缩的文件",
                    file_type=ft.FilePickerFileType.ANY,
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
            if is_extract:
                # 解压模式只保留第一个压缩包
                self._files = [paths[0]]
            else:
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
                if f.is_dir():
                    size_str = "文件夹"
                else:
                    size = f.stat().st_size
                    size_str = (
                        f"{size / 1024:.1f} KB" if size < 1024 * 1024
                        else f"{size / 1024 / 1024:.1f} MB"
                    )
            except OSError:
                size_str = "?"
            ext = f.suffix.lower().lstrip(".")
            is_archive = ext in _ARCHIVE_EXTS
            is_dir = f.is_dir() if f.exists() else False
            if is_dir:
                thumb_icon = ft.Icons.FOLDER
                tag_color = "#d97706"
                tag_bg = "#fef3c7"
                tag_text = "文件夹"
            elif is_archive:
                thumb_icon = ft.Icons.FOLDER_ZIP
                tag_color = "#7c3aed"
                tag_bg = "#ede9fe"
                tag_text = ext.upper()
            else:
                thumb_icon = ft.Icons.INSERT_DRIVE_FILE
                tag_color = "#005f98"
                tag_bg = "#d5e3ff"
                tag_text = ext.upper() or "FILE"
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
                                        tag_text, size=10,
                                        weight=ft.FontWeight.BOLD,
                                        color=tag_color,
                                        font_family="Plus Jakarta Sans",
                                    ),
                                    bgcolor=tag_bg,
                                    border_radius=6,
                                    padding=ft.padding.symmetric(
                                        horizontal=6, vertical=2),
                                ),
                                ft.Container(expand=True),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_color="#94a3b8",
                                    icon_size=14,
                                    tooltip="移除",
                                    on_click=lambda _, path=f: self._remove_file(path),
                                    style=ft.ButtonStyle(
                                        overlay_color=ft.Colors.with_opacity(
                                            0.08, "#dc2626"),
                                        padding=ft.padding.all(4),
                                    ),
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        ft.Text(
                            f.name, size=13, color="#162f50",
                            font_family="42dot Sans",
                            weight=ft.FontWeight.W_500,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(size_str, size=11, color="#455c7f",
                                font_family="Plus Jakarta Sans"),
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
        self._run_btn.content.controls[1].value = (
            f"立即处理 ({len(self._files)}个文件)"
        )
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
            self._param_panel.border = ft.border.only(
                top=ft.BorderSide(1, "#d5e3ff"))
            new_body = ft.Column(
                controls=[self._main_content, self._param_panel],
                expand=True, spacing=0, scroll=ft.ScrollMode.AUTO,
            )
        else:
            self._param_panel.width = 320
            self._param_panel.border_radius = 16
            self._param_panel.border = ft.border.only(
                left=ft.BorderSide(1, "#d5e3ff"))
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
            show_toast(self._page, "请先选择文件")
            return

        out_dir = settings_service.resolve_output_dir(self._files[0])
        func = self._selected_func

        if func == "extract":
            # 解压：取第一个压缩包
            archive_files = [p for p in self._files
                             if p.suffix.lower().lstrip(".") in _ARCHIVE_EXTS]
            if not archive_files:
                show_toast(self._page, "解压需要选择压缩包文件")
                return
            kwargs = {"input_file": archive_files[0], "output_dir": out_dir}
            fn = extract
        elif func == "compress_zip":
            kwargs = {"input_files": self._files, "output_dir": out_dir,
                      "format": "zip"}
            fn = compress
        elif func == "compress_7z":
            kwargs = {"input_files": self._files, "output_dir": out_dir,
                      "format": "7z"}
            fn = compress
        elif func == "compress_targz":
            kwargs = {"input_files": self._files, "output_dir": out_dir,
                      "format": "tar.gz"}
            fn = compress
        else:
            show_toast(self._page, f"未知功能：{func}")
            return

        self._show_processing(f"{len(self._files)} 个文件")

        async def _run():
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d) -> None:
        self._update_processing_progress(c, t, d)

    def _on_complete(self, result: TaskResult) -> None:
        history_service.save_task(
            "archive", self._selected_func, result,
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

    def _update_processing_progress(self, current: int, total: int,
                                    desc: str) -> None:
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_pct.value = f"{pct}%"
        self._progress_bar.value = current / total if total > 0 else 0
        row_idx = current - 1
        row = ft.Row(
            controls=[
                ft.Icon(ft.Icons.FOLDER_ZIP, color="#005f98", size=16),
                ft.Text(desc, size=13, color="#162f50", expand=True,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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

    def _show_complete(self, result: TaskResult) -> None:
        if result.status == TaskStatus.SUCCESS:
            self._result_title.value = "处理完成！"
            self._result_title.color = "#16a34a"
        else:
            self._result_title.value = f"处理失败：{result.error_message or '未知错误'}"
            self._result_title.color = "#dc2626"

        self._result_file_rows.controls.clear()
        # 对于压缩：output_files 是生成的归档；对于解压：output_dir 是解压目标
        display_files = result.output_files or []
        if not display_files and result.output_dir:
            display_files = []
            try:
                # 解压后无列表文件，展示目标目录本身
                self._result_file_rows.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_OPEN, color="#005f98",
                                        size=16),
                                ft.Text(
                                    str(result.output_dir), size=13,
                                    color="#162f50", expand=True, max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        "已解压", size=10, color="#16a34a",
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    bgcolor="#dcfce7",
                                    border_radius=6,
                                    padding=ft.padding.symmetric(
                                        horizontal=8, vertical=2),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FOLDER_OPEN,
                                    icon_color="#005f98",
                                    icon_size=16,
                                    tooltip="打开目录",
                                    on_click=lambda _, p=result.output_dir:
                                        self._open_dir(p),
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
            except (OSError, AttributeError):
                pass
        else:
            for fp in display_files[:8]:
                self._result_file_rows.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_ZIP, color="#005f98",
                                        size=16),
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
                                    padding=ft.padding.symmetric(
                                        horizontal=8, vertical=2),
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
            if len(display_files) > 8:
                self._result_file_rows.controls.append(
                    ft.Text(f"…共 {len(display_files)} 个文件",
                            size=12, color="#455c7f")
                )

        self._workspace_view.visible = False
        self._processing_view.visible = False
        self._complete_view.visible = True
        self.update()

    def _open_output_folder(self, _) -> None:
        if self._output_dir and self._output_dir.exists():
            self._open_dir(self._output_dir)

    def _open_dir(self, path: Path) -> None:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

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


# 解压输入参数适配包装（预留：若将来需要批量解压多个压缩包）
def _batch_extract(
    input_files: list[Path],
    output_dir: Path,
    progress_callback=None,
):
    t0 = time.time()
    if not input_files:
        return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")
    output_dirs: list[Path] = []
    total = len(input_files)
    for i, path in enumerate(input_files, start=1):
        res = extract(path, output_dir, progress_callback=None)
        if res.status == TaskStatus.FAILED:
            return TaskResult(
                status=TaskStatus.FAILED,
                error_message=res.error_message,
                output_dir=output_dir,
                duration_seconds=time.time() - t0,
            )
        if res.output_dir:
            output_dirs.append(res.output_dir)
        if progress_callback:
            progress_callback(i, total, f"已解压：{path.name} ({i}/{total})")
    return TaskResult(
        status=TaskStatus.SUCCESS,
        output_files=[],
        output_dir=output_dir,
        duration_seconds=time.time() - t0,
    )
