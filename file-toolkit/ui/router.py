"""
File Toolkit — 路由管理

采用「Shell + Content」布局模式：
- Shell（NavRail + 顶栏）全局常驻，不随路由销毁重建
- Content 区域根据路由动态替换

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
    # 未知路由回退到首页
    return HomePage(page)


def setup_router(page: ft.Page) -> None:
    """
    初始化路由体系。

    布局结构：
      Row(
        NavRail,           # 左侧导航，常驻
        VerticalDivider,   # 1px 分隔（通过背景色区分，No-Line 规则可选隐藏）
        content_area,      # 右侧内容，随路由切换
      )
    """
    content_area = ft.Container(expand=True)
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

    def route_change(e: ft.RouteChangeEvent) -> None:
        route = e.route
        # 更新导航栏高亮
        nav.sync_selected(route)
        # 替换内容区域
        content_area.content = ft.Column(
            controls=[_resolve_page(route, page)],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
        page.views.clear()
        page.views.append(
            ft.View(
                route=route,
                controls=[shell],
                padding=ft.padding.all(0),
                bgcolor=ft.Colors.SURFACE,
            )
        )
        page.update()

    def view_pop(e: ft.ViewPopEvent) -> None:
        page.views.pop()
        if page.views:
            page.go(page.views[-1].route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go("/")
