"""PDF 合并操作页"""
import asyncio
from pathlib import Path

import flet as ft

from core.pdf.merger import merge_pdf
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.file_list import FileList
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class PdfMergePage(ft.Column):
    """PDF 合并：拖入多个文件 → 拖拽排序 → 设置输出文件名 → 执行合并"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self._output_dir: Path | None = None
        self._task: asyncio.Task | None = None

        self._drop_zone = DropZone(
            label="拖拽多个 PDF 文件到此处",
            sublabel="或点击选择文件（可多选）",
            allowed_extensions=["pdf"],
            on_files_selected=self._on_files_added,
            allow_multiple=True,
            icon=ft.Icons.PICTURE_AS_PDF,
        )
        self._drop_zone.set_page(page)

        self._file_list = FileList(
            on_order_changed=self._on_order_changed,
            on_remove=self._on_file_removed,
        )

        self._file_count_text = ft.Text(
            "已选 0 个文件",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )

        self._output_name_field = ft.TextField(
            value="merged.pdf",
            label="输出文件名",
            width=240,
            border_radius=8,
        )
        self._output_dir_text = ft.Text(
            "（与第一个输入文件同级目录）",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            expand=True,
        )

        self._progress_card = ProgressCard(on_cancel=self._cancel_task)
        self._result_card = ResultCard(on_reset=self._reset)

        self._run_btn = ft.FilledButton(
            "开始合并",
            icon=ft.Icons.MERGE,
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
                    ft.Text("🔗 PDF 合并", style=ft.TextThemeStyle.HEADLINE_SMALL,
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
                    self._section(
                        "Step 1  添加 PDF 文件",
                        ft.Column(
                            controls=[
                                self._drop_zone,
                                ft.Row(
                                    controls=[self._file_count_text, ft.Container(expand=True),
                                              ft.TextButton("清空列表", on_click=self._clear_list,
                                                            style=ft.ButtonStyle(color=ft.Colors.ERROR))],
                                ),
                                self._file_list,
                            ],
                            spacing=12,
                        ),
                    ),
                    self._section(
                        "Step 2  输出设置",
                        ft.Column(
                            controls=[
                                self._output_name_field,
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

    def _on_files_added(self, paths: list[Path]) -> None:
        self._file_list.add_files(paths)
        self._sync_state()

    def _on_order_changed(self, paths: list[Path]) -> None:
        self._sync_state()

    def _on_file_removed(self, path: Path) -> None:
        self._sync_state()

    def _clear_list(self, _: ft.ControlEvent) -> None:
        self._file_list.clear()
        self._file_list.update()
        self._drop_zone.clear()
        self._drop_zone.update()
        self._sync_state()

    def _sync_state(self) -> None:
        count = len(self._file_list.files)
        self._file_count_text.value = f"已选 {count} 个文件"
        self._file_count_text.update()
        self._run_btn.disabled = count < 2
        self._run_btn.update()
        if count > 0 and self._output_dir is None:
            self._output_dir = settings_service.resolve_output_dir(self._file_list.files[0])
            self._output_dir_text.value = str(self._output_dir)
            self._output_dir_text.update()

    def _pick_output_dir(self, _: ft.ControlEvent) -> None:
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

    def _start_task(self, _: ft.ControlEvent) -> None:
        files = self._file_list.files
        if len(files) < 2:
            return
        out_dir = self._output_dir or settings_service.resolve_output_dir(files[0])
        out_name = (self._output_name_field.value or "merged.pdf").strip()
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        output_file = out_dir / out_name

        self._run_btn.disabled = True
        self._result_card.hide()
        self._progress_card.show(f"合并 {len(files)} 个文件", "正在合并...")

        async def _run() -> None:
            await run_task(
                merge_pdf,
                {"input_files": files, "output_file": output_file},
                self._on_progress,
                self._on_complete,
            )

        self._task = self._page.run_task(_run)

    def _on_progress(self, current: int, total: int, desc: str) -> None:
        self._progress_card.update_progress(current, total, desc)

    def _on_complete(self, result) -> None:
        self._progress_card.hide()
        self._result_card.show(result, "合并完成！")
        self._run_btn.disabled = False
        self._run_btn.update()
        files = self._file_list.files
        history_service.save_task("pdf", "merge", result,
                                  input_desc=f"{len(files)} 个文件")

    def _cancel_task(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress_card.hide()
        self._run_btn.disabled = False
        self._run_btn.update()

    def _reset(self) -> None:
        self._file_list.clear()
        self._file_list.update()
        self._drop_zone.clear()
        self._drop_zone.update()
        self._output_dir = None
        self._run_btn.disabled = True
        self._run_btn.update()
