"""
设计令牌（尺寸 / 字体 / 动效）与共享组件 — 暖灰黑白 · 弹簧动效风格。

颜色令牌在 ui/palette.py；这里放其余令牌和几个所有页面共用的小组件，
页面只引用这里的常量和工厂函数，不各自写死尺寸、圆角和动画。

Flet 的隐式动画只接受「时长 + 内置曲线」，没有自定义弹簧，
按规范用 EASE_OUT_CUBIC / EASE_OUT_QUART 近似（不用 BOUNCE / ELASTIC / BACK）：
    snappy()   悬停、按下、焦点、透明度
    default()  位置、尺寸、高亮块滑动
    smooth()   面板展开、通知胶囊、页面入场
    lead() / trail()  指示条前沿 / 后沿（两段式拉伸）
"""
import asyncio
import unicodedata
from collections.abc import Callable

import flet as ft

from ui.palette import c

# ── 字体 ─────────────────────────────────────────────────────────────
FONT = "Geist"
MONO = "Geist Mono"

# ── 圆角 / 尺寸 ───────────────────────────────────────────────────────
R_BUTTON = 9
R_PRIMARY = 11
R_INPUT = 10
R_PANEL = 16
H_BUTTON = 34
H_PRIMARY = 42
H_INPUT = 40
H_ROW = 46
PAGE_X = 24

# ── 动效 ─────────────────────────────────────────────────────────────
# 每次调用返回新实例：Flet 会跟踪属性值对象，同一个实例挂在多个控件上会出错
DUR_SNAPPY = 200


def snappy() -> ft.Animation:
    return ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC)


def default() -> ft.Animation:
    return ft.Animation(360, ft.AnimationCurve.EASE_OUT_QUART)


def smooth() -> ft.Animation:
    return ft.Animation(480, ft.AnimationCurve.EASE_OUT_QUART)


def lead() -> ft.Animation:
    return ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC)


def trail() -> ft.Animation:
    return ft.Animation(420, ft.AnimationCurve.EASE_OUT_QUART)

# ── 字号刻度：(字号, 字重, 默认颜色令牌) ────────────────────────────────
_TEXT = {
    "headline": (22, ft.FontWeight.W_600, "ink"),
    "title": (15, ft.FontWeight.W_600, "ink"),
    "body": (13, ft.FontWeight.W_400, "ink"),
    "body-medium": (13, ft.FontWeight.W_500, "ink"),
    "label": (13, ft.FontWeight.W_500, "ink"),
    "small": (12, ft.FontWeight.W_400, "ink-2"),
    "caption": (11, ft.FontWeight.W_500, "ink-3"),
    "mono": (12.5, ft.FontWeight.W_400, "ink-2"),
}


def text(value: str = "", kind: str = "body", color: str | None = None, **kwargs) -> ft.Text:
    size, weight, token = _TEXT[kind]
    kwargs.setdefault("size", size)
    kwargs.setdefault("weight", weight)
    return ft.Text(
        value,
        color=c(color or token, "fg"),
        font_family=MONO if kind == "mono" else FONT,
        **kwargs,
    )


def text_width(value: str, size: float = 13) -> float:
    """估算文字宽度（中文按全角，其余按半角）。用于胶囊、指示条这类要先知道宽度的形状。"""
    w = 0.0
    for ch in value:
        w += size if unicodedata.east_asian_width(ch) in ("W", "F") else size * 0.58
    return w


# ── 按钮 ─────────────────────────────────────────────────────────────
def button_style(kind: str = "primary", radius: float = R_BUTTON) -> ft.ButtonStyle:
    """kind: primary / secondary / ghost / danger / accent。"""
    if kind == "primary":
        bg = {ft.ControlState.HOVERED: c("ink-hover"), ft.ControlState.DEFAULT: c("ink")}
        fg, side = c("on-ink"), None
    elif kind == "accent":
        bg = {ft.ControlState.DEFAULT: c("accent")}
        fg, side = c("on-accent"), None
    elif kind == "danger":
        bg = {ft.ControlState.DEFAULT: c("danger")}
        fg, side = "#FFFFFF", None
    elif kind == "secondary":
        bg = {ft.ControlState.HOVERED: c("surface-2"), ft.ControlState.DEFAULT: c("surface")}
        fg = c("ink")
        side = {
            ft.ControlState.HOVERED: ft.BorderSide(1, c("line-strong")),
            ft.ControlState.DEFAULT: ft.BorderSide(1, c("line")),
        }
    else:  # ghost
        bg = {
            ft.ControlState.HOVERED: ft.Colors.with_opacity(0.75, c("surface-3")),
            ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
        }
        fg = {ft.ControlState.HOVERED: c("ink"), ft.ControlState.DEFAULT: c("ink-2")}
        side = None
    return ft.ButtonStyle(
        bgcolor=bg,
        color=fg,
        icon_color=fg,
        icon_size=16,
        overlay_color=ft.Colors.TRANSPARENT,
        shadow_color=ft.Colors.TRANSPARENT,
        elevation=0,
        side=side,
        shape=ft.RoundedRectangleBorder(radius=radius),
        padding=ft.Padding.symmetric(horizontal=14),
        text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_500, font_family=FONT),
        animation_duration=DUR_SNAPPY,
    )


