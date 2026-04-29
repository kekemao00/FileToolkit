"""
共享顶部栏组件 — 基于 Figma 设计稿

规格：
  高度：80px
  背景：毛玻璃 rgba(255,255,255,0.8) + blur(12)
  底部边框：1px rgba(226,232,240,0.5)
  搜索框：288px 宽，圆角 18px（9999），背景 rgba(248,250,252,0.5)
  右侧：通知 + 设置图标按钮
"""
import flet as ft


class TopBar(ft.Container):
    """毛玻璃顶部栏：搜索框 + 通知 + 设置"""

    def __init__(self, page: ft.Page) -> None:
        self._page = page
        super().__init__(
            height=80,
            bgcolor=ft.Colors.with_opacity(0.8, "#ffffff"),
            blur=ft.Blur(12, 12),
            border=ft.border.only(
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#e2e8f0"))
            ),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
            padding=ft.padding.only(left=40, right=24),
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                self._build_search(),
                                ft.IconButton(
                                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                                    icon_color="#475569",
                                    icon_size=20,
                                    tooltip="通知",
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SETTINGS_OUTLINED,
                                    icon_color="#475569",
                                    icon_size=20,
                                    tooltip="设置",
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
        )

    def _build_search(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SEARCH, color="#94a3b8", size=15),
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
            border_radius=9999,
            padding=ft.padding.symmetric(horizontal=15),
        )
