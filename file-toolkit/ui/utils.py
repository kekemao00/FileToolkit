"""UI 工具函数。

show_toast 是灵动岛式通知：顶部居中的墨黑胶囊，从 10px 小圆点展开成消息宽度，
停留后先收成圆、再缩成小点淡出。新消息来时不新建控件，同一个胶囊改宽度，
徽标和文字在淡入淡出里换掉（同一时刻只有一个形状）。

Flet 0.84 没有 Page.open()，胶囊挂在 page.overlay 里，每个 page 只建一次。
"""
import asyncio

import flet as ft

from ui import style as s
from ui.palette import c

_PILL_H = 40

# 旧调用方传的是背景色，这里换成通知类型
_SUCCESS_COLORS = {"#047857", "#16a34a", "#059669", "#10b981"}
_ERROR_COLORS = {"#b31b25", "#be123c", "#dc2626", "#b91c1c", "#e11d48"}
_WARN_COLORS = {"#b45309", "#d97706"}


class _Island:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.seq = 0
        self.badge_icon = ft.Icon(ft.Icons.CHECK_ROUNDED, size=14)
        self.badge = ft.Container(
            content=self.badge_icon, width=22, height=22, border_radius=11,
            alignment=ft.Alignment(0, 0), animate=s.snappy(),
        )
        self.label = ft.Text(size=13, weight=ft.FontWeight.W_500, font_family=s.FONT,
                             no_wrap=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.body = ft.Row(
            controls=[self.badge, self.label], spacing=10, tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.body_box = ft.Container(content=self.body, opacity=0, animate_opacity=s.snappy(),
                                     padding=ft.padding.only(left=9, right=16))
        self.pill = ft.Container(
            content=self.body_box, width=10, height=10, border_radius=5, opacity=0,
            alignment=ft.Alignment(-1, 0), clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=s.smooth(), animate_opacity=s.snappy(),
        )
        self.host = ft.Row(
            controls=[ft.Container(content=self.pill, height=_PILL_H, alignment=ft.Alignment(0, 0))],
            alignment=ft.MainAxisAlignment.CENTER, top=14, left=0, right=0,
        )
        page.overlay.append(self.host)

    def _style(self, kind: str) -> None:
        self.pill.bgcolor = c("ink")
        self.label.color = c("on-ink", "fg")
        if kind == "success":
            self.badge.bgcolor, icon, fg = c("accent"), ft.Icons.CHECK_ROUNDED, "#FFFFFF"
        elif kind == "error":
            self.badge.bgcolor, icon, fg = c("danger"), ft.Icons.CLOSE_ROUNDED, "#FFFFFF"
        elif kind == "warning":
            self.badge.bgcolor = ft.Colors.with_opacity(0.18, c("on-ink", "fg"))
            icon, fg = ft.Icons.PRIORITY_HIGH_ROUNDED, c("on-ink", "fg")
        else:
            self.badge.bgcolor = ft.Colors.with_opacity(0.18, c("on-ink", "fg"))
            icon, fg = ft.Icons.INFO_OUTLINE_ROUNDED, c("on-ink", "fg")
        self.badge_icon.icon, self.badge_icon.color = icon, fg

    async def show(self, message: str, kind: str, duration_ms: int) -> None:
        self.seq += 1
        seq = self.seq
        expanded = self.pill.width and self.pill.width > _PILL_H
        width = min(560.0, 9 + 22 + 10 + s.text_width(message, 13) + 16 + 4)

        if expanded:
            # 同一个胶囊换内容：旧内容先淡出，再改宽度、淡入新内容
            self.body_box.opacity = 0
            self.page.update()
            await asyncio.sleep(0.11)
        else:
            self.pill.width = self.pill.height = 10
            self.pill.border_radius = 5
            self.pill.opacity = 1
            self._style(kind)
            self.page.update()
            await asyncio.sleep(0.03)
        self._style(kind)
        self.label.value = message
        self.pill.width, self.pill.height, self.pill.border_radius = width, _PILL_H, _PILL_H / 2
        self.page.update()
        # 形状展开到一大半后内容才出现
        await asyncio.sleep(0.2)
        if seq != self.seq:
            return
        self.body_box.opacity = 1
        self.page.update()

        await asyncio.sleep(duration_ms / 1000)
        if seq != self.seq:
            return
        # 消失：先收成圆，再缩成小点淡出
        self.body_box.opacity = 0
        self.pill.width = _PILL_H
        self.page.update()
        await asyncio.sleep(0.2)
        if seq != self.seq:
            return
        self.pill.width = self.pill.height = 8
        self.pill.border_radius = 4
        self.pill.opacity = 0
        self.page.update()


_islands: dict[int, _Island] = {}


def _kind_from_color(color: str | None) -> str:
    if not color:
        return "info"
    key = color.lower()
    if key in _SUCCESS_COLORS:
        return "success"
    if key in _ERROR_COLORS:
        return "error"
    if key in _WARN_COLORS:
        return "warning"
    return "info"


def show_toast(
    page: ft.Page,
    message: str,
    duration: int | None = None,
    color: str | None = None,
    kind: str | None = None,
) -> None:
    """显示一条顶部通知。

    Args:
        page: Flet Page 实例。
        message: 展示的文字。
        duration: 停留毫秒数；默认 1.8s + 每字 60ms（最多再加 2.6s）。
        color: 兼容旧调用：传入的颜色会换算成通知类型（绿=成功、红=错误、琥珀=提醒）。
        kind: success / error / warning / info，优先于 color。
    """
    kind = kind or _kind_from_color(color)
    if duration is None:
        duration = 1800 + min(2600, 60 * len(message))
    try:
        island = _islands.get(id(page))
        if island is None or island.host not in page.overlay:
            island = _islands[id(page)] = _Island(page)
        elif page.overlay[-1] is not island.host:
            # 之后打开的浮层（如看图器）会盖住通知，挪回最上层
            page.overlay.remove(island.host)
            page.overlay.append(island.host)
        page.run_task(island.show, message, kind, duration)
    except Exception:
        pass


def is_mounted(control: ft.Control) -> bool:
    """Flet 0.84 未挂载时访问 .page 会抛 RuntimeError。"""
    try:
        return control.page is not None
    except RuntimeError:
        return False


def _launch(cmd: list[str]) -> bool:
    import subprocess
    try:
        subprocess.Popen(cmd)
        return True
    except OSError:
        return False


def open_folder(path) -> bool:
    """用系统文件管理器打开目录；目录不存在或打不开时返回 False。"""
    import sys
    from pathlib import Path

    target = Path(path)
    if not str(path) or not target.exists():
        return False
    if sys.platform == "win32":
        return _launch(["explorer", str(target)])
    if sys.platform == "darwin":
        return _launch(["open", str(target)])
    return _launch(["xdg-open", str(target)])


def reveal_file(path) -> bool:
    """在文件管理器中显示并选中文件（Linux 没有统一的选中方式，打开所在目录）。"""
    import sys
    from pathlib import Path

    target = Path(path)
    if not target.exists():
        return False
    if sys.platform == "win32":
        return _launch(["explorer", "/select,", str(target)])
    if sys.platform == "darwin":
        return _launch(["open", "-R", str(target)])
    return open_folder(target.parent)


def notify_task_done(page: ft.Page, output_dir) -> None:
    """按设置「处理完成后」的选项：打开输出目录 / 仅提示 / 静默。"""
    from services import settings_service

    after = settings_service.get("after_complete", "open_dir")
    if after == "open_dir" and output_dir:
        open_folder(output_dir)
    elif after == "notify":
        show_toast(page, "处理完成", kind="success")
