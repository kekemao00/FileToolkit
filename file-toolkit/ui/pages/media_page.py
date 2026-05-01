"""音视频处理中心 — 基于 Figma 设计稿 13:2953 的 1:1 复刻

布局：Center Stage — 标题 + 功能标签页 + 渐变拖拽区 + 最近处理表格
"""
import asyncio
from pathlib import Path

import flet as ft

from services import history_service
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard

_FUNC_TABS = [
    {"label": "格式转换", "icon": ft.Icons.SWAP_HORIZ, "key": "convert", "route": "/media/video-convert"},
    {"label": "提取音频", "icon": ft.Icons.MUSIC_NOTE, "key": "extract", "route": "/media/audio-extract"},
    {"label": "视频压缩", "icon": ft.Icons.COMPRESS, "key": "compress", "route": "/media/video-compress"},
    {"label": "视频剪切", "icon": ft.Icons.CONTENT_CUT, "key": "cut", "route": "/media/video-cut"},
]

_FORMAT_BADGES = [
    ("MP4", "#005f98"), ("MKV", "#6b1ef3"), ("MOV", "#0891b2"), ("WAV", "#ea580c"),
]


class MediaPage(ft.Column):
    """音视频处理中心 — Center Stage 布局"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._selected_tab = "convert"
        self._files: list[Path] = []
        self._task: asyncio.Task | None = None

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)

        self.controls = [self._build_content()]

    # ── 整体内容 ──────────────────────────────────────────
    def _build_content(self) -> ft.Control:
        return ft.Container(
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack(
                expand=True,
                controls=[
                    # 装饰性模糊圆
                    ft.Container(
                        width=512, height=409,
                        border_radius=9999,
                        bgcolor=ft.Colors.with_opacity(0.08, "#6b1ef3"),
                        blur=60,
                        right=-128, top=-102,
                    ),
                    ft.Container(
                        width=384, height=307,
                        border_radius=9999,
                        bgcolor=ft.Colors.with_opacity(0.08, "#2aa7ff"),
                        blur=50,
                        left=128, bottom=-102,
                    ),
                    # 主内容
                    ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        spacing=0,
                        controls=[
                            self._build_center_stage(),
                            self._build_recent_activity(),
                        ],
                    ),
                ],
            ),
        )

    # ── Center Stage ─────────────────────────────────────
    def _build_center_stage(self) -> ft.Control:
        return ft.Container(
            padding=ft.padding.only(top=48, left=64, right=64, bottom=32),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=32,
                controls=[
                    # 标题
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Text(
                                "音视频处理中心", size=30,
                                weight=ft.FontWeight.W_500,
                                color="#162f50", font_family="Manrope",
                            ),
                            ft.Text(
                                "专业级文件转码与剪辑工具，支持超过50种媒体格式",
                                size=16, color="#455c7f", font_family="Manrope",
                            ),
                        ],
                    ),
                    # 功能标签页
                    self._build_func_tabs(),
                    # 拖拽区
                    self._build_drop_zone(),
                    # 进度/结果
                    ft.Container(
                        width=700,
                        content=ft.Column(
                            controls=[self._progress, self._result],
                            spacing=8,
                        ),
                    ),
                ],
            ),
        )

    def _build_func_tabs(self) -> ft.Control:
        tabs = []
        for t in _FUNC_TABS:
            active = t["key"] == self._selected_tab
            tab = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            t["icon"],
                            color="#ffffff" if active else "#455c7f",
                            size=16,
                        ),
                        ft.Text(
                            t["label"], size=14,
                            color="#ffffff" if active else "#455c7f",
                            font_family="Manrope",
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#005f98" if active else ft.Colors.with_opacity(0.5, "#ffffff"),
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
                border=None if active else ft.border.all(
                    1, ft.Colors.with_opacity(0.2, "#94a3b8"),
                ),
                shadow=ft.BoxShadow(
                    blur_radius=10, spread_radius=-2,
                    color=ft.Colors.with_opacity(0.2, "#005f98"),
                    offset=ft.Offset(0, 4),
                ) if active else None,
                on_click=lambda _, k=t["key"]: self._select_tab(k),
                ink=True,
                data=t["key"],
            )
            tabs.append(tab)

        return ft.Row(
            controls=tabs,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
        )

    def _build_drop_zone(self) -> ft.Control:
        # 格式徽章
        badges = []
        for label, color in _FORMAT_BADGES:
            badges.append(
                ft.Container(
                    content=ft.Text(
                        label, size=10, color=color,
                        weight=ft.FontWeight.BOLD,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.1, color),
                    border_radius=6,
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                ),
            )

        return ft.Container(
            width=700,
            height=260,
            content=ft.Stack(
                controls=[
                    # 渐变模糊背景
                    ft.Container(
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment(-1, -1),
                            end=ft.Alignment(1, 1),
                            colors=[
                                ft.Colors.with_opacity(0.05, "#005f98"),
                                ft.Colors.with_opacity(0.05, "#6b1ef3"),
                            ],
                        ),
                        border_radius=24,
                        blur=ft.Blur(4, 4),
                        expand=True,
                    ),
                    # 主体
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.MOVIE, color="#2aa7ff", size=36,
                                    ),
                                    width=72, height=72,
                                    bgcolor=ft.Colors.with_opacity(0.15, "#2aa7ff"),
                                    border_radius=9999,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Text(
                                    "拖拽文件到此处开始", size=22,
                                    color="#162f50", font_family="Manrope",
                                    weight=ft.FontWeight.W_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    "支持 MP4, MOV, MKV, AVI, MP3, WAV 等主流格式",
                                    size=14, color="#455c7f",
                                    font_family="Manrope",
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Row(
                                    controls=badges,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=8,
                                ),
                                ft.Container(
                                    content=ft.Container(
                                        content=ft.Text(
                                            "选择文件", size=16,
                                            color="#ffffff", font_family="Manrope",
                                        ),
                                        bgcolor="#005f98",
                                        border_radius=12,
                                        padding=ft.padding.symmetric(
                                            horizontal=28, vertical=10,
                                        ),
                                        shadow=ft.BoxShadow(
                                            blur_radius=15, spread_radius=-3,
                                            color=ft.Colors.with_opacity(0.3, "#005f98"),
                                            offset=ft.Offset(0, 10),
                                        ),
                                    ),
                                    on_click=self._pick_files,
                                ),
                            ],
                            spacing=12,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.7, "#ffffff"),
                        border=ft.border.all(2, ft.Colors.with_opacity(0.3, "#2aa7ff")),
                        border_radius=24,
                        padding=ft.padding.symmetric(vertical=24),
                        expand=True,
                    ),
                ],
            ),
        )

    # ── 最近处理表格 ─────────────────────────────────────
    def _build_recent_activity(self) -> ft.Control:
        tasks = history_service.get_recent_tasks(limit=5)
        media_tasks = [
            t for t in tasks if t.get("module", "").upper() == "MEDIA"
        ]

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            "文件名", size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "时长", size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=80,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "目标格式", size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=100,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "状态", size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=100,
                    ),
                ],
                spacing=0,
            ),
            border=ft.border.only(bottom=ft.BorderSide(1, "#dee9ff")),
            padding=ft.padding.only(bottom=12),
        )

        rows = ft.Column(spacing=0)
        if media_tasks:
            for task in media_tasks:
                rows.controls.append(self._build_table_row(task))
        else:
            rows.controls.append(
                ft.Container(
                    content=ft.Text(
                        "暂无处理记录", size=13, color="#94a3b8",
                        font_family="Manrope",
                    ),
                    padding=ft.padding.symmetric(vertical=20),
                    alignment=ft.Alignment(0, 0),
                ),
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "最近处理", size=16,
                                weight=ft.FontWeight.W_600,
                                color="#162f50", font_family="Manrope",
                            ),
                            ft.Container(expand=True),
                            ft.TextButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Text(
                                            "查看全部", size=13,
                                            color="#005f98", font_family="Manrope",
                                        ),
                                        ft.Icon(
                                            ft.Icons.CHEVRON_RIGHT,
                                            color="#005f98", size=14,
                                        ),
                                    ],
                                    spacing=4, tight=True,
                                ),
                                on_click=lambda _: self._page.go("/history"),
                            ),
                        ],
                    ),
                    header,
                    rows,
                ],
                spacing=12,
            ),
            bgcolor="#ffffff",
            border_radius=20,
            padding=ft.padding.all(24),
            margin=ft.margin.only(left=64, right=64, bottom=40),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
        )

    def _build_table_row(self, task: dict) -> ft.Control:
        status = task.get("status", "success")
        status_colors = {
            "success": ("#d1fae5", "#047857", "已完成"),
            "failed": ("#fee2e2", "#b91c1c", "失败"),
            "cancelled": ("#fef9c3", "#92400e", "已取消"),
            "running": ("#dee9ff", "#005f98", "处理中"),
        }
        bg, color, label = status_colors.get(status, ("#dee9ff", "#005f98", status))
        input_desc = task.get("input_desc", "")
        action = task.get("action", "")

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.MOVIE, color="#9333ea", size=14,
                                    ),
                                    width=32, height=32,
                                    bgcolor="#f3e8ff",
                                    border_radius=8,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Text(
                                    input_desc or action, size=13,
                                    color="#162f50", font_family="Manrope",
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "--", size=12, color="#455c7f", font_family="Manrope",
                        ),
                        width=80,
                    ),
                    ft.Container(
                        content=ft.Text(
                            action.upper(), size=12, color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=100,
                    ),
                    ft.Container(
                        content=ft.Container(
                            content=ft.Text(
                                label, size=10, color=color, font_family="Manrope",
                            ),
                            bgcolor=bg,
                            border_radius=9999,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        ),
                        width=100,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            border=ft.border.only(
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#dee9ff")),
            ),
            padding=ft.padding.symmetric(vertical=12),
        )

    # ── 事件处理 ──────────────────────────────────────────
    def _select_tab(self, key: str) -> None:
        self._selected_tab = key
        # 跳转到对应子页面
        route_map = {t["key"]: t["route"] for t in _FUNC_TABS}
        route = route_map.get(key)
        if route:
            self._page.go(route)

    def _pick_files(self, _) -> None:
        self._page.run_task(self._pick_files_async)

    async def _pick_files_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
            self._page.overlay.append(self._file_picker)
        picker = self._file_picker
        try:
            files = await picker.pick_files(
                dialog_title="选择音视频文件",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=[
                    "mp4", "avi", "mkv", "mov", "flv", "wmv", "webm",
                    "mp3", "wav", "flac", "aac", "ogg", "wma",
                ],
                allow_multiple=True,
            )
        except RuntimeError:
            files = None
        if not files:
            self._page.update()
            return
        paths = [Path(f.path) for f in files if f.path]
        if paths:
            self._files = paths
            # 选择文件后跳转到对应子页面
            route_map = {t["key"]: t["route"] for t in _FUNC_TABS}
            self._page.go(route_map.get(self._selected_tab, "/media/video-convert"))

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress.hide()

    def _reset(self) -> None:
        self._files.clear()
