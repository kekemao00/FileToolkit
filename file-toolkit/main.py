"""
File Toolkit — Flet 应用入口
"""
import flet as ft

from ui.theme import get_app_theme
from ui.router import setup_router


def main(page: ft.Page) -> None:
    # 窗口配置
    page.title = "File Toolkit"
    page.window_width = 1280
    page.window_height = 800
    page.window_min_width = 900
    page.window_min_height = 600

    # 字体注册（Manrope + Inter，从 assets/fonts/ 加载）
    page.fonts = {
        "Manrope": "fonts/Manrope-VariableFont_wght.ttf",
        "Inter": "fonts/Inter-VariableFont_opsz,wght.ttf",
    }

    # 主题配置
    light_theme, dark_theme = get_app_theme()
    page.theme = light_theme
    page.dark_theme = dark_theme
    page.theme_mode = ft.ThemeMode.SYSTEM

    # 路由初始化
    setup_router(page)
    page.update()


def main_entry() -> None:
    """pyproject.toml [project.scripts] 入口点"""
    ft.run(target=main, assets_dir="assets")


if __name__ == "__main__":
    main_entry()
