"""
文件拖拽区域 — flet 0.84 async FilePicker API

flet 0.84 breaking change:
  - pick_files() 是 async，直接返回 list[FilePickerFile]，无 on_result 回调
  - get_directory_path() 也是 async，直接返回 str | None
  - allowed_extensions 需配合 file_type=FilePickerFileType.CUSTOM 使用

使用方法：
    zone = DropZone(
        label="拖拽 PDF 文件到此处",
        allowed_extensions=["pdf"],
        on_files_selected=lambda paths: ...,
        allow_multiple=False,
    )
    zone.set_page(page)   # 在加入 page 后调用
"""
from pathlib import Path
from typing import Callable

import flet as ft


class DropZone(ft.Container):
    """
    文件拖拽区域（点击弹出系统文件选择器）。

    状态：
        IDLE     — 默认虚线感知区，提示文字居中
        HOVER    — 鼠标悬停，边框高亮
        SELECTED — 已选文件，chip 列表显示
        ERROR    — 格式不匹配，红色提示
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
        self._icon_name = icon
        self._selected_files: list[Path] = []
        self._page_ref: ft.Page | None = None

        # 内部控件引用
        self._icon_ctrl = ft.Icon(icon, size=48, color=ft.Colors.ON_SURFACE_VARIANT)
        self._label_ctrl = ft.Text(
            label, size=14, color=ft.Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.CENTER,
        )
        self._sub_ctrl = ft.Text(
            sublabel, size=12, color=ft.Colors.OUTLINE,
            text_align=ft.TextAlign.CENTER,
        )
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

        self._file_chips = ft.Column(spacing=6, visible=False)

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
        """点击时启动异步文件选择（通过 page.run_task）。"""
        if self._page_ref is None:
            return
        self._page_ref.run_task(self._pick_async)

    async def _pick_async(self) -> None:
        """flet 0.84: pick_files 是 async，直接返回 list[FilePickerFile]。"""
        if self._page_ref is None:
            return

        picker = ft.FilePicker()
        self._page_ref.overlay.append(picker)
        self._page_ref.update()

        file_type = (
            ft.FilePickerFileType.CUSTOM
            if self._allowed_ext
            else ft.FilePickerFileType.ANY
        )

        try:
            files = await picker.pick_files(
                dialog_title=self._label,
                file_type=file_type,
                allowed_extensions=self._allowed_ext or None,
                allow_multiple=self._allow_multiple,
            )
        except RuntimeError:
            # WSL/无头环境下 FilePicker 超时，静默忽略
            files = None
        finally:
            # 清理 overlay
            self._page_ref.overlay.remove(picker)

        if not files:
            self._page_ref.update()
            return

        paths = [Path(f.path) for f in files if f.path]
        if not paths:
            self._page_ref.update()
            return

        self._set_files(paths)
        self._page_ref.update()

    def _set_files(self, paths: list[Path]) -> None:
        """校验格式后设置选中文件列表。"""
        if self._allowed_ext:
            bad = [p for p in paths if p.suffix.lower().lstrip(".") not in self._allowed_ext]
            if bad:
                self._show_error(f"不支持的格式：{', '.join(p.suffix for p in bad)}")
                return

        self._error_text.visible = False
        self._selected_files = paths
        self._rebuild_chips()
        self._apply_selected_style()

        if self._on_files_selected:
            self._on_files_selected(paths)

    def _show_error(self, msg: str) -> None:
        self._apply_error_style()
        self._error_text.value = msg
        self._error_text.visible = True

    def _rebuild_chips(self) -> None:
        self._file_chips.controls.clear()
        for path in self._selected_files:
            try:
                size_bytes = path.stat().st_size
                size_str = (
                    f"{size_bytes / 1024:.1f} KB"
                    if size_bytes < 1024 * 1024
                    else f"{size_bytes / 1024 / 1024:.1f} MB"
                )
            except OSError:
                size_str = "?"

            chip = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=16, color=ft.Colors.PRIMARY),
                        ft.Text(
                            path.name, size=13, expand=True,
                            no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
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
        """在控件加入 page 后调用，提供 page 引用以使用 run_task。"""
        self._page_ref = page
