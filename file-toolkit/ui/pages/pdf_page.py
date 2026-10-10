"""PDF 工作台 — 合并 / 拆分 / 压缩 / 转 Office / Office 转 PDF / 加密水印"""
import os
import time
from pathlib import Path

import flet as ft

from core.models import TaskResult, TaskStatus
from core.pdf.compressor import compress_pdf
from core.pdf.converter import office_to_pdf, pdf_to_docx, pdf_to_images, pdf_to_pptx, pdf_to_xlsx
from core.pdf.encryptor import encrypt_pdf
from core.pdf.merger import merge_pdf
from core.pdf.splitter import split_pdf
from core.pdf.watermark import add_text_watermark
from ui.components.workbench import (
    ChoiceGroup,
    Workbench,
    WorkbenchFunction,
    is_mounted,
    unique_path,
)
from ui.palette import c
from ui.utils import show_toast

_PDF = ("pdf",)
_OFFICE = ("doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "rtf")


def _protect_pdf(
    input_file: Path,
    output_file: Path,
    wm_text: str,
    wm_opacity: float,
    password: str,
    progress_callback=None,
) -> TaskResult:
    """先加水印再加密（加密后内容不可再改）。每步写临时文件，最后原子替换。"""
    t0 = time.time()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    current = input_file
    tmp = output_file.with_name(output_file.name + ".tmp")
    steps = []
    if wm_text:
        steps.append(lambda src, dst: add_text_watermark(
            input_file=src, output_file=dst, text=wm_text, opacity=wm_opacity))
    if password:
        steps.append(lambda src, dst: encrypt_pdf(input_file=src, output_file=dst, user_password=password))
    for step in steps:
        res = step(current, tmp)
        if res.status != TaskStatus.SUCCESS:
            if tmp.exists():
                tmp.unlink()
            return TaskResult(status=TaskStatus.FAILED, error_message=res.error_message or "处理失败",
                              duration_seconds=time.time() - t0)
        os.replace(tmp, output_file)
        current = output_file
    return TaskResult(status=TaskStatus.SUCCESS, output_files=[output_file],
                      output_dir=output_file.parent, duration_seconds=time.time() - t0)


class PdfPage(Workbench):
    TITLE = "PDF 工作台"
    SUBTITLE = "合并、拆分、压缩、转图片、格式互转与加密水印"
    MODULE = "pdf"
    PICK_LABEL = "点击选择文件"
    PICK_ICON = ft.Icons.UPLOAD_FILE_OUTLINED
    FILE_ICON = ft.Icons.PICTURE_AS_PDF_OUTLINED
    FUNCTIONS = [
        WorkbenchFunction("merge", "合并", "多个 PDF 按顺序合成一个", ft.Icons.MERGE_OUTLINED,
                          _PDF, min_files=2, orderable=True),
        WorkbenchFunction("split", "拆分", "按页数、页码范围或逐页", ft.Icons.CONTENT_CUT_OUTLINED,
                          _PDF),
        WorkbenchFunction("compress", "压缩", "减小文件体积", ft.Icons.COMPRESS_OUTLINED,
                          _PDF, show_size=True),
        WorkbenchFunction("to_office", "转 Office", "PDF 转 Word / Excel / PPT", ft.Icons.DESCRIPTION_OUTLINED,
                          _PDF),
        WorkbenchFunction("to_images", "转图片", "每页导出为一张 PNG / JPG", ft.Icons.IMAGE_OUTLINED,
                          _PDF),
        WorkbenchFunction("from_office", "Office 转 PDF", "Word / Excel / PPT 转 PDF", ft.Icons.PICTURE_AS_PDF_OUTLINED,
                          _OFFICE),
        WorkbenchFunction("protect", "加密水印", "添加文字水印或打开密码", ft.Icons.LOCK_OUTLINED,
                          _PDF),
    ]

    def __init__(self, page: ft.Page, initial_func: str | None = None) -> None:
        # 旧深链兼容
        initial_func = {"to_word": "to_office"}.get(initial_func, initial_func)
        # 合并
        self._merge_name = self.text_field("merged.pdf", "输出文件名")
        # 拆分
        self._split_mode = ChoiceGroup(
            [("pages", "固定页数"), ("range", "页码范围"), ("each", "每页一个")], "pages",
            on_change=lambda _: self._sync_split_mode(),
        )
        self._split_pages = self.text_field("5", "每份页数", keyboard_type=ft.KeyboardType.NUMBER)
        self._split_ranges = self.text_field("", "如 1-5, 6-10, 12")
        self._split_template = self.text_field("{stem}_第{n}部分", "命名模板")
        # 压缩
        self._compress_level = ChoiceGroup(
            [("high", "轻度"), ("medium", "推荐"), ("low", "强力")], "medium",
            on_change=lambda _: self._sync_compress_hint(),
        )
        self._compress_hint = ft.Text(size=11, color=c("ink-2", "fg"))
        # 转 Office
        self._office_format = ChoiceGroup([("docx", "Word"), ("xlsx", "Excel"), ("pptx", "PPT")], "docx",
                                          on_change=lambda _: self._sync_office_hint())
        self._office_hint = ft.Text(size=11, color=c("ink-3", "fg"))
        self._sync_office_hint()
        # 转图片
        self._image_format = ChoiceGroup([("png", "PNG"), ("jpg", "JPG")], "png")
        self._image_dpi = ChoiceGroup([("96", "96 dpi"), ("150", "150 dpi"), ("300", "300 dpi")], "150")
        # 加密水印
        self._wm_text = self.text_field("", "水印文字，留空则不加")
        self._wm_opacity = ft.Slider(min=10, max=80, value=30, divisions=7, label="{value}%",
                                     active_color=c("ink", "fg"), inactive_color=c("surface-3"), expand=True)
        self._password = self.text_field("", "打开密码，留空则不加密", password=True, can_reveal_password=True)

        self._sync_split_mode()
        self._sync_compress_hint()
        super().__init__(page, initial_func)

    def _sync_split_mode(self) -> None:
        mode = self._split_mode.value
        self._split_pages.visible = mode == "pages"
        self._split_ranges.visible = mode == "range"
        if is_mounted(self._split_pages):
            self._split_pages.update()
            self._split_ranges.update()

    def _sync_compress_hint(self) -> None:
        self._compress_hint.value = {
            "high": "只去除冗余数据，图片不重新编码，画质无损",
            "medium": "图片按 JPEG 72 质量重新编码，体积和画质较均衡",
            "low": "图片 JPEG 45 质量并降到 150dpi，体积最小",
        }[self._compress_level.value]
        if is_mounted(self._compress_hint):
            self._compress_hint.update()

    def _sync_office_hint(self) -> None:
        self._office_hint.value = {
            "docx": "尽量还原排版，文字可编辑；扫描件需先做 OCR",
            "xlsx": "提取表格；没有表格的页面按行导出文字",
            "pptx": "每页一张幻灯片，版式与 PDF 一致（内容为图片，不可编辑文字）",
        }[self._office_format.value]
        if is_mounted(self._office_hint):
            self._office_hint.update()

    def build_params(self, key: str) -> list[ft.Control]:
        if key == "merge":
            return [
                self.section("输出文件名", self._merge_name),
                ft.Text("在左侧列表用上下箭头调整合并顺序", size=11, color=c("ink-3", "fg")),
            ]
        if key == "split":
            return [
                self.section("拆分方式", ft.Column(
                    controls=[self._split_mode, self._split_pages, self._split_ranges], spacing=12)),
                self.section("命名模板", ft.Column(controls=[
                    self._split_template,
                    ft.Text("{stem} 原文件名　{n} 序号　{start} {end} 起止页", size=11, color=c("ink-3", "fg")),
                ], spacing=6)),
            ]
        if key == "compress":
            return [self.section("压缩强度", ft.Column(controls=[self._compress_level, self._compress_hint], spacing=8))]
        if key == "to_office":
            return [
                self.section("目标格式", ft.Column(controls=[self._office_format, self._office_hint], spacing=8)),
            ]
        if key == "to_images":
            return [
                self.section("图片格式", self._image_format),
                self.section("清晰度", ft.Column(controls=[
                    self._image_dpi,
                    ft.Text("150 dpi 适合屏幕查看，300 dpi 适合打印", size=11, color=c("ink-3", "fg")),
                ], spacing=8)),
            ]
        if key == "from_office":
            return [ft.Text("需要本机安装 LibreOffice。支持 Word、Excel、PowerPoint 及 OpenDocument 文件。",
                            size=12, color=c("ink-2", "fg"))]
        return [
            self.section("文字水印", ft.Column(controls=[
                self._wm_text,
                ft.Row(controls=[ft.Text("透明度", size=12, color=c("ink-2", "fg")), self._wm_opacity],
                       spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=8)),
            self.section("打开密码", self._password),
        ]

    def build_task(self, key: str, files: list[Path], out_dir: Path):
        if key == "merge":
            name = (self._merge_name.value or "").strip() or "merged.pdf"
            if not name.lower().endswith(".pdf"):
                name += ".pdf"
            return merge_pdf, {"input_files": files, "output_file": unique_path(out_dir / name)}

        if key == "split":
            mode = self._split_mode.value
            extra: dict = {"mode": mode, "filename_template": self._split_template.value or "{stem}_第{n}部分"}
            if mode == "pages":
                try:
                    extra["pages_per_file"] = max(1, int(self._split_pages.value or "5"))
                except ValueError:
                    show_toast(self._page, "每份页数必须是正整数")
                    return None
            elif mode == "range":
                ranges = [r.strip() for r in (self._split_ranges.value or "").split(",") if r.strip()]
                if not ranges:
                    show_toast(self._page, "请填写页码范围，如 1-5, 6-10")
                    return None
                extra["page_ranges"] = ranges
            return self.each(split_pdf, files, lambda p: {"input_file": p, "output_dir": out_dir, **extra})

        if key == "compress":
            level = self._compress_level.value
            return self.each(compress_pdf, files, lambda p: {
                "input_file": p, "output_file": unique_path(out_dir / f"{p.stem}_compressed.pdf"), "quality": level})

        if key == "to_office":
            fn = {"docx": pdf_to_docx, "xlsx": pdf_to_xlsx, "pptx": pdf_to_pptx}[self._office_format.value]
            return self.each(fn, files, lambda p: {"input_file": p, "output_dir": out_dir})

        if key == "to_images":
            fmt, dpi = self._image_format.value, int(self._image_dpi.value)
            return self.each(pdf_to_images, files, lambda p: {
                "input_file": p, "output_dir": out_dir, "image_format": fmt, "dpi": dpi})

        if key == "from_office":
            return self.each(office_to_pdf, files, lambda p: {"input_file": p, "output_dir": out_dir})

        wm = (self._wm_text.value or "").strip()
        pwd = self._password.value or ""
        if not wm and not pwd:
            show_toast(self._page, "请至少填写水印文字或打开密码")
            return None
        opacity = self._wm_opacity.value / 100
        suffix = "_protected" if pwd else "_watermarked"
        return self.each(_protect_pdf, files, lambda p: {
            "input_file": p, "output_file": unique_path(out_dir / f"{p.stem}{suffix}.pdf"),
            "wm_text": wm, "wm_opacity": opacity, "password": pwd})

