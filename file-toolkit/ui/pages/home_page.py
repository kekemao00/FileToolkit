"""首页 — 快速入口 + 最近任务"""
import flet as ft

from services import history_service
from ui.components.action_card import ActionCard

_MODULE_CARDS = [
    ("PDF 工具",   ft.Icons.PICTURE_AS_PDF, "分割 / 合并 / 压缩 / 转换", "/pdf",    ft.Colors.PRIMARY),
    ("图片工具",   ft.Icons.IMAGE,          "格式转换 / 压缩 / 水印",      "/image",  ft.Colors.SECONDARY),
    ("音视频",     ft.Icons.MOVIE,          "格式转换 / 压缩 / 剪切",      "/media",  ft.Colors.TERTIARY),
    ("压缩解压",   ft.Icons.FOLDER_ZIP,     "zip / 7z / tar.gz / rar",    "/archive", ft.Colors.OUTLINE),
]

_STATUS_ICON = {
    "success":   ("✅", ft.Colors.TERTIARY),
    "failed":    ("❌", ft.Colors.ERROR),
    "cancelled": ("⚠️", ft.Colors.OUTLINE),
}


class HomePage(ft.Column):
    """首页：顶部欢迎语 + 快速入口 4 格 + 最近任务列表"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self._history_list = ft.Column(spacing=8)
        self.spacing = 0
        self.controls = [
            self._build_header(),
            self._build_quick_entry(),
            self._build_history_section(),
        ]
        self._load_history()

    # ── 顶部欢迎区 ──────────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "你好，欢迎使用 File Toolkit",
                        style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                        font_family="Manrope",
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    ft.Text(
                        "本地处理，文件不上传，安全可靠",
                        style=ft.TextThemeStyle.BODY_MEDIUM,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.padding.only(left=28, top=28, right=28, bottom=20),
        )

    # ── 快速入口 ────────────────────────────────────────────────────
    def _build_quick_entry(self) -> ft.Control:
        grid = ft.ResponsiveRow(
            controls=[
                ft.Column(
                    col={"xs": 12, "sm": 6, "lg": 3},
                    controls=[
                        ActionCard(
                            icon=icon,
                            title=title,
                            subtitle=subtitle,
                            on_click=lambda _, r=route: self._page.go(r),
                            icon_color=color,
                        )
                    ],
                )
                for title, icon, subtitle, route, color in _MODULE_CARDS
            ],
            spacing=12,
            run_spacing=12,
        )
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "🔥 快速入口",
                        weight=ft.FontWeight.W_600,
                        font_family="Manrope",
                        size=16,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    grid,
                ],
                spacing=12,
            ),
            padding=ft.padding.symmetric(horizontal=28, vertical=8),
        )

    # ── 最近任务 ────────────────────────────────────────────────────
    def _build_history_section(self) -> ft.Control:
        self._empty_hint = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.HISTORY, size=48, color=ft.Colors.OUTLINE),
                    ft.Text(
                        "暂无历史记录",
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        size=14,
                    ),
                    ft.Text(
                        "完成第一次文件处理后，这里会显示记录",
                        color=ft.Colors.OUTLINE,
                        size=12,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=32),
            alignment=ft.alignment.Alignment(0, 0),
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "📋 最近任务",
                                weight=ft.FontWeight.W_600,
                                font_family="Manrope",
                                size=16,
                                color=ft.Colors.ON_SURFACE,
                                expand=True,
                            ),
                            ft.TextButton(
                                "清空历史",
                                on_click=self._clear_history,
                                style=ft.ButtonStyle(color=ft.Colors.ERROR),
                            ),
                        ],
                    ),
                    self._history_list,
                    self._empty_hint,
                ],
                spacing=12,
            ),
            padding=ft.padding.only(left=28, top=16, right=28, bottom=28),
        )

    # ── 数据加载 ────────────────────────────────────────────────────
    def _load_history(self) -> None:
        tasks = history_service.get_recent_tasks(limit=30)
        self._history_list.controls.clear()

        if not tasks:
            self._empty_hint.visible = True
            return

        self._empty_hint.visible = False
        for task in tasks:
            self._history_list.controls.append(self._build_task_row(task))

    def _build_task_row(self, task: dict) -> ft.Control:
        status = task.get("status", "success")
        icon_str, icon_color = _STATUS_ICON.get(status, ("ℹ️", ft.Colors.PRIMARY))
        output_dir = task.get("output_dir") or ""

        def _open_dir(_, d=output_dir):
            if d:
                import subprocess, sys
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", d])

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(icon_str, size=20),
                    ft.Column(
                        controls=[
                            ft.Text(
                                f"{task['module'].upper()} · {task['action']}",
                                weight=ft.FontWeight.W_500,
                                size=13,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                task.get("input_desc", ""),
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Text(
                        task.get("created_at", "")[:16],
                        size=11,
                        color=ft.Colors.OUTLINE,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                        tooltip="打开输出目录",
                        icon_size=18,
                        on_click=_open_dir,
                        visible=bool(output_dir),
                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            border_radius=ft.border_radius.all(16),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        )

    def _clear_history(self, _: ft.ControlEvent) -> None:
        history_service.clear_history()
        self._load_history()
        self._page.update()
