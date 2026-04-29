"""
File Toolkit — 全局主题配置（基于 Figma 设计稿）

配色系统（浅蓝白系）：
  主色：#005f98（深蓝）
  背景：#f4f6ff（浅蓝白）
  深色文字：#162f50
  次级文字：#455c7f
  强调色：#00a3ff（激活态）
"""
import flet as ft


def build_color_scheme() -> ft.ColorScheme:
    return ft.ColorScheme(
        primary="#005f98",
        on_primary="#ffffff",
        primary_container="#cbdeff",
        on_primary_container="#162f50",
        secondary="#455c7f",
        on_secondary="#ffffff",
        secondary_container="#dee9ff",
        on_secondary_container="#162f50",
        tertiary="#00a3ff",
        on_tertiary="#ffffff",
        tertiary_container="#e0f4ff",
        on_tertiary_container="#001d33",
        surface="#f4f6ff",
        on_surface="#162f50",
        on_surface_variant="#455c7f",
        surface_container_low="#f8fafc",
        surface_container="#f1f5f9",
        surface_container_high="#e2e8f0",
        surface_container_highest="#dee9ff",
        surface_container_lowest="#ffffff",
        surface_bright="#ffffff",
        surface_dim="#e2e8f0",
        outline="#94a3b8",
        outline_variant="#e2e8f0",
        error="#b91c1c",
        on_error="#ffffff",
        error_container="#fee2e2",
        on_error_container="#7f1d1d",
        inverse_surface="#162f50",
        inverse_primary="#cbdeff",
    )


def build_text_theme() -> ft.TextTheme:
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
