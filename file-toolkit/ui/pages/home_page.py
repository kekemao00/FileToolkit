"""
首页 — 基于 Figma 设计稿

布局：
  顶部栏（毛玻璃）+ Hero 区域 + 工具卡片网格（5列）+ 最近操作表格
"""
import flet as ft

from services import history_service

# 工具卡片配置：(title, subtitle, icon, icon_bg, badge1, badge2, badge1_bg, badge2_bg, route)
_TOOL_CARDS = [
    (
        "PDF工具", "合并、拆分或压缩\nPDF 文档",
        ft.Icons.PICTURE_AS_PDF, "#fef2f2",
        "PDF", "DOC", "#fee2e2", "#dbeafe",
        "/pdf",
    ),
    (
        "图片工具", "无损压缩、格式转换与\n裁剪",
        ft.Icons.IMAGE, "#f0fdf4",
        "PNG", "JPG", "#dcfce7", "#ffedd5",
        "/image",
    ),
    (
        "音视频工具", "转码、提取音频或剪辑",
        ft.Icons.MOVIE, "#faf5ff",
        "MP4", "GIF", "#f3e8ff", "#fef9c3",
        "/media",
    ),
    (
        "压缩解压", "极速打包与安全解压文\n件",
        ft.Icons.FOLDER_ZIP, "#eff6ff",
        "ZIP", "7Z", "#dbeafe", "#f1f5f9",
        "/archive",
    ),
    (
        "OCR识别", "从图像提取可编辑的文\n本",
        ft.Icons.DOCUMENT_SCANNER, "#ecfeff",
        "TXT", "OCR", "#cffafe", "#d1fae5",
        "/ocr",
    ),
]

_STATUS_COLORS = {
    "success":   ("#d1fae5", "#047857"),
    "failed":    ("#fee2e2", "#b91c1c"),
    "cancelled": ("#fef9c3", "#92400e"),
    "running":   ("#dee9ff", "#005f98"),
}

_STATUS_LABELS = {
    "success":   "已完成",
    "failed":    "解析失败",
    "cancelled": "已取消",
    "running":   "处理中",
}


