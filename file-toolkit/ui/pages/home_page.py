"""
首页

布局（canvas 底，左右 24 留白）：
  顶部栏 → 标题行（headline + 说明，主操作在最右）→ 常用工具卡片
  → 特性条（一张白卡片四等分）→ 最近操作表格（白卡片，行高 46，悬停 surface-2）
"""

import flet as ft

from services import history_service
from ui import style as s
from ui.components.top_bar import TopBar
from ui.features import ACTION_LABELS
from ui.palette import c
from ui.utils import open_folder, show_toast

# 工具卡片配置：(title, subtitle, icon, tags, route)
_TOOL_CARDS = [
    ("PDF工具", "合并、拆分或压缩 PDF 文档", ft.Icons.PICTURE_AS_PDF_OUTLINED, ("PDF", "DOC"), "/pdf"),
    ("图片工具", "无损压缩、格式转换与裁剪", ft.Icons.IMAGE_OUTLINED, ("PNG", "JPG"), "/image"),
    ("音视频工具", "转码、提取音频或剪辑", ft.Icons.MOVIE_OUTLINED, ("MP4", "MP3"), "/media"),
    ("压缩解压", "极速打包与安全解压文件", ft.Icons.FOLDER_ZIP_OUTLINED, ("ZIP", "7Z"), "/archive"),
    ("OCR识别", "从图像提取可编辑的文本", ft.Icons.DOCUMENT_SCANNER_OUTLINED, ("TXT", "OCR"), "/ocr"),
    ("提示词出图", "AI 智能生成精美图片", ft.Icons.AUTO_FIX_HIGH_OUTLINED, ("AI", "IMG"), "/prompt-image"),
]

_FEATURES = [
    ("极速处理", "本地多线程，不排队", ft.Icons.BOLT_OUTLINED),
    ("隐私保护", "文件不离开本机", ft.Icons.LOCK_OUTLINED),
    ("批量操作", "一次处理一整批", ft.Icons.LAYERS_OUTLINED),
    ("格式丰富", "主流格式自由互转", ft.Icons.SWAP_HORIZ_OUTLINED),
]

# 状态 → (圆点颜色令牌, 文字颜色令牌)
_STATUS_COLORS = {
    "success":   ("accent", "ink-2"),
    "failed":    ("danger", "danger"),
    "cancelled": ("ink-3", "ink-3"),
    "running":   ("ink", "ink"),
}

_STATUS_LABELS = {
    "success":   "已完成",
    "failed":    "失败",
    "cancelled": "已取消",
    "running":   "处理中",
}

_MODULE_ICONS = {
    "PDF": ft.Icons.PICTURE_AS_PDF_OUTLINED,
    "IMAGE": ft.Icons.IMAGE_OUTLINED,
    "MEDIA": ft.Icons.MOVIE_OUTLINED,
    "ARCHIVE": ft.Icons.FOLDER_ZIP_OUTLINED,
    "OCR": ft.Icons.DOCUMENT_SCANNER_OUTLINED,
}

# 表格列宽（文件名列自适应）
_COL_TYPE, _COL_STATUS, _COL_TIME, _COL_ACTION = 110, 110, 128, 48


