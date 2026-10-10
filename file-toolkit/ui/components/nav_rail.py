"""
侧边导航栏 — 暖灰黑白风格

规格：
  宽度 232，canvas 底色，无阴影；右侧 1px line 分隔
  品牌区：32px 应用图标，标题 title 字号，副标题 small
  导航项：36 高、圆角 9；选中指示是一块墨黑胶囊，切换时在项之间滑动
          （同一个形状移动，不是每项各自变色），未选中项悬停 surface-3
  底部：问题反馈、设置入口
"""
import flet as ft

from ui import style as s
from ui.palette import c

# 导航项配置：(label, route, icon_outline, icon_selected)
_NAV_ITEMS = [
    ("首页",      "/",        ft.Icons.HOME_OUTLINED,          ft.Icons.HOME_OUTLINED),
    ("AI 智能任务", "/ai",    ft.Icons.AUTO_AWESOME_OUTLINED,  ft.Icons.AUTO_AWESOME_OUTLINED),
    ("提示词出图", "/prompt-image", ft.Icons.AUTO_FIX_HIGH_OUTLINED, ft.Icons.AUTO_FIX_HIGH_OUTLINED),
    ("PDF工具",   "/pdf",     ft.Icons.PICTURE_AS_PDF_OUTLINED, ft.Icons.PICTURE_AS_PDF_OUTLINED),
    ("图片工具",  "/image",   ft.Icons.IMAGE_OUTLINED,          ft.Icons.IMAGE_OUTLINED),
    ("音视频工具", "/media",  ft.Icons.MOVIE_OUTLINED,          ft.Icons.MOVIE_OUTLINED),
    ("压缩解压",  "/archive", ft.Icons.FOLDER_ZIP_OUTLINED,     ft.Icons.FOLDER_ZIP_OUTLINED),
    ("OCR识别",   "/ocr",     ft.Icons.DOCUMENT_SCANNER_OUTLINED, ft.Icons.DOCUMENT_SCANNER_OUTLINED),
    ("最近操作",  "/history", ft.Icons.HISTORY_OUTLINED,                 ft.Icons.HISTORY_OUTLINED),
]

_ITEM_H = 36
_GAP = 2
_WIDTH = 232
_PAD = 12


