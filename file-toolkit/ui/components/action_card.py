"""
功能入口卡片 — xl 圆角（24px），悬停 Ambient Shadow

来自 Fluid Architect 设计系统：
- 默认背景：surface-container-low (#f1f4f8)
- 悬停：surface-container-high + box-shadow: 0 12px 40px rgba(0,77,100,0.08)
- 无边框（No-Line 规则）
"""
import flet as ft


class ActionCard(ft.Container):
    """
    功能入口卡片，用于模块列表页（如 PDF 工具集列表）。

    Args:
        icon: Material Symbol 图标名
        title: 功能名称
        subtitle: 简短描述
        on_click: 点击回调
        icon_color: 图标颜色（对应模块色，默认 primary）
    """

    def __init__(
        self,
        icon: str,
        title: str,
        subtitle: str,
        on_click: callable,
        icon_color: str | None = None,
    ) -> None:
        self._icon = icon
        self._title = title
        self._subtitle = subtitle
        self._icon_color = icon_color or ft.Colors.PRIMARY

        super().__init__(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            icon,
                            color=self._icon_color,
                            size=32,
                        ),
                        width=56,
                        height=56,
                        border_radius=ft.border_radius.all(16),
                        bgcolor=ft.Colors.with_opacity(0.08, self._icon_color),
                        alignment=ft.alignment.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                title,
                                weight=ft.FontWeight.W_600,
                                font_family="42dot Sans",
                                size=15,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                subtitle,
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                font_family="Plus Jakarta Sans",
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(
                        ft.Icons.ARROW_FORWARD_IOS,
                        size=16,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.all(20),
            border_radius=ft.border_radius.all(24),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            on_click=on_click,
            on_hover=self._on_hover,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    def _on_hover(self, e: ft.ControlEvent) -> None:
        if e.data == "true":
            self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGH
            self.shadow = ft.BoxShadow(
                spread_radius=0,
                blur_radius=40,
                offset=ft.Offset(0, 12),
                color=ft.Colors.with_opacity(0.08, "#004d64"),
            )
        else:
            self.bgcolor = ft.Colors.SURFACE_CONTAINER_LOW
            self.shadow = None
        self.update()
