"""
File Toolkit — 路由管理

布局策略：直接操作 page.controls，不使用 page.views 多视图栈。
Shell（NavRail）常驻，content_area 随路由动态替换内容。

路由表（共 21 个路由）：
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
    if route == "/settings":
        return SettingsPage(page)
    return HomePage(page)


def setup_router(page: ft.Page) -> None:
    """
    初始化路由体系。

    布局：直接在 page 上放置一个全屏 Row，不使用 page.views 多视图栈。
    NavRail 常驻左侧，content_area 是右侧可替换的 Container。

    page
    └── Row(expand=True)
        ├── NavRail(固定宽度，可折叠)
        ├── VerticalDivider
        └── content_area(expand=True) ← 随路由替换 content
    """
    # page 级别设置：无 padding，充满窗口
    page.padding = 0
    page.spacing = 0

    content_area = ft.Container(
        expand=True,
        height=page.height,  # 初始高度，后续 expand 接管
    )

    nav = NavRail(on_navigate=lambda route: page.go(route))

    shell = ft.Row(
        controls=[
            nav,
            ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
            content_area,
        ],
        expand=True,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    # 直接挂载到 page，不用 page.views
    page.add(shell)

    def route_change(e: ft.RouteChangeEvent) -> None:
        route = e.route
        nav.sync_selected(route)
        content_area.content = _resolve_page(route, page)
        page.update()

    page.on_route_change = route_change
    page.go("/")
