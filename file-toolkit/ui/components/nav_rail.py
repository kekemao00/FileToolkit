"""
侧边导航栏 — 基于 Figma 设计稿

设计规格：
  宽度：256px（固定）
  背景：渐变 #f8fafc → #f1f5f9，右侧 1px border #e2e8f0
  Logo 区：48px 图标 + 标题 + 副标题
  导航项：44px 高，激活态背景 rgba(0,163,255,0.08)，激活色 #00a3ff
  底部：用户信息区
"""
import flet as ft

# 导航项配置：(label, route, icon_name)
_NAV_ITEMS = [
    ("首页",      "/",        ft.Icons.HOME_OUTLINED,          ft.Icons.HOME),
    ("AI 智能任务", "/ai",    ft.Icons.AUTO_AWESOME_OUTLINED,  ft.Icons.AUTO_AWESOME),
    ("PDF工具",   "/pdf",     ft.Icons.PICTURE_AS_PDF_OUTLINED, ft.Icons.PICTURE_AS_PDF),
    ("图片工具",  "/image",   ft.Icons.IMAGE_OUTLINED,          ft.Icons.IMAGE),
    ("音视频工具", "/media",  ft.Icons.MOVIE_OUTLINED,          ft.Icons.MOVIE),
    ("压缩解压",  "/archive", ft.Icons.FOLDER_ZIP_OUTLINED,     ft.Icons.FOLDER_ZIP),
    ("OCR识别",   "/ocr",     ft.Icons.DOCUMENT_SCANNER_OUTLINED, ft.Icons.DOCUMENT_SCANNER),
    ("最近操作",  "/history", ft.Icons.HISTORY,                 ft.Icons.HISTORY),
]

# 不在主导航中但需要 sync 的路由前缀映射
_ROUTE_PREFIX_MAP = {
    "/pdf":     1,  # index in _NAV_ITEMS
    "/image":   2,
    "/media":   3,
    "/archive": 4,
    "/ocr":     5,
}


class NavRail(ft.Container):
    """
    自定义侧边导航栏，完全按照 Figma 设计实现。
    on_navigate: 路由跳转回调。
    """

    def __init__(self, on_navigate: callable) -> None:
        self._on_navigate = on_navigate
        self._selected_index = 0
        self._nav_item_refs: list[ft.Container] = []

        super().__init__(
            width=256,
            expand_loose=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
                colors=["#f8fafc", "#f1f5f9"],
            ),
            border=ft.border.only(right=ft.BorderSide(1, "#e2e8f0")),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=25,
                color=ft.Colors.with_opacity(0.05, "#1e3a8a"),
                offset=ft.Offset(20, 0),
            ),
            content=ft.Column(
                controls=[
                    self._build_logo(),
                    self._build_nav_list(),
                    self._build_user_section(),
                ],
                spacing=0,
                expand=True,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=16),
        )

    # ── Logo 区 ──────────────────────────────────────────────────────────
    def _build_logo(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.FOLDER_SPECIAL,
                            color="#005f98",
                            size=28,
                        ),
                        width=48,
                        height=48,
                        border_radius=8,
                        bgcolor="#ffffff",
                        shadow=ft.BoxShadow(
                            blur_radius=2,
                            color=ft.Colors.with_opacity(0.05, "#000000"),
                        ),
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "文件全能王",
                                size=18,
                                weight=ft.FontWeight.W_600,
                                color="#001d33",
                                font_family="Manrope",
                            ),
                            ft.Text(
                                "一个软件，搞定所有文件",
                                size=11,
                                color=ft.Colors.with_opacity(0.7, "#001d33"),
                                font_family="Manrope",
                            ),
                        ],
                        spacing=2,
                        tight=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(bottom=32),
        )

    # ── 导航列表 ─────────────────────────────────────────────────────────
    def _build_nav_list(self) -> ft.Control:
        self._nav_item_refs.clear()
        items = []
        for i, (label, route, icon, selected_icon) in enumerate(_NAV_ITEMS):
            item = self._build_nav_item(i, label, route, icon, selected_icon)
            self._nav_item_refs.append(item)
            items.append(item)

        return ft.Container(
            content=ft.Column(controls=items, spacing=4),
            expand=True,
        )

    def _build_nav_item(
        self,
        index: int,
        label: str,
        route: str,
        icon: str,
        selected_icon: str,
    ) -> ft.Container:
        is_selected = index == self._selected_index
        item_ref = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        selected_icon if is_selected else icon,
                        color="#00a3ff" if is_selected else "#475569",
                        size=18,
                    ),
                    ft.Text(
                        label,
                        size=14,
                        color="#00a3ff" if is_selected else "#475569",
                        font_family="Manrope",
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.08, "#00a3ff") if is_selected else None,
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            on_click=lambda e, r=route: self._on_navigate(r),
            ink=True,
            data=index,
        )
        return item_ref

    # ── 用户信息区 ───────────────────────────────────────────────────────
    def _build_user_section(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.5, "#e2e8f0")),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.PERSON,
                                        color="#ffffff",
                                        size=20,
                                    ),
                                    width=40,
                                    height=40,
                                    border_radius=20,
                                    bgcolor="#005f98",
                                    alignment=ft.Alignment(0, 0),
                                    border=ft.border.all(2, "#ffffff"),
                                    shadow=ft.BoxShadow(
                                        blur_radius=2,
                                        color=ft.Colors.with_opacity(0.05, "#000000"),
                                    ),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "本地用户",
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color="#0f172a",
                                            font_family="Manrope",
                                        ),
                                        ft.Text(
                                            "免费版",
                                            size=11,
                                            color="#64748b",
                                            font_family="Manrope",
                                        ),
                                    ],
                                    spacing=2,
                                    tight=True,
                                    expand=True,
                                ),
                                ft.Icon(
                                    ft.Icons.CHEVRON_RIGHT,
                                    color="#64748b",
                                    size=16,
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        border_radius=8,
                        ink=True,
                        on_click=lambda e: self._on_navigate("/settings"),
                    ),
                ],
                spacing=0,
            ),
            padding=ft.padding.only(top=8),
        )

    # ── 公共方法 ─────────────────────────────────────────────────────────
    def sync_selected(self, route: str) -> None:
        """根据当前路由同步导航栏高亮。"""
        new_index = 0
        for i, (label, r, icon, sel_icon) in enumerate(_NAV_ITEMS):
            if route == r or (r != "/" and route.startswith(r)):
                new_index = i
                break

        if new_index == self._selected_index:
            return

        old_index = self._selected_index
        self._selected_index = new_index

        # 更新旧选中项
        if old_index < len(self._nav_item_refs):
            old_item = self._nav_item_refs[old_index]
            _, _, icon, sel_icon = _NAV_ITEMS[old_index]
            row: ft.Row = old_item.content
            row.controls[0].name = icon
            row.controls[0].color = "#475569"
            row.controls[1].color = "#475569"
            old_item.bgcolor = None

        # 更新新选中项
        if new_index < len(self._nav_item_refs):
            new_item = self._nav_item_refs[new_index]
            _, _, icon, sel_icon = _NAV_ITEMS[new_index]
            row: ft.Row = new_item.content
            row.controls[0].name = sel_icon
            row.controls[0].color = "#00a3ff"
            row.controls[1].color = "#00a3ff"
            new_item.bgcolor = ft.Colors.with_opacity(0.08, "#00a3ff")
