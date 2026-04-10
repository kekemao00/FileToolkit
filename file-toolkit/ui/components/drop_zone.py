"""
文件拖拽区域 — 5 种状态机

IDLE         默认：虚线感知区，提示文字居中
DRAG_HOVER   拖入：背景加深，图标放大（Flet 原生 on_hover 模拟）
SELECTED     已选：显示文件信息，可移除
ERROR        格式错误：红色边框提示
LOADING      处理中：禁止交互

使用方法：
    zone = DropZone(
        label="拖拽 PDF 文件到此处",
        allowed_extensions=["pdf"],
        on_files_selected=lambda paths: ...,
        allow_multiple=False,
    )
"""
from pathlib import Path
from typing import Callable

import flet as ft


class DropZone(ft.Container):
    """
    文件拖拽区域。

    支持：
    - 点击选择文件
    - FilePicker 对话框
    - 文件移除（×）
    - 错误态（格式不匹配）
    """

    def __init__(
        self,
        label: str = "拖拽文件到此处",
        sublabel: str = "或点击选择文件",
        allowed_extensions: list[str] | None = None,
        on_files_selected: Callable[[list[Path]], None] | None = None,
        allow_multiple: bool = False,
        icon: str = ft.Icons.UPLOAD_FILE,
    ) -> None:
        super().__init__()

        self._label = label
        self._sublabel = sublabel
        self._allowed_ext = [e.lower().lstrip(".") for e in (allowed_extensions or [])]
        self._on_files_selected = on_files_selected
        self._allow_multiple = allow_multiple
        self._icon = icon
        self._selected_files: list[Path] = []
        self._page_ref: ft.Page | None = None

        # 内部控件引用
        self._icon_ctrl = ft.Icon(icon, size=48, color=ft.Colors.ON_SURFACE_VARIANT)
        self._label_ctrl = ft.Text(label, size=14, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER)
        self._sub_ctrl = ft.Text(sublabel, size=12, color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER)
        self._file_chips = ft.Column(spacing=6, visible=False)
        self._error_text = ft.Text("", size=12, color=ft.Colors.ERROR, visible=False)

        self._idle_content = ft.Column(
            controls=[
                self._icon_ctrl,
                self._label_ctrl,
                self._sub_ctrl,
                self._error_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        self.content = ft.Column(
            controls=[self._idle_content, self._file_chips],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        )
        self._apply_idle_style()
        self.on_click = self._open_picker
        self.on_hover = self._on_hover

    # ── 状态样式 ────────────────────────────────────────────────────

    def _apply_idle_style(self) -> None:
        self.bgcolor = ft.Colors.SURFACE_CONTAINER_LOW
        self.border = ft.border.all(2, ft.Colors.OUTLINE_VARIANT)
        self.border_radius = ft.border_radius.all(16)
        self.padding = ft.padding.all(32)
        self.animate = ft.Animation(200, ft.AnimationCurve.EASE_OUT)

    def _apply_hover_style(self) -> None:
        self.bgcolor = ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY)
        self.border = ft.border.all(2, ft.Colors.PRIMARY)

    def _apply_selected_style(self) -> None:
        self.bgcolor = ft.Colors.SURFACE_CONTAINER_LOW
        self.border = ft.border.all(2, ft.Colors.OUTLINE_VARIANT)

    def _apply_error_style(self) -> None:
        self.bgcolor = ft.Colors.with_opacity(0.04, ft.Colors.ERROR)
        self.border = ft.border.all(2, ft.Colors.ERROR)

    # ── 交互 ────────────────────────────────────────────────────────

    def _on_hover(self, e: ft.ControlEvent) -> None:
        if self._selected_files:
            return
        if e.data == "true":
            self._apply_hover_style()
            self._icon_ctrl.color = ft.Colors.PRIMARY
        else:
            self._apply_idle_style()
            self._icon_ctrl.color = ft.Colors.ON_SURFACE_VARIANT
        self.update()

    def _open_picker(self, _: ft.ControlEvent) -> None:
        if self._page_ref is None:
            return
        picker = ft.FilePicker(on_result=self._on_pick_result)
        self._page_ref.overlay.append(picker)
        self._page_ref.update()
        picker.pick_files(
            dialog_title=self._label,
            allowed_extensions=self._allowed_ext or None,
            allow_multiple=self._allow_multiple,
        )

    def _on_pick_result(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        paths = [Path(f.path) for f in e.files]
        self._set_files(paths)

    def _set_files(self, paths: list[Path]) -> None:
        # 格式校验
        if self._allowed_ext:
            bad = [p for p in paths if p.suffix.lower().lstrip(".") not in self._allowed_ext]
            if bad:
                self._show_error(f"不支持的格式：{', '.join(p.suffix for p in bad)}")
                return

        self._error_text.visible = False
        self._selected_files = paths
        self._rebuild_chips()
        self._apply_selected_style()
        self.update()

        if self._on_files_selected:
            self._on_files_selected(paths)

    def _show_error(self, msg: str) -> None:
        self._apply_error_style()
        self._error_text.value = msg
        self._error_text.visible = True
        self.update()

    def _rebuild_chips(self) -> None:
        self._file_chips.controls.clear()
        for path in self._selected_files:
            size_kb = path.stat().st_size / 1024 if path.exists() else 0
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            chip = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=16, color=ft.Colors.PRIMARY),
                        ft.Text(path.name, size=13, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(size_str, size=11, color=ft.Colors.OUTLINE),
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            icon_size=16,
                            on_click=lambda _, p=path: self._remove_file(p),
                            icon_color=ft.Colors.ON_SURFACE_VARIANT,
                            style=ft.ButtonStyle(padding=ft.padding.all(2)),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=ft.border_radius.all(8),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
            )
            self._file_chips.controls.append(chip)
        self._file_chips.visible = bool(self._selected_files)
        self._idle_content.visible = not bool(self._selected_files)

    def _remove_file(self, path: Path) -> None:
        self._selected_files = [p for p in self._selected_files if p != path]
        if self._selected_files:
            self._rebuild_chips()
        else:
            self._file_chips.visible = False
            self._idle_content.visible = True
            self._apply_idle_style()
        self.update()
        if self._on_files_selected:
            self._on_files_selected(self._selected_files)

    # ── 公开 API ─────────────────────────────────────────────────────

    @property
    def files(self) -> list[Path]:
        return list(self._selected_files)

    def clear(self) -> None:
        """重置到空状态。"""
        self._selected_files.clear()
        self._file_chips.controls.clear()
        self._file_chips.visible = False
        self._idle_content.visible = True
        self._error_text.visible = False
        self._apply_idle_style()

    def set_page(self, page: ft.Page) -> None:
        """必须在加入 page 后调用，以便 FilePicker 使用 page.overlay。"""
        self._page_ref = page
