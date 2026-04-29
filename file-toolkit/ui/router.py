"""
File Toolkit — 路由管理

布局策略：page.add(shell) 挂载一次，内容区通过 controls 列表动态切换。
不使用 page.views / page.go() 路由栈，避免 Flet 0.84 的白屏和渲染问题。

路由表（共 23 个路由）：
  /                         → HomePage
  /pdf                      → PdfPage
  /pdf/split                → PdfSplitPage
  /pdf/merge                → PdfMergePage
  /pdf/compress             → PdfCompressPage
  /pdf/to-office            → PdfConvertPage (mode=to_office)
  /pdf/from-office          → PdfConvertPage (mode=from_office)
  /pdf/ocr                  → OcrPage
  /image                    → ImagePage
  /image/convert            → ImageConvertPage
  /image/compress           → ImageCompressPage
  /image/watermark          → ImageWatermarkPage
  /image/rename             → ImageRenamePage
  /media                    → MediaPage
  /media/video-convert      → VideoConvertPage
  /media/video-compress     → VideoCompressPage
  /media/audio-extract      → AudioExtractPage
  /media/audio-convert      → AudioConvertPage
  /media/video-cut          → VideoCutPage
  /archive                  → ArchivePage
  /ai                       → AiTaskPage
  /history                  → HistoryPage
  /settings                 → SettingsPage
"""
import flet as ft

from ui.components.nav_rail import NavRail
from ui.pages.home_page import HomePage
from ui.pages.pdf_page import PdfPage
from ui.pages.pdf_split_page import PdfSplitPage
from ui.pages.pdf_merge_page import PdfMergePage
from ui.pages.pdf_compress_page import PdfCompressPage
from ui.pages.pdf_convert_page import PdfConvertPage
from ui.pages.image_page import ImagePage
from ui.pages.image_convert_page import ImageConvertPage
from ui.pages.image_compress_page import ImageCompressPage
from ui.pages.image_watermark_page import ImageWatermarkPage
from ui.pages.image_rename_page import ImageRenamePage
from ui.pages.media_page import MediaPage
from ui.pages.media_video_convert_page import VideoConvertPage
from ui.pages.media_video_compress_page import VideoCompressPage
from ui.pages.media_audio_extract_page import AudioExtractPage
from ui.pages.media_audio_convert_page import AudioConvertPage
from ui.pages.media_video_cut_page import VideoCutPage
from ui.pages.archive_page import ArchivePage
from ui.pages.ocr_page import OcrPage
from ui.pages.ai_task_page import AiTaskPage
from ui.pages.history_page import HistoryPage
from ui.pages.settings_page import SettingsPage


def _resolve_page(route: str, page: ft.Page) -> ft.Control:
    """根据路由字符串返回对应页面控件。"""
    if route == "/":
        return HomePage(page)
    if route == "/pdf":
        return PdfPage(page)
    if route == "/pdf/split":
        return PdfSplitPage(page)
    if route == "/pdf/merge":
        return PdfMergePage(page)
    if route == "/pdf/compress":
        return PdfCompressPage(page)
    if route == "/pdf/to-office":
        return PdfConvertPage(page, mode="to_office")
    if route == "/pdf/from-office":
        return PdfConvertPage(page, mode="from_office")
    if route == "/pdf/ocr":
        return OcrPage(page)
    if route == "/image":
        return ImagePage(page)
    if route == "/image/convert":
        return ImageConvertPage(page)
    if route == "/image/compress":
        return ImageCompressPage(page)
    if route == "/image/watermark":
        return ImageWatermarkPage(page)
    if route == "/image/rename":
        return ImageRenamePage(page)
    if route == "/media":
        return MediaPage(page)
    if route == "/media/video-convert":
        return VideoConvertPage(page)
    if route == "/media/video-compress":
        return VideoCompressPage(page)
    if route == "/media/audio-extract":
        return AudioExtractPage(page)
    if route == "/media/audio-convert":
        return AudioConvertPage(page)
    if route == "/media/video-cut":
        return VideoCutPage(page)
    if route == "/archive":
        return ArchivePage(page)
    if route == "/ai":
        return AiTaskPage(page)
    if route == "/history":
        return HistoryPage(page)
    if route == "/settings":
        return SettingsPage(page)
    return HomePage(page)


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
    content_area = ft.Column(expand=True)

    def navigate(route: str) -> None:
        """手动导航：切换内容区 + 同步 NavRail 高亮。"""
        nav.sync_selected(route)
        content_area.controls = [_resolve_page(route, page)]
        page.update()

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
    navigate("/")
