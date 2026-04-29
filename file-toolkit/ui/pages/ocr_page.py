"""OCR 识别操作页 — 图片上传 + 识别结果展示"""
import asyncio
from pathlib import Path

import flet as ft

from core.ocr.client import recognize
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.progress_card import ProgressCard


class OcrPage(ft.Column):
    """OCR 识别：上传图片 → 调用 OCR API → 展示可编辑文本"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._input_file: Path | None = None
        self._task: asyncio.Task | None = None

        self._drop_zone = DropZone(
            label="拖拽图片或扫描件到此处",
            sublabel="支持 PNG / JPG / BMP / PDF 扫描件",
            allowed_extensions=["png", "jpg", "jpeg", "bmp", "tiff", "pdf"],
            on_files_selected=self._on_file_selected,
            allow_multiple=False,
            icon=ft.Icons.DOCUMENT_SCANNER,
        )
        self._drop_zone.set_page(page)

        self._lang_dropdown = ft.Dropdown(
            value="chi_sim",
            options=[
                ft.dropdown.Option("chi_sim", "简体中文"),
                ft.dropdown.Option("eng", "English"),
                ft.dropdown.Option("chi_sim+eng", "中英混合"),
                ft.dropdown.Option("jpn", "日本語"),
            ],
            width=180,
            border_radius=8,
            label="识别语言",
        )

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result_text = ft.TextField(
            multiline=True,
            min_lines=8,
            max_lines=20,
            read_only=False,
            border_radius=12,
            visible=False,
            label="识别结果（可编辑）",
        )
        self._copy_btn = ft.OutlinedButton(
            "复制全部",
            icon=ft.Icons.COPY,
            on_click=self._copy_result,
            visible=False,
        )
        self._save_btn = ft.OutlinedButton(
            "保存为 TXT",
            icon=ft.Icons.SAVE_ALT,
            on_click=self._save_result,
            visible=False,
        )
        self._run_btn = ft.FilledButton(
            "开始识别",
            icon=ft.Icons.DOCUMENT_SCANNER,
            on_click=self._start_task,
            disabled=True,
        )

        self.controls = [
            self._build_header(),
            self._build_body(),
        ]

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.DOCUMENT_SCANNER, color="#0891b2", size=24),
                        width=48,
                        height=48,
                        bgcolor="#ecfeff",
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "OCR 文字识别",
                                size=24,
                                weight=ft.FontWeight.W_600,
                                color="#162f50",
                                font_family="Manrope",
                            ),
                            ft.Text(
                                "从图像或扫描件中提取可编辑文本（需联网）",
                                size=14,
                                color="#455c7f",
                                font_family="Manrope",
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=40, top=32, right=40, bottom=24),
        )

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择图片", self._drop_zone),
                    self._section("识别设置", self._lang_dropdown),
                    self._progress,
                    self._section(
                        "识别结果",
                        ft.Column(
                            controls=[
                                self._result_text,
                                ft.Row(
                                    controls=[self._copy_btn, self._save_btn],
                                    spacing=12,
                                ),
                            ],
                            spacing=12,
                        ),
                    ),
                    ft.Container(
                        content=self._run_btn,
                        alignment=ft.Alignment(0, 0),
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
            bgcolor="#ffffff",
            border_radius=16,
            padding=ft.padding.all(20),
            shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.05, "#000000"), offset=ft.Offset(0, 1)),
        )

    def _on_file_selected(self, paths: list[Path]) -> None:
        self._input_file = paths[0] if paths else None
        self._run_btn.disabled = self._input_file is None
        self._run_btn.update()

    def _start_task(self, _) -> None:
        if not self._input_file:
            return
        kwargs = {
            "input_file": self._input_file,
            "language": self._lang_dropdown.value,
        }
        self._run_btn.disabled = True
        self._result_text.visible = False
        self._copy_btn.visible = False
        self._save_btn.visible = False
        self._progress.show(self._input_file.name, "正在识别...")

        async def _run():
            await run_task(recognize, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, current, total, desc):
        self._progress.update_progress(current, total, desc)

    def _on_complete(self, result):
        self._progress.hide()
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        self._result_text.value = text
        self._result_text.visible = True
        self._copy_btn.visible = True
        self._save_btn.visible = True
        self._run_btn.disabled = False
        self.update()
        history_service.save_task("ocr", "recognize", result, input_desc=self._input_file.name if self._input_file else "")

    def _copy_result(self, _) -> None:
        if self._result_text.value:
            self._page.set_clipboard(self._result_text.value)
            self._page.snack_bar = ft.SnackBar(content=ft.Text("已复制到剪贴板"), bgcolor="#005f98")
            self._page.snack_bar.open = True
            self._page.update()

    def _save_result(self, _) -> None:
        if not self._result_text.value or not self._input_file:
            return
        out_dir = settings_service.resolve_output_dir(self._input_file)
        out_path = out_dir / f"{self._input_file.stem}_ocr.txt"
        out_path.write_text(self._result_text.value, encoding="utf-8")
        self._page.snack_bar = ft.SnackBar(content=ft.Text(f"已保存到 {out_path}"), bgcolor="#005f98")
        self._page.snack_bar.open = True
        self._page.update()

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress.hide()
        self._run_btn.disabled = False
        self._run_btn.update()
