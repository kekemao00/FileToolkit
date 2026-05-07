"""
File Toolkit — Flet 应用入口
"""
import flet as ft
from pathlib import Path

from services import history_service, settings_service
from ui.theme import get_app_theme
from ui.router import setup_router

# 运行时数据目录（开发环境放项目根，打包后用 flet 提供的用户目录）
_DATA_DIR = Path(__file__).parent / ".data"
_DB_FILE  = _DATA_DIR / "file_toolkit.db"


def _init_services() -> None:
    """初始化数据库和设置服务（幂等，应用启动时调用一次）。"""
    _DATA_DIR.mkdir(exist_ok=True)
    history_service.init_db(_DB_FILE)
    settings_service.init_settings(_DB_FILE)


def main(page: ft.Page) -> None:
    # 数据服务初始化
    _init_services()

    # 窗口配置
    page.title = "文件全能王"
    page.window.width = 1280
    page.window.height = 800
    page.window.min_width = 1024
    page.window.min_height = 640
    page.bgcolor = "#F4F6FF"

    # 字体注册（42dot Sans + Plus Jakarta Sans，从 assets/fonts/ 加载）
    page.fonts = {
        "42dot Sans": "fonts/42dotSans-VariableFont_wght.ttf",
        "Plus Jakarta Sans": "fonts/PlusJakartaSans-VariableFont_wght.ttf",
    }

    # 主题配置（从设置读取持久化的模式）
    light_theme, dark_theme = get_app_theme()
    page.theme = light_theme
    page.dark_theme = dark_theme
    saved_mode = settings_service.get("theme_mode", "system")
    page.theme_mode = {
        "system": ft.ThemeMode.SYSTEM,
        "light":  ft.ThemeMode.LIGHT,
        "dark":   ft.ThemeMode.DARK,
    }.get(saved_mode, ft.ThemeMode.SYSTEM)

    # 路由初始化
    setup_router(page)
    page.update()


def main_entry() -> None:
    """pyproject.toml [project.scripts] 入口点"""
    import os
    # WSL 无 display 时自动降级到浏览器模式
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        ft.run(main, assets_dir="assets", view=ft.AppView.WEB_BROWSER)
    else:
        ft.run(main, assets_dir="assets")


if __name__ == "__main__":
    main_entry()
