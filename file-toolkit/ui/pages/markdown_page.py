"""Markdown 工作台 — 文档转 Markdown（交给 AI）/ Markdown 转 Word、PDF、网页"""
from pathlib import Path

import flet as ft

from core.markdown._common import IMAGE_EMBED, IMAGE_EXTRACT, IMAGE_SKIP
from core.markdown.converter import markdown_stats, merge_to_markdown, to_markdown
from core.markdown.from_md import from_markdown
from core.models import TaskResult, TaskStatus
from ui import style as s
from ui.components.workbench import (
    ChoiceGroup,
    Workbench,
    WorkbenchFunction,
    is_mounted,
    unique_path,
)
from ui.palette import c
from ui.utils import show_toast

# 转 Markdown 支持的格式（前 8 个显示在选择区提示里）
TO_MD_EXTENSIONS = ("docx", "pdf", "pptx", "xlsx", "html", "csv", "txt", "doc",
                    "htm", "xlsm", "rtf", "odt", "wps", "xls", "ods", "ppt", "odp")
FROM_MD_EXTENSIONS = ("md", "markdown", "txt")


def _checkbox(label: str, value: bool = False) -> ft.Checkbox:
    return ft.Checkbox(label=label, value=value, active_color=c("ink", "fg"),
                       label_style=ft.TextStyle(size=12.5, color=c("ink-2", "fg"), font_family=s.FONT))


