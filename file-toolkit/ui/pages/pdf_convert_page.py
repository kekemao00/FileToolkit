"""PDF↔Office 转换操作页"""
import asyncio
from pathlib import Path
from typing import Literal

import flet as ft

from core.pdf.converter import pdf_to_docx, pdf_to_xlsx, pdf_to_pptx, office_to_pdf
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class PdfConvertPage(ft.Column):
    """PDF 转 Office / Office 转 PDF"""

    def __init__(self, page: ft.Page, mode: Literal["to_office", "from_office"] = "to_office") -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._mode = mode
        self._input_file: Path | None = None
        self._output_dir: Path | None = None
        self._task: asyncio.Task | None = None

        is_to_office = mode == "to_office"
        title = "PDF 转 Office" if is_to_office else "Office 转 PDF"
        icon_color = "#9333ea" if is_to_office else "#ea580c"
        icon_bg = "#faf5ff" if is_to_office else "#fff7ed"
        icon = ft.Icons.SWAP_HORIZ if is_to_office else ft.Icons.PICTURE_AS_PDF
        exts = ["pdf"] if is_to_office else ["docx", "doc", "xlsx", "xls", "pptx", "ppt"]
        ext_hint = "PDF" if is_to_office else "Word / Excel / PPT"

        self._drop_zone = DropZone(
            label=f"拖拽 {ext_hint} 文件到此处",
            sublabel="或点击选择文件",
            allowed_extensions=exts,
            on_files_selected=self._on_file_selected,
            allow_multiple=False,
            icon=icon,
        )
        self._drop_zone.set_page(page)

        if is_to_office:
            self._format_dropdown = ft.Dropdown(
                value="docx",
                options=[
                    ft.dropdown.Option("docx", "Word (.docx)"),
                    ft.dropdown.Option("xlsx", "Excel (.xlsx)"),
                    ft.dropdown.Option("pptx", "PowerPoint (.pptx)"),
                ],
                width=200,
                border_radius=8,
                label="目标格式",
            )
        else:
            self._format_dropdown = None

        self._output_dir_text = ft.Text(
            "（与输入文件同级 output/ 目录）",
            size=12,
            color="#455c7f",
            expand=True,
        )

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)
        self._run_btn = ft.FilledButton(
            "开始转换",
            icon=ft.Icons.SWAP_HORIZ,
            on_click=self._start_task,
            disabled=True,
        )

        self._title = title
        self._icon_color = icon_color
        self._icon_bg = icon_bg
        self._icon = icon

        self.controls = [self._build_header(), self._build_body()]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        ft.Icons.ARROW_BACK,
                        on_click=lambda _: self._page.go("/pdf"),
                        icon_color="#455c7f",
                    ),
                    ft.Container(
                        content=ft.Icon(self._icon, color=self._icon_color, size=20),
                        width=40,
                        height=40,
                        bgcolor=self._icon_bg,
                        border_radius=10,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        self._title,
                        size=20,
                        weight=ft.FontWeight.W_600,
                        color="#162f50",
                        font_family="Manrope",
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=28, top=24, right=40, bottom=16),
        )

    def _build_body(self) -> ft.Control:
        sections = [
            self._section("选择文件", self._drop_zone),
        ]
        if self._format_dropdown:
            sections.append(self._section("目标格式", self._format_dropdown))

        sections.append(
            self._section(
                "输出设置",
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.FOLDER_OUTLINED, color="#455c7f", size=18),
                        self._output_dir_text,
                        ft.OutlinedButton("更改", on_click=self._pick_output_dir, icon=ft.Icons.FOLDER_OPEN),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )
        sections.extend([
            self._progress,
            self._result,
            ft.Container(
                content=self._run_btn,
                alignment=ft.Alignment(0, 0),
                padding=ft.padding.symmetric(vertical=8),
            ),
        ])

        return ft.Container(
            content=ft.Column(controls=sections, spacing=16),
            padding=ft.padding.symmetric(horizontal=40, vertical=8),
        )

    def _section(self, title: str, content: ft.Control) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(title, size=14, weight=ft.FontWeight.W_600, color="#162f50", font_family="Manrope"),
                    content,
                ],
                spacing=10,
            ),
            bgcolor="#ffffff",
            border_radius=16,
            padding=ft.padding.all(20),
            shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.05, "#000000"), offset=ft.Offset(0, 1)),
        )

    def _on_file_selected(self, paths: list[Path]) -> None:
        self._input_file = paths[0] if paths else None
        if self._input_file and self._output_dir is None:
            self._output_dir = settings_service.resolve_output_dir(self._input_file)
            self._output_dir_text.value = str(self._output_dir)
            self._output_dir_text.update()
        self._run_btn.disabled = self._input_file is None
        self._run_btn.update()

    def _pick_output_dir(self, _) -> None:
        self._page.run_task(self._pick_output_dir_async)

    async def _pick_output_dir_async(self) -> None:
        picker = ft.FilePicker()
        self._page.overlay.append(picker)
        self._page.update()
        path = await picker.get_directory_path(dialog_title="选择输出目录")
        self._page.overlay.remove(picker)
        if path:
            self._output_dir = Path(path)
            self._output_dir_text.value = path
            self._output_dir_text.update()
        self._page.update()

    def _start_task(self, _) -> None:
        if not self._input_file:
            return
        out_dir = self._output_dir or settings_service.resolve_output_dir(self._input_file)
        kwargs = {
            "input_file": self._input_file,
            "output_dir": out_dir,
            "mode": self._mode,
        }
        if self._format_dropdown:
            kwargs["target_format"] = self._format_dropdown.value

        self._run_btn.disabled = True
        self._result.hide()
        self._progress.show(self._input_file.name, "正在转换...")

        async def _run():
            if self._mode == "to_office":
                fmt = kwargs.get("target_format", "docx")
                fn = {"docx": pdf_to_docx, "xlsx": pdf_to_xlsx, "pptx": pdf_to_pptx}.get(fmt, pdf_to_docx)
            else:
                fn = office_to_pdf
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, current, total, desc):
        self._progress.update_progress(current, total, desc)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "转换完成！")
        self._run_btn.disabled = False
        self._run_btn.update()
        history_service.save_task("pdf", "convert", result, input_desc=self._input_file.name if self._input_file else "")

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress.hide()
        self._run_btn.disabled = False
        self._run_btn.update()

    def _reset(self) -> None:
        self._input_file = None
        self._output_dir = None
        self._drop_zone.clear()
        self._drop_zone.update()
        self._run_btn.disabled = True
        self._run_btn.update()
