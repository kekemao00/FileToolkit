"""UI 工具函数。

Flet 0.84 的 Page 没有稳定的 snack_bar 属性赋值接口，直接使用
`page.snack_bar = ft.SnackBar(...)` 可能不生效。此处通过
`page.overlay.append(snack); snack.open = True` 的方式弹出
SnackBar，并在超时后清理 overlay，避免泄漏。
"""
import threading

import flet as ft


def show_toast(
    page: ft.Page,
    message: str,
    duration: int = 2000,
    color: str = "#005f98",
) -> None:
    """显示一条 toast 提示。

    Args:
        page: Flet Page 实例。
        message: 展示的文字。
        duration: 展示毫秒数，默认 2000ms。
        color: 背景色，默认主题蓝 #005f98。
    """
    snack = ft.SnackBar(
        content=ft.Text(message, color="#ffffff"),
        bgcolor=color,
        duration=duration,
    )
    try:
        page.overlay.append(snack)
        snack.open = True
        page.update()
    except Exception:
        # 兜底：overlay 不可用时降级为直接 open + update
        snack.open = True
        try:
            page.update()
        except Exception:
            return

    def _cleanup() -> None:
        try:
            if snack in page.overlay:
                page.overlay.remove(snack)
                page.update()
        except Exception:
            pass

    threading.Timer(duration / 1000 + 1, _cleanup).start()
