"""PDF 压缩操作页"""
import asyncio
from pathlib import Path

import flet as ft

from core.pdf.compressor import compress_pdf
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class PdfCompressPage(ft.Column):
    """PDF 压缩：选文件 → 选压缩质量 → 执行"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO)
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

        # 压缩质量选择（分段按钮）
        self._quality_radio = ft.RadioGroup(
            value="medium",
            content=ft.Column(
                controls=[
                    ft.Radio(value="high",   label="高质量 — 仅去除冗余，图片不重编码"),
                    ft.Radio(value="medium", label="中等压缩 — JPEG 72 质量，推荐"),
                    ft.Radio(value="low",    label="强力压缩 — JPEG 45 质量 + 150dpi 下采样"),
                ],
                spacing=4,
            ),
        )

        self._output_suffix_field = ft.TextField(
            value="_compressed",
            label="输出文件名后缀",
            width=180,
            border_radius=8,
        )
        self._output_dir_text = ft.Text(
            "（与输入文件同级 output/ 目录）",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            expand=True,
        )

        self._progress_card = ProgressCard(on_cancel=self._cancel_task)
        self._result_card = ResultCard(on_reset=self._reset)

        self._run_btn = ft.FilledButton(
            "开始压缩",
            icon=ft.Icons.COMPRESS,
            on_click=self._start_task,
            disabled=True,
        )

        self.spacing = 0
        self.controls = [self._build_header(), self._build_body()]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: self._page.go("/pdf"),
                                  icon_color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("🗜️ PDF 压缩", style=ft.TextThemeStyle.HEADLINE_SMALL,
                            font_family="Manrope", weight=ft.FontWeight.W_600),
                ],
                spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=16, top=20, right=28, bottom=12),
        )

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("Step 1  选择 PDF 文件", self._drop_zone),
                    self._section("Step 2  压缩质量", self._quality_radio),
                    self._section(
                        "Step 3  输出设置",
                        ft.Column(
                            controls=[
                                self._output_suffix_field,
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.FOLDER_OUTLINED, color=ft.Colors.ON_SURFACE_VARIANT, size=18),
                                        self._output_dir_text,
                                        ft.OutlinedButton("更改", on_click=self._pick_output_dir,
                                                          icon=ft.Icons.FOLDER_OPEN),
                                    ],
                                    spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=12,
                        ),
                    ),
                    self._progress_card,
                    self._result_card,
                    ft.Container(
                        content=self._run_btn,
                        alignment=ft.alignment.Alignment(0, 0),
                        padding=ft.padding.symmetric(vertical=8),
                    ),
                ],
                spacing=16,
            ),
            padding=ft.padding.symmetric(horizontal=28, vertical=8),
        )

    def _section(self, title: str, content: ft.Control) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[ft.Text(title, size=14, weight=ft.FontWeight.W_600), content],
                spacing=10,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=ft.border_radius.all(16),
            padding=ft.padding.all(20),
        )

    def _on_file_selected(self, paths: list[Path]) -> None:
        self._input_file = paths[0] if paths else None
        if self._input_file and self._output_dir is None:
            self._output_dir = settings_service.resolve_output_dir(self._input_file)
            self._output_dir_text.value = str(self._output_dir)
            self._output_dir_text.update()
        self._run_btn.disabled = self._input_file is None
        self._run_btn.update()

    def _pick_output_dir(self, _: ft.ControlEvent) -> None:
        def on_result(e: ft.FilePickerResultEvent) -> None:
            if e.path:
                self._output_dir = Path(e.path)
                self._output_dir_text.value = e.path
                self._output_dir_text.update()

        picker = ft.FilePicker(on_result=on_result)
        self._page.overlay.append(picker)
        self._page.update()
        picker.get_directory_path(dialog_title="选择输出目录")

    def _start_task(self, _: ft.ControlEvent) -> None:
        if not self._input_file:
            return
        quality = self._quality_radio.value or "medium"
        out_dir = self._output_dir or settings_service.resolve_output_dir(self._input_file)
        suffix = self._output_suffix_field.value or "_compressed"
        out_file = out_dir / f"{self._input_file.stem}{suffix}.pdf"

        self._run_btn.disabled = True
        self._result_card.hide()
        self._progress_card.show(self._input_file.name, f"正在压缩（{quality}）...")

        async def _run() -> None:
            await run_task(
                compress_pdf,
                {"input_file": self._input_file, "output_file": out_file, "quality": quality},
                self._on_progress,
                self._on_complete,
            )

        self._task = self._page.run_task(_run)

    def _on_progress(self, current: int, total: int, desc: str) -> None:
        self._progress_card.update_progress(current, total, desc)

    def _on_complete(self, result) -> None:
        self._progress_card.hide()
        self._result_card.show(result, "压缩完成！")
        self._run_btn.disabled = False
        self._run_btn.update()
        history_service.save_task("pdf", "compress", result,
                                  input_desc=self._input_file.name if self._input_file else "")

    def _cancel_task(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress_card.hide()
        self._run_btn.disabled = False
        self._run_btn.update()

    def _reset(self) -> None:
        self._input_file = None
        self._output_dir = None
        self._drop_zone.clear()
        self._drop_zone.update()
        self._run_btn.disabled = True
        self._run_btn.update()
