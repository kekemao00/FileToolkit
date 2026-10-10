"""
File Toolkit — 路由管理

布局策略：page.add(shell) 挂载一次，内容区通过 controls 列表动态切换。
不使用 page.views / page.go() 路由栈，避免 Flet 0.84 的白屏和渲染问题。

路由表：
  /                → HomePage
  /pdf             → PdfPage      （?func=merge|split|compress|to_office|from_office|protect）
  /image           → ImagePage    （?func=compress|convert|resize|watermark|rename）
  /media           → MediaPage    （?func=video_convert|video_compress|video_cut|audio_extract|audio_convert）
  /archive         → ArchivePage  （?func=compress_zip|compress_7z|compress_targz|extract）
  /ocr             → OcrPage
  /ai              → AiTaskPage
  /prompt-image    → PromptImagePage
  /history         → HistoryPage
  /settings        → SettingsPage
  /feedback        → FeedbackPage （?kind=bug|feature）
旧的独立子页路由（如 /pdf/merge）重定向到对应工作台功能，见 _LEGACY_ROUTES。
"""
import asyncio

import flet as ft

from ui import style as s
from ui.components.nav_rail import NavRail
from ui.pages.ai_task_page import AiTaskPage
from ui.pages.archive_page import ArchivePage
from ui.pages.feedback_page import FeedbackPage
from ui.pages.history_page import HistoryPage
from ui.pages.home_page import HomePage
from ui.pages.image_page import ImagePage
from ui.pages.media_page import MediaPage
from ui.pages.ocr_page import OcrPage
from ui.pages.pdf_page import PdfPage
from ui.pages.prompt_image_page import PromptImagePage
from ui.pages.settings_page import SettingsPage
from ui.theme import set_rebuild_hook


def _parse_route(route: str) -> tuple[str, dict[str, str]]:
    """拆分 `/pdf?func=split` 为 ("/pdf", {"func": "split"})。"""
    path, _, query = route.partition("?")
    params: dict[str, str] = {}
    for pair in query.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v
    return path, params


# 旧的独立子页路由 → 工作台对应功能（功能已并入工作台）
_LEGACY_ROUTES = {
    "/pdf/merge": "/pdf?func=merge",
    "/pdf/split": "/pdf?func=split",
    "/pdf/compress": "/pdf?func=compress",
    "/pdf/to-office": "/pdf?func=to_office",
    "/pdf/from-office": "/pdf?func=from_office",
    "/pdf/ocr": "/ocr",
    "/image/convert": "/image?func=convert",
    "/image/compress": "/image?func=compress",
    "/image/watermark": "/image?func=watermark",
    "/image/rename": "/image?func=rename",
    "/media/video-convert": "/media?func=video_convert",
    "/media/video-compress": "/media?func=video_compress",
    "/media/audio-extract": "/media?func=audio_extract",
    "/media/audio-convert": "/media?func=audio_convert",
    "/media/video-cut": "/media?func=video_cut",
}


def _resolve_page(route: str, page: ft.Page) -> ft.Control:
    """根据路由字符串返回对应页面控件。"""
    route = _LEGACY_ROUTES.get(route, route)
    route, params = _parse_route(route)
    func = params.get("func")
    if route == "/":
        return HomePage(page)
    if route == "/pdf":
        return PdfPage(page, initial_func=func)
    if route == "/ocr":
        return OcrPage(page)
    if route == "/image":
        return ImagePage(page, initial_func=func)
    if route == "/media":
        return MediaPage(page, initial_func=func)
    if route == "/archive":
        return ArchivePage(page, initial_func=func)
    if route == "/ai":
        return AiTaskPage(page)
    if route == "/prompt-image":
        return PromptImagePage(page)
    if route == "/history":
        return HistoryPage(page)
    if route == "/settings":
        return SettingsPage(page)
    if route == "/feedback":
        return FeedbackPage(page, initial_kind=params.get("kind"))
    return _unknown_route_page(page, route)


def _unknown_route_page(page: ft.Page, route: str) -> ft.Column:
    """未知路由提示页面：显示路由信息 + 返回首页按钮。"""
    return ft.Column(
        controls=[
            s.empty_state(ft.Icons.SEARCH_OFF_OUTLINED, f"页面不存在: {route}",
                          "请检查入口链接或返回首页重新选择功能。"),
            s.button("返回首页", lambda _: page.go("/")),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        expand=True,
    )


def setup_router(page: ft.Page) -> None:
    """
    初始化路由体系。

    不使用 page.go() / page.views 路由栈（Flet 0.84 下会导致
    白屏或内容替换失效）。改为手动管理导航：
      - NavRail / ActionCard 的 page.go() 调用全部替换为 navigate()
      - navigate() 直接操作 content_area.controls 完成页面切换

    page
    └── Row(expand=True)
        ├── NavRail(固定宽度，可折叠)
        ├── VerticalDivider
        └── content_area(expand=True) ← 随路由替换 controls
    """
    page.padding = 0
    page.spacing = 0

    # 内容区域用 Column，通过 controls 列表切换
    frame = ft.Container(expand=True)
    content_area = ft.Column(controls=[frame], expand=True)
    current_route = "/"

    async def _fade_in() -> None:
        await asyncio.sleep(0.016)
        frame.animate_opacity = s.smooth()
        frame.opacity = 1
        frame.update()

    def navigate(route: str) -> None:
        """手动导航：切换内容区 + 同步 NavRail 高亮。"""
        nonlocal current_route
        current_route = route
        path, _ = _parse_route(route)
        nav.sync_selected(path)
        # 页面入场：新页面从透明淡入（相当于一层 canvas 色遮罩从 1 淡到 0）
        frame.animate_opacity = None
        frame.opacity = 0
        frame.content = _resolve_page(route, page)
        page.update()
        page.run_task(_fade_in)

    def rebuild() -> None:
        """主题切换后重建侧栏和当前页（颜色在构建时求值）。"""
        nonlocal nav
        nav = NavRail(on_navigate=navigate)
        shell.controls = [nav, content_area]
        navigate(current_route)

    # 将 navigate 挂到 page 上，供子页面调用 page.go() 的替代
    page.go = navigate  # type: ignore[assignment]

    nav = NavRail(on_navigate=navigate)

    shell = ft.Row(
        controls=[
            nav,
            content_area,
        ],
        expand=True,
        spacing=0,
    )

    page.add(shell)
    set_rebuild_hook(page, rebuild)
    navigate("/")