class HomePage(ft.Column):
    """首页：顶部栏 + 标题行 + 工具卡片 + 特性条 + 最近操作"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._history_rows = ft.Column(spacing=0)
        self.controls = [
            self._build_topbar(),
            self._build_body(),
        ]
        self._load_history()

    def _build_topbar(self) -> ft.Control:
        return TopBar(self._page)

    # ── 主体内容 ──────────────────────────────────────────────────────────
    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._build_hero(),
                    self._build_tools_section(),
                    self._build_features(),
                    self._build_history_section(),
                ],
                spacing=24,
            ),
            padding=ft.padding.only(left=s.PAGE_X, right=s.PAGE_X, top=4, bottom=24),
            expand=True,
        )

    # ── 标题行 ───────────────────────────────────────────────────────────
    def _build_hero(self) -> ft.Control:
        return ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        s.text("一个软件，搞定所有文件", "headline"),
                        s.text("简单高效的工具集，一站式解决 PDF 转换、图像优化及媒体处理需求。", "small"),
                    ],
                    spacing=4,
                    expand=True,
                ),
                s.button("了解更多", lambda e: self._page.go("/ai"), kind="secondary"),
                s.button("快速开始", lambda e: self._page.go("/pdf"), icon=ft.Icons.ARROW_FORWARD_OUTLINED),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

    # ── 工具卡片网格 ──────────────────────────────────────────────────────
    def _build_tools_section(self) -> ft.Control:
        cards = ft.ResponsiveRow(
            controls=[self._build_tool_card(*card) for card in _TOOL_CARDS],
            spacing=12,
            run_spacing=12,
        )
        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        s.text("常用工具", "title", expand=True),
                        s.button("查看 PDF 工具", lambda e: self._page.go("/pdf"), kind="ghost",
                                 icon=ft.Icons.CHEVRON_RIGHT_OUTLINED, height=30),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                cards,
            ],
            spacing=10,
        )

    def _build_tool_card(
        self,
        title: str,
        subtitle: str,
        icon: str,
        tags: tuple[str, ...],
        route: str,
    ) -> ft.Control:
        icon_tile = s.icon_tile(icon, size=32)
        card = s.card(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            icon_tile,
                            ft.Container(expand=True),
                            *[self._tag(t) for t in tags],
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=4),
                    s.text(title, "label"),
                    s.text(subtitle, "small", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ],
                spacing=4,
            ),
            padding=16,
            col={"xs": 12, "sm": 6, "lg": 4},
            on_click=lambda e, r=route: self._page.go(r),
        )
        s.hover_surface(card)
        return card

    @staticmethod
    def _tag(label: str) -> ft.Control:
        return ft.Container(
            content=s.text(label, "caption", color="ink-2"),
            height=20,
            alignment=ft.Alignment(0, 0),
            border=ft.border.all(1, c("line-strong")),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=7),
        )

    # ── 特性条 ───────────────────────────────────────────────────────────
    def _build_features(self) -> ft.Control:
        cells: list[ft.Control] = []
        for i, (label, desc, icon) in enumerate(_FEATURES):
            cells.append(ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=16, color=c("ink-2", "fg")),
                        ft.Column(
                            controls=[s.text(label, "body-medium"), s.text(desc, "caption")],
                            spacing=1, tight=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
                border=None if i == 0 else ft.border.only(left=ft.BorderSide(1, c("line"))),
                col={"xs": 6, "md": 3},
            ))
        return s.card(ft.ResponsiveRow(controls=cells, spacing=0, run_spacing=0), padding=0)

    # ── 最近操作 ──────────────────────────────────────────────────────────
    def _build_history_section(self) -> ft.Control:
        self._empty_hint = ft.Container(
            content=s.empty_state(ft.Icons.HISTORY_OUTLINED, "暂无历史记录", "完成第一次文件处理后，这里会显示记录"),
            padding=ft.padding.symmetric(vertical=28),
            alignment=ft.Alignment(0, 0),
        )

        header_row = ft.Container(
            content=ft.Row(
                controls=[
                    self._build_table_header("文件", expand=True),
                    self._build_table_header("类型", width=_COL_TYPE),
                    self._build_table_header("状态", width=_COL_STATUS),
                    self._build_table_header("时间", width=_COL_TIME),
                    self._build_table_header("", width=_COL_ACTION),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=40,
            padding=ft.padding.symmetric(horizontal=16),
            border=ft.border.only(bottom=ft.BorderSide(1, c("line"))),
        )

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        s.text("最近操作", "title", expand=True),
                        s.button("查看全部", lambda e: self._page.go("/history"), kind="ghost",
                                 icon=ft.Icons.CHEVRON_RIGHT_OUTLINED, height=30),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                s.card(
                    ft.Column(
                        controls=[header_row, self._history_rows, self._empty_hint],
                        spacing=0,
                    ),
                    padding=ft.padding.only(bottom=4),
                ),
            ],
            spacing=10,
        )

    def _build_table_header(
        self,
        text: str,
        expand: bool = False,
        width: int | None = None,
        align: ft.TextAlign = ft.TextAlign.LEFT,
    ) -> ft.Control:
        ctrl = s.text(text, "caption", text_align=align)
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
        for i, task in enumerate(tasks):
            if i:
                self._history_rows.controls.append(
                    ft.Container(height=1, bgcolor=c("line"), margin=ft.margin.symmetric(horizontal=12))
                )
            self._history_rows.controls.append(self._build_history_row(task))

    def _build_history_row(self, task: dict) -> ft.Control:
        status = task.get("status", "success")
        dot_token, text_token = _STATUS_COLORS.get(status, ("ink-3", "ink-2"))
        status_label = _STATUS_LABELS.get(status, status)

        module = task.get("module", "").upper()
        action = task.get("action", "")
        input_desc = task.get("input_desc", "")
        created_at = task.get("created_at", "")[:16] if task.get("created_at") else ""
        output_dir = task.get("output_dir") or ""
        icon_name = _MODULE_ICONS.get(module, ft.Icons.DESCRIPTION_OUTLINED)

        def _open_dir(_, d=output_dir):
            if d and not open_folder(d):
                show_toast(self._page, "目录不存在或已被移动", kind="error")

        status_widget = ft.Row(
            controls=[
                ft.Container(width=6, height=6, border_radius=3, bgcolor=c(dot_token)),
                s.text(status_label, "small", color=text_token),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        row = ft.Container(
            content=ft.Row(
                controls=[
                    # 文件名列
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(icon_name, color=c("ink-2", "fg"), size=14),
                                    width=26,
                                    height=26,
                                    bgcolor=c("surface-3"),
                                    border_radius=13,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                s.text(input_desc or f"{module} · {action}", "body-medium",
                                       max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        expand=True,
                    ),
                    ft.Container(content=s.text(ACTION_LABELS.get(action, action), "body", color="ink-2"),
                                 width=_COL_TYPE),
                    ft.Container(content=status_widget, width=_COL_STATUS),
                    ft.Container(content=s.text(created_at, "mono"), width=_COL_TIME),
                    ft.Container(
                        content=s.icon_button(ft.Icons.FOLDER_OPEN_OUTLINED, _open_dir, tooltip="打开目录",
                                              size=28, visible=bool(output_dir)),
                        width=_COL_ACTION,
                        alignment=ft.Alignment(1, 0),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s.H_ROW,
            padding=ft.padding.only(left=16, right=12),
            animate=s.snappy(),
        )
        row.on_hover = lambda e, r=row: self._row_hover(r, e)
        return row

    @staticmethod
    def _row_hover(row: ft.Container, e: ft.ControlEvent) -> None:
        row.bgcolor = c("surface-2") if e.data in (True, "true") else None
        row.update()
