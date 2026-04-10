"""
File Toolkit — 全局主题配置

实现「The Fluid Architect」设计系统：
- 主色调：深青蓝 #004d64（Military-grade security 感）
- 模块色彩映射：PDF=primary, 图片=secondary, 音视频=tertiary
- No-Line 规则：禁用 1px border，用背景色变化区分层级
- 圆角规范：功能卡片 24px，标准卡片 16px，按钮 full pill
"""
import flet as ft


def build_color_scheme() -> ft.ColorScheme:
    """
    基于设计稿配置 Material You 色彩体系。
    Flet ColorScheme 参数名与 Material Design 3 Token 对应。
    """
    return ft.ColorScheme(
        primary="#004d64",
        on_primary="#ffffff",
        primary_container="#006684",
        on_primary_container="#a2e1ff",
        secondary="#4d616c",
        on_secondary="#ffffff",
        secondary_container="#d0e6f3",
        on_secondary_container="#536772",
        tertiary="#004f4f",
        on_tertiary="#ffffff",
        tertiary_container="#006969",
        on_tertiary_container="#95e5e5",
        background="#f7f9fe",
        on_background="#181c1f",
        surface="#f7f9fe",
        on_surface="#181c1f",
        surface_variant="#e0e3e7",
        on_surface_variant="#3f484d",
        outline="#70787e",
        outline_variant="#bfc8cd",
        error="#ba1a1a",
        on_error="#ffffff",
        error_container="#ffdad6",
        on_error_container="#93000a",
        inverse_surface="#2d3134",
        inverse_on_surface="#eef1f6",
        inverse_primary="#87d0f2",
    )


def build_text_theme() -> ft.TextTheme:
    """字体规范：标题使用 Manrope，正文使用 Inter。"""
    return ft.TextTheme(
        display_large=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.BOLD),
        display_medium=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.BOLD),
        headline_large=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.W_600),
        headline_medium=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.W_600),
        title_large=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.W_500),
        title_medium=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.W_500),
        body_large=ft.TextStyle(font_family="Inter"),
        body_medium=ft.TextStyle(font_family="Inter"),
        body_small=ft.TextStyle(font_family="Inter"),
        label_large=ft.TextStyle(font_family="Inter", weight=ft.FontWeight.W_500),
        label_medium=ft.TextStyle(font_family="Inter"),
        label_small=ft.TextStyle(font_family="Inter"),
    )


def get_app_theme() -> tuple[ft.Theme, ft.Theme]:
    """
    返回 (light_theme, dark_theme)。
    深色模式下 Flet 基于 color_scheme 自动生成反转色系。
    """
    color_scheme = build_color_scheme()
    text_theme = build_text_theme()

    light = ft.Theme(
        color_scheme=color_scheme,
        text_theme=text_theme,
        font_family="Inter",
    )
    dark = ft.Theme(
        color_scheme=color_scheme,
        text_theme=text_theme,
        font_family="Inter",
    )
    return light, dark
