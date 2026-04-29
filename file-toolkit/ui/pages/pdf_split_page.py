"""PDF 分割 — Figma 设计语言统一"""
import asyncio
from pathlib import Path

import flet as ft

from core.pdf.splitter import split_pdf
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.sub_page_header import SubPageHeader
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class PdfSplitPage(ft.Column):
    """PDF 分割：选文件 → 设置分割方式 → 输出目录 → 执行"""

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

        self._mode_radio = ft.RadioGroup(
            value="pages",
            content=ft.Column(
                controls=[
                    ft.Radio(value="pages", label="按固定页数"),
                    ft.Radio(value="range", label="按页码范围"),
                    ft.Radio(value="each", label="每页单独保存"),
                ],
                spacing=4,
            ),
            on_change=self._on_mode_change,
        )
        self._pages_field = ft.TextField(
            value="5", label="每份页数", width=120,
            keyboard_type=ft.KeyboardType.NUMBER, border_radius=12,
            bgcolor="#f8fafc", border_color="transparent",
        )
        self._range_field = ft.TextField(
            label="页码范围（如 1-5, 6-10）",
            hint_text="1-5, 6-10, 11-20",
            expand=True, border_radius=12,
            bgcolor="#f8fafc", border_color="transparent",
            visible=False,
        )
        self._mode_extra = ft.Row(
            controls=[self._pages_field, self._range_field], spacing=12,
        )

        self._output_dir_text = ft.Text(
            "（与输入文件同级 output/ 目录）",
            size=12, color="#455c7f", expand=True,
        )
        self._template_field = ft.TextField(
            value="{stem}_第{n}部分",
            label="文件命名模板",
            hint_text="{stem} {n} {start} {end}",
            expand=True, border_radius=12,
            bgcolor="#f8fafc", border_color="transparent",
        )

        self._progress_card = ProgressCard(on_cancel=self._cancel_task)
        self._result_card = ResultCard(on_reset=self._reset)

        self._run_btn = self._build_run_button("开始分割", ft.Icons.CONTENT_CUT)

        self.controls = [
            SubPageHeader(
                title="PDF 分割",
                icon=ft.Icons.CONTENT_CUT,
                icon_color="#dc2626",
                icon_bg="#fef2f2",
                on_back=lambda: self._page.go("/pdf"),
            ),
            self._build_body(),
        ]

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择 PDF 文件", self._drop_zone),
                    self._section(
                        "分割方式",
                        ft.Column(
                            controls=[self._mode_radio, self._mode_extra],
                            spacing=12,
                        ),
                    ),
                    self._section(
                        "输出设置",
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.FOLDER_OUTLINED,
                                            color="#455c7f", size=18,
                                        ),
                                        self._output_dir_text,
                                        ft.OutlinedButton(
                                            "更改",
                                            on_click=self._pick_output_dir,
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
                                self._template_field,
                            ],
                            spacing=12,
                        ),
                    ),
                    self._progress_card,
                    self._result_card,
                    ft.Container(
                        content=self._run_btn,
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
                    ft.Text(
                        title, size=14, weight=ft.FontWeight.W_600,
                        color="#162f50", font_family="Manrope",
                    ),
                    content,
                ],
                spacing=10,
            ),
            bgcolor="#ffffff",
            border_radius=16,
            padding=ft.padding.all(20),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
        )

    def _build_run_button(self, label: str, icon: str) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color="#ffffff", size=18),
                    ft.Text(
                        label, size=16, color="#ffffff",
                        font_family="Manrope", weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#005f98",
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=["#005f98", "#2aa7ff"],
            ),
            border_radius=16,
            padding=ft.padding.symmetric(vertical=14),
            shadow=ft.BoxShadow(
                blur_radius=20, spread_radius=-5,
                color=ft.Colors.with_opacity(0.2, "#005f98"),
                offset=ft.Offset(0, 10),
            ),
            on_click=self._start_task,
            ink=True,
            opacity=0.5 if not self._input_file else 1.0,
        )

    # ── 交互 ─────────────────────────────────────────────
    def _on_file_selected(self, paths: list[Path]) -> None:
        self._input_file = paths[0] if paths else None
        if self._input_file and self._output_dir is None:
            self._output_dir = settings_service.resolve_output_dir(self._input_file)
            self._output_dir_text.value = str(self._output_dir)
            self._output_dir_text.update()
        self._run_btn.opacity = 0.5 if not self._input_file else 1.0
        self._run_btn.update()

    def _on_mode_change(self, e: ft.ControlEvent) -> None:
        mode = e.data
        self._pages_field.visible = (mode == "pages")
        self._range_field.visible = (mode == "range")
        self._mode_extra.update()

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
        mode = self._mode_radio.value
        out_dir = self._output_dir or settings_service.resolve_output_dir(self._input_file)
        kwargs: dict = {
            "input_file": self._input_file,
            "output_dir": out_dir,
            "mode": mode,
            "filename_template": self._template_field.value or "{stem}_第{n}部分",
        }
        if mode == "pages":
            try:
                kwargs["pages_per_file"] = max(1, int(self._pages_field.value or "5"))
            except ValueError:
                kwargs["pages_per_file"] = 5
        elif mode == "range":
            raw = self._range_field.value or ""
            kwargs["page_ranges"] = [r.strip() for r in raw.split(",") if r.strip()]

        self._run_btn.opacity = 0.5
        self._run_btn.update()
        self._result_card.hide()
        self._progress_card.show(self._input_file.name, "正在分割...")

        async def _run() -> None:
            await run_task(split_pdf, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, current: int, total: int, desc: str) -> None:
        self._progress_card.update_progress(current, total, desc)

    def _on_complete(self, result) -> None:
        self._progress_card.hide()
        self._result_card.show(result, "分割完成！")
        self._run_btn.opacity = 1.0
        self._run_btn.update()
        history_service.save_task(
            "pdf", "split", result,
            input_desc=self._input_file.name if self._input_file else "",
        )

    def _cancel_task(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress_card.hide()
        self._run_btn.opacity = 1.0
        self._run_btn.update()

    def _reset(self) -> None:
        self._input_file = None
        self._output_dir = None
        self._drop_zone.clear()
        self._drop_zone.update()
        self._run_btn.opacity = 0.5
        self._run_btn.update()
