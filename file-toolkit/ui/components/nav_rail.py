"""
侧边导航栏 — 展开（220dp）/ 收起（72dp图标模式）

模块色彩映射（来自 Fluid Architect 设计系统）：
  首页        primary
  PDF         primary
  图片        secondary
  音视频      tertiary
  压缩解压    surface_tint
  设置        on_surface_variant
"""
from dataclasses import dataclass

import flet as ft


@dataclass
class NavItem:
    label: str
    icon: str
    selected_icon: str
    route: str


NAV_ITEMS: list[NavItem] = [
    NavItem("首页",   ft.Icons.HOME_OUTLINED,          ft.Icons.HOME,          "/"),
    NavItem("PDF",    ft.Icons.PICTURE_AS_PDF_OUTLINED, ft.Icons.PICTURE_AS_PDF, "/pdf"),
    NavItem("图片",   ft.Icons.IMAGE_OUTLINED,          ft.Icons.IMAGE,         "/image"),
    NavItem("音视频", ft.Icons.MOVIE_OUTLINED,          ft.Icons.MOVIE,         "/media"),
    NavItem("压缩",   ft.Icons.FOLDER_ZIP_OUTLINED,     ft.Icons.FOLDER_ZIP,    "/archive"),
    NavItem("设置",   ft.Icons.SETTINGS_OUTLINED,       ft.Icons.SETTINGS,      "/settings"),
]

_COLLAPSED_WIDTH = 72
_EXPANDED_WIDTH = 220


class NavRail(ft.NavigationRail):
    """
    侧边导航栏，继承 NavigationRail。
    on_navigate: 路由跳转回调，接收目标 route str。
    """

    def __init__(self, on_navigate: callable) -> None:
        self._on_navigate = on_navigate
        self._expanded = True

        super().__init__(
            selected_index=0,
            min_width=_COLLAPSED_WIDTH,
            min_extended_width=_EXPANDED_WIDTH,
            extended=True,
            group_alignment=-1.0,
            leading=self._build_leading(),
            destinations=self._build_destinations(),
            on_change=self._handle_change,
        )

    def _build_leading(self) -> ft.Control:
        self._title_text = ft.Text(
            "File Toolkit",
            weight=ft.FontWeight.W_600,
            font_family="Manrope",
            size=15,
        )
        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.MENU,
                            tooltip="折叠/展开",
                            on_click=self._toggle_expand,
                            icon_color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        self._title_text,
                    ],
                    spacing=4,
                ),
            ],
            spacing=0,
        )

    def _build_destinations(self) -> list[ft.NavigationRailDestination]:
        return [
            ft.NavigationRailDestination(
                icon=item.icon,
                selected_icon=item.selected_icon,
                label=item.label,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
            )
            for item in NAV_ITEMS
        ]

    def _handle_change(self, e: ft.ControlEvent) -> None:
        self._on_navigate(NAV_ITEMS[int(e.data)].route)

    def _toggle_expand(self, _: ft.ControlEvent) -> None:
        self._expanded = not self._expanded
        self.extended = self._expanded
        self._title_text.visible = self._expanded
        self.update()

    def sync_selected(self, route: str) -> None:
        """根据当前路由同步导航栏高亮（子路由如 /pdf/split → /pdf）。"""
        for i, item in enumerate(NAV_ITEMS):
            if route == item.route or (item.route != "/" and route.startswith(item.route)):
                self.selected_index = i
                return
        self.selected_index = 0
