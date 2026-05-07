"""
File Toolkit — 全局主题配置（基于 Figma 设计稿 1:1 对齐）

色彩系统：
  主色：#005F98（深蓝）
  激活态：#00A3FF
  背景：#F4F6FF（浅蓝白）
  深色文字：#162F50

字体系统：
  标题/导航：42dot Sans
  正文/辅助：Plus Jakarta Sans
"""
import flet as ft


def build_color_scheme() -> ft.ColorScheme:
    return ft.ColorScheme(
        primary="#005F98",
        on_primary="#FFFFFF",
        primary_container="#CBDEFF",
        on_primary_container="#162F50",
        secondary="#455C7F",
        on_secondary="#FFFFFF",
        secondary_container="#DEE9FF",
        on_secondary_container="#162F50",
        tertiary="#00A3FF",
        on_tertiary="#FFFFFF",
        tertiary_container="#E0F4FF",
        on_tertiary_container="#001D33",
        surface="#F4F6FF",
        on_surface="#162F50",
        on_surface_variant="#455C7F",
        surface_container_low="#F8FAFC",
        surface_container="#F1F5F9",
        surface_container_high="#E2E8F0",
        surface_container_highest="#DEE9FF",
        surface_container_lowest="#FFFFFF",
        surface_bright="#FFFFFF",
        surface_dim="#E2E8F0",
        outline="#94A3B8",
        outline_variant="#E2E8F0",
        error="#B91C1C",
        on_error="#FFFFFF",
        error_container="#FEE2E2",
        on_error_container="#7F1D1D",
        inverse_surface="#162F50",
        inverse_primary="#CBDEFF",
    )


def build_text_theme() -> ft.TextTheme:
    return ft.TextTheme(
        display_large=ft.TextStyle(font_family="42dot Sans", weight=ft.FontWeight.BOLD),
        display_medium=ft.TextStyle(font_family="42dot Sans", weight=ft.FontWeight.BOLD),
        headline_large=ft.TextStyle(font_family="42dot Sans", weight=ft.FontWeight.W_600),
        headline_medium=ft.TextStyle(font_family="42dot Sans", weight=ft.FontWeight.W_600),
        title_large=ft.TextStyle(font_family="42dot Sans", weight=ft.FontWeight.W_500),
        title_medium=ft.TextStyle(font_family="42dot Sans", weight=ft.FontWeight.W_500),
        body_large=ft.TextStyle(font_family="Plus Jakarta Sans"),
        body_medium=ft.TextStyle(font_family="Plus Jakarta Sans"),
        body_small=ft.TextStyle(font_family="Plus Jakarta Sans"),
        label_large=ft.TextStyle(font_family="Plus Jakarta Sans", weight=ft.FontWeight.W_500),
        label_medium=ft.TextStyle(font_family="Plus Jakarta Sans"),
        label_small=ft.TextStyle(font_family="Plus Jakarta Sans"),
    )


def get_app_theme() -> tuple[ft.Theme, ft.Theme]:
    color_scheme = build_color_scheme()
    text_theme = build_text_theme()

    light = ft.Theme(
        color_scheme=color_scheme,
        text_theme=text_theme,
        font_family="Plus Jakarta Sans",
    )
    dark = ft.Theme(
        color_scheme=color_scheme,
        text_theme=text_theme,
        font_family="Plus Jakarta Sans",
    )
    return light, dark