def button(
    label: str,
    on_click: Callable | None = None,
    kind: str = "primary",
    icon: str | None = None,
    height: float = H_BUTTON,
    **kwargs,
) -> ft.Button:
    radius = R_PRIMARY if height >= H_PRIMARY else R_BUTTON
    return ft.Button(
        content=label,
        icon=icon,
        on_click=on_click,
        height=height,
        style=button_style(kind, radius),
        **kwargs,
    )


def icon_button(
    icon: str,
    on_click: Callable | None = None,
    tooltip: str | None = None,
    size: float = 32,
    color: str = "ink-2",
    **kwargs,
) -> ft.IconButton:
    """纯图标幽灵按钮：正方形，悬停 surface-3。"""
    return ft.IconButton(
        icon=icon,
        icon_size=16,
        icon_color=c(color, "fg"),
        tooltip=tooltip,
        on_click=on_click,
        width=size,
        height=size,
        style=ft.ButtonStyle(
            padding=ft.Padding.all(0),
            shape=ft.RoundedRectangleBorder(radius=R_BUTTON),
            bgcolor={
                ft.ControlState.HOVERED: ft.Colors.with_opacity(0.75, c("surface-3")),
                ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
            },
            overlay_color=ft.Colors.TRANSPARENT,
            animation_duration=DUR_SNAPPY,
        ),
        **kwargs,
    )


# ── 表面 ─────────────────────────────────────────────────────────────
def card(content: ft.Control | None = None, padding: float | ft.Padding = 20, **kwargs) -> ft.Container:
    """白色主卡片：1px line 描边、圆角 16、无阴影。"""
    kwargs.setdefault("bgcolor", c("surface"))
    kwargs.setdefault("border", ft.Border.all(1, c("line")))
    kwargs.setdefault("border_radius", R_PANEL)
    return ft.Container(content=content, padding=padding, **kwargs)


def icon_tile(icon: str, size: float = 32, icon_size: float = 16, active: bool = False) -> ft.Container:
    """功能图标底块：中性 surface-2 方块 + ink-2 线性图标；选中时换成强调色。"""
    return ft.Container(
        content=ft.Icon(icon, size=icon_size, color=c("accent-fg" if active else "ink-2", "fg")),
        width=size,
        height=size,
        border_radius=R_BUTTON if size <= 36 else 12,
        bgcolor=c("accent-soft" if active else "surface-2"),
        alignment=ft.Alignment(0, 0),
        animate=snappy(),
    )


def hover_surface(
    container: ft.Container,
    bg: str | None = "surface",
    hover_bg: str = "surface-2",
    border: str | None = "line",
    hover_border: str = "line-strong",
) -> ft.Container:
    """给可点的白色表面加悬停：底色 → surface-2，描边 → line-strong（snappy()）。"""
    container.animate = snappy()

    def _on_hover(e: ft.ControlEvent) -> None:
        on = e.data in (True, "true")
        if bg is not None:
            container.bgcolor = c(hover_bg if on else bg)
        if border is not None:
            container.border = ft.Border.all(1, c(hover_border if on else border))
        container.update()

    container.on_hover = _on_hover
    return container


def empty_state(icon: str, title: str, body: str = "") -> ft.Control:
    """空状态：44px surface-2 圆 + 20px 图标 + title + body，居中。"""
    controls: list[ft.Control] = [
        ft.Container(
            content=ft.Icon(icon, size=20, color=c("ink-2", "fg")),
            width=44, height=44, border_radius=22, bgcolor=c("surface-2"),
            alignment=ft.Alignment(0, 0),
        ),
        text(title, "title"),
    ]
    if body:
        controls.append(text(body, "small", text_align=ft.TextAlign.CENTER))
    return ft.Column(
        controls=controls, spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
    )


