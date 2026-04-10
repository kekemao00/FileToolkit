"""
File Toolkit — 路由管理

路由表（共 20 个路由）：
  /                         → HomePage        首页，快速入口 + 最近任务
  /pdf                      → PdfPage         PDF 工具集列表
  /pdf/split                → PdfSplitPage    PDF 分割
  /pdf/merge                → PdfMergePage    PDF 合并
  /pdf/compress             → PdfCompressPage PDF 压缩
  /pdf/to-office            → PdfConvertPage  PDF 转 Office
  /pdf/from-office          → PdfConvertPage  Office 转 PDF
  /pdf/ocr                  → OcrPage         OCR 识别（联网）
  /image                    → ImagePage       图片工具集列表
  /image/convert            → ImageConvertPage 格式转换
  /image/compress           → ImageCompressPage 批量压缩
  /image/watermark          → ImageWatermarkPage 添加水印
  /image/rename             → ImageRenamePage 批量重命名
  /media                    → MediaPage       音视频工具集列表
  /media/video-convert      → VideoConvertPage 视频格式转换
  /media/video-compress     → VideoCompressPage 视频压缩
  /media/audio-extract      → AudioExtractPage 音频提取
  /media/audio-convert      → AudioConvertPage 音频格式转换
  /media/video-cut          → VideoCutPage    视频剪切
  /archive                  → ArchivePage     压缩解压（Tab 切换）
  /settings                 → SettingsPage    设置
"""
import flet as ft


def setup_router(page: ft.Page) -> None:
    """注册路由表，设置初始路由为首页。"""
    def route_change(route: ft.RouteChangeEvent) -> None:
        # TODO: Week 2 实现完整路由分发（导入各页面类，根据 route 渲染）
        page.views.clear()
        page.views.append(
            ft.View(
                route="/",
                controls=[
                    ft.Text(
                        "File Toolkit — 路由初始化中",
                        style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                    ),
                ],
            )
        )
        page.update()

    def view_pop(e: ft.ViewPopEvent) -> None:
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go("/")
