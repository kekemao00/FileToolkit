"""PDF 合并 — Figma 设计语言统一"""
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
from ui.components.sub_page_header import SubPageHeader


class PdfMergePage(ft.Column):
    """PDF 合并：拖入多个文件 → 拖拽排序 → 设置输出文件名 → 执行合并"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
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
            "已选 0 个文件", size=12, color="#455c7f",
        )

        self._output_name_field = ft.TextField(
            value="merged.pdf", label="输出文件名",
            width=240, border_radius=12,
            bgcolor="#f8fafc", border_color="transparent",
        )
        self._output_dir_text = ft.Text(
            "（与第一个输入文件同级目录）",
            size=12, color="#455c7f", expand=True,
        )

        self._progress_card = ProgressCard(on_cancel=self._cancel_task)
        self._result_card = ResultCard(on_reset=self._reset)

        self._run_btn = self._build_run_button()

        self.controls = [
            SubPageHeader(
                title="PDF 合并",
                icon=ft.Icons.MERGE,
                icon_color="#2563eb",
                icon_bg="#eff6ff",
                on_back=lambda: self._page.go("/pdf"),
            ),
            self._build_body(),
        ]

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section(
                        "添加 PDF 文件",
                        ft.Column(
                            controls=[
                                self._drop_zone,
                                ft.Row(
                                    controls=[
                                        self._file_count_text,
                                        ft.Container(expand=True),
                                        ft.TextButton(
                                            "清空列表",
                                            on_click=self._clear_list,
                                            style=ft.ButtonStyle(color="#dc2626"),
                                        ),
                                    ],
                                ),
                                self._file_list,
                            ],
                            spacing=12,
                        ),
                    ),
                    self._section(
                        "输出设置",
                        ft.Column(
                            controls=[
                                self._output_name_field,
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
            padding=ft.padding.all(32),
        )

    def _section(self, title: str, content: ft.Control) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        title, size=14, weight=ft.FontWeight.W_600,
                        color="#162f50", font_family="42dot Sans",
                    ),
                    content,
                ],
                spacing=10,
            ),
            bgcolor="#ffffff",
            border_radius=12,
            padding=ft.padding.all(20),
            shadow=ft.BoxShadow(
                blur_radius=2,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
        )

    def _build_run_button(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.MERGE, color="#ffffff", size=18),
                    ft.Text(
                        "开始合并", size=16, color="#ffffff",
                        font_family="42dot Sans", weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#005f98",
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=["#005f98", "#00a3ff"],
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
            opacity=0.5,
        )

    # ── 交互 ─────────────────────────────────────────────
    def _on_files_added(self, paths: list[Path]) -> None:
        self._file_list.add_files(paths)
        self._sync_state()

    def _on_order_changed(self, paths: list[Path]) -> None:
        self._sync_state()

    def _on_file_removed(self, path: Path) -> None:
        self._sync_state()

    def _clear_list(self, _) -> None:
        self._file_list.clear()
        self._file_list.update()
        self._drop_zone.clear()
        self._drop_zone.update()
        self._sync_state()

    def _sync_state(self) -> None:
        count = len(self._file_list.files)
        self._file_count_text.value = f"已选 {count} 个文件"
        self._file_count_text.update()
        self._run_btn.opacity = 1.0 if count >= 2 else 0.5
        self._run_btn.update()
        if count > 0 and self._output_dir is None:
            self._output_dir = settings_service.resolve_output_dir(
                self._file_list.files[0],
            )
            self._output_dir_text.value = str(self._output_dir)
            self._output_dir_text.update()

    def _pick_output_dir(self, _) -> None:
        self._page.run_task(self._pick_output_dir_async)

    async def _pick_output_dir_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        try:
            path = await picker.get_directory_path(dialog_title="选择输出目录")
        except RuntimeError:
            path = None
        if path:
            self._output_dir = Path(path)
            self._output_dir_text.value = path
            self._output_dir_text.update()
        self._page.update()

    def _start_task(self, _) -> None:
        files = self._file_list.files
        if len(files) < 2:
            return
        out_dir = self._output_dir or settings_service.resolve_output_dir(files[0])
        out_name = (self._output_name_field.value or "merged.pdf").strip()
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        output_file = out_dir / out_name

        self._run_btn.opacity = 0.5
        self._run_btn.update()
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
        self._run_btn.opacity = 1.0
        self._run_btn.update()
        files = self._file_list.files
        history_service.save_task(
            "pdf", "merge", result,
            input_desc=f"{len(files)} 个文件",
        )

    def _cancel_task(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress_card.hide()
        self._run_btn.opacity = 1.0
        self._run_btn.update()

    def _reset(self) -> None:
        self._file_list.clear()
        self._file_list.update()
        self._drop_zone.clear()
        self._drop_zone.update()
        self._output_dir = None
        self._run_btn.opacity = 0.5
        self._run_btn.update()