# ── 输入框 ───────────────────────────────────────────────────────────
def field_style() -> dict:
    """TextField / Dropdown 共用的外观参数：白底、1px line、圆角 10，聚焦描边 accent。"""
    return dict(
        bgcolor=c("surface"),
        filled=True,
        fill_color=c("surface"),
        border_radius=R_INPUT,
        border_color=c("line"),
        border_width=1,
        focused_border_color=c("accent"),
        focused_border_width=1.5,
        text_style=ft.TextStyle(size=13.5, color=c("ink", "fg"), font_family=FONT),
        hint_style=ft.TextStyle(size=13.5, color=c("ink-3", "fg"), font_family=FONT),
        label_style=ft.TextStyle(size=12, color=c("ink-2", "fg"), font_family=FONT),
    )


def text_field(value: str = "", hint: str = "", **kwargs) -> ft.TextField:
    opts = field_style()
    opts.update(
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=13),
        dense=True,
        text_size=13.5,
        cursor_color=c("ink"),
        selection_color=ft.Colors.with_opacity(0.3, c("accent")),
    )
    if kwargs.get("prefix_icon"):
        # 默认前缀图标占 48×48，会把输入框撑高
        opts["prefix_icon_size_constraints"] = ft.BoxConstraints(min_width=36, min_height=36)
    opts.update(kwargs)
    return ft.TextField(value=value, hint_text=hint, **opts)


# ── 分段标签页 ───────────────────────────────────────────────────────
class Segmented(ft.Container):
    """分段标签页：白色胶囊轨道 + 墨黑胶囊指示条。

    指示条按规范的「两弹簧拉伸」近似：先用短时长把指示条拉长到同时覆盖新旧两个
    标签（前沿先到），稍后再用长时长把后沿收到新标签上。
    """

    PAD = 3
    GAP = 2
    HEIGHT = 34

    def __init__(
        self,
        options: list[tuple[str, str]],
        value: str,
        on_change: Callable[[str], None] | None = None,
        size: float = 13,
        fill_width: float | None = None,
    ) -> None:
        """fill_width：给定总宽时按比例拉伸各标签铺满（如参数面板里整行宽度）。"""
        self.value = value
        self._options = options
        self._on_change = on_change
        self._size = size
        self._widths = [max(44.0, text_width(label, size) + 26) for _, label in options]
        if fill_width:
            avail = fill_width - 2 - 2 * self.PAD - self.GAP * (len(options) - 1)
            scale = avail / sum(self._widths)
            self._widths = [w * scale for w in self._widths]
        lefts, x = [], float(self.PAD)
        for w in self._widths:
            lefts.append(x)
            x += w + self.GAP
        self._lefts = lefts
        total = x - self.GAP + self.PAD
        idx = self._index(value)
        h = self.HEIGHT - 2 * self.PAD
        self._indicator = ft.Container(
            left=lefts[idx], top=self.PAD, width=self._widths[idx], height=h,
            bgcolor=c("ink"), border_radius=h / 2,
            animate_position=default(), animate_size=default(),
        )
        self._labels: list[ft.Text] = []
        tabs: list[ft.Control] = []
        for i, (val, label) in enumerate(options):
            lbl = ft.Text(
                label, size=size, weight=ft.FontWeight.W_500, font_family=FONT,
                color=c("on-ink" if i == idx else "ink-2", "fg"),
                text_align=ft.TextAlign.CENTER, no_wrap=True,
            )
            self._labels.append(lbl)
            tabs.append(ft.Container(
                content=lbl, left=lefts[i], top=self.PAD, width=self._widths[i], height=h,
                alignment=ft.Alignment(0, 0), border_radius=h / 2,
                on_click=lambda _, v=val: self.select(v),
            ))
        super().__init__(
            content=ft.Stack(controls=[self._indicator, *tabs], width=total, height=self.HEIGHT),
            width=total + 2, height=self.HEIGHT + 2,
            bgcolor=c("surface"),
            border=ft.Border.all(1, c("line")),
            border_radius=(self.HEIGHT + 2) / 2,
        )

    def _index(self, value: str) -> int:
        for i, (v, _) in enumerate(self._options):
            if v == value:
                return i
        return 0

    def select(self, value: str, notify: bool = True) -> None:
        if value == self.value:
            return
        old, new = self._index(self.value), self._index(value)
        self.value = value
        for i, lbl in enumerate(self._labels):
            lbl.color = c("on-ink" if i == new else "ink-2", "fg")
        try:
            self.page.run_task(self._stretch_to, old, new)
        except RuntimeError:
            self._indicator.left, self._indicator.width = self._lefts[new], self._widths[new]
        if notify and self._on_change:
            self._on_change(value)

    async def _stretch_to(self, old: int, new: int) -> None:
        ind = self._indicator
        lo, hi = min(old, new), max(old, new)
        left, right = self._lefts[lo], self._lefts[hi] + self._widths[hi]
        # 前沿先到：拉长到覆盖新旧两个标签
        ind.animate_position, ind.animate_size = lead(), lead()
        ind.left, ind.width = left, right - left
        self.update()
        await asyncio.sleep(0.12)
        # 后沿跟上：收到新标签
        ind.animate_position, ind.animate_size = trail(), trail()
        ind.left, ind.width = self._lefts[new], self._widths[new]
        self.update()

    @property
    def natural_width(self) -> float:
        return self.width or 0


