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
from collections.abc import Callable

import flet as ft

from ui.palette import c, resolve_dark, set_dark


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


def build_dark_color_scheme() -> ft.ColorScheme:
    """深色方案：与 ui/palette.py 的深色表保持一致。"""
    return ft.ColorScheme(
        primary="#6CB8F0",
        on_primary="#00253F",
        primary_container="#23395C",
        on_primary_container="#CFE3FF",
        secondary="#A3B3CC",
        on_secondary="#0F1620",
        secondary_container="#1F3150",
        on_secondary_container="#E3EAF5",
        tertiary="#4DBBFF",
        on_tertiary="#001D33",
        tertiary_container="#16304A",
        on_tertiary_container="#E3EAF5",
        surface="#0F1620",
        on_surface="#E3EAF5",
        on_surface_variant="#A3B3CC",
        surface_container_low="#151D29",
        surface_container="#1A2332",
        surface_container_high="#1E2836",
        surface_container_highest="#2A3546",
        surface_container_lowest="#0B1119",
        surface_bright="#2A3546",
        surface_dim="#0F1620",
        outline="#3A4658",
        outline_variant="#2A3546",
        error="#F87171",
        on_error="#3A1A1F",
        error_container="#3A1A1F",
        on_error_container="#FECACA",
        inverse_surface="#E3EAF5",
        inverse_primary="#005F98",
    )


def build_text_theme(color: str) -> ft.TextTheme:
    """color 显式写入：Flet 不会按深浅色替换自定义 TextStyle 的默认文字色。"""
    return ft.TextTheme(
        display_large=ft.TextStyle(color=color, font_family="42dot Sans", weight=ft.FontWeight.BOLD),
        display_medium=ft.TextStyle(color=color, font_family="42dot Sans", weight=ft.FontWeight.BOLD),
        headline_large=ft.TextStyle(color=color, font_family="42dot Sans", weight=ft.FontWeight.W_600),
        headline_medium=ft.TextStyle(color=color, font_family="42dot Sans", weight=ft.FontWeight.W_600),
        title_large=ft.TextStyle(color=color, font_family="42dot Sans", weight=ft.FontWeight.W_500),
        title_medium=ft.TextStyle(color=color, font_family="42dot Sans", weight=ft.FontWeight.W_500),
        body_large=ft.TextStyle(color=color, font_family="Plus Jakarta Sans"),
        body_medium=ft.TextStyle(color=color, font_family="Plus Jakarta Sans"),
        body_small=ft.TextStyle(color=color, font_family="Plus Jakarta Sans"),
        label_large=ft.TextStyle(color=color, font_family="Plus Jakarta Sans", weight=ft.FontWeight.W_500),
        label_medium=ft.TextStyle(color=color, font_family="Plus Jakarta Sans"),
        label_small=ft.TextStyle(color=color, font_family="Plus Jakarta Sans"),
    )


def get_app_theme() -> tuple[ft.Theme, ft.Theme]:
    light = ft.Theme(
        color_scheme=build_color_scheme(),
        text_theme=build_text_theme("#162F50"),
        font_family="Plus Jakarta Sans",
    )
    dark = ft.Theme(
        color_scheme=build_dark_color_scheme(),
        text_theme=build_text_theme("#E3EAF5"),
        font_family="Plus Jakarta Sans",
    )
    return light, dark


# ── 主题切换 ─────────────────────────────────────────────────────────
# 页面颜色在构建时通过 c() 求值，切换主题后需要重建界面；
# router 在初始化时注册重建函数。
_rebuild_hooks: dict[int, Callable[[], None]] = {}


def set_rebuild_hook(page: ft.Page, hook: Callable[[], None]) -> None:
    _rebuild_hooks[id(page)] = hook


def apply_theme_mode(page: ft.Page, mode: str) -> None:
    """应用主题模式（system / light / dark）并重建界面。"""
    dark = resolve_dark(mode, page)
    set_dark(dark)
    page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
    page.bgcolor = c("#f4f6ff")
    hook = _rebuild_hooks.get(id(page))
    if hook:
        hook()