class HomePage(ft.Column):
    """首页：顶部栏 + Hero + 工具卡片 + 最近操作"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._history_rows = ft.Column(spacing=0)
        self.controls = [
            self._build_topbar(),
            self._build_body(),
        ]
        self._load_history()

    # ── 顶部栏 ────────────────────────────────────────────────────────────
    def _build_topbar(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),  # 占位，让右侧内容靠右
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                # 搜索框
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.SEARCH,
                                                color="#94a3b8",
                                                size=15,
                                            ),
                                            ft.Container(
                                                content=ft.Text(
                                                    "搜索功能或指令...",
                                                    size=13,
                                                    color="#94a3b8",
                                                    font_family="Manrope",
                                                ),
                                                padding=ft.padding.only(left=8),
                                                expand=True,
                                            ),
                                        ],
                                        spacing=0,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    width=288,
                                    height=36,
                                    bgcolor=ft.Colors.with_opacity(0.5, "#f8fafc"),
                                    border=ft.border.all(1, ft.Colors.with_opacity(0.6, "#e2e8f0")),
                                    border_radius=18,
                                    padding=ft.padding.symmetric(horizontal=15),
                                ),
                                # 通知按钮
                                ft.IconButton(
                                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                                    icon_color="#475569",
                                    icon_size=20,
                                    tooltip="通知",
                                ),
                                # 设置按钮
                                ft.IconButton(
                                    icon=ft.Icons.SETTINGS_OUTLINED,
                                    icon_color="#475569",
                                    icon_size=20,
                                    tooltip="设置",
                                    on_click=lambda e: self._page.go("/settings"),
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
            bgcolor=ft.Colors.with_opacity(0.8, "#ffffff"),
            blur=ft.Blur(12, 12),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#e2e8f0"))),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
            padding=ft.padding.only(left=40, right=24),
        )

    # ── 主体内容 ──────────────────────────────────────────────────────────
    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._build_hero(),
                    self._build_tools_section(),
                    self._build_history_section(),
                ],
                spacing=40,
            ),
            padding=ft.padding.all(40),
            expand=True,
        )

    # ── Hero 区域 ─────────────────────────────────────────────────────────
    def _build_hero(self) -> ft.Control:
        feature_cards = [
            ("智能推荐", ft.Icons.LIGHTBULB_OUTLINED),
            ("极速处理", ft.Icons.BOLT_OUTLINED),
            ("隐私保护", ft.Icons.LOCK_OUTLINED),
            ("多端同步", ft.Icons.SYNC_OUTLINED),
        ]
        feature_grid = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self._build_feature_card(label, icon)
                            for label, icon in feature_cards[:2]
                        ],
                        spacing=16,
                    ),
                    ft.Row(
                        controls=[
                            self._build_feature_card(label, icon)
                            for label, icon in feature_cards[2:]
                        ],
                        spacing=16,
                    ),
                ],
                spacing=16,
            ),
            width=409,
            height=320,
            bgcolor=ft.Colors.with_opacity(0.4, "#ffffff"),
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, "#ffffff")),
            border_radius=16,
            shadow=ft.BoxShadow(
                blur_radius=50,
                color=ft.Colors.with_opacity(0.25, "#000000"),
                offset=ft.Offset(0, 25),
            ),
            blur=ft.Blur(2, 2),
            padding=ft.padding.all(24),
            alignment=ft.Alignment(0, 0),
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    # 左侧文字
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "一个软件，",
                                            size=48,
                                            weight=ft.FontWeight.W_500,
                                            color="#162f50",
                                            font_family="Manrope",
                                            height=1.0,
                                        ),
                                        ft.Text(
                                            "搞定所有文件",
                                            size=48,
                                            weight=ft.FontWeight.W_500,
                                            color="#005f98",
                                            font_family="Manrope",
                                            italic=True,
                                            height=1.0,
                                        ),
                                    ],
                                    spacing=0,
                                    tight=True,
                                ),
                                ft.Text(
                                    "简单高效的工具集，一站式解决您的 PDF 转换、图像优化及媒体处理需求。",
                                    size=18,
                                    color="#455c7f",
                                    font_family="Manrope",
                                    max_lines=2,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.ElevatedButton(
                                            "快速开始",
                                            style=ft.ButtonStyle(
                                                bgcolor="#005f98",
                                                color="#ecf3ff",
                                                shape=ft.RoundedRectangleBorder(radius=12),
                                                padding=ft.padding.symmetric(horizontal=32, vertical=12),
                                                shadow_color=ft.Colors.with_opacity(0.2, "#005f98"),
                                                elevation={"": 4, "hovered": 8},
                                            ),
                                            on_click=lambda e: self._page.go("/pdf"),
                                        ),
                                        ft.ElevatedButton(
                                            "了解更多",
                                            style=ft.ButtonStyle(
                                                bgcolor="#cbdeff",
                                                color="#005f98",
                                                shape=ft.RoundedRectangleBorder(radius=12),
                                                padding=ft.padding.symmetric(horizontal=32, vertical=12),
                                                elevation={"": 0},
                                            ),
                                        ),
                                    ],
                                    spacing=16,
                                ),
                            ],
                            spacing=16,
                        ),
                        width=407,
                    ),
                    # 右侧特性卡片
                    feature_grid,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#ebf1ff",
            border_radius=24,
            padding=ft.padding.all(48),
        )

    def _build_feature_card(self, label: str, icon: str) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(icon, color="#455c7f", size=28),
                    ft.Text(
                        label,
                        size=10,
                        color="#455c7f",
                        font_family="Manrope",
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                tight=True,
            ),
            bgcolor="#ffffff",
            border_radius=12,
            padding=ft.padding.all(16),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
            expand=True,
        )

    # ── 工具卡片网格 ──────────────────────────────────────────────────────
    def _build_tools_section(self) -> ft.Control:
        cards = ft.Row(
            controls=[
                self._build_tool_card(*card)
                for card in _TOOL_CARDS
            ],
            spacing=24,
        )
        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            "常用工具",
                            size=20,
                            weight=ft.FontWeight.W_500,
                            color="#162f50",
                            font_family="Manrope",
                        ),
                        ft.Container(expand=True),
                        ft.TextButton(
                            content=ft.Row(
                                controls=[
                                    ft.Text(
                                        "查看全部",
                                        size=14,
                                        color="#005f98",
                                        font_family="Manrope",
                                    ),
                                    ft.Icon(
                                        ft.Icons.CHEVRON_RIGHT,
                                        color="#005f98",
                                        size=16,
                                    ),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                        ),
                    ],
                ),
                cards,
            ],
            spacing=24,
        )

    def _build_tool_card(
        self,
        title: str,
        subtitle: str,
        icon: str,
        icon_bg: str,
        badge1: str,
        badge2: str,
        badge1_bg: str,
        badge2_bg: str,
        route: str,
    ) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    # 图标
                    ft.Container(
                        content=ft.Icon(icon, color="#162f50", size=25),
                        width=56,
                        height=56,
                        bgcolor=icon_bg,
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    # 标题
                    ft.Container(
                        content=ft.Text(
                            title,
                            size=16,
                            color="#162f50",
                            font_family="Manrope",
                            weight=ft.FontWeight.W_500,
                        ),
                        padding=ft.padding.only(top=20),
                    ),
                    # 副标题
                    ft.Text(
                        subtitle,
                        size=12,
                        color="#455c7f",
                        font_family="Manrope",
                        max_lines=2,
                    ),
                    # 格式徽章
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(
                                        badge1,
                                        size=8,
                                        color="#162f50",
                                        text_align=ft.TextAlign.CENTER,
                                        font_family="Manrope",
                                    ),
                                    width=24,
                                    height=24,
                                    bgcolor=badge1_bg,
                                    border_radius=12,
                                    border=ft.border.all(2, "#ffffff"),
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        badge2,
                                        size=8,
                                        color="#162f50",
                                        text_align=ft.TextAlign.CENTER,
                                        font_family="Manrope",
                                    ),
                                    width=24,
                                    height=24,
                                    bgcolor=badge2_bg,
                                    border_radius=12,
                                    border=ft.border.all(2, "#ffffff"),
                                    alignment=ft.Alignment(0, 0),
                                    margin=ft.margin.only(left=-8),
                                ),
                            ],
                            spacing=0,
                        ),
                        padding=ft.padding.only(top=12),
                    ),
                ],
                spacing=4,
            ),
            bgcolor="#ffffff",
            border_radius=16,
            padding=ft.padding.all(24),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
            expand=True,
            ink=True,
            on_click=lambda e, r=route: self._page.go(r),
        )

    # ── 最近操作 ──────────────────────────────────────────────────────────
    def _build_history_section(self) -> ft.Control:
        self._empty_hint = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.HISTORY, size=48, color="#94a3b8"),
                    ft.Text(
                        "暂无历史记录",
                        color="#455c7f",
                        size=14,
                        font_family="Manrope",
                    ),
                    ft.Text(
                        "完成第一次文件处理后，这里会显示记录",
                        color="#94a3b8",
                        size=12,
                        font_family="Manrope",
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=32),
            alignment=ft.Alignment(0, 0),
        )

        header_row = ft.Container(
            content=ft.Row(
                controls=[
                    self._build_table_header("文件名", expand=True),
                    self._build_table_header("类型", width=96),
                    self._build_table_header("状态", width=178),
                    self._build_table_header("时间", width=97),
                    self._build_table_header("操作", width=158, align=ft.TextAlign.RIGHT),
                ],
                spacing=0,
            ),
            border=ft.border.only(bottom=ft.BorderSide(1, "#dee9ff")),
            padding=ft.padding.only(bottom=16),
        )

        view_all_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.TextButton(
                            "查看所有历史记录",
                            style=ft.ButtonStyle(
                                color="#455c7f",
                                shape=ft.RoundedRectangleBorder(radius=12),
                                side=ft.BorderSide(1, "#dee9ff"),
                                padding=ft.padding.symmetric(horizontal=17, vertical=9),
                            ),
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "最近操作",
                                size=20,
                                weight=ft.FontWeight.W_500,
                                color="#162f50",
                                font_family="Manrope",
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.FILTER_LIST,
                                icon_color="#455c7f",
                                icon_size=18,
                                tooltip="筛选",
                            ),
                            ft.IconButton(
                                icon=ft.Icons.MORE_VERT,
                                icon_color="#455c7f",
                                icon_size=16,
                                tooltip="更多",
                            ),
                        ],
                    ),
                    header_row,
                    self._history_rows,
                    self._empty_hint,
                    view_all_btn,
                ],
                spacing=24,
            ),
            bgcolor="#ffffff",
            border_radius=24,
            padding=ft.padding.all(24),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
        )

    def _build_table_header(
        self,
        text: str,
        expand: bool = False,
        width: int | None = None,
        align: ft.TextAlign = ft.TextAlign.LEFT,
    ) -> ft.Control:
        ctrl = ft.Text(
            text.upper(),
            size=12,
            color="#455c7f",
            font_family="Manrope",
            text_align=align,
        )
        if expand:
            return ft.Container(content=ctrl, expand=True)
        return ft.Container(content=ctrl, width=width)

    # ── 数据加载 ──────────────────────────────────────────────────────────
    def _load_history(self) -> None:
        tasks = history_service.get_recent_tasks(limit=10)
        self._history_rows.controls.clear()

        if not tasks:
            self._empty_hint.visible = True
            return

        self._empty_hint.visible = False
        for task in tasks:
            self._history_rows.controls.append(self._build_history_row(task))

    def _build_history_row(self, task: dict) -> ft.Control:
        status = task.get("status", "success")
        status_bg, status_color = _STATUS_COLORS.get(status, ("#dee9ff", "#005f98"))
        status_label = _STATUS_LABELS.get(status, status)

        module = task.get("module", "").upper()
        action = task.get("action", "")
        input_desc = task.get("input_desc", "")
        created_at = task.get("created_at", "")[:16] if task.get("created_at") else ""
        output_dir = task.get("output_dir") or ""

        # 模块图标颜色
        module_colors = {
            "PDF": ("#fee2e2", ft.Icons.PICTURE_AS_PDF),
            "IMAGE": ("#dcfce7", ft.Icons.IMAGE),
            "MEDIA": ("#f3e8ff", ft.Icons.MOVIE),
            "ARCHIVE": ("#dbeafe", ft.Icons.FOLDER_ZIP),
            "OCR": ("#cffafe", ft.Icons.DOCUMENT_SCANNER),
        }
        icon_bg, icon_name = module_colors.get(module, ("#dee9ff", ft.Icons.DESCRIPTION))

        def _open_dir(_, d=output_dir):
            if d:
                import subprocess, sys
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", d])

        # 进度条（running 状态）
        progress_widget: ft.Control
        if status == "running":
            progress_widget = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Container(
                            bgcolor="#005f98",
                            width=42,  # 约 66%
                        ),
                        width=64,
                        height=4,
                        bgcolor="#dee9ff",
                        border_radius=2,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    ),
                    ft.Text("68%", size=10, color="#005f98", font_family="Manrope"),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        else:
            progress_widget = ft.Container(
                content=ft.Container(
                    content=ft.Text(
                        status_label,
                        size=10,
                        color=status_color,
                        font_family="Manrope",
                    ),
                    bgcolor=status_bg,
                    border_radius=9999,
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                ),
            )

        return ft.Container(
            content=ft.Row(
                controls=[
                    # 文件名列
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(icon_name, color="#162f50", size=13),
                                    width=32,
                                    height=32,
                                    bgcolor=icon_bg,
                                    border_radius=8,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            input_desc or f"{module} · {action}",
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color="#162f50",
                                            font_family="Manrope",
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Text(
                                            task.get("input_desc", ""),
                                            size=10,
                                            color="#455c7f",
                                            font_family="Manrope",
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                    ],
                                    spacing=2,
                                    tight=True,
                                    expand=True,
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        expand=True,
                    ),
                    # 类型列
                    ft.Container(
                        content=ft.Text(
                            action,
                            size=12,
                            color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=96,
                    ),
                    # 状态列
                    ft.Container(
                        content=progress_widget,
                        width=178,
                    ),
                    # 时间列
                    ft.Container(
                        content=ft.Text(
                            created_at,
                            size=12,
                            color="#455c7f",
                            font_family="Manrope",
                        ),
                        width=97,
                    ),
                    # 操作列
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                                    icon_color="#455c7f",
                                    icon_size=18,
                                    tooltip="打开目录",
                                    on_click=_open_dir,
                                    visible=bool(output_dir),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.MORE_VERT,
                                    icon_color="#455c7f",
                                    icon_size=16,
                                    tooltip="更多",
                                ),
                            ],
                            spacing=0,
                            alignment=ft.MainAxisAlignment.END,
                        ),
                        width=158,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            border=ft.border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#dee9ff"))),
            padding=ft.padding.symmetric(vertical=14),
        )