# ── 会变形的主按钮 ───────────────────────────────────────────────────
class MorphButton(ft.Container):
    """主按钮 → 加载 → 对勾 / 错误，始终是同一个形状。

    加载时宽度收成圆（宽 = 高），里面换成转圈；成功时圆里出现对勾，
    片刻后展开回按钮；失败时展开回全宽、底色变 danger 并显示错误文字，1.8s 后复原。
    内容在 AnimatedSwitcher 里淡入淡出切换，不会新旧叠在一起。
    """

    def __init__(
        self,
        on_click: Callable,
        label: str = "",
        icon: str | None = ft.Icons.PLAY_ARROW_ROUNDED,
        full_width: float | None = 278,
        height: float = H_PRIMARY,
    ) -> None:
        self._label = label
        self._icon = icon
        self._enabled = True
        self._state = "idle"
        self._seq = 0
        self._height = height
        self._full_width = full_width
        self._switcher = ft.AnimatedSwitcher(
            content=self._label_row(),
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=170,
            reverse_duration=110,
            switch_in_curve=ft.AnimationCurve.EASE_OUT_CUBIC,
            switch_out_curve=ft.AnimationCurve.EASE_OUT_CUBIC,
        )
        super().__init__(
            content=self._switcher,
            width=full_width,
            height=height,
            bgcolor=c("ink"),
            border_radius=R_PRIMARY,
            alignment=ft.Alignment(0, 0),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            on_click=self._clicked,
            on_hover=self._hover,
            animate=smooth(),
            animate_opacity=snappy(),
        )
        self._on_click = on_click

    # 宽屏 / 窄屏切换时由页面设置
    @property
    def full_width(self) -> float | None:
        return self._full_width

    @full_width.setter
    def full_width(self, value: float | None) -> None:
        self._full_width = value
        if self._state in ("idle", "error"):
            self.width = value

    def _label_row(self) -> ft.Control:
        controls: list[ft.Control] = []
        if self._icon:
            controls.append(ft.Icon(self._icon, color=c("on-ink", "fg"), size=16))
        controls.append(ft.Text(self._label, size=13.5, weight=ft.FontWeight.W_500,
                                color=c("on-ink", "fg"), font_family=FONT, no_wrap=True))
        return ft.Row(controls=controls, spacing=6, tight=True,
                      alignment=ft.MainAxisAlignment.CENTER,
                      vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _hover(self, e: ft.ControlEvent) -> None:
        if self._state != "idle" or not self._enabled:
            return
        self.bgcolor = c("ink-hover") if e.data in (True, "true") else c("ink")
        self.update()

    def _clicked(self, e) -> None:
        if self._state == "idle" and not self.disabled:
            self._on_click(e)

    def set_label(self, label: str, enabled: bool = True) -> None:
        self._label = label
        self._enabled = enabled
        self.opacity = 1.0 if enabled else 0.4
        if self._state == "idle":
            self._switcher.content = self._label_row()

    def _safe_update(self) -> bool:
        try:
            self.update()
            return True
        except RuntimeError:
            return False

    def morph_idle(self) -> None:
        self._seq += 1
        self._state = "idle"
        self.width, self.border_radius = self._full_width, R_PRIMARY
        self.bgcolor = c("ink")
        self._switcher.content = self._label_row()
        self._safe_update()

    def morph_loading(self) -> None:
        self._seq += 1
        self._state = "loading"
        self.opacity = 1.0
        self.width, self.border_radius = self._height, self._height / 2
        self.bgcolor = c("ink")
        self._switcher.content = ft.ProgressRing(
            width=16, height=16, stroke_width=1.75, color=c("on-ink", "fg"),
            bgcolor=ft.Colors.with_opacity(0.22, c("on-ink", "fg")),
        )
        self._safe_update()

    def morph_result(self, ok: bool, error: str = "") -> None:
        self._seq += 1
        seq = self._seq
        if ok:
            self._state = "success"
            self.width, self.border_radius = self._height, self._height / 2
            self.bgcolor = c("accent")
            self._switcher.content = ft.Icon(ft.Icons.CHECK_ROUNDED, color="#FFFFFF", size=18)
            hold = 1.2
        else:
            self._state = "error"
            self.width, self.border_radius = self._full_width, R_PRIMARY
            self.bgcolor = c("danger")
            self._switcher.content = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color="#FFFFFF", size=16),
                    ft.Text(error or "处理失败", size=13.5, weight=ft.FontWeight.W_500,
                            color="#FFFFFF", font_family=FONT, no_wrap=True),
                ],
                spacing=6, tight=True, alignment=ft.MainAxisAlignment.CENTER,
            )
            hold = 1.8
        if not self._safe_update():
            return

        async def _back() -> None:
            await asyncio.sleep(hold)
            if seq == self._seq:
                self.morph_idle()

        try:
            self.page.run_task(_back)
        except RuntimeError:
            pass


