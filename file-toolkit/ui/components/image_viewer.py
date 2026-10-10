"""全窗口看图器 — 提示词出图结果的大图预览。

替代原来 82%×78% 的对话框：图片铺满整个窗口（四周只留 16px），
工具按钮做成悬浮在图片上的胶囊，鼠标静止一会儿就淡出，移动时淡入。

交互：
    滚轮 / 触控板捏合   以指针为中心缩放（最高到原图像素的 4 倍）
    拖动               平移
    双击图片            在「适应窗口」和「1:1 原始像素」之间切换
    右键图片 / Ctrl+C   复制到剪贴板（直接粘贴到聊天窗口分享）
    ← / →             切换最近作品
    + / - / 0 / 1      放大 / 缩小 / 适应窗口 / 原始像素
    Esc / 点空白处      关闭

动效（沿用 ui/style.py 的令牌）：遮罩淡入 + 背景虚化，图片从 94% 缩放淡入，
顶部信息条和底部工具条从上下两侧错开滑入；切图时交叉淡入淡出；
按钮缩放分多帧逐级放大，看起来是平滑过渡而不是跳变。
"""
from __future__ import annotations

import asyncio
import io
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import flet as ft

from services import clipboard_service
from ui import style as s
from ui.palette import c, is_dark
from ui.utils import show_toast

INSET = 16                 # 图片与窗口边缘的距离（适应窗口时）
_IDLE_HIDE = 2.6           # 鼠标静止多少秒后隐藏工具条
_ZOOM_STEP = 1.5           # + / - 每次缩放倍数
_ZOOM_FRAMES = 8           # 按钮缩放拆成多少帧
_MAX_PIXEL_SCALE = 4.0     # 最多放大到原图像素的几倍


@dataclass
class ViewerItem:
    """看图器里的一张图。path 和 data 至少给一个；桌面端优先用 path 加载。"""
    path: Path | None = None
    data: bytes | None = None
    title: str = ""
    meta: str = ""
    _size: tuple[int, int] | None = field(default=None, repr=False)

    def pixel_size(self) -> tuple[int, int] | None:
        """原图像素尺寸（读文件头，不解码整张图）。"""
        if self._size is None:
            try:
                from PIL import Image
                src = io.BytesIO(self.data) if self.data else self.path
                with Image.open(src) as im:
                    self._size = im.size
            except Exception:
                return None
        return self._size

    def file_bytes(self) -> int:
        if self.data:
            return len(self.data)
        try:
            return self.path.stat().st_size if self.path else 0
        except OSError:
            return 0


def fit_ratio(img: tuple[int, int], view: tuple[float, float]) -> float:
    """适应窗口时图片的显示比例（不放大小图，所以不超过 1）。"""
    iw, ih = img
    vw, vh = view
    if iw <= 0 or ih <= 0 or vw <= 0 or vh <= 0:
        return 1.0
    return min(1.0, vw / iw, vh / ih)


def human_size(n: int) -> str:
    if n <= 0:
        return ""
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


