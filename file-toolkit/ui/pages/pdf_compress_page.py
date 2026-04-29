"""PDF 压缩 — Figma 设计语言统一"""
import asyncio
from pathlib import Path

import flet as ft

from core.pdf.compressor import compress_pdf
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.sub_page_header import SubPageHeader
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class PdfCompressPage(ft.Column):
    """PDF 压缩：选文件 → 选压缩质量 → 执行"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._input_file: Path | None = None
        self._output_dir: Path | None = None
        self._task: asyncio.Task | None = None

        self._drop_zone = DropZone(
            label="拖拽 PDF 文件到此处",
            sublabel="或点击选择文件",
            allowed_extensions=["pdf"],
            on_files_selected=self._on_file_selected,
            allow_multiple=False,
            icon=ft.Icons.PICTURE_AS_PDF,
        )
        self._drop_zone.set_page(page)

        self._quality_radio = ft.RadioGroup(
            value="medium",
            content=ft.Column(
                controls=[
                    ft.Radio(value="high", label="高质量 — 仅去除冗余，图片不重编码"),
                    ft.Radio(value="medium", label="中等压缩 — JPEG 72 质量，推荐"),
                    ft.Radio(value="low", label="强力压缩 — JPEG 45 质量 + 150dpi 下采样"),
                ],
                spacing=4,
            ),
        )

        self._output_suffix_field = ft.TextField(
            value="_compressed", label="输出文件名后缀",
            width=180, border_radius=12,
            bgcolor="#f8fafc", border_color="transparent",
        )
        self._output_dir_text = ft.Text(
            "（与输入文件同级 output/ 目录）",
            size=12, color="#455c7f", expand=True,
        )

        self._progress_card = ProgressCard(on_cancel=self._cancel_task)
        self._result_card = ResultCard(on_reset=self._reset)

        self.controls = [
            SubPageHeader(
                title="PDF 压缩",
                icon=ft.Icons.COMPRESS,
                icon_color="#ea580c",
                icon_bg="#fff7ed",
                on_back=lambda: self._page.go("/pdf"),
            ),
            self._build_body(),
        ]

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择 PDF 文件", self._drop_zone),
                    self._section("压缩质量", self._quality_radio),
                    self._section(
                        "输出设置",
                        ft.Column(
                            controls=[
                                self._output_suffix_field,
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.FOLDER_OUTLINED, color="#455c7f", size=18),
                                        self._output_dir_text,
                                        ft.OutlinedButton(
                                            "更改", on_click=self._pick_output_dir,
                                            icon=ft.Icons.FOLDER_OPEN,
                                            style=ft.ButtonStyle(
                                                color="#005f98",
                                                side=ft.BorderSide(1, "#d5e3ff"),
                                                shape=ft.RoundedRectangleBorder(radius=12),
                                            ),
                                        ),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=12,
                        ),
                    ),
                    self._progress_card,
                    self._result_card,
                    ft.Container(
                        content=self._build_run_button(),
                        padding=ft.padding.symmetric(vertical=8),
                    ),
                ],
                spacing=16,
            ),
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
            bgcolor="#ffffff", border_radius=16, padding=ft.padding.all(20),
            shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.05, "#000000"), offset=ft.Offset(0, 1)),
        )

    def _build_run_button(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.COMPRESS, color="#ffffff", size=18),
                    ft.Text("开始压缩", size=16, color="#ffffff", font_family="Manrope", weight=ft.FontWeight.W_500),
                ],
                spacing=8, alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#005f98",
            gradient=ft.LinearGradient(begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0), colors=["#005f98", "#2aa7ff"]),
            border_radius=16, padding=ft.padding.symmetric(vertical=14),
            shadow=ft.BoxShadow(blur_radius=20, spread_radius=-5, color=ft.Colors.with_opacity(0.2, "#005f98"), offset=ft.Offset(0, 10)),
            on_click=self._start_task, ink=True,
        )

    def _on_file_selected(self, paths: list[Path]) -> None:
        self._input_file = paths[0] if paths else None
        if self._input_file and self._output_dir is None:
            self._output_dir = settings_service.resolve_output_dir(self._input_file)
            self._output_dir_text.value = str(self._output_dir)
            self._output_dir_text.update()

    def _pick_output_dir(self, _) -> None:
        self._page.run_task(self._pick_output_dir_async)

    async def _pick_output_dir_async(self) -> None:
        picker = ft.FilePicker()
        self._page.overlay.append(picker)
        self._page.update()
        try:
            path = await picker.get_directory_path(dialog_title="选择输出目录")
        except RuntimeError:
            path = None
        finally:
            self._page.overlay.remove(picker)
        if path:
            self._output_dir = Path(path)
            self._output_dir_text.value = path
            self._output_dir_text.update()
        self._page.update()

    def _start_task(self, _) -> None:
        if not self._input_file:
            return
        quality = self._quality_radio.value or "medium"
        out_dir = self._output_dir or settings_service.resolve_output_dir(self._input_file)
        suffix = self._output_suffix_field.value or "_compressed"
        out_file = out_dir / f"{self._input_file.stem}{suffix}.pdf"

        self._result_card.hide()
        self._progress_card.show(self._input_file.name, f"正在压缩（{quality}）...")

        async def _run() -> None:
            await run_task(
                compress_pdf,
                {"input_file": self._input_file, "output_file": out_file, "quality": quality},
                self._on_progress, self._on_complete,
            )
        self._task = self._page.run_task(_run)

    def _on_progress(self, current: int, total: int, desc: str) -> None:
        self._progress_card.update_progress(current, total, desc)

    def _on_complete(self, result) -> None:
        self._progress_card.hide()
        self._result_card.show(result, "压缩完成！")
        history_service.save_task("pdf", "compress", result, input_desc=self._input_file.name if self._input_file else "")

    def _cancel_task(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress_card.hide()

    def _reset(self) -> None:
        self._input_file = None
        self._output_dir = None
        self._drop_zone.clear()
        self._drop_zone.update()