# ── 浮层确认面板（替代系统对话框）─────────────────────────────────────
def confirm(
    page: ft.Page,
    title: str,
    body: str = "",
    confirm_label: str = "确定",
    on_confirm: Callable[[], None] | None = None,
    danger: bool = False,
    cancel_label: str = "取消",
) -> None:
    """窗口内确认面板：暖黑遮罩淡入，面板从 96% 缩放淡入；Esc、点遮罩、取消都能关。"""
    prev_key = page.on_keyboard_event

    async def _close_async() -> None:
        scrim.opacity = 0
        panel.opacity, panel.scale = 0, 0.96
        page.on_keyboard_event = prev_key
        page.update()
        await asyncio.sleep(0.2)
        if host in page.overlay:
            page.overlay.remove(host)
            page.update()

    def close(_=None) -> None:
        page.run_task(_close_async)

    def ok(_=None) -> None:
        close()
        if on_confirm:
            on_confirm()

    def on_key(e: ft.KeyboardEvent) -> None:
        if e.key == "Escape":
            close()
        elif prev_key:
            prev_key(e)

    scrim = ft.Container(
        bgcolor=ft.Colors.with_opacity(0.26, c("scrim")),
        left=0, top=0, right=0, bottom=0,
        opacity=0, animate_opacity=snappy(),
        on_click=close,
    )
    panel = card(
        ft.Column(
            controls=[
                ft.Row(
                    controls=[text(title, "title", expand=True),
                              icon_button(ft.Icons.CLOSE_OUTLINED, close, size=32)],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                *([text(body, "small")] if body else []),
                ft.Container(height=4),
                ft.Row(
                    controls=[
                        button(cancel_label, close, kind="secondary"),
                        button(confirm_label, ok, kind="danger" if danger else "primary"),
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=10,
            tight=True,
        ),
        padding=ft.Padding.only(left=20, right=12, top=12, bottom=16),
        width=380,
        opacity=0, scale=0.96,
        animate_opacity=snappy(), animate_scale=smooth(),
    )
    host = ft.Stack(
        controls=[
            scrim,
            ft.Container(content=panel, alignment=ft.Alignment(0, 0), left=0, top=0, right=0, bottom=0),
        ],
        left=0, top=0, right=0, bottom=0,
    )
    page.overlay.append(host)
    page.on_keyboard_event = on_key
    page.update()

    async def _open() -> None:
        await asyncio.sleep(0.016)
        scrim.opacity = 1
        panel.opacity, panel.scale = 1, 1
        page.update()

    page.run_task(_open)
