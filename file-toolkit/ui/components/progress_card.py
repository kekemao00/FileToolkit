"""
进度展示卡片

show(filename, desc)        → 切换到进行中状态（不确定进度）
update_progress(n, total, desc) → 更新确定进度
done()                      → 隐藏（任务完成后由父页面接管 UI）
"""
from typing import Callable

import flet as ft


class ProgressCard(ft.Container):
    """
    任务进度卡片。

    状态：
        hidden    → visible=False
        running   → 不确定进度条（循环动画）
        progress  → 确定进度条（百分比 + 描述）

    通过 show() / update_progress() / hide() 控制状态切换。
    on_cancel: 用户点击「取消」时的回调。
    """

    def __init__(self, on_cancel: Callable[[], None] | None = None) -> None:
        self._on_cancel = on_cancel

        self._filename_text = ft.Text("", size=14, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE)
        self._desc_text = ft.Text("准备中...", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self._percent_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)

        self._progress_bar = ft.ProgressBar(
            value=None,           # None = 不确定（循环）
            bgcolor=ft.Colors.SECONDARY_CONTAINER,
            color=ft.Colors.PRIMARY,
            border_radius=ft.border_radius.all(999),
            height=8,
        )

        super().__init__(
            visible=False,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.HOURGLASS_TOP, size=20, color=ft.Colors.PRIMARY),
                            self._filename_text,
                            ft.Container(expand=True),
                            self._percent_text,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self._progress_bar,
                    ft.Row(
                        controls=[
                            self._desc_text,
                            ft.Container(expand=True),
                            ft.TextButton(
                                "取消",
                                on_click=self._handle_cancel,
                                style=ft.ButtonStyle(color=ft.Colors.ERROR),
                                visible=on_cancel is not None,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=10,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=ft.border_radius.all(16),
            padding=ft.padding.all(20),
        )

    # ── 公开 API ─────────────────────────────────────────────────────

    def show(self, filename: str = "", desc: str = "处理中...") -> None:
        """切换到运行态（不确定进度）。"""
        self._filename_text.value = filename
        self._desc_text.value = desc
        self._percent_text.value = ""
        self._progress_bar.value = None
        self.visible = True
        self.update()

    def update_progress(self, current: int, total: int, desc: str = "") -> None:
        """更新确定进度（0~1）。"""
        ratio = current / total if total > 0 else 0
        self._progress_bar.value = ratio
        self._percent_text.value = f"{int(ratio * 100)}%"
        self._desc_text.value = desc or f"{current} / {total}"
        self.update()

    def hide(self) -> None:
        self.visible = False
        self.update()

    def _handle_cancel(self, _: ft.ControlEvent) -> None:
        if self._on_cancel:
            self._on_cancel()
