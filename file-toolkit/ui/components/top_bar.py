"""
共享顶部栏 — 全局功能搜索 + 设置入口

规格：
  高度：64，canvas 底色，无阴影
  搜索框：白底 1px line、圆角 10，Ctrl+K 打开；输入功能名/关键词（如「压缩」「mp3」「水印」），回车或点击结果跳转
  右侧：设置按钮

`leading` 可放页面自己的控件（如最近操作页的筛选框），位于搜索框左侧。
"""
import flet as ft

from ui import style as s
from ui.features import Feature, search_features
from ui.palette import c


class TopBar(ft.Container):
    """顶部栏：全局搜索（Ctrl+K）+ 设置"""

    def __init__(self, page: ft.Page, leading: ft.Control | None = None) -> None:
        self._page = page
        self._results: list[Feature] = []
        hint_style = ft.TextStyle(size=13, color=c("ink-3", "fg"), font_family=s.FONT)
        self._search = ft.SearchBar(
            bar_hint_text="搜索功能，如：压缩、水印",
            view_hint_text="输入功能名或关键词，回车打开第一个结果",
            bar_leading=ft.Icon(ft.Icons.SEARCH_OUTLINED, color=c("ink-3", "fg"), size=16),
            bar_trailing=[ft.Container(
                content=ft.Text("Ctrl K", size=11, color=c("ink-3", "fg"), font_family=s.MONO),
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                border=ft.border.all(1, c("line")), border_radius=6,
            )],
            bar_bgcolor=c("surface"),
            bar_overlay_color=ft.Colors.TRANSPARENT,
            bar_shadow_color=ft.Colors.TRANSPARENT,
            bar_elevation=0,
            bar_border_side=ft.BorderSide(1, c("line")),
            bar_shape=ft.RoundedRectangleBorder(radius=s.R_INPUT),
            bar_padding=ft.padding.symmetric(horizontal=12),
            bar_text_style=ft.TextStyle(size=13, color=c("ink", "fg"), font_family=s.FONT),
            bar_hint_text_style=hint_style,
            bar_size_constraints=ft.BoxConstraints(min_height=36, max_height=36),
            view_bgcolor=c("surface"),
            view_elevation=0,
            view_side=ft.BorderSide(1, c("line")),
            view_shape=ft.RoundedRectangleBorder(radius=s.R_PANEL),
            view_size_constraints=ft.BoxConstraints(max_height=420, min_width=560, max_width=560),
            view_header_text_style=ft.TextStyle(size=13.5, color=c("ink", "fg"), font_family=s.FONT),
            view_hint_text_style=hint_style,
            view_header_height=44,
            divider_color=c("line"),
            on_change=self._on_change,
            on_submit=self._on_submit,
            on_tap=self._on_tap,
            width=300,
        )
        self._refresh_results("")

        super().__init__(
            height=64,
            padding=ft.padding.only(left=s.PAGE_X, right=s.PAGE_X - 4),
            content=ft.Row(
                controls=[
                    leading or ft.Container(),
                    ft.Container(expand=True),
                    self._search,
                    s.icon_button(ft.Icons.SETTINGS_OUTLINED, lambda _: self._page.go("/settings"),
                                  tooltip="设置"),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def did_mount(self) -> None:
        self._prev_key_handler = self._page.on_keyboard_event
        self._page.on_keyboard_event = self._on_key

    def will_unmount(self) -> None:
        if self._page.on_keyboard_event == self._on_key:
            self._page.on_keyboard_event = getattr(self, "_prev_key_handler", None)

    def _on_key(self, e: ft.KeyboardEvent) -> None:
        if e.key.upper() == "K" and (e.ctrl or e.meta):
            self._page.run_task(self._search.open_view)

    # ── 搜索 ─────────────────────────────────────────────────────────────
    def _refresh_results(self, query: str) -> None:
        self._results = search_features(query)
        if self._results:
            self._search.controls = [self._result_tile(f) for f in self._results]
        else:
            self._search.controls = [
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.SEARCH_OFF_OUTLINED, color=c("ink-3", "fg"), size=16),
                    title=s.text("没有找到相关功能", "body-medium"),
                    subtitle=s.text("换个关键词试试，例如「合并」「mp4」「解压」", "small"),
                )
            ]

    def _result_tile(self, feature: Feature) -> ft.Control:
        return ft.ListTile(
            leading=ft.Icon(feature.icon, color=c("ink-2", "fg"), size=16),
            title=s.text(feature.title, "body-medium"),
            trailing=s.text(feature.group, "caption"),
            min_height=44,
            hover_color=c("surface-2"),
            dense=True,
            on_click=lambda _, f=feature: self._page.run_task(self._open, f),
        )

    def _on_change(self, e: ft.ControlEvent) -> None:
        self._refresh_results(e.control.value or "")
        self._search.update()

    def _on_tap(self, _) -> None:
        self._page.run_task(self._search.open_view)

    def _on_submit(self, e: ft.ControlEvent) -> None:
        results = search_features(e.control.value or "")
        if results:
            self._page.run_task(self._open, results[0])

    async def _open(self, feature: Feature) -> None:
        try:
            await self._search.close_view("")
        except Exception:
            pass
        self._page.go(feature.route)