class NavRail(ft.Container):
    """
    自定义侧边导航栏。
    on_navigate: 路由跳转回调。
    """

    def __init__(self, on_navigate: callable) -> None:
        self._on_navigate = on_navigate
        self._selected_index = 0
        self._nav_item_refs: list[ft.Container] = []

        super().__init__(
            width=_WIDTH,
            expand_loose=True,
            bgcolor=c("canvas"),
            border=ft.Border.only(right=ft.BorderSide(1, c("line"))),
            content=ft.Column(
                controls=[
                    self._build_logo(),
                    self._build_nav_list(),
                    self._build_footer(),
                ],
                spacing=0,
                expand=True,
            ),
            padding=ft.Padding.only(left=_PAD, right=_PAD, top=16, bottom=14),
        )

    # ── 品牌区 ───────────────────────────────────────────────────────────
    def _build_logo(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    # 应用图标（assets/icon.png，与安装包图标同一张）
                    ft.Image(src="icon.png", width=32, height=32,
                             filter_quality=ft.FilterQuality.HIGH),
                    ft.Column(
                        controls=[
                            s.text("文件全能王", "title"),
                            s.text("一个软件，搞定所有文件", "caption"),
                        ],
                        spacing=1,
                        tight=True,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(left=6, bottom=22, top=2),
        )

    # ── 导航列表 ─────────────────────────────────────────────────────────
    def _build_nav_list(self) -> ft.Control:
        self._nav_item_refs.clear()
        self._indicator = ft.Container(
            left=0, right=0, top=0, height=_ITEM_H,
            bgcolor=c("ink"), border_radius=s.R_BUTTON,
            animate_position=s.default(), animate_opacity=s.snappy(),
        )
        items: list[ft.Control] = []
        for i, (label, route, icon, _sel) in enumerate(_NAV_ITEMS):
            item = self._build_nav_item(i, label, route, icon)
            self._nav_item_refs.append(item)
            items.append(item)
        self._place_indicator(animate=False)

        return ft.Container(
            content=ft.Stack(
                controls=[self._indicator, *items],
                height=len(_NAV_ITEMS) * (_ITEM_H + _GAP),
            ),
            expand=True,
        )

    def _build_nav_item(self, index: int, label: str, route: str, icon: str) -> ft.Container:
        selected = index == self._selected_index
        fg = c("on-ink" if selected else "ink-2", "fg")
        item = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color=fg, size=16),
                    ft.Text(label, size=13, color=fg, font_family=s.FONT, weight=ft.FontWeight.W_500),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            left=0, right=0, top=index * (_ITEM_H + _GAP), height=_ITEM_H,
            border_radius=s.R_BUTTON,
            padding=ft.Padding.symmetric(horizontal=12),
            on_click=lambda e, r=route: self._on_navigate(r),
            on_hover=lambda e, i=index: self._on_item_hover(i, e),
            animate=s.snappy(),
            data=index,
        )
        return item

    def _on_item_hover(self, index: int, e: ft.ControlEvent) -> None:
        if index == self._selected_index:
            return
        item = self._nav_item_refs[index]
        on = e.data in (True, "true")
        item.bgcolor = ft.Colors.with_opacity(0.75, c("surface-3")) if on else None
        row: ft.Row = item.content
        row.controls[0].color = row.controls[1].color = c("ink" if on else "ink-2", "fg")
        item.update()

    def _place_indicator(self, animate: bool = True) -> None:
        idx = self._selected_index
        self._indicator.animate_position = s.default() if animate else None
        if 0 <= idx < len(_NAV_ITEMS):
            self._indicator.top = idx * (_ITEM_H + _GAP)
            self._indicator.opacity = 1
        else:
            self._indicator.opacity = 0

    # ── 底部 ─────────────────────────────────────────────────────────────
    def _build_footer(self) -> ft.Control:
        feedback = self._footer_item(ft.Icons.FEEDBACK_OUTLINED, "问题反馈", "/feedback")
        settings = self._footer_item(ft.Icons.SETTINGS_OUTLINED, "设置", "/settings",
                                     trailing=s.text("本地处理", "caption"))
        return ft.Container(
            content=ft.Column(controls=[feedback, settings], spacing=_GAP),
            padding=ft.Padding.only(top=8),
            border=ft.Border.only(top=ft.BorderSide(1, c("line"))),
        )

    def _footer_item(self, icon: str, label: str, route: str,
                     trailing: ft.Control | None = None) -> ft.Container:
        controls: list[ft.Control] = [
            ft.Icon(icon, color=c("ink-2", "fg"), size=16),
            s.text(label, "label", "ink-2", expand=True),
        ]
        if trailing is not None:
            controls.append(trailing)
        item = ft.Container(
            content=ft.Row(
                controls=controls,
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=_ITEM_H,
            padding=ft.Padding.symmetric(horizontal=12),
            border_radius=s.R_BUTTON,
            on_click=lambda e: self._on_navigate(route),
            animate=s.snappy(),
        )
        item.on_hover = lambda e: self._footer_hover(item, e)
        return item

    @staticmethod
    def _footer_hover(item: ft.Container, e: ft.ControlEvent) -> None:
        on = e.data in (True, "true")
        item.bgcolor = ft.Colors.with_opacity(0.75, c("surface-3")) if on else None
        item.update()

    # ── 公共方法 ─────────────────────────────────────────────────────────
    def sync_selected(self, route: str) -> None:
        """根据当前路由同步导航栏高亮；路由不属于任何导航项（如 /settings）时全部取消高亮。"""
        new_index = -1
        for i, (_label, r, _icon, _sel_icon) in enumerate(_NAV_ITEMS):
            if route == r or (r != "/" and route.startswith(r + "/")):
                new_index = i
                break

        if new_index == self._selected_index:
            return

        old_index = self._selected_index
        was_hidden = not (0 <= old_index < len(_NAV_ITEMS))
        self._selected_index = new_index
        if 0 <= old_index < len(self._nav_item_refs):
            self._style_item(old_index, selected=False)
        if 0 <= new_index < len(self._nav_item_refs):
            self._style_item(new_index, selected=True)
        # 从无选中状态出现时直接到位再淡入，不从别处滑过来
        self._place_indicator(animate=not was_hidden)

    def _style_item(self, index: int, selected: bool) -> None:
        item = self._nav_item_refs[index]
        row: ft.Row = item.content
        fg = c("on-ink" if selected else "ink-2", "fg")
        row.controls[0].color = fg
        row.controls[1].color = fg
        item.bgcolor = None
