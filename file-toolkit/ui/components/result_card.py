"""
处理结果卡片

show(result, title)  → 展示成功或失败结果
on_reset: 「再次处理」按钮回调，由父页面实现重置逻辑
"""
import subprocess
import sys
from pathlib import Path
from typing import Callable

import flet as ft

from core.models import TaskResult, TaskStatus


class ResultCard(ft.Container):
    """
    任务结果卡片，成功时展示文件列表 + 操作按钮，失败时展示错误信息。

    show(result)  切换到结果态（visible=True）
    hide()        隐藏
    """

    def __init__(self, on_reset: Callable[[], None] | None = None) -> None:
        self._on_reset = on_reset

        self._status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=28, color=ft.Colors.TERTIARY)
        self._title_text = ft.Text("", size=15, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE)
        self._subtitle_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self._file_list = ft.Column(spacing=6)
        self._open_btn = ft.FilledButton(
            "📂 打开输出目录",
            on_click=self._open_output_dir,
        )
        self._reset_btn = ft.OutlinedButton(
            "再次处理",
            on_click=self._handle_reset,
            icon=ft.Icons.REFRESH,
        )
        self._output_dir: Path | None = None

        super().__init__(
            visible=False,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self._status_icon,
                            ft.Column(
                                controls=[self._title_text, self._subtitle_text],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    self._file_list,
                    ft.Row(
                        controls=[self._open_btn, self._reset_btn],
                        spacing=12,
                    ),
                ],
                spacing=16,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=ft.border_radius.all(16),
            padding=ft.padding.all(20),
        )

    # ── 公开 API ─────────────────────────────────────────────────────

    def show(self, result: TaskResult, title: str = "") -> None:
        """根据 TaskResult 渲染成功或失败状态。"""
        self._output_dir = result.output_dir

        if result.status == TaskStatus.SUCCESS:
            self._status_icon.name = ft.Icons.CHECK_CIRCLE
            self._status_icon.color = ft.Colors.TERTIARY
            file_count = len(result.output_files)
            dir_str = str(result.output_dir) if result.output_dir else ""
            self._title_text.value = title or f"处理完成！共生成 {file_count} 个文件"
            self._subtitle_text.value = f"保存至：{dir_str}"
            self._open_btn.visible = result.output_dir is not None
            self._build_file_list(result.output_files[:8])  # 最多展示 8 条
        else:
            self._status_icon.name = ft.Icons.ERROR
            self._status_icon.color = ft.Colors.ERROR
            self._title_text.value = "处理失败"
            self._subtitle_text.value = result.error_message or "未知错误"
            self._open_btn.visible = False
            self._file_list.controls.clear()

        self.visible = True
        self.update()

    def hide(self) -> None:
        self.visible = False
        self.update()

    # ── 内部 ─────────────────────────────────────────────────────────

    def _build_file_list(self, files: list[Path]) -> None:
        self._file_list.controls.clear()
        for path in files:
            size_kb = path.stat().st_size / 1024 if path.exists() else 0
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
            row = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=16, color=ft.Colors.PRIMARY),
                        ft.Text(path.name, size=12, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(size_str, size=11, color=ft.Colors.OUTLINE),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=ft.border_radius.all(8),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
            )
            self._file_list.controls.append(row)

    def _open_output_dir(self, _: ft.ControlEvent) -> None:
        if self._output_dir and self._output_dir.exists():
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(self._output_dir)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self._output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(self._output_dir)])

    def _handle_reset(self, _: ft.ControlEvent) -> None:
        self.hide()
        if self._on_reset:
            self._on_reset()