class MarkdownPage(Workbench):
    TITLE = "Markdown 转换"
    SUBTITLE = "把 Word、PDF、PPT、Excel、网页转成 AI 最好读的 Markdown，或把 Markdown 转回 Word / PDF / 网页"
    MODULE = "markdown"
    PICK_LABEL = "点击选择文件"
    FILE_ICON = ft.Icons.ARTICLE_OUTLINED
    FUNCTIONS = [
        WorkbenchFunction("to_md", "转 Markdown", "Word / PDF / PPT / Excel / 网页转成 Markdown，方便交给 AI",
                          ft.Icons.ARTICLE_OUTLINED, TO_MD_EXTENSIONS),
        WorkbenchFunction("from_md", "MD 转出", "Markdown 转成 Word / PDF / 网页",
                          ft.Icons.IOS_SHARE_OUTLINED, FROM_MD_EXTENSIONS),
    ]

    def __init__(self, page: ft.Page, initial_func: str | None = None) -> None:
        # 转 Markdown
        self._image_mode = ChoiceGroup(
            [(IMAGE_EXTRACT, "单独保存"), (IMAGE_SKIP, "不要图片"), (IMAGE_EMBED, "内嵌")], IMAGE_EXTRACT,
            on_change=lambda _: self._sync_image_hint())
        self._image_hint = ft.Text(size=11, color=c("ink-3", "fg"))
        self._output_mode = ChoiceGroup([("each", "每个文件一份"), ("merge", "合并为一份")], "each",
                                        on_change=lambda _: self._sync_output_mode())
        self._merge_name = self.text_field("合并资料.md", "合并后的文件名")
        self._output_hint = ft.Text(size=11, color=c("ink-3", "fg"))
        self._include_meta = _checkbox("写入文档信息（来源、页数等）")
        self._page_markers = _checkbox("PDF 标注页码，方便 AI 引用")
        # Markdown 转出
        self._target = ChoiceGroup([("docx", "Word"), ("pdf", "PDF"), ("html", "网页")], "docx",
                                   on_change=lambda _: self._sync_target_hint())
        self._target_hint = ft.Text(size=11, color=c("ink-3", "fg"))

        self._sync_image_hint()
        self._sync_output_mode()
        self._sync_target_hint()
        super().__init__(page, initial_func)

    # ── 参数联动 ─────────────────────────────────────────────────────────
    @staticmethod
    def _refresh(*controls: ft.Control) -> None:
        for ctl in controls:
            if is_mounted(ctl):
                ctl.update()

    def _sync_image_hint(self) -> None:
        self._image_hint.value = {
            IMAGE_EXTRACT: "图片存到同名 _assets 文件夹，Markdown 里用相对路径引用",
            IMAGE_SKIP: "只保留文字和表格，最省 token，适合直接交给 AI",
            IMAGE_EMBED: "图片以 base64 写进 .md，单文件可移动，但体积和 token 会很大",
        }[self._image_mode.value]
        self._refresh(self._image_hint)

    def _sync_output_mode(self) -> None:
        merge = self._output_mode.value == "merge"
        self._merge_name.visible = merge
        self._output_hint.value = ("所有文件合成一份 .md，每个文件一个一级标题，一次交给 AI" if merge
                                   else "每个文件生成一份同名 .md")
        self._refresh(self._merge_name, self._output_hint)

    def _sync_target_hint(self) -> None:
        self._target_hint.value = {
            "docx": "使用 Word 内置样式，标题会出现在导航窗格",
            "pdf": "A4 排版，自动使用系统中文字体",
            "html": "单个网页文件，图片内嵌，支持浅色 / 深色",
        }[self._target.value]
        self._refresh(self._target_hint)

    # ── 参数面板 ─────────────────────────────────────────────────────────
    def build_params(self, key: str) -> list[ft.Control]:
        if key == "to_md":
            return [
                self.section("图片", ft.Column(controls=[self._image_mode, self._image_hint], spacing=8)),
                self.section("输出方式", ft.Column(
                    controls=[self._output_mode, self._merge_name, self._output_hint], spacing=8)),
                self.section("更多选项", ft.Column(controls=[self._include_meta, self._page_markers], spacing=0)),
                ft.Text("doc / xls / ppt / rtf 等旧格式需要本机安装 LibreOffice；扫描版 PDF 装了 Tesseract 会自动识别文字",
                        size=11, color=c("ink-3", "fg")),
            ]
        return [self.section("目标格式", ft.Column(controls=[self._target, self._target_hint], spacing=8))]

    def build_task(self, key: str, files: list[Path], out_dir: Path):
        if key == "from_md":
            target = self._target.value
            return self.each(from_markdown, files, lambda p: {
                "input_file": p, "output_dir": out_dir, "target": target})

        opts = {"image_mode": self._image_mode.value, "include_meta": bool(self._include_meta.value),
                "page_markers": bool(self._page_markers.value)}
        if self._output_mode.value == "merge":
            name = (self._merge_name.value or "").strip() or "合并资料.md"
            if any(ch in name for ch in '\\/:*?"<>|'):
                show_toast(self._page, "文件名不能包含 \\ / : * ? \" < > |")
                return None
            if not name.lower().endswith(".md"):
                name += ".md"
            return merge_to_markdown, {"input_files": files, "output_file": unique_path(out_dir / name), **opts}
        return self.each(to_markdown, files, lambda p: {"input_file": p, "output_dir": out_dir, **opts})

    # ── 完成视图：字数 / token 与复制 ────────────────────────────────────
    def result_extras(self, key: str, result: TaskResult) -> list[ft.Control]:
        if key != "to_md" or result.status != TaskStatus.SUCCESS:
            return []
        md_files = [p for p in result.output_files if p.suffix.lower() == ".md"]
        if not md_files:
            return []
        chars, tokens = markdown_stats(md_files)
        return [ft.Container(
            content=ft.Row(controls=[
                ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED, size=16, color=c("ink-2", "fg")),
                s.text(f"共 {chars:,} 字符，预估约 {tokens:,} tokens", "body", expand=True),
                s.button("复制 Markdown", lambda _: self._page.run_task(self._copy_markdown, md_files),
                         icon=ft.Icons.CONTENT_COPY_OUTLINED, kind="secondary", height=32),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=c("surface-2"), border_radius=s.R_INPUT,
            padding=ft.Padding.only(left=12, right=6, top=6, bottom=6),
        )]

    async def _copy_markdown(self, files: list[Path]) -> None:
        try:
            text = "\n\n---\n\n".join(p.read_text(encoding="utf-8").strip() for p in files) + "\n"
            await ft.Clipboard().set(text)
        except Exception as exc:
            show_toast(self._page, f"复制失败：{exc}", duration=3000)
            return
        show_toast(self._page, "已复制，可以直接粘贴给 AI")
