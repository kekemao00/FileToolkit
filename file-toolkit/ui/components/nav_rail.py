"""
侧边导航栏 — 1:1 还原 Figma 设计稿

设计规格：
  宽度：256px（固定）
  背景：#FFFFFF，阴影 offset=(0,20) blur=25 spread=-5 rgba(30,58,138,0.05)
  内边距：16px
  Logo 区：48px 图标 + 标题 + 副标题
  导航项：44px 高，激活态 bg=#00A3FF 实色，r=12，文字白色，图标白色
  未激活态：无背景，r=12，文字 #475569，图标 #475569
  底部用户区：分隔线 + 用户信息
"""
import flet as ft

from ui.palette import c

# 导航项配置：(label, route, icon_outline, icon_filled)
_NAV_ITEMS = [
    ("首页",      "/",        ft.Icons.HOME_OUTLINED,          ft.Icons.HOME),
    ("AI 智能任务", "/ai",    ft.Icons.AUTO_AWESOME_OUTLINED,  ft.Icons.AUTO_AWESOME),
    ("提示词出图", "/prompt-image", ft.Icons.AUTO_FIX_HIGH_OUTLINED, ft.Icons.AUTO_FIX_HIGH),
    ("PDF工具",   "/pdf",     ft.Icons.PICTURE_AS_PDF_OUTLINED, ft.Icons.PICTURE_AS_PDF),
    ("图片工具",  "/image",   ft.Icons.IMAGE_OUTLINED,          ft.Icons.IMAGE),
    ("音视频工具", "/media",  ft.Icons.MOVIE_OUTLINED,          ft.Icons.MOVIE),
    ("压缩解压",  "/archive", ft.Icons.FOLDER_ZIP_OUTLINED,     ft.Icons.FOLDER_ZIP),
    ("OCR识别",   "/ocr",     ft.Icons.DOCUMENT_SCANNER_OUTLINED, ft.Icons.DOCUMENT_SCANNER),
    ("最近操作",  "/history", ft.Icons.HISTORY,                 ft.Icons.HISTORY),
]


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
            bgcolor=c("#ffffff"),
            border=ft.border.only(right=ft.BorderSide(1, c("#e2e8f0"))),
            shadow=ft.BoxShadow(
                spread_radius=-5,
                blur_radius=25,
                color=ft.Colors.with_opacity(0.05, c("#1e3a8a", "fg")),
                offset=ft.Offset(0, 20),
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
            padding=16,
        )

    # ── Logo 区 ──────────────────────────────────────────────────────────
    def _build_logo(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.FOLDER_SPECIAL,
                            color=c("#005f98", "fg"),
                            size=28,
                        ),
                        width=48,
                        height=48,
                        border_radius=8,
                        bgcolor=c("#ffffff"),
                        shadow=ft.BoxShadow(
                            blur_radius=2,
                            color=ft.Colors.with_opacity(0.05, c("#000000", "fg")),
                        ),
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "文件全能王",
                                size=18,
                                weight=ft.FontWeight.W_600,
                                color=c("#001d33", "fg"),
                                font_family="42dot Sans",
                            ),
                            ft.Text(
                                "一个软件，搞定所有文件",
                                size=11,
                                color=c("#001d33", "fg"),
                                font_family="42dot Sans",
                                opacity=0.7,
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
                        color=c("#ffffff", "fg") if is_selected else c("#475569", "fg"),
                        size=18,
                    ),
                    ft.Text(
                        label,
                        size=14,
                        color=c("#ffffff", "fg") if is_selected else c("#475569", "fg"),
                        font_family="42dot Sans",
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=c("#00a3ff") if is_selected else None,
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
                    ft.Divider(height=1, color=c("#e2e8f0", "fg")),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.PERSON,
                                        color=c("#ffffff", "fg"),
                                        size=20,
                                    ),
                                    width=40,
                                    height=40,
                                    border_radius=20,
                                    bgcolor=c("#005f98"),
                                    alignment=ft.Alignment(0, 0),
                                    border=ft.border.all(2, c("#ffffff")),
                                    shadow=ft.BoxShadow(
                                        blur_radius=2,
                                        color=ft.Colors.with_opacity(0.05, c("#000000", "fg")),
                                    ),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "本地用户",
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color=c("#0f172a", "fg"),
                                            font_family="42dot Sans",
                                        ),
                                        ft.Text(
                                            "免费版",
                                            size=11,
                                            color=c("#64748b", "fg"),
                                            font_family="42dot Sans",
                                        ),
                                    ],
                                    spacing=2,
                                    tight=True,
                                    expand=True,
                                ),
                                ft.Icon(
                                    ft.Icons.CHEVRON_RIGHT,
                                    color=c("#64748b", "fg"),
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
        """根据当前路由同步导航栏高亮；路由不属于任何导航项（如 /settings）时全部取消高亮。"""
        new_index = -1
        for i, (_label, r, _icon, _sel_icon) in enumerate(_NAV_ITEMS):
            if route == r or (r != "/" and route.startswith(r + "/")):
                new_index = i
                break

        if new_index == self._selected_index:
            return

        old_index = self._selected_index
        self._selected_index = new_index
        if 0 <= old_index < len(self._nav_item_refs):
            self._style_item(old_index, selected=False)
        if 0 <= new_index < len(self._nav_item_refs):
            self._style_item(new_index, selected=True)

    def _style_item(self, index: int, selected: bool) -> None:
        item = self._nav_item_refs[index]
        _, _, icon, sel_icon = _NAV_ITEMS[index]
        row: ft.Row = item.content
        row.controls[0].icon = sel_icon if selected else icon
        row.controls[0].color = c("#ffffff", "fg") if selected else c("#475569", "fg")
        row.controls[1].color = c("#ffffff", "fg") if selected else c("#475569", "fg")
        item.bgcolor = c("#00a3ff") if selected else None
