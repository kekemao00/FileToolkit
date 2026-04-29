"""批量重命名 — Figma 设计语言统一"""
import asyncio
from pathlib import Path

import flet as ft

from core.image.renamer import batch_rename
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.sub_page_header import SubPageHeader
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


class ImageRenamePage(ft.Column):
    """批量重命名：选文件 → 设置命名规则 → 预览 → 执行"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._input_files: list[Path] = []
        self._task: asyncio.Task | None = None

        self._drop_zone = DropZone(
            label="拖拽图片文件到此处",
            sublabel="支持所有图片格式，可多选",
            allowed_extensions=["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif"],
            on_files_selected=self._on_files,
            allow_multiple=True,
            icon=ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
        )
        self._drop_zone.set_page(page)

        self._template = ft.TextField(
            value="{name}_{n:03d}",
            label="命名模板",
            hint_text="{name} 原名  {n} 序号  {date} 日期  {ext} 扩展名",
            expand=True, border_radius=12,
            bgcolor="#f8fafc", border_color="transparent",
        )
        self._start_num = ft.TextField(
            value="1", label="起始序号", width=100,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=12, bgcolor="#f8fafc", border_color="transparent",
        )

        self._preview_list = ft.Column(spacing=4, visible=False)

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)
        self._run_btn = self._build_run_button("开始重命名", ft.Icons.DRIVE_FILE_RENAME_OUTLINE)
        self._preview_btn = ft.OutlinedButton(
            "预览", icon=ft.Icons.PREVIEW, on_click=self._preview,
            style=ft.ButtonStyle(
                color="#005f98",
                side=ft.BorderSide(1, "#d5e3ff"),
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )

        self.controls = [
            SubPageHeader(
                title="批量重命名",
                icon=ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
                icon_color="#ea580c",
                icon_bg="#fff7ed",
                on_back=lambda: self._page.go("/image"),
            ),
            self._build_body(),
        ]

    def _build_body(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    self._section("选择文件", self._drop_zone),
                    self._section("命名规则", ft.Column(controls=[
                        ft.Row(controls=[self._template, self._start_num], spacing=12),
                        ft.Text(
                            "可用变量：{name} 原文件名  {n} 序号  {n:03d} 补零序号  {date} 日期  {ext} 扩展名",
                            size=11, color="#94a3b8", font_family="Manrope",
                        ),
                        self._preview_btn,
                    ], spacing=10)),
                    self._section("预览", self._preview_list),
                    self._progress,
                    self._result,
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
            on_click=self._start,
            ink=True,
            opacity=0.5,
        )

    # ── 交互 ─────────────────────────────────────────────
    def _on_files(self, paths):
        self._input_files = paths
        self._run_btn.opacity = 1.0 if paths else 0.5
        self._run_btn.update()

    def _preview(self, _):
        if not self._input_files:
            return
        self._preview_list.controls.clear()
        template = self._template.value or "{name}_{n:03d}"
        try:
            start = max(1, int(self._start_num.value or "1"))
        except ValueError:
            start = 1

        from datetime import date
        today = date.today().strftime("%Y%m%d")

        for i, f in enumerate(self._input_files[:10]):
            n = start + i
            try:
                new_name = template.format(name=f.stem, n=n, date=today, ext=f.suffix.lstrip("."))
            except (KeyError, ValueError):
                new_name = f"{f.stem}_{n:03d}"
            new_name += f.suffix

            self._preview_list.controls.append(
                ft.Row(controls=[
                    ft.Text(f.name, size=12, color="#455c7f", width=200, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Icon(ft.Icons.ARROW_FORWARD, size=14, color="#94a3b8"),
                    ft.Text(new_name, size=12, color="#162f50", weight=ft.FontWeight.W_500),
                ], spacing=8)
            )

        if len(self._input_files) > 10:
            self._preview_list.controls.append(
                ft.Text(f"... 共 {len(self._input_files)} 个文件", size=11, color="#94a3b8"),
            )

        self._preview_list.visible = True
        self.update()

    def _start(self, _):
        if not self._input_files:
            return
        try:
            start = max(1, int(self._start_num.value or "1"))
        except ValueError:
            start = 1
        kwargs = {
            "input_files": self._input_files,
            "template": self._template.value or "{name}_{n:03d}",
            "start_number": start,
        }
        self._run_btn.opacity = 0.5
        self._run_btn.update()
        self._result.hide()
        self._progress.show(f"{len(self._input_files)} 个文件", "正在重命名...")

        async def _run():
            await run_task(batch_rename, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d):
        self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "重命名完成！")
        self._run_btn.opacity = 1.0
        self._run_btn.update()
        history_service.save_task("image", "rename", result, input_desc=f"{len(self._input_files)} 个文件")

    def _cancel(self):
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress.hide()
        self._run_btn.opacity = 1.0
        self._run_btn.update()

    def _reset(self):
        self._input_files.clear()
        self._drop_zone.clear()
        self._drop_zone.update()
        self._preview_list.controls.clear()
        self._preview_list.visible = False
        self._run_btn.opacity = 0.5
        self._run_btn.update()
