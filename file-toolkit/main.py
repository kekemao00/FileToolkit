"""
File Toolkit — Flet 应用入口
"""
import os
import sys
from pathlib import Path

import flet as ft

from services import history_service, settings_service, update_service
from ui.router import setup_router
from ui.theme import apply_theme_mode, get_app_theme
from ui.utils import show_toast


def _resolve_data_dir() -> Path:
    """运行时数据目录。

    打包后 flet 会设置 FLET_APP_STORAGE_DATA 指向可写的用户数据目录；
    直接写程序安装目录在 Windows「Program Files」下会因只读权限失败。
    开发环境无此变量时退回项目根的 .data/。
    """
    storage = os.environ.get("FLET_APP_STORAGE_DATA")
    if storage:
        return Path(storage)
    return Path(__file__).parent / ".data"


_DATA_DIR = _resolve_data_dir()
_DB_FILE  = _DATA_DIR / "file_toolkit.db"


def _init_services() -> None:
    """初始化数据库和设置服务（幂等，应用启动时调用一次）。"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
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
    # 打包后的 exe 自带图标；开发模式下由这里给 Windows 窗口设图标（其它平台忽略）
    page.window.icon = str(Path(__file__).parent / "assets" / "icons" / "app.ico")

    # 字体注册（Geist + Geist Mono，SIL OFL，从 assets/fonts/ 加载）；
    # 中文字形不在 Geist 里，由系统字体自动回落
    page.fonts = {
        "Geist": "fonts/Geist-Variable.ttf",
        "Geist Mono": "fonts/GeistMono-Variable.ttf",
    }

    # 主题配置（从设置读取持久化的模式）
    light_theme, dark_theme = get_app_theme()
    page.theme = light_theme
    page.dark_theme = dark_theme
    # 先确定深浅色再构建界面，页面颜色在构建时按当前主题求值
    saved_mode = settings_service.get("theme_mode", "system")
    if saved_mode not in ("system", "light", "dark"):
        saved_mode = "system"
    apply_theme_mode(page, saved_mode)

    # 跟随系统时，系统亮度变化后重建界面
    def _on_brightness_change(_) -> None:
        if settings_service.get("theme_mode", "system") == "system":
            apply_theme_mode(page, "system")

    page.on_platform_brightness_change = _on_brightness_change

    # 路由初始化
    setup_router(page)
    page.update()

    page.run_task(_startup_update_check, page)


async def _startup_update_check(page: ft.Page) -> None:
    """上次「重启并更新」的结果提示；按设置在启动后静默检查一次新版本。"""
    import asyncio

    pending = update_service.consume_pending()
    if pending:
        result, version = pending
        if result == "updated":
            show_toast(page, f"已更新到 v{version}", kind="success")
        else:
            show_toast(page, f"更新到 v{version} 未完成，可在设置里重试", kind="warning", duration=4000)
        await asyncio.sleep(3)
    if not update_service.auto_check_enabled():
        return
    # 等界面稳定、不和首屏渲染抢网络
    await asyncio.sleep(3)
    st = await update_service.check()
    if st.status == "available" and st.release:
        show_toast(page, f"发现新版本 v{st.release.version}，可在「设置 → 关于」中更新", duration=5000)


def main_entry() -> None:
    """pyproject.toml [project.scripts] 入口点"""
    import os
    # Linux / WSL 没有图形界面时自动降级到浏览器模式；Windows / macOS 总有桌面
    headless = (sys.platform.startswith("linux")
                and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"))
    if headless:
        ft.run(main, assets_dir="assets", view=ft.AppView.WEB_BROWSER)
    else:
        ft.run(main, assets_dir="assets")


if __name__ == "__main__":
    main_entry()
