"""
文件列表组件 — 支持多文件展示、移除、上下拖拽排序

用于 PDF 合并等需要对文件排序的场景。
"""
from pathlib import Path
from typing import Callable

import flet as ft


class FileList(ft.Column):
    """
    可排序文件列表。

    on_order_changed(paths): 顺序变化时回调（拖拽完成后）
    on_remove(path): 移除单文件时回调
    """

    def __init__(
        self,
        on_order_changed: Callable[[list[Path]], None] | None = None,
        on_remove: Callable[[Path], None] | None = None,
    ) -> None:
        super().__init__(spacing=6)
        self._on_order_changed = on_order_changed
        self._on_remove = on_remove
        self._files: list[Path] = []

    # ── 公开 API ─────────────────────────────────────────────────────

    @property
    def files(self) -> list[Path]:
        return list(self._files)

    def set_files(self, paths: list[Path]) -> None:
        self._files = list(paths)
        self._rebuild()

    def add_files(self, paths: list[Path]) -> None:
        existing = {p.resolve() for p in self._files}
        for p in paths:
            if p.resolve() not in existing:
                self._files.append(p)
                existing.add(p.resolve())
        self._rebuild()

    def clear(self) -> None:
        self._files.clear()
        self.controls.clear()

    # ── 内部构建 ─────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        self.controls.clear()
        for i, path in enumerate(self._files):
            self.controls.append(self._build_row(i, path))

    def _build_row(self, idx: int, path: Path) -> ft.Control:
        size_kb = path.stat().st_size / 1024 if path.exists() else 0
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
        total = len(self._files)

        return ft.Container(
            content=ft.Row(
                controls=[
                    # 排序按钮
                    ft.Column(
                        controls=[
                            ft.IconButton(
                                ft.Icons.KEYBOARD_ARROW_UP,
                                icon_size=16,
                                disabled=(idx == 0),
                                on_click=lambda _, i=idx: self._move(i, -1),
                                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                style=ft.ButtonStyle(padding=ft.padding.all(0)),
                            ),
                            ft.IconButton(
                                ft.Icons.KEYBOARD_ARROW_DOWN,
                                icon_size=16,
                                disabled=(idx == total - 1),
                                on_click=lambda _, i=idx: self._move(i, +1),
                                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                style=ft.ButtonStyle(padding=ft.padding.all(0)),
                            ),
                        ],
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        str(idx + 1),
                        width=24,
                        size=12,
                        color=ft.Colors.OUTLINE,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Icon(ft.Icons.PICTURE_AS_PDF, size=20, color=ft.Colors.PRIMARY),
                    ft.Column(
                        controls=[
                            ft.Text(
                                path.name,
                                size=13,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(size_str, size=11, color=ft.Colors.OUTLINE),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE,
                        icon_size=16,
                        on_click=lambda _, p=path: self._remove(p),
                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                        style=ft.ButtonStyle(padding=ft.padding.all(4)),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=ft.border_radius.all(10),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
        )

    def _move(self, idx: int, direction: int) -> None:
        new_idx = idx + direction
        if 0 <= new_idx < len(self._files):
            self._files[idx], self._files[new_idx] = self._files[new_idx], self._files[idx]
            self._rebuild()
            self.update()
            if self._on_order_changed:
                self._on_order_changed(self._files)

    def _remove(self, path: Path) -> None:
        self._files = [p for p in self._files if p != path]
        self._rebuild()
        self.update()
        if self._on_remove:
            self._on_remove(path)
