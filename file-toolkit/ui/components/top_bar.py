"""
共享顶部栏 — 全局功能搜索 + 设置入口

规格：
  高度：80px，白底，底部细阴影
  搜索框：pill 形，输入功能名/关键词（如「压缩」「mp3」「水印」），回车或点击结果跳转
  右侧：设置按钮

`leading` 可放页面自己的控件（如最近操作页的筛选框），位于搜索框左侧。
"""
import flet as ft

from ui.features import Feature, search_features
from ui.palette import c


class TopBar(ft.Container):
    """顶部栏：全局搜索 + 设置"""

    def __init__(self, page: ft.Page, leading: ft.Control | None = None) -> None:
        self._page = page
        self._results: list[Feature] = []
        self._search = ft.SearchBar(
            bar_hint_text="搜索功能，如：压缩、转 Word、水印",
            view_hint_text="输入功能名或关键词，回车打开第一个结果",
            bar_leading=ft.Icon(ft.Icons.SEARCH, color=c("#94a3b8", "fg"), size=18),
            bar_bgcolor=c("#f8fafc"),
            bar_elevation=0,
            bar_border_side=ft.BorderSide(1, c("#e2e8f0")),
            bar_text_style=ft.TextStyle(size=13, color=c("#162f50", "fg"), font_family="42dot Sans"),
            bar_hint_text_style=ft.TextStyle(size=13, color=c("#94a3b8", "fg"), font_family="42dot Sans"),
            bar_size_constraints=ft.BoxConstraints(min_height=40, max_height=40),
            view_bgcolor=c("#ffffff"),
            view_elevation=8,
            view_size_constraints=ft.BoxConstraints(max_height=420),
            view_hint_text_style=ft.TextStyle(size=13, color=c("#94a3b8", "fg"), font_family="42dot Sans"),
            divider_color=c("#e2e8f0"),
            on_change=self._on_change,
            on_submit=self._on_submit,
            on_tap=self._on_tap,
            width=320,
        )
        self._refresh_results("")

        super().__init__(
            height=80,
            bgcolor=c("#ffffff"),
            shadow=ft.BoxShadow(
                blur_radius=2,
                color=ft.Colors.with_opacity(0.05, c("#000000", "fg")),
                offset=ft.Offset(0, 1),
            ),
            padding=ft.padding.only(left=32, right=24),
            content=ft.Row(
                controls=[
                    leading or ft.Container(),
                    ft.Container(expand=True),
                    self._search,
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS_OUTLINED,
                        icon_color=c("#475569", "fg"),
                        icon_size=20,
                        tooltip="设置",
                        on_click=lambda _: self._page.go("/settings"),
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    # ── 搜索 ─────────────────────────────────────────────────────────────
    def _refresh_results(self, query: str) -> None:
        self._results = search_features(query)
        if self._results:
            self._search.controls = [self._result_tile(f) for f in self._results]
        else:
            self._search.controls = [
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.SEARCH_OFF, color=c("#94a3b8", "fg")),
                    title=ft.Text("没有找到相关功能", size=13, color=c("#455c7f", "fg")),
                    subtitle=ft.Text("换个关键词试试，例如「合并」「mp4」「解压」", size=11, color=c("#94a3b8", "fg")),
                )
            ]

    def _result_tile(self, feature: Feature) -> ft.Control:
        return ft.ListTile(
            leading=ft.Container(
                content=ft.Icon(feature.icon, color=c("#005f98", "fg"), size=18),
                width=32,
                height=32,
                bgcolor=c("#e0f0ff"),
                border_radius=8,
                alignment=ft.Alignment(0, 0),
            ),
            title=ft.Text(feature.title, size=13, color=c("#162f50", "fg"), font_family="42dot Sans"),
            trailing=ft.Text(feature.group, size=11, color=c("#94a3b8", "fg")),
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