class ImageViewer:
    """挂在 page.overlay 上的全窗口看图器。用 `ImageViewer(page, items, index).open()` 打开。"""

    def __init__(
        self,
        page: ft.Page,
        items: list[ViewerItem],
        index: int = 0,
        on_save: Callable[[ViewerItem], None] | None = None,
        on_reveal: Callable[[ViewerItem], None] | None = None,
    ) -> None:
        self._page = page
        self._items = items
        self._index = max(0, min(index, len(items) - 1))
        self._on_save = on_save
        self._on_reveal = on_reveal
        self._prev_key = None
        self._closing = False
        self._s = 1.0              # 当前缩放（相对适应窗口）
        self._t = (0.0, 0.0)       # 当前平移（屏幕像素）
        self._pointer: tuple[float, float] | None = None
        self._gesture = False
        self._g_scale = 1.0
        self._zoom_busy = False
        self._copying = False
        self._last_move = time.monotonic()
        self._chrome_on = True
        self._over_chrome = False
        self._build()

    # ── 构建 ─────────────────────────────────────────────────────────
    def _build(self) -> None:
        dark = is_dark()
        self._scrim = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.94 if dark else 0.9, c("viewer-bg")),
            blur=ft.Blur(24, 24),
            left=0, top=0, right=0, bottom=0,
            opacity=0, animate_opacity=s.default(),
        )
        self._switcher = ft.AnimatedSwitcher(
            content=self._image_frame(),
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=ft.Duration(milliseconds=260),
            reverse_duration=ft.Duration(milliseconds=160),
            switch_in_curve=ft.AnimationCurve.EASE_OUT_CUBIC,
            switch_out_curve=ft.AnimationCurve.EASE_IN_CUBIC,
        )
        self._viewer = ft.InteractiveViewer(
            content=ft.GestureDetector(
                content=ft.Container(content=self._switcher, alignment=ft.Alignment(0, 0),
                                     padding=INSET, expand=True),
                on_hover=self._on_content_hover, hover_interval=30,
                on_tap=self._on_stage_tap,
                on_secondary_tap_down=self._on_secondary_tap,
                on_double_tap=lambda _e: self._run(self._toggle_actual),
                expand=True,
            ),
            min_scale=1, max_scale=self._max_scale(),
            scale_factor=320,
            interaction_update_interval=0,
            on_interaction_start=self._on_interaction_start,
            on_interaction_update=self._on_interaction,
            on_interaction_end=self._on_interaction_end,
            expand=True,
        )
        self._stage = ft.Container(
            content=self._viewer,
            left=0, top=0, right=0, bottom=0,
            opacity=0, scale=0.94,
            animate_opacity=s.default(), animate_scale=s.smooth(),
        )

        # 顶部：左侧信息胶囊，右侧关闭按钮
        self._title = s.text("", "body", "ink", size=13, weight=ft.FontWeight.W_500,
                             max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self._meta = s.text("", "mono", "ink-3", size=11, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS)
        self._counter = s.text("", "mono", "ink-2", size=11)
        self._info = self._glass(
            ft.Row(
                controls=[self._counter_chip(), ft.Column([self._title, self._meta], spacing=1, tight=True)],
                spacing=10, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(left=8, right=16, top=8, bottom=8),
        )
        self._top = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(self._info, expand=True, alignment=ft.Alignment(-1, 0)),
                    self._glass(self._tool(ft.Icons.CLOSE_ROUNDED, "关闭（Esc）", self._close_click),
                                padding=4),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            left=INSET + 8, right=INSET + 8, top=INSET + 8,
            offset=ft.Offset(0, -0.6), opacity=0,
            animate_offset=s.smooth(), animate_opacity=s.default(),
        )

        # 底部工具条
        self._fit_btn = self._tool(ft.Icons.FIT_SCREEN_OUTLINED, "适应窗口（0）", lambda _e: self._run(self._fit))
        self._one_btn = self._tool_text("1:1", "原始像素（1）", lambda _e: self._run(self._actual))
        tools = [
            self._tool(ft.Icons.REMOVE_ROUNDED, "缩小（-）", lambda _e: self._run(self._zoom_by, 1 / _ZOOM_STEP)),
            self._fit_btn,
            self._one_btn,
            self._tool(ft.Icons.ADD_ROUNDED, "放大（+）", lambda _e: self._run(self._zoom_by, _ZOOM_STEP)),
        ]
        extra = [self._tool(ft.Icons.CONTENT_COPY_OUTLINED, "复制图片（右键 / Ctrl+C）",
                            lambda _e: self._run(self._copy))]
        if self._on_save:
            extra.append(self._tool(ft.Icons.DOWNLOAD_OUTLINED, "另存为",
                                    lambda _e: self._on_save(self._item)))
        if self._on_reveal:
            extra.append(self._tool(ft.Icons.FOLDER_OPEN_OUTLINED, "打开所在文件夹",
                                    lambda _e: self._on_reveal(self._item)))
        tools += [self._sep(), *extra]
        self._toolbar = ft.Container(
            content=self._glass(ft.Row(tools, spacing=2, tight=True), padding=5),
            left=0, right=0, bottom=INSET + 12, alignment=ft.Alignment(0, 1),
            offset=ft.Offset(0, 0.8), opacity=0,
            animate_offset=s.smooth(), animate_opacity=s.default(),
        )
        self._hint = ft.Container(
            content=s.text("滚轮缩放 · 拖动平移 · 双击切换原图 · 右键复制 · ← → 切换作品", "small", "ink-2", size=11.5),
            bgcolor=ft.Colors.with_opacity(0.78, c("surface")), border_radius=999,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        )
        self._hint_host = ft.Container(
            content=self._hint, left=0, right=0, bottom=INSET + 72, alignment=ft.Alignment(0, 1),
            opacity=0, animate_opacity=s.smooth(), ignore_interactions=True,
        )

        # 左右切换
        multi = len(self._items) > 1
        self._prev = self._nav(ft.Icons.CHEVRON_LEFT_ROUNDED, "上一张（←）", -1, left=INSET + 8, visible=multi)
        self._next = self._nav(ft.Icons.CHEVRON_RIGHT_ROUNDED, "下一张（→）", 1, right=INSET + 8, visible=multi)

        self._chrome = [self._top, self._toolbar, self._prev, self._next]
        self.host = ft.GestureDetector(
            content=ft.Stack(
                controls=[self._scrim, self._stage, self._prev, self._next,
                          self._top, self._hint_host, self._toolbar],
                expand=True,
            ),
            on_hover=self._on_pointer, hover_interval=120,
            left=0, top=0, right=0, bottom=0,
        )
        self._fill_info()

    def _glass(self, content: ft.Control, padding=8) -> ft.Container:
        """悬浮胶囊：半透明表面 + 背景虚化 + 1px 描边 + 柔和阴影。"""
        return ft.Container(
            content=content, padding=padding,
            bgcolor=ft.Colors.with_opacity(0.82, c("surface")),
            blur=ft.Blur(18, 18),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.7, c("line"))),
            border_radius=999,
            shadow=ft.BoxShadow(blur_radius=24, offset=ft.Offset(0, 8), spread_radius=-6,
                                color=ft.Colors.with_opacity(0.18, c("shadow"))),
            on_hover=self._on_chrome_hover,
        )

    def _tool(self, icon: str, tip: str, on_click) -> ft.Control:
        return s.icon_button(icon, on_click, tooltip=tip, size=34, color="ink")

    def _tool_text(self, label: str, tip: str, on_click) -> ft.Control:
        return ft.Container(
            content=s.text(label, "mono", "ink", size=12, weight=ft.FontWeight.W_600),
            width=40, height=34, border_radius=s.R_BUTTON, alignment=ft.Alignment(0, 0),
            tooltip=tip, on_click=on_click, animate=s.snappy(),
            on_hover=lambda e: self._hover_fill(e.control, e.data),
        )

    @staticmethod
    def _hover_fill(ctrl: ft.Container, on) -> None:
        ctrl.bgcolor = ft.Colors.with_opacity(0.75, c("surface-3")) if on in (True, "true") else None
        try:
            ctrl.update()
        except RuntimeError:
            pass

    def _sep(self) -> ft.Control:
        return ft.Container(width=1, height=18, bgcolor=c("line"), margin=ft.Margin.symmetric(horizontal=6))

    def _counter_chip(self) -> ft.Control:
        self._counter_box = ft.Container(
            content=self._counter, bgcolor=c("surface-3"), border_radius=999,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            visible=len(self._items) > 1,
        )
        return self._counter_box

    def _nav(self, icon: str, tip: str, step: int, visible: bool, **pos) -> ft.Container:
        btn = self._glass(
            ft.IconButton(icon=icon, icon_size=22, icon_color=c("ink", "fg"), tooltip=tip,
                          width=44, height=44, on_click=lambda _e: self._run(self._go, step),
                          style=ft.ButtonStyle(overlay_color=ft.Colors.TRANSPARENT,
                                               shape=ft.CircleBorder())),
            padding=0,
        )
        return ft.Container(
            content=btn, top=0, bottom=0, alignment=ft.Alignment(0, 0), visible=visible,
            opacity=0, offset=ft.Offset(-0.4 if step < 0 else 0.4, 0),
            animate_opacity=s.default(), animate_offset=s.smooth(), **pos,
        )

    def _image_frame(self) -> ft.Control:
        item = self._items[self._index]
        if item.path is not None and item.path.exists() and not self._page.web:
            src: str | bytes = str(item.path)
        elif item.data:
            src = item.data
        elif item.path is not None and item.path.exists():
            src = item.path.read_bytes()
        else:
            src = b""
        image = ft.Image(
            src=src, fit=ft.BoxFit.CONTAIN, filter_quality=ft.FilterQuality.HIGH,
            gapless_playback=True,
            error_content=s.empty_state(ft.Icons.BROKEN_IMAGE_OUTLINED, "图片加载失败",
                                        "文件可能已被移动或删除"),
        )
        self._frame = ft.Container(
            content=image, border_radius=6, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            shadow=ft.BoxShadow(blur_radius=48, offset=ft.Offset(0, 18), spread_radius=-12,
                                color=ft.Colors.with_opacity(0.35, c("shadow"))),
            scale=1, animate_scale=s.snappy(),
            key=f"img-{self._index}",
        )
        return self._frame

    # ── 尺寸计算 ─────────────────────────────────────────────────────
    @property
    def _item(self) -> ViewerItem:
        return self._items[self._index]

    def _view_size(self) -> tuple[float, float]:
        return ((self._page.width or 1280) - 2 * INSET, (self._page.height or 800) - 2 * INSET)

    def _actual_scale(self) -> float:
        """1:1 原始像素相对「适应窗口」需要放大的倍数。"""
        size = self._item.pixel_size()
        if not size:
            return 2.0
        return 1 / fit_ratio(size, self._view_size())

    def _image_rect(self) -> tuple[float, float, float, float]:
        """适应窗口时图片在内容坐标里的位置 (x, y, w, h)。"""
        w, h = self._viewport()
        size = self._item.pixel_size() or (1, 1)
        r = fit_ratio(size, self._view_size())
        dw, dh = size[0] * r, size[1] * r
        return (w - dw) / 2, (h - dh) / 2, dw, dh

    def _hit_image(self, pos) -> bool:
        x, y, w, h = self._image_rect()
        return pos is not None and x <= pos.x <= x + w and y <= pos.y <= y + h

    def _on_secondary_tap(self, e) -> None:
        """右键点图片任意位置：复制到剪贴板。"""
        if self._hit_image(getattr(e, "local_position", None)):
            self._run(self._copy)

    async def _copy(self) -> None:
        if self._copying:
            return
        self._copying = True
        item = self._item
        # 按压回弹，给「已复制」一个触感反馈
        self._frame.scale = 0.97
        self._safe_update(self._frame)
        await asyncio.sleep(0.12)
        self._frame.scale = 1
        self._safe_update(self._frame)
        try:
            ok = await self._copy_item(item)
        except Exception:
            ok = False
        finally:
            self._copying = False
        if ok:
            show_toast(self._page, "图片已复制，可直接粘贴发送", kind="success")
        else:
            show_toast(self._page, "复制失败，可用「另存为」保存后发送", kind="error")

    async def _copy_item(self, item: ViewerItem) -> bool:
        page = self._page
        web_like = page.web or page.platform.is_mobile()
        if web_like:
            data = item.data or (item.path.read_bytes() if item.path and item.path.exists() else None)
            if not data:
                return False
            await ft.Clipboard().set_image(data)
            return True
        path = item.path if item.path and item.path.exists() else None
        if path is None and item.data:
            path = Path(tempfile.gettempdir()) / f"file-toolkit-clip-{int(time.time())}.png"
            path.write_bytes(item.data)
        if path is None:
            return False
        return await asyncio.to_thread(clipboard_service.copy_image_file, path)

    def _on_stage_tap(self, e) -> None:
        """点图片以外的空白处关闭；点图片本身不响应。"""
        pos = getattr(e, "local_position", None)
        if pos is not None and not self._hit_image(pos):
            self._close_click()

    def _max_scale(self) -> float:
        return max(4.0, self._actual_scale() * _MAX_PIXEL_SCALE)

    def _fill_info(self) -> None:
        item = self._item
        self._title.value = item.title or (item.path.name if item.path else "图片")
        parts = []
        size = item.pixel_size()
        if size:
            parts.append(f"{size[0]} × {size[1]}")
        if (fs := human_size(item.file_bytes())):
            parts.append(fs)
        if item.meta:
            parts.append(item.meta)
        self._meta.value = "  ·  ".join(parts)
        self._counter.value = f"{self._index + 1} / {len(self._items)}"

    # ── 开关 ─────────────────────────────────────────────────────────
    def open(self) -> None:
        page = self._page
        page.overlay.append(self.host)
        self._prev_key = page.on_keyboard_event
        page.on_keyboard_event = self._on_key
        page.update()
        page.run_task(self._enter)

    async def _enter(self) -> None:
        await asyncio.sleep(0.016)
        self._scrim.opacity = 1
        self._stage.opacity, self._stage.scale = 1, 1
        self._safe_update()
        await asyncio.sleep(0.09)
        self._show_chrome(True)
        await asyncio.sleep(0.25)
        self._hint_host.opacity = 1
        self._safe_update(self._hint_host)
        self._page.run_task(self._idle_loop)

    def _close_click(self, _e=None) -> None:
        self._run(self.close)

    async def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        page = self._page
        if page.on_keyboard_event == self._on_key:
            page.on_keyboard_event = self._prev_key
        self._scrim.opacity = 0
        self._stage.opacity, self._stage.scale = 0, 0.96
        self._hint_host.opacity = 0
        self._show_chrome(False, update=False)
        self._safe_update()
        await asyncio.sleep(0.26)
        if self.host in page.overlay:
            page.overlay.remove(self.host)
            page.update()

    def _safe_update(self, *controls: ft.Control) -> None:
        try:
            if controls:
                for ctrl in controls:
                    ctrl.update()
            else:
                self.host.update()
        except RuntimeError:
            pass

    def _run(self, fn, *args) -> None:
        self._page.run_task(fn, *args)

    # ── 工具条显隐 ───────────────────────────────────────────────────
    def _show_chrome(self, on: bool, update: bool = True) -> None:
        self._chrome_on = on
        self._top.opacity = 1 if on else 0
        self._top.offset = ft.Offset(0, 0 if on else -0.6)
        self._toolbar.opacity = 1 if on else 0
        self._toolbar.offset = ft.Offset(0, 0 if on else 0.8)
        for nav, dx in ((self._prev, -0.4), (self._next, 0.4)):
            nav.opacity = 1 if on else 0
            nav.offset = ft.Offset(0 if on else dx, 0)
        if update:
            self._safe_update(*self._chrome)

    def _on_pointer(self, _e=None) -> None:
        self._last_move = time.monotonic()
        if not self._chrome_on and not self._closing:
            self._show_chrome(True)

    def _on_chrome_hover(self, e) -> None:
        self._over_chrome = e.data in (True, "true")
        self._last_move = time.monotonic()

    async def _idle_loop(self) -> None:
        started = time.monotonic()
        while not self._closing:
            await asyncio.sleep(0.4)
            now = time.monotonic()
            if self._hint_host.opacity and now - started > 3.2:
                self._hint_host.opacity = 0
                self._safe_update(self._hint_host)
            if self._chrome_on and not self._over_chrome and now - self._last_move > _IDLE_HIDE:
                self._show_chrome(False)

    # ── 缩放 ─────────────────────────────────────────────────────────
    # InteractiveViewer 不回传变换矩阵，这里自己维护一份：屏幕坐标 = t + s × 内容坐标。
    # s 由缩放手势累计；t 每次鼠标移动时用「同一个指针的屏幕坐标 / 内容坐标」直接校正，
    # 拖动、惯性滑动后的误差在下一次移动鼠标时就消掉了。
    # Flet 的 zoom() / pan() 都是右乘矩阵：zoom 不动 t，pan(d) 让 t 增加 s × d。
    def _clamp_t(self, s: float, tx: float, ty: float) -> tuple[float, float]:
        w, h = self._viewport()
        return min(0.0, max(w * (1 - s), tx)), min(0.0, max(h * (1 - s), ty))

    def _viewport(self) -> tuple[float, float]:
        return float(self._page.width or 1280), float(self._page.height or 800)

    def _on_content_hover(self, e) -> None:
        a, p = e.local_position, e.global_position
        if a is None or p is None:
            return
        self._pointer = (p.x, p.y)
        if not self._gesture:
            self._t = self._clamp_t(self._s, p.x - self._s * a.x, p.y - self._s * a.y)

    def _on_interaction_start(self, _e) -> None:
        self._gesture, self._g_scale = True, 1.0

    def _on_interaction(self, e) -> None:
        scale = getattr(e, "scale", 1.0) or 1.0
        k, self._g_scale = scale / self._g_scale, scale
        s2 = max(1.0, min(self._max_scale(), self._s * k))
        k = s2 / self._s
        fp, d = e.local_focal_point, e.focal_point_delta
        tx, ty = self._t
        if fp is not None:
            tx, ty = fp.x - k * (fp.x - tx), fp.y - k * (fp.y - ty)
        if d is not None:
            tx, ty = tx + d.x, ty + d.y
        self._s = s2
        self._t = self._clamp_t(s2, tx, ty)
        self._on_pointer()

    def _on_interaction_end(self, _e) -> None:
        self._gesture = False

    def _center(self) -> tuple[float, float]:
        w, h = self._viewport()
        return w / 2, h / 2

    async def _zoom_to(self, target: float, pivot: tuple[float, float] | None = None) -> None:
        """以屏幕上的 pivot 点为中心缩放到 target 倍，分多帧做缓出过渡。"""
        target = max(1.0, min(self._max_scale(), target))
        if abs(target / self._s - 1) < 1e-3 or self._zoom_busy:
            return
        px, py = pivot or self._center()
        s0, (tx0, ty0) = self._s, self._t
        self._zoom_busy = True
        try:
            for i in range(1, _ZOOM_FRAMES + 1):
                p = 1 - (1 - i / _ZOOM_FRAMES) ** 3          # ease-out cubic
                s1 = s0 * (target / s0) ** p
                r = s1 / s0
                t1 = self._clamp_t(s1, px - r * (px - tx0), py - r * (py - ty0))
                await self._viewer.zoom(s1 / self._s)
                await self._viewer.pan((t1[0] - self._t[0]) / s1, (t1[1] - self._t[1]) / s1)
                self._s, self._t = s1, t1
                await asyncio.sleep(0.012)
        except Exception:
            pass
        finally:
            self._zoom_busy = False

    async def _zoom_by(self, factor: float) -> None:
        await self._zoom_to(self._s * factor)

    async def _fit(self) -> None:
        self._s, self._t = 1.0, (0.0, 0.0)
        try:
            await self._viewer.reset(animation_duration=ft.Duration(milliseconds=360))
        except Exception:
            pass

    async def _actual(self, pivot: tuple[float, float] | None = None) -> None:
        await self._zoom_to(self._actual_scale(), pivot)

    async def _toggle_actual(self) -> None:
        """双击：已放大就回到适应窗口，否则以鼠标所在位置为中心放大到原始像素。"""
        if self._s > 1.01:
            await self._fit()
        else:
            await self._actual(self._pointer)

    # ── 切换 ─────────────────────────────────────────────────────────
    async def _go(self, step: int) -> None:
        if len(self._items) < 2:
            return
        self._index = (self._index + step) % len(self._items)
        self._s, self._t = 1.0, (0.0, 0.0)
        try:
            await self._viewer.reset()
        except Exception:
            pass
        self._viewer.max_scale = self._max_scale()
        self._switcher.content = self._image_frame()
        self._fill_info()
        self._safe_update(self._viewer, self._info)

    # ── 键盘 ─────────────────────────────────────────────────────────
    def _on_key(self, e: ft.KeyboardEvent) -> None:
        key = e.key
        if (e.ctrl or getattr(e, "meta", False)) and key.upper() == "C":
            self._run(self._copy)
            return
        actions = {
            "Escape": (self.close,),
            "Arrow Left": (self._go, -1),
            "Arrow Right": (self._go, 1),
            "=": (self._zoom_by, _ZOOM_STEP),
            "+": (self._zoom_by, _ZOOM_STEP),
            "Numpad Add": (self._zoom_by, _ZOOM_STEP),
            "-": (self._zoom_by, 1 / _ZOOM_STEP),
            "Minus": (self._zoom_by, 1 / _ZOOM_STEP),
            "Numpad Subtract": (self._zoom_by, 1 / _ZOOM_STEP),
            "0": (self._fit,),
            "Numpad 0": (self._fit,),
            "1": (self._actual,),
            "Numpad 1": (self._actual,),
        }
        if key in actions:
            self._on_pointer()
            self._run(*actions[key])
