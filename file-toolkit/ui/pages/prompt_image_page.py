"""提示词出图页 — 选模板 → 填写 / 增强 → 生成 → 预览。

布局（三栏，各自滚动，页面本身不滚动）：
  Header：返回 + 标题 + 「提示词源」管理入口
  ├── 左栏 272px：来源下拉 + 搜索 + 分类 + 模板列表
  ├── 中栏 expand：模板信息 → 变量表单 → 风格增强 → 最终提示词（可手改）
  │                底部固定：尺寸 / 质量 + 生成按钮
  └── 右栏 expand：生成结果（常驻可见）→ 操作按钮 → 最近作品

生成结果放在常驻的右栏里，生成完成后不需要滚动就能看到；
桌面端直接用保存好的本地文件加载预览，Web 端用图片字节。
"""
from __future__ import annotations

import asyncio
import io
import tempfile
import time
from datetime import datetime
from pathlib import Path

import flet as ft

from core.prompt_image import modifiers as mods
from core.prompt_image import sources as src
from core.prompt_image import templates as tpl
from core.prompt_image.option_labels import option_label
from services import prompt_image_service, settings_service
from services import prompt_library_service as lib
from ui import style as s
from ui.components.image_viewer import ImageViewer, ViewerItem
from ui.palette import c
from ui.utils import open_folder, show_toast

_LIST_LIMIT = 300          # 左栏最多渲染的模板数，超出提示用户搜索
_CHIP_CATEGORY_LIMIT = 14  # 分类不超过这个数用标签，否则改用下拉框
_HISTORY_THUMBS = 12
_KEY_LAST_SOURCE = "prompt_image_last_source"
_KEY_LAST_TEMPLATE = "prompt_image_last_template"
_KEY_MODIFIERS = "prompt_image_modifiers"
_REF_EXTS = ("png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff")
_REF_TEMP_DIR = Path(tempfile.gettempdir()) / "file-toolkit-refs"
_FONT = s.FONT


def _txt(value: str, size: float = 12, color: str = "ink-2", **kw) -> ft.Text:
    return ft.Text(value, size=size, color=c(color, "fg"), font_family=_FONT, **kw)


def _dropdown(**kw) -> ft.Dropdown:
    """统一风格的下拉框：白底 1px 描边，聚焦时描边换成强调色。"""
    opts = s.field_style()
    opts.pop("label_style")
    opts.update(dense=True, text_size=13,
                content_padding=ft.padding.symmetric(horizontal=12, vertical=9))
    opts.update(kw)
    return ft.Dropdown(**opts)


def _field(**kw) -> ft.TextField:
    """统一风格的输入框（多行时去掉 dense，留出行高）。"""
    kw.setdefault("text_size", 13)
    if kw.get("multiline"):
        kw.setdefault("dense", False)
        kw.setdefault("content_padding", ft.padding.symmetric(horizontal=12, vertical=10))
    return s.text_field(**kw)


def _card(content: ft.Control, **kw) -> ft.Container:
    return s.card(content, **kw)


def _outlined(icon: str) -> str:
    """模板自带的图标名换成线性版本（有的话），保证全页图标风格一致。"""
    name = getattr(icon, "name", str(icon)).upper()
    if name.endswith(("_OUTLINED", "_OUTLINE")):
        return icon
    return getattr(ft.Icons, f"{name}_OUTLINED", icon)


class PromptImagePage(ft.Column):
    """提示词出图主页面。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._mounted = False

        # ── 状态 ────────────────────────────────────────────────────────
        saved_source = settings_service.get(_KEY_LAST_SOURCE, tpl.BUILTIN_SOURCE)
        valid_sources = {k for k, _ in lib.source_options()}
        self._source: str = saved_source if saved_source in valid_sources else tpl.BUILTIN_SOURCE
        self._category: str = "全部"
        self._keyword: str = ""
        self._templates: list[dict] = []
        self._current: dict | None = None
        self._var_controls: dict[str, ft.Control] = {}
        self._modifiers: list[str] = [
            m for m in settings_service.get(_KEY_MODIFIERS, "").split(",") if m
        ]
        self._manual_prompt = False
        self._generating = False
        self._gen_started = 0.0
        self._last_bytes: bytes | None = None
        self._last_path: Path | None = None
        self._last_prompt = ""
        self._ref_images: list[Path] = []
        self._refresh_seq = 0
        self._gen_job: asyncio.Future | None = None
        self._gen_loop: asyncio.AbstractEventLoop | None = None

        # ── 左栏控件 ────────────────────────────────────────────────────
        self._source_dd = _dropdown(
            value=self._source, options=[], dense=True, border_radius=10, expand=True,
            text_size=13, on_select=self._on_source_change,
        )
        self._search = _field(
            hint="搜索名称 / 标签 / 提示词",
            prefix_icon=ft.Icons.SEARCH_OUTLINED,
            on_change=self._on_search_change,
        )
        self._category_area = ft.Container()
        self._count_text = _txt("", 11, "ink-3")
        self._template_list = ft.ListView(expand=True, spacing=6, padding=ft.padding.only(right=6))

        # ── 中栏控件 ────────────────────────────────────────────────────
        self._tpl_header = ft.Column(spacing=6)
        self._form_area = ft.Column(spacing=12)
        self._ref_title = s.text("参考图", "title", size=14)
        self._ref_badge = _txt("", 11, "ink-3")
        self._ref_hint = _txt("", 11.5, "ink-3")
        self._ref_row = ft.Row(spacing=8, run_spacing=8, wrap=True)
        self._ref_clear = s.button("清空", self._on_clear_refs, kind="ghost", height=26,
                                   visible=False)
        self._modifier_area = ft.Column(spacing=10, visible=bool(self._modifiers))
        self._modifier_toggle_icon = ft.Icon(
            ft.Icons.EXPAND_LESS_OUTLINED if self._modifiers else ft.Icons.EXPAND_MORE_OUTLINED,
            size=18, color=c("ink-3", "fg"),
        )
        self._modifier_count = _txt("", 11, "ink-3")
        self._negative = _field(
            hint="避免出现的内容（可选），如：文字水印、多余手指、模糊",
            on_change=lambda _e: self._schedule_refresh(),
        )
        self._prompt_state = _txt("自动生成", 11, "ink-3")
        self._restore_btn = s.button("恢复自动", self._on_restore_prompt, kind="ghost",
                                     height=26, visible=False)
        self._prompt_field = _field(
            multiline=True, min_lines=4, max_lines=10,
            text_style=ft.TextStyle(color=c("ink", "fg"), size=13, font_family=s.MONO),
            on_change=self._on_prompt_edited,
        )
        self._size_dd = _dropdown(
            value="1024x1024", dense=True, border_radius=10, expand=True, text_size=13,
            options=[
                ft.dropdown.Option("1024x1024", "1:1 方形"),
                ft.dropdown.Option("1024x1536", "2:3 竖版"),
                ft.dropdown.Option("1536x1024", "3:2 横版"),
                ft.dropdown.Option("auto", "自动"),
            ],
        )
        self._quality_dd = _dropdown(
            value="high", dense=True, border_radius=10, expand=True, text_size=13,
            options=[
                ft.dropdown.Option("low", "低 · 快速"),
                ft.dropdown.Option("medium", "中 · 平衡"),
                ft.dropdown.Option("high", "高 · 精细"),
                ft.dropdown.Option("auto", "自动"),
            ],
        )
        self._generate_label = _txt("生成图片", 13.5, "on-ink", weight=ft.FontWeight.W_500)
        self._generate_btn = self._build_generate_button()
        self._config_hint = self._build_config_hint()

        # ── 右栏控件 ────────────────────────────────────────────────────
        self._preview = ft.Container(
            expand=True, border_radius=12, bgcolor=c("surface-2"),
            border=ft.border.all(1, c("line")), alignment=ft.Alignment(0, 0),
            padding=8, animate=s.snappy(),
        )
        self._result_meta = s.text("", "mono", "ink-3", size=11, max_lines=2,
                                 overflow=ft.TextOverflow.ELLIPSIS)
        self._result_actions = ft.Row(spacing=6, run_spacing=6, wrap=True, visible=False)
        self._history_row = ft.Row(spacing=8, run_spacing=8, wrap=True)
        self._history_section = ft.Column(spacing=8)

        self.controls = [self._build_header(), self._build_body()]

        self._show_empty()
        self._render_history()
        self._reload_library(select_id=settings_service.get(_KEY_LAST_TEMPLATE, ""))

    def did_mount(self) -> None:
        self._mounted = True

    def will_unmount(self) -> None:
        self._mounted = False

    def _update(self, *controls: ft.Control) -> None:
        if not self._mounted:
            return
        try:
            for ctrl in controls:
                ctrl.update()
        except RuntimeError:
            pass

    # ═════════════════════════════════════════════════════════════════
    # 布局
    # ═════════════════════════════════════════════════════════════════
    def _build_header(self) -> ft.Control:
        return ft.Container(
            padding=ft.padding.only(left=s.PAGE_X - 8, top=16, right=s.PAGE_X, bottom=14),
            content=ft.Row(
                controls=[
                    s.icon_button(ft.Icons.ARROW_BACK_OUTLINED, lambda _e: self._page.go("/"), "返回首页"),
                    ft.Column(
                        controls=[
                            s.text("提示词出图", "headline"),
                            s.text("挑一个模板，填几个关键词，AI 帮你出图", "small"),
                        ],
                        spacing=2, tight=True,
                    ),
                    ft.Container(expand=True),
                    s.button("提示词源", self._open_source_manager, kind="secondary",
                             icon=ft.Icons.HUB_OUTLINED),
                    s.button("新建模板", lambda _e: self._open_template_editor(), kind="secondary",
                             icon=ft.Icons.ADD_OUTLINED),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _build_body(self) -> ft.Control:
        left = _card(
            ft.Column(
                controls=[
                    ft.Row([self._source_dd], spacing=6),
                    self._search,
                    self._category_area,
                    self._count_text,
                    self._template_list,
                ],
                spacing=10,
                expand=True,
            ),
            width=272, padding=ft.padding.only(left=14, top=14, right=8, bottom=8),
        )

        self._editor_scroll = editor_scroll = ft.Column(
            controls=[
                self._tpl_header,
                self._divider(),
                self._section_title("填写内容", ft.Icons.EDIT_OUTLINED),
                self._form_area,
                self._divider(),
                self._build_ref_section(),
                self._divider(),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TUNE_OUTLINED, size=16, color=c("ink-2", "fg")),
                            s.text("风格增强", "title", size=14),
                            self._modifier_count,
                            ft.Container(expand=True),
                            self._modifier_toggle_icon,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    on_click=self._toggle_modifiers,
                    border_radius=8, padding=ft.padding.symmetric(vertical=4),
                ),
                self._modifier_area,
                self._negative,
                self._divider(),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SUBJECT_OUTLINED, size=16, color=c("ink-2", "fg")),
                        s.text("最终提示词", "title", size=14),
                        self._prompt_state,
                        self._restore_btn,
                        ft.Container(expand=True),
                        s.icon_button(ft.Icons.COPY_ALL_OUTLINED, self._on_copy_prompt, "复制提示词"),
                        s.icon_button(ft.Icons.BOOKMARK_ADD_OUTLINED, self._on_save_as_template,
                                      "存为我的模板"),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self._prompt_field,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        bottom_bar = ft.Container(
            content=ft.Column(
                controls=[
                    self._config_hint,
                    ft.Row(
                        controls=[
                            self._labeled("尺寸", self._size_dd),
                            self._labeled("质量", self._quality_dd),
                        ],
                        spacing=12,
                    ),
                    self._generate_btn,
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=ft.padding.only(top=12),
            border=ft.border.only(top=ft.BorderSide(1, c("line"))),
        )
        middle = _card(
            ft.Column([ft.Container(editor_scroll, expand=True, padding=ft.padding.only(right=8)),
                       bottom_bar], spacing=0, expand=True),
            expand=1, padding=ft.padding.only(left=20, top=16, right=12, bottom=16),
        )

        right = _card(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=16, color=c("ink-2", "fg")),
                            s.text("生成结果", "title", size=14),
                        ],
                        spacing=6,
                    ),
                    self._preview,
                    self._result_meta,
                    self._result_actions,
                    self._history_section,
                ],
                spacing=10,
                expand=True,
            ),
            expand=1, padding=16,
        )

        return ft.Container(
            content=ft.Row(
                controls=[left, middle, right],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            ),
            padding=ft.padding.only(left=s.PAGE_X, right=s.PAGE_X, bottom=s.PAGE_X),
            expand=True,
        )

    def _divider(self) -> ft.Control:
        return ft.Divider(height=1, thickness=1, color=c("line"))

    def _section_title(self, title: str, icon: str) -> ft.Control:
        return ft.Row(
            controls=[ft.Icon(icon, size=16, color=c("ink-2", "fg")),
                      s.text(title, "title", size=14)],
            spacing=6,
        )

    def _labeled(self, label: str, body: ft.Control) -> ft.Control:
        return ft.Column([s.text(label, "caption", "ink-2"), body], spacing=5, expand=True)

    def _small_button(self, label: str, icon: str, on_click, primary: bool = False) -> ft.Control:
        btn = s.button(label, on_click, kind="primary" if primary else "secondary", icon=icon,
                       height=30)
        btn.style.padding = ft.padding.symmetric(horizontal=10)
        btn.style.icon_size = 14
        return btn

    # ═════════════════════════════════════════════════════════════════
    # 左栏：模板库
    # ═════════════════════════════════════════════════════════════════
    def _reload_library(self, select_id: str = "") -> None:
        """来源 / 来源内容变化后重载下拉框、分类与列表。"""
        options = lib.source_options()
        keys = {k for k, _ in options}
        if self._source not in keys:
            self._source = tpl.BUILTIN_SOURCE
        self._source_dd.options = [ft.dropdown.Option(k, label) for k, label in options]
        self._source_dd.value = self._source
        self._templates = lib.templates_for(self._source)
        cats = lib.categories_for(self._templates)
        if self._category not in cats:
            self._category = "全部"
        self._render_categories(cats)
        self._render_list()

        target = None
        if select_id:
            target = lib.find_template(select_id)
        if target is None and self._current is not None:
            target = lib.find_template(self._current["id"])
        if target is None and self._templates:
            target = self._templates[0]
        if target is None:
            target = tpl.TEMPLATES[0]
        if self._current is None or target["id"] != self._current["id"] or select_id:
            self._select_template(target)
        self._update(self._source_dd)

    def _on_source_change(self, e) -> None:
        self._source = e.control.value or tpl.BUILTIN_SOURCE
        settings_service.set(_KEY_LAST_SOURCE, self._source)
        self._category = "全部"
        self._templates = lib.templates_for(self._source)
        self._render_categories(lib.categories_for(self._templates))
        self._render_list()

    def _on_search_change(self, e) -> None:
        self._keyword = (e.control.value or "").strip()
        self._render_list()

    def _render_categories(self, cats: list[str]) -> None:
        if len(cats) <= 2:
            self._category_area.content = None
        elif len(cats) > _CHIP_CATEGORY_LIMIT:
            self._category_area.content = ft.Row([_dropdown(
                value=self._category, expand=True,
                options=[ft.dropdown.Option(cat) for cat in cats],
                on_select=lambda e: self._on_category_change(e.control.value or "全部"),
            )])
        else:
            chips = []
            for cat in cats:
                active = cat == self._category
                chips.append(self._chip(cat, active,
                                        lambda _e, cat=cat: self._on_category_change(cat)))
            self._category_area.content = ft.Row(chips, spacing=6, run_spacing=6, wrap=True)
        self._update(self._category_area)

    def _on_category_change(self, cat: str) -> None:
        self._category = cat
        self._render_categories(lib.categories_for(self._templates))
        self._render_list()

    def _render_list(self) -> None:
        items = tpl.get_templates(self._category, self._keyword, self._templates)
        favs = set(lib.list_favorites())
        self._template_list.controls = [self._template_tile(t, t["id"] in favs)
                                        for t in items[:_LIST_LIMIT]]
        if not items:
            hint = "还没有自己的模板，点右上角「新建模板」，或在提示词旁点书签保存" \
                if self._source == lib.CUSTOM_SOURCE and not self._keyword else "没有匹配的模板"
            self._template_list.controls = [ft.Container(
                content=_txt(hint, 12, "ink-3", text_align=ft.TextAlign.CENTER),
                padding=ft.padding.symmetric(vertical=24, horizontal=8),
                alignment=ft.Alignment(0, 0),
            )]
        count = f"共 {len(items)} 个模板"
        if len(items) > _LIST_LIMIT:
            count += f"，显示前 {_LIST_LIMIT} 个，可搜索缩小范围"
        self._count_text.value = count
        self._update(self._template_list, self._count_text)

    def _template_tile(self, t: dict, favorite: bool) -> ft.Control:
        selected = self._current is not None and self._current["id"] == t["id"]
        icon = getattr(ft.Icons, t.get("icon") or "AUTO_AWESOME", ft.Icons.AUTO_AWESOME_OUTLINED)
        sub = t.get("author") or (lib.source_label(t["source"])
                                  if t.get("source") not in (tpl.BUILTIN_SOURCE, None) else "")
        texts: list[ft.Control] = [
            ft.Row(
                controls=[
                    s.text(t["name"], "label", expand=True,
                           max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Icon(ft.Icons.STAR_ROUNDED, size=13, color=c("ink", "fg"), visible=favorite),
                ],
                spacing=4,
            ),
            _txt(t.get("description", ""), 11.5, "ink-2", max_lines=1,
                 overflow=ft.TextOverflow.ELLIPSIS),
        ]
        if sub:
            texts.append(_txt(sub, 10.5, "ink-3", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
        tile = ft.Container(
            content=ft.Row(
                controls=[
                    s.icon_tile(_outlined(icon), size=32, icon_size=16, active=selected),
                    ft.Column(texts, spacing=1, expand=True, tight=True),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=c("accent-soft") if selected else None,
            border=ft.border.all(1, c("accent") if selected else ft.Colors.TRANSPARENT),
            border_radius=s.R_INPUT,
            padding=ft.padding.symmetric(horizontal=8, vertical=7),
            on_click=lambda _e, t=t: self._select_template(t),
            animate=s.snappy(),
        )
        if not selected:
            tile.on_hover = lambda e, tile=tile: self._tile_hover(tile, e)
        return tile

    @staticmethod
    def _tile_hover(tile: ft.Container, e: ft.ControlEvent) -> None:
        on = e.data in (True, "true")
        tile.bgcolor = c("surface-2") if on else None
        tile.update()

    @staticmethod
    def _chip(label: str, active: bool, on_click) -> ft.Control:
        """可选标签：未选中 surface-2 底 + ink-2 字，选中墨黑实心。"""
        chip = ft.Container(
            content=_txt(label, 12, "on-ink" if active else "ink-2", weight=ft.FontWeight.W_500),
            bgcolor=c("ink") if active else c("surface-2"),
            border=ft.border.all(1, c("ink") if active else c("line")),
            border_radius=999,
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            on_click=on_click,
            animate=s.snappy(),
        )
        if not active:
            def _hover(e: ft.ControlEvent) -> None:
                on = e.data in (True, "true")
                chip.border = ft.border.all(1, c("line-strong") if on else c("line"))
                chip.content.color = c("ink" if on else "ink-2", "fg")
                chip.update()
            chip.on_hover = _hover
        return chip

    # ═════════════════════════════════════════════════════════════════
    # 中栏：模板信息、表单、风格增强、最终提示词
    # ═════════════════════════════════════════════════════════════════
    def _select_template(self, template: dict) -> None:
        self._current = template
        self._manual_prompt = False
        self._var_controls.clear()
        settings_service.set(_KEY_LAST_TEMPLATE, template["id"])
        size = template.get("default_size", "1024x1024")
        if size in [o.key for o in self._size_dd.options]:
            self._size_dd.value = size
        self._render_template_header()
        self._render_form()
        self._render_refs()
        self._render_modifiers()
        self._render_list()
        self._refresh_prompt()
        self._update(self._size_dd)
        if self._mounted:
            self._page.run_task(self._scroll_editor_top)

    async def _scroll_editor_top(self) -> None:
        try:
            await self._editor_scroll.scroll_to(offset=0, duration=150)
        except Exception:
            pass

    def _render_template_header(self) -> None:
        t = self._current
        if not t:
            return
        fav = lib.is_favorite(t["id"])
        icon = getattr(ft.Icons, t.get("icon") or "AUTO_AWESOME", ft.Icons.AUTO_AWESOME_OUTLINED)
        actions: list[ft.Control] = [
            s.icon_button(
                ft.Icons.STAR_ROUNDED if fav else ft.Icons.STAR_BORDER_ROUNDED,
                self._on_toggle_favorite, "取消收藏" if fav else "收藏",
                color="ink" if fav else "ink-3",
            ),
        ]
        if t.get("source") == lib.CUSTOM_SOURCE:
            actions += [
                s.icon_button(ft.Icons.EDIT_OUTLINED,
                              lambda _e: self._open_template_editor(self._current), "编辑模板"),
                s.icon_button(ft.Icons.DELETE_OUTLINE, self._on_delete_custom, "删除模板",
                              color="danger"),
            ]
        credit: list[ft.Control] = [
            self._badge(t.get("category") or "未分类"),
            self._badge(lib.source_label(t.get("source") or tpl.BUILTIN_SOURCE)),
        ]
        if t.get("author"):
            credit.append(_txt(f"作者 {t['author']}", 11, "ink-3"))
        if t.get("license"):
            credit.append(_txt(t["license"], 11, "ink-3"))
        if t.get("link"):
            link = ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_NEW_OUTLINED, size=12, color=c("ink-2", "fg")),
                                _txt("原文", 11, "ink-2", weight=ft.FontWeight.W_500)],
                               spacing=3, tight=True),
                on_click=lambda _e, url=t["link"]: self._launch(url), border_radius=6,
                padding=ft.padding.symmetric(horizontal=5, vertical=2),
            )
            credit.append(s.hover_surface(link, bg=None, hover_bg="surface-2", border=None))
        self._tpl_header.controls = [
            ft.Row(
                controls=[
                    s.icon_tile(_outlined(icon), size=42, icon_size=20),
                    ft.Column(
                        controls=[
                            s.text(t["name"], "title", size=17,
                                   max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            _txt(t.get("description", ""), 12, "ink-2", max_lines=2,
                                 overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                        spacing=2, expand=True, tight=True,
                    ),
                    *actions,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(credit, spacing=8, wrap=True, run_spacing=4,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ]
        self._update(self._tpl_header)

    def _badge(self, text: str) -> ft.Control:
        return ft.Container(
            content=_txt(text, 10.5, "ink-2", weight=ft.FontWeight.W_500),
            bgcolor=c("surface-2"), border=ft.border.all(1, c("line")), border_radius=999,
            padding=ft.padding.symmetric(horizontal=8, vertical=1),
        )

    def _render_form(self) -> None:
        self._form_area.controls.clear()
        t = self._current
        if not t:
            return
        variables = t.get("variables") or []
        if not variables:
            self._form_area.controls.append(_txt(
                "这个提示词没有需要填写的内容，可以直接生成，或在下方「最终提示词」里修改。",
                12, "ink-3"))
        for var in variables:
            name = var["name"]
            var_type = var.get("type", "text")
            default = var.get("default", "")
            if var_type == "select" and var.get("options"):
                ctrl: ft.Control = _dropdown(
                    value=default or var["options"][0], dense=True, text_size=13,
                    options=[ft.dropdown.Option(o, option_label(o)) for o in var["options"]],
                    expand=True,
                    on_select=lambda _e: self._refresh_prompt(),
                )
            else:
                multiline = var_type == "textarea"
                ctrl = _field(
                    value=default, hint=var.get("placeholder", ""),
                    multiline=multiline, min_lines=4 if multiline else None,
                    max_lines=10 if multiline else 1,
                    on_change=lambda _e: self._schedule_refresh(),
                )
            self._var_controls[name] = ctrl
            label = var.get("label") or name
            self._form_area.controls.append(ft.Column(
                controls=[
                    ft.Row([_txt(label, 12, "ink-2", weight=ft.FontWeight.W_500),
                            _txt("*", 12, "danger", visible=bool(var.get("required")))], spacing=2),
                    ctrl,
                ],
                spacing=4,
            ))
        self._update(self._form_area)

    # ── 参考图 ───────────────────────────────────────────────────────
    def _build_ref_section(self) -> ft.Control:
        return ft.Container(
            key="refs",
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, size=16,
                                    color=c("ink-2", "fg")),
                            self._ref_title,
                            self._ref_badge,
                            ft.Container(expand=True),
                            self._ref_clear,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self._ref_hint,
                    self._ref_row,
                ],
                spacing=8,
            ),
        )

    def _render_refs(self) -> None:
        spec = tpl.reference_spec(self._current)
        required = bool(spec and not spec["inferred"])
        limit = spec["max"] if required else tpl.MAX_REFERENCE_IMAGES
        count = len(self._ref_images)
        self._ref_title.value = "参考图" if required else "参考图（可选）"
        self._ref_badge.value = f"{count} / {limit}" if count or required else ""
        self._ref_badge.color = c("danger" if required and count < spec["min"] else "ink-3", "fg")
        if required:
            self._ref_hint.value = spec["hint"]
            self._ref_hint.color = c("ink-2", "fg")
        elif spec:
            self._ref_hint.value = spec["hint"]
            self._ref_hint.color = c("accent", "fg")
        else:
            self._ref_hint.value = "上传照片后，AI 会参考其中的人物 / 物体来生成，例如两张单人照合成合照"
            self._ref_hint.color = c("ink-3", "fg")
        tiles: list[ft.Control] = [self._ref_thumb(i, p) for i, p in enumerate(self._ref_images)]
        if count < limit:
            tiles.append(self._ref_add_tile())
        self._ref_row.controls = tiles
        self._ref_clear.visible = count > 1
        self._update(self._ref_title, self._ref_badge, self._ref_hint, self._ref_row,
                     self._ref_clear)

    def _ref_thumb(self, index: int, path: Path) -> ft.Control:
        return ft.Stack(
            controls=[
                ft.Container(
                    content=ft.Image(src=self._thumb_source(path), width=76, height=76,
                                     fit=ft.BoxFit.COVER, border_radius=s.R_INPUT,
                                     cache_width=152,
                                     error_content=ft.Icon(ft.Icons.BROKEN_IMAGE_OUTLINED,
                                                           size=18, color=c("danger", "fg"))),
                    width=76, height=76, border_radius=s.R_INPUT, bgcolor=c("surface-2"),
                    border=ft.border.all(1, c("line")),
                    tooltip=path.name,
                ),
                ft.Container(
                    content=_txt(f"{index + 1}", 10, "on-ink", weight=ft.FontWeight.W_500),
                    bgcolor=ft.Colors.with_opacity(0.72, c("ink")), border_radius=999,
                    padding=ft.padding.symmetric(horizontal=6, vertical=1), left=5, bottom=5,
                ),
                ft.Container(
                    content=ft.Icon(ft.Icons.CLOSE_ROUNDED, size=12, color=c("on-ink", "fg")),
                    width=20, height=20, border_radius=10, alignment=ft.Alignment(0, 0),
                    bgcolor=ft.Colors.with_opacity(0.72, c("ink")), right=4, top=4,
                    tooltip="移除", on_click=lambda _e, i=index: self._on_remove_ref(i),
                ),
            ],
            width=76, height=76,
        )

    def _ref_add_tile(self) -> ft.Control:
        tile = ft.Container(
            content=ft.Column(
                controls=[ft.Icon(ft.Icons.ADD_OUTLINED, size=18, color=c("ink-2", "fg")),
                          _txt("添加照片", 11, "ink-2")],
                spacing=2, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=76, height=76, border_radius=s.R_INPUT, alignment=ft.Alignment(0, 0),
            bgcolor=c("surface"), border=ft.border.all(1, c("line-strong")),
            on_click=self._on_add_refs, animate=s.snappy(),
        )

        def _hover(e: ft.ControlEvent) -> None:
            tile.bgcolor = c("surface-2") if e.data in (True, "true") else c("surface")
            tile.update()

        tile.on_hover = _hover
        return tile

    def _on_add_refs(self, _e=None) -> None:
        self._page.run_task(self._pick_refs_async)

    async def _pick_refs_async(self) -> None:
        if not hasattr(self, "_ref_picker"):
            self._ref_picker = ft.FilePicker()
        try:
            picked = await self._ref_picker.pick_files(
                dialog_title="选择参考照片", file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=list(_REF_EXTS), allow_multiple=True,
                with_data=bool(self._page.web),
            )
        except Exception as e:
            show_toast(self._page, f"无法打开文件选择器：{e}", kind="error")
            return
        self._add_refs(picked or [])

    def _add_refs(self, picked: list) -> None:
        """把选中的文件加入参考图（Web 端没有本地路径，先把字节存到临时目录）。"""
        spec = tpl.reference_spec(self._current)
        limit = spec["max"] if spec and not spec["inferred"] else tpl.MAX_REFERENCE_IMAGES
        added = skipped = 0
        for f in picked:
            path = Path(f.path) if getattr(f, "path", None) else None
            if path is None and getattr(f, "bytes", None):
                path = _REF_TEMP_DIR / f"{int(time.time() * 1000)}_{f.name}"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f.bytes)
            if path is None or not path.exists():
                continue
            if path in self._ref_images:
                continue
            if len(self._ref_images) >= limit:
                skipped += 1
                continue
            self._ref_images.append(path)
            added += 1
        if skipped:
            show_toast(self._page, f"这个模板最多 {limit} 张参考图，多出的 {skipped} 张没有添加",
                       kind="warning")
        if added:
            self._render_refs()

    def _on_remove_ref(self, index: int) -> None:
        if 0 <= index < len(self._ref_images):
            self._ref_images.pop(index)
            self._render_refs()

    def _on_clear_refs(self, _e=None) -> None:
        self._ref_images.clear()
        self._render_refs()

    async def _scroll_editor_to_refs(self) -> None:
        try:
            await self._editor_scroll.scroll_to(scroll_key="refs", duration=200)
        except Exception:
            pass

    def _collect_values(self) -> dict:
        values = {}
        for name, ctrl in self._var_controls.items():
            v = ctrl.value
            values[name] = v.strip() if isinstance(v, str) else (v or "")
        return values

    def _render_modifiers(self) -> None:
        groups = []
        selected = set(self._modifiers)
        for group, items in mods.MODIFIER_GROUPS:
            chips = []
            for mid, label, _text in items:
                on = mid in selected
                chips.append(self._chip(label, on,
                                        lambda _e, mid=mid: self._on_toggle_modifier(mid)))
            groups.append(ft.Column(
                controls=[_txt(group, 11, "ink-3"),
                          ft.Row(chips, spacing=6, run_spacing=6, wrap=True)],
                spacing=4,
            ))
        self._modifier_area.controls = groups
        self._modifier_count.value = f"已选 {len(self._modifiers)} 项" if self._modifiers else ""
        self._update(self._modifier_area, self._modifier_count)

    def _toggle_modifiers(self, _e) -> None:
        self._modifier_area.visible = not self._modifier_area.visible
        self._modifier_toggle_icon.icon = (ft.Icons.EXPAND_LESS_OUTLINED if self._modifier_area.visible
                                           else ft.Icons.EXPAND_MORE_OUTLINED)
        self._update(self._modifier_area, self._modifier_toggle_icon)

    def _on_toggle_modifier(self, mid: str) -> None:
        if mid in self._modifiers:
            self._modifiers.remove(mid)
        else:
            self._modifiers.append(mid)
        settings_service.set(_KEY_MODIFIERS, ",".join(self._modifiers))
        self._render_modifiers()
        self._refresh_prompt()

    def _build_prompt(self) -> str:
        if not self._current:
            return ""
        base = tpl.assemble_prompt(self._current, self._collect_values())
        return mods.apply_modifiers(base, self._modifiers, self._negative.value or "")

    def _schedule_refresh(self) -> None:
        """输入框每敲一个字都会触发 on_change。长提示词（导入源里有上万字的）每次都整段
        重发给界面、重新排版，Windows 上连续输入或输入法组字时会明显卡住；
        这里合并成停顿 250ms 后刷新一次。"""
        self._refresh_seq += 1
        if not self._mounted:
            self._refresh_prompt()
            return
        self._page.run_task(self._debounced_refresh, self._refresh_seq)

    async def _debounced_refresh(self, seq: int) -> None:
        await asyncio.sleep(0.25)
        if seq == self._refresh_seq:
            self._refresh_prompt()

    def _refresh_prompt(self) -> None:
        """变量 / 增强项变化后刷新最终提示词（用户手改过则不覆盖）。"""
        if self._manual_prompt:
            state = "已手动修改，上方改动不会自动同步"
            if self._prompt_state.value != state:
                self._prompt_state.value = state
                self._update(self._prompt_state)
            return
        prompt = self._build_prompt()
        state = "根据上方内容自动生成，可直接修改"
        if (prompt == self._prompt_field.value and self._prompt_state.value == state
                and not self._restore_btn.visible):
            return
        self._prompt_field.value = prompt
        self._prompt_state.value = state
        self._restore_btn.visible = False
        self._update(self._prompt_field, self._prompt_state, self._restore_btn)

    def _on_prompt_edited(self, _e) -> None:
        if not self._manual_prompt:
            self._manual_prompt = True
            self._prompt_state.value = "已手动修改"
            self._restore_btn.visible = True
            self._update(self._prompt_state, self._restore_btn)

    def _on_restore_prompt(self, _e) -> None:
        self._manual_prompt = False
        self._refresh_prompt()

    def _on_toggle_favorite(self, _e) -> None:
        if not self._current:
            return
        on = lib.toggle_favorite(self._current["id"])
        show_toast(self._page, "已收藏" if on else "已取消收藏", kind="success" if on else "info")
        self._render_template_header()
        self._reload_library()

    # ═════════════════════════════════════════════════════════════════
    # 生成
    # ═════════════════════════════════════════════════════════════════
    def _build_generate_button(self) -> ft.Control:
        """墨黑主按钮。生成中图标换成转圈、文字换成「生成中…」，形状不变（宽度随栏宽）。"""
        self._generate_icon = ft.AnimatedSwitcher(
            content=ft.Icon(ft.Icons.AUTO_FIX_HIGH_OUTLINED, color=c("on-ink", "fg"), size=16),
            transition=ft.AnimatedSwitcherTransition.FADE, duration=170, reverse_duration=110,
        )
        btn = ft.Container(
            content=ft.Row(
                controls=[self._generate_icon, self._generate_label],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=c("ink"),
            border_radius=s.R_PRIMARY,
            height=s.H_PRIMARY,
            on_click=self._on_generate,
            animate=s.snappy(),
        )

        def _hover(e: ft.ControlEvent) -> None:
            if self._generating:
                return
            btn.bgcolor = c("ink-hover") if e.data in (True, "true") else c("ink")
            btn.update()

        btn.on_hover = _hover
        return btn

    def _build_config_hint(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, color=c("ink-2", "fg"), size=16),
                    _txt("尚未配置 AI 生图 API Key", 12, "ink", expand=True),
                    s.button("去设置", lambda _e: self._page.go("/settings"), kind="ghost",
                             height=28),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            bgcolor=c("surface-2"),
            border=ft.border.all(1, c("line")),
            border_radius=s.R_INPUT,
            padding=ft.padding.only(left=12, right=4, top=4, bottom=4),
            visible=not prompt_image_service.is_configured(),
        )

    def _on_generate(self, _e=None) -> None:
        if self._generating or not self._current:
            return
        if not self._manual_prompt:
            values = self._collect_values()
            missing = [v.get("label") or v["name"] for v in self._current.get("variables", [])
                       if v.get("required") and not values.get(v["name"])]
            if missing:
                show_toast(self._page, f"请填写：{'、'.join(missing)}", kind="error")
                return
        self._refresh_seq += 1  # 丢弃还没执行的延迟刷新
        if not self._manual_prompt:
            self._refresh_prompt()
        prompt = (self._prompt_field.value or "").strip()
        if not prompt:
            show_toast(self._page, "提示词为空", kind="error")
            return
        if not prompt_image_service.is_configured():
            self._config_hint.visible = True
            self._update(self._config_hint)
            show_toast(self._page, "请先在设置中配置 AI 生图 API Key", kind="warning")
            return

        spec = tpl.reference_spec(self._current)
        refs = [p for p in self._ref_images if p.exists()]
        if spec and len(refs) < spec["min"]:
            show_toast(self._page, f"这个模板需要至少 {spec['min']} 张参考图，请先在「参考图」里添加",
                       kind="warning", duration=3500)
            self._page.run_task(self._scroll_editor_to_refs)
            return

        size = self._size_dd.value or "1024x1024"
        quality = self._quality_dd.value or "high"
        self._set_generating(True)
        self._page.run_task(self._generate_task, prompt, size, quality, refs)

    async def _generate_task(self, prompt: str, size: str, quality: str,
                             refs: list[Path] | None = None) -> None:
        refs = refs or []
        self._gen_started = time.time()
        self._show_loading(prompt, len(refs))
        self._page.run_task(self._tick_loading)
        if refs:
            call = prompt_image_service.edit_image(prompt=prompt, images=refs, size=size,
                                                   quality=quality)
        else:
            call = prompt_image_service.generate_image(prompt=prompt, size=size, quality=quality)
        self._gen_loop = asyncio.get_running_loop()
        self._gen_job = asyncio.ensure_future(call)
        try:
            result = await self._gen_job
        except asyncio.CancelledError:
            self._gen_job = None
            self._set_generating(False)
            self._show_cancelled()
            return
        except Exception as e:  # 服务层已兜底，这里防御未知异常，避免界面卡在生成中
            result = {"success": False, "error": str(e)}
        self._gen_job = None
        elapsed = time.time() - self._gen_started
        self._set_generating(False)

        if not result.get("success") or not result.get("image_bytes"):
            self._show_error(result.get("error") or "未获取到图片数据")
            return

        image_bytes = result["image_bytes"]
        saved_path: Path | None = None
        try:
            saved_path = prompt_image_service.save_image(image_bytes)
            lib.add_history(saved_path, prompt, self._current["name"] if self._current else "",
                            size)
        except Exception as e:
            show_toast(self._page, f"保存失败：{e}", kind="error")

        self._last_bytes = image_bytes
        self._last_path = saved_path
        self._last_prompt = prompt
        meta = [f"{size}", f"耗时 {elapsed:.1f}s"]
        if refs:
            meta.insert(1, f"参考图 {len(refs)} 张")
        if saved_path:
            meta.append(str(saved_path))
        self._show_image(image_bytes, saved_path, "  ·  ".join(meta))
        self._render_history()

    async def _tick_loading(self) -> None:
        while self._generating:
            if isinstance(self._preview.data, ft.Text):
                self._preview.data.value = f"已等待 {int(time.time() - self._gen_started)} 秒"
                self._update(self._preview.data)
            await asyncio.sleep(1)

    def _on_cancel_generate(self, _e=None) -> None:
        """取消生成：服务端可能仍在出图，但界面立即恢复可用。"""
        job, loop = self._gen_job, self._gen_loop
        if job is None or loop is None or job.done():
            return
        loop.call_soon_threadsafe(job.cancel)

    def _show_cancelled(self) -> None:
        self._preview.data = None
        self._preview.on_click = None
        self._preview.on_hover = None
        self._set_preview_frame(True)
        self._preview.content = self._preview_state(
            ft.Icons.STOP_CIRCLE_OUTLINED, "已取消生成", "可以调整提示词后重新生成")
        self._result_meta.value = ""
        self._result_actions.visible = False
        self._update(self._preview, self._result_actions, self._result_meta)

    def _set_generating(self, on: bool) -> None:
        self._generating = on
        self._generate_btn.disabled = on
        self._generate_btn.bgcolor = c("ink")
        self._generate_icon.content = ft.ProgressRing(
            width=15, height=15, stroke_width=1.75, color=c("on-ink", "fg"),
            bgcolor=ft.Colors.with_opacity(0.22, c("on-ink", "fg")),
        ) if on else ft.Icon(ft.Icons.AUTO_FIX_HIGH_OUTLINED, color=c("on-ink", "fg"), size=16)
        self._generate_label.value = "生成中…" if on else "生成图片"
        self._update(self._generate_btn)

    # ── 右栏状态 ─────────────────────────────────────────────────────
    def _preview_state(self, icon: str, title: str, detail: str = "",
                       color: str = "ink-2", extra: ft.Control | None = None) -> ft.Control:
        controls: list[ft.Control] = [
            ft.Container(
                content=ft.Icon(icon, size=20, color=c(color, "fg")),
                width=44, height=44, border_radius=22, bgcolor=c("surface"),
                border=ft.border.all(1, c("line")), alignment=ft.Alignment(0, 0),
            ),
            s.text(title, "label", text_align=ft.TextAlign.CENTER),
        ]
        if detail:
            controls.append(_txt(detail, 11.5, "ink-3", text_align=ft.TextAlign.CENTER))
        if extra:
            controls.append(extra)
        return ft.Column(controls, spacing=8, tight=True,
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _show_empty(self) -> None:
        self._preview.data = None
        self._preview.on_click = None
        self._preview.on_hover = None
        self._set_preview_frame(True)
        self._preview.content = self._preview_state(
            ft.Icons.AUTO_FIX_HIGH_OUTLINED, "生成的图片会显示在这里",
            "选好模板、填写内容后点「生成图片」")
        self._result_actions.visible = False
        self._result_meta.value = ""
        self._update(self._preview, self._result_actions, self._result_meta)

    def _show_loading(self, prompt: str, ref_count: int = 0) -> None:
        waited = s.text("已等待 0 秒", "mono", "ink-3", size=11)
        self._preview.data = waited
        self._preview.on_click = None
        self._preview.on_hover = None
        self._set_preview_frame(True)
        self._preview.content = ft.Column(
            controls=[
                ft.ProgressRing(width=28, height=28, stroke_width=2, color=c("ink", "fg"),
                                bgcolor=c("surface-3")),
                s.text(f"AI 正在参考 {ref_count} 张图创作中…" if ref_count else "AI 正在创作中…",
                       "label"),
                waited,
                ft.Container(
                    content=_txt(prompt, 11, "ink-3", max_lines=4,
                                 overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.CENTER),
                    padding=ft.padding.symmetric(horizontal=16),
                ),
                s.button("取消", self._on_cancel_generate, kind="secondary", height=30,
                         icon=ft.Icons.CLOSE_OUTLINED),
            ],
            spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._result_actions.visible = False
        self._result_meta.value = ("带参考图通常需要 30–120 秒" if ref_count
                                   else "高质量通常需要 20–60 秒")
        self._update(self._preview, self._result_actions, self._result_meta)

    def _show_error(self, error: str) -> None:
        self._preview.data = None
        self._preview.on_click = None
        self._preview.on_hover = None
        self._set_preview_frame(True)
        self._preview.content = self._preview_state(
            ft.Icons.ERROR_OUTLINE, "生成失败", error[:300], color="danger",
            extra=self._small_button("重试", ft.Icons.REFRESH_OUTLINED, self._on_generate, primary=True),
        )
        self._result_meta.value = ""
        self._result_actions.visible = False
        self._update(self._preview, self._result_actions, self._result_meta)

    def _image_control(self, image_bytes: bytes | None, path: Path | None, **kw) -> ft.Image:
        """桌面端优先用本地文件加载（不经过界面通道传输大块数据），Web 端用字节。"""
        if path is not None and path.exists() and not self._page.web:
            source: str | bytes = str(path)
        elif image_bytes:
            source = image_bytes
        elif path is not None and path.exists():
            source = path.read_bytes()
        else:
            source = b""
        return ft.Image(
            src=source, fit=ft.BoxFit.CONTAIN, border_radius=10, gapless_playback=True,
            error_content=ft.Column(
                controls=[ft.Icon(ft.Icons.BROKEN_IMAGE_OUTLINED, color=c("danger", "fg")),
                          _txt("预览加载失败，图片已保存，可点「打开图片」查看", 11, "danger")],
                tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            **kw,
        )

    def _set_preview_frame(self, on: bool) -> None:
        """空态 / 生成中 / 出错时显示灰底描边框；出图后去掉，只留图片本身。"""
        self._preview.bgcolor = c("surface-2") if on else None
        self._preview.border = ft.border.all(1, c("line")) if on else None
        self._preview.padding = 8 if on else 0

    def _show_image(self, image_bytes: bytes | None, path: Path | None, meta: str) -> None:
        self._preview.data = None
        # 出图后去掉灰底和描边，只显示按原比例缩放的圆角图片；徽标跟着图片右上角走
        image = ft.Container(
            self._image_control(image_bytes, path), border_radius=10,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            shadow=ft.BoxShadow(blur_radius=18, offset=ft.Offset(0, 6), spread_radius=-8,
                                color=ft.Colors.with_opacity(0.28, c("shadow"))),
            scale=1, animate_scale=s.default(),
        )
        badge = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.ZOOM_OUT_MAP_OUTLINED, size=14, color=c("on-ink", "fg")),
                            _txt("查看大图", 11.5, "on-ink", weight=ft.FontWeight.W_500)],
                           spacing=5, tight=True),
            bgcolor=ft.Colors.with_opacity(0.72, c("ink")), border_radius=999,
            padding=ft.padding.only(left=8, right=10, top=5, bottom=5),
            right=8, top=8, opacity=0.0, offset=ft.Offset(0, -0.2),
            animate_opacity=s.snappy(), animate_offset=s.default(),
        )

        def _hover(e: ft.ControlEvent) -> None:
            on = e.data in (True, "true")
            image.scale = 1.015 if on else 1
            badge.opacity, badge.offset = (1, ft.Offset(0, 0)) if on else (0, ft.Offset(0, -0.2))
            self._update(image, badge)

        self._set_preview_frame(False)
        self._preview.content = ft.Stack(controls=[image, badge])
        self._preview.on_hover = _hover
        self._preview.on_click = lambda _e: self._open_lightbox()
        self._result_meta.value = meta
        self._result_actions.controls = [
            self._small_button("打开图片", ft.Icons.OPEN_IN_NEW_OUTLINED, self._on_open_image),
            self._small_button("打开目录", ft.Icons.FOLDER_OPEN_OUTLINED, self._on_open_dir),
            self._small_button("另存为", ft.Icons.DOWNLOAD_OUTLINED, self._on_download),
            self._small_button("复用提示词", ft.Icons.REPLAY_OUTLINED, self._on_reuse_prompt),
            self._small_button("再来一张", ft.Icons.REFRESH_OUTLINED, self._on_generate, primary=True),
        ]
        self._result_actions.visible = True
        self._update(self._preview, self._result_meta, self._result_actions)

    # ── 最近作品 ─────────────────────────────────────────────────────
    def _render_history(self) -> None:
        history = lib.list_history()[:_HISTORY_THUMBS]
        self._history_row.controls = [self._history_thumb(h) for h in history]
        self._history_section.controls = [
            ft.Row([_txt("最近作品", 12, "ink-2", weight=ft.FontWeight.W_500),
                    s.text(f"{len(history)}", "mono", "ink-3", size=11)], spacing=6),
            self._history_row,
        ] if history else []
        self._update(self._history_section)

    def _thumb_source(self, path: Path) -> str | bytes:
        if not self._page.web:
            return str(path)
        try:
            from PIL import Image
            with Image.open(path) as im:
                im.thumbnail((128, 128))
                buf = io.BytesIO()
                im.convert("RGB").save(buf, "JPEG", quality=80)
                return buf.getvalue()
        except Exception:
            return b""

    def _history_thumb(self, h: dict) -> ft.Control:
        path = Path(h["path"])
        current = self._last_path is not None and path == self._last_path
        stamp = datetime.fromtimestamp(h.get("created_at", 0)).strftime("%m-%d %H:%M")
        return ft.Container(
            content=ft.Image(src=self._thumb_source(path), width=56, height=56,
                             fit=ft.BoxFit.COVER, border_radius=8, cache_width=112,
                             error_content=ft.Icon(ft.Icons.IMAGE_OUTLINED, size=18)),
            width=60, height=60, border_radius=10, padding=2,
            border=ft.border.all(2, c("accent") if current else ft.Colors.TRANSPARENT),
            tooltip=f"{h.get('template') or '提示词出图'} · {stamp}",
            on_click=lambda _e, h=h: self._show_history_item(h),
        )

    def _show_history_item(self, h: dict) -> None:
        path = Path(h["path"])
        if not path.exists():
            show_toast(self._page, "图片文件已不存在", kind="error")
            self._render_history()
            return
        self._last_path = path
        self._last_bytes = None
        self._last_prompt = h.get("prompt", "")
        stamp = datetime.fromtimestamp(h.get("created_at", 0)).strftime("%Y-%m-%d %H:%M")
        self._show_image(None, path, f"{h.get('template') or ''}  ·  {h.get('size', '')}  ·  {stamp}")
        self._render_history()

    # ── 结果区操作 ───────────────────────────────────────────────────
    def _current_image_bytes(self) -> bytes | None:
        if self._last_bytes:
            return self._last_bytes
        if self._last_path and self._last_path.exists():
            return self._last_path.read_bytes()
        return None

    def _open_lightbox(self) -> None:
        """全窗口看图器：当前结果 + 最近作品，可缩放到原图像素、左右切换。"""
        if not (self._last_path or self._last_bytes):
            return
        items, index = [], -1
        for h in lib.list_history():
            path = Path(h["path"])
            stamp = datetime.fromtimestamp(h.get("created_at", 0)).strftime("%Y-%m-%d %H:%M")
            if self._last_path is not None and path == self._last_path:
                index = len(items)
            items.append(ViewerItem(path=path, title=h.get("template") or "", meta=stamp))
        if index < 0:
            # 结果没进最近作品（如 Web 端只有字节）时单独放在最前
            items.insert(0, ViewerItem(path=self._last_path, data=self._last_bytes,
                                       title=(self._current or {}).get("name", "")))
            index = 0
        ImageViewer(
            self._page, items, index,
            on_save=lambda it: self._page.run_task(self._download_async, it),
            on_reveal=lambda it: it.path and open_folder(it.path.parent),
        ).open()

    def _on_open_image(self, _e) -> None:
        if self._last_path and self._last_path.exists():
            open_folder(self._last_path)

    def _on_open_dir(self, _e) -> None:
        if self._last_path:
            open_folder(self._last_path.parent)

    def _on_reuse_prompt(self, _e) -> None:
        if not self._last_prompt:
            return
        self._manual_prompt = True
        self._prompt_field.value = self._last_prompt
        self._prompt_state.value = "已载入这张图的提示词"
        self._restore_btn.visible = True
        self._update(self._prompt_field, self._prompt_state, self._restore_btn)
        show_toast(self._page, "已载入提示词，可修改后再次生成")

    def _on_download(self, _e) -> None:
        self._page.run_task(self._download_async)

    async def _download_async(self, item: ViewerItem | None = None) -> None:
        """另存为；item 来自看图器（可能是最近作品里的另一张），不传则存当前结果。"""
        if item is None:
            data, path = self._current_image_bytes(), self._last_path
        else:
            path = item.path
            data = item.data or (path.read_bytes() if path and path.exists() else None)
        if not data:
            return
        if not hasattr(self, "_save_picker"):
            self._save_picker = ft.FilePicker()
        ext = path.suffix.lstrip(".") if path else "png"
        try:
            target = await self._save_picker.save_file(
                dialog_title="保存图片",
                file_name=f"prompt_image_{int(time.time())}.{ext or 'png'}",
                initial_directory=settings_service.get("default_output_dir", "") or str(Path.home()),
            )
        except Exception as e:
            show_toast(self._page, f"无法打开保存对话框：{e}", kind="error")
            return
        if not target:
            return
        try:
            Path(target).write_bytes(data)
            show_toast(self._page, "已保存", kind="success")
        except OSError as e:
            show_toast(self._page, f"保存失败：{e}", kind="error")

    def _on_copy_prompt(self, _e) -> None:
        text = self._prompt_field.value or ""
        if text:
            self._page.run_task(self._copy_async, text)

    async def _copy_async(self, text: str) -> None:
        try:
            await ft.Clipboard().set(text)
            show_toast(self._page, "提示词已复制", kind="success")
        except Exception as e:
            show_toast(self._page, f"复制失败：{e}", kind="error")

    def _launch(self, url: str) -> None:
        self._page.run_task(self._page.launch_url, url)

    # ═════════════════════════════════════════════════════════════════
    # 我的模板
    # ═════════════════════════════════════════════════════════════════
    def _on_save_as_template(self, _e) -> None:
        prompt = self._prompt_field.value or ""
        if self._current and not self._manual_prompt and self._current.get("variables"):
            # 未手改时保存模板原文（保留 {变量}），再叠加当前的风格增强
            prompt = mods.apply_modifiers(self._current["prompt_template"], self._modifiers,
                                          self._negative.value or "")
        name = f"{self._current['name']}（我的）" if self._current else ""
        self._open_template_editor({"name": name, "prompt_template": prompt,
                                    "category": "我的模板",
                                    "default_size": self._size_dd.value or "1024x1024"})

    def _open_template_editor(self, template: dict | None = None) -> None:
        template = template or {}
        editing_id = template.get("id", "") if template.get("source") == lib.CUSTOM_SOURCE else ""
        name = _field(label="模板名称", value=template.get("name", ""))
        category = _field(label="分类", value=template.get("category") or "我的模板")
        prompt = _field(
            label="提示词", value=template.get("prompt_template", ""), multiline=True,
            min_lines=6, max_lines=12,
            hint="例如：A cozy {房间} interior in {风格} style, warm light",
        )
        detected = _txt("", 11, "ink-2")

        def refresh_detected(_e=None) -> None:
            _p, variables = src.detect_variables(prompt.value or "")
            detected.value = ("可填写项：" + "、".join(v["label"] for v in variables)
                              if variables else "用 {变量名} 标记需要每次填写的部分")
            if _e is not None:
                detected.update()

        prompt.on_change = refresh_detected
        refresh_detected()

        def save(_e) -> None:
            if not (prompt.value or "").strip():
                show_toast(self._page, "提示词不能为空", kind="error")
                return
            item = lib.save_custom(name.value or "", prompt.value or "",
                                   category=category.value or "我的模板",
                                   default_size=template.get("default_size", "1024x1024"),
                                   template_id=editing_id)
            self._page.pop_dialog()
            show_toast(self._page, "模板已保存", kind="success")
            self._source = lib.CUSTOM_SOURCE
            settings_service.set(_KEY_LAST_SOURCE, self._source)
            self._category = "全部"
            self._reload_library(select_id=item["id"])

        dlg = ft.AlertDialog(
            modal=True,
            title=s.text("编辑模板" if editing_id else "保存为我的模板", "title", size=16),
            content=ft.Container(
                ft.Column([name, category, prompt, detected], spacing=12, tight=True,
                          scroll=ft.ScrollMode.AUTO,
                          horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                width=520,
            ),
            actions=[
                s.button("取消", lambda _e: self._page.pop_dialog(), kind="secondary"),
                s.button("保存", save),
            ],
        )
        self._page.show_dialog(dlg)

    def _on_delete_custom(self, _e) -> None:
        t = self._current
        if not t:
            return

        def confirm() -> None:
            lib.delete_custom(t["id"])
            self._current = None
            self._reload_library()
            show_toast(self._page, "模板已删除")

        s.confirm(self._page, "删除模板", f"确定删除「{t['name']}」吗？此操作不可撤销。",
                  confirm_label="删除", on_confirm=confirm, danger=True)

    # ═════════════════════════════════════════════════════════════════
    # 提示词源管理
    # ═════════════════════════════════════════════════════════════════
    def _open_source_manager(self, _e=None) -> None:
        self._source_body = ft.Column(spacing=14, tight=True, scroll=ft.ScrollMode.AUTO)
        self._source_url = _field(
            hint="粘贴 JSON / CSV / Markdown 提示词集合的链接（支持 GitHub 文件页地址）",
            expand=True,
        )
        self._source_busy = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
        self._render_source_manager()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.HUB_OUTLINED, color=c("ink-2", "fg"), size=18),
                s.text("提示词源", "title", size=16),
                self._source_busy,
            ], spacing=8),
            content=ft.Container(self._source_body, width=600, height=520),
            actions=[s.button("完成", self._close_source_manager)],
        )
        self._page.show_dialog(dlg)

    def _close_source_manager(self, _e) -> None:
        self._page.pop_dialog()
        self._reload_library()

    def _render_source_manager(self) -> None:
        sources = lib.list_sources()
        added_urls = {item.get("url") for item in sources}
        body: list[ft.Control] = []

        body.append(s.text("已添加", "label"))
        if not sources:
            body.append(_txt("还没有添加外部提示词源。可从下方推荐里一键添加，或粘贴链接 / 导入本地文件。",
                             12, "ink-3"))
        for s_ in sources:
            updated = datetime.fromtimestamp(s_.get("updated_at", 0)).strftime("%Y-%m-%d")
            info = f"{s_.get('count', 0)} 条 · 更新于 {updated}"
            if s_.get("license"):
                info += f" · {s_['license']}"
            body.append(ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column([
                            s.text(s_["name"], "label",
                                   max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            s.text(info, "mono", "ink-3", size=11),
                        ], spacing=2, expand=True, tight=True),
                        ft.Switch(value=s_.get("enabled", True), scale=0.8, tooltip="在模板库中显示",
                                  on_change=lambda e, sid=s_["id"]: self._on_source_enabled(sid, e)),
                        s.icon_button(ft.Icons.REFRESH_OUTLINED, lambda _e, sid=s_["id"]: self._run_source_op(
                                          lib.refresh_source(sid), "已更新"), "重新下载"),
                        s.icon_button(ft.Icons.OPEN_IN_NEW_OUTLINED,
                                      lambda _e, u=s_.get("homepage") or s_["url"]: self._launch(u),
                                      "打开主页",
                                      visible=bool(s_.get("homepage") or s_["url"].startswith("http"))),
                        s.icon_button(ft.Icons.DELETE_OUTLINE,
                                      lambda _e, sid=s_["id"]: self._on_remove_source(sid), "移除",
                                      color="danger"),
                    ],
                    spacing=2,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=c("surface-2"), border=ft.border.all(1, c("line")), border_radius=s.R_INPUT,
                padding=ft.padding.only(left=12, right=4, top=4, bottom=4),
            ))

        body.append(ft.Container(height=4))
        body.append(s.text("推荐的开源提示词库", "label"))
        body.append(_txt("内容从 GitHub 下载到本机，版权归原作者，使用时请遵守对应许可证并保留署名。",
                         11, "ink-3"))
        for rec in src.RECOMMENDED_SOURCES:
            added = rec["url"] in added_urls
            body.append(ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column([
                            ft.Row([s.text(rec["name"], "label"),
                                    self._badge(rec["license"])], spacing=6),
                            _txt(rec["description"], 11.5, "ink-2"),
                        ], spacing=2, expand=True, tight=True),
                        s.icon_button(ft.Icons.OPEN_IN_NEW_OUTLINED,
                                      lambda _e, u=rec["homepage"]: self._launch(u), "查看仓库"),
                        s.button(
                            "已添加" if added else "添加",
                            lambda _e, rec=rec: self._run_source_op(
                                lib.add_source(rec["url"], rec["name"], rec["homepage"],
                                               rec["license"]), "已添加"),
                            kind="secondary" if added else "primary", height=30, disabled=added,
                        ),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                border=ft.border.all(1, c("line")), border_radius=s.R_INPUT,
                padding=ft.padding.only(left=12, right=8, top=6, bottom=6),
            ))

        body.append(ft.Container(height=4))
        body.append(s.text("添加其他来源", "label"))
        body.append(ft.Row([
            self._source_url,
            s.button("添加", self._on_add_url, height=s.H_INPUT),
        ], spacing=8))
        body.append(ft.Row([
            self._small_button("从本地文件导入", ft.Icons.UPLOAD_FILE_OUTLINED, self._on_import_file),
            self._small_button("导出我的模板", ft.Icons.IOS_SHARE_OUTLINED, self._on_export_custom),
        ], spacing=8))
        body.append(_txt(
            "支持格式：① JSON：{\"name\": \"库名\", \"templates\": [{\"name\": ..., \"prompt\": ..., "
            "\"category\": ...}]}；② CSV：含 prompt 列，可选 title / category / tags；"
            "③ Markdown：每个标题下第一个代码块为一条提示词。提示词中的 {变量} 或 [变量] 会变成可填写项。",
            11, "ink-3"))
        self._source_body.controls = body
        self._update(self._source_body)

    def _set_source_busy(self, busy: bool) -> None:
        self._source_busy.visible = busy
        self._update(self._source_busy)

    def _run_source_op(self, coro, ok_text: str) -> None:
        async def runner() -> None:
            self._set_source_busy(True)
            try:
                record = await coro
                show_toast(self._page, f"{ok_text}：{record['name']}（{record['count']} 条）",
                           kind="success")
            except Exception as e:
                show_toast(self._page, f"操作失败：{_friendly_error(e)}", kind="error",
                           duration=4000)
            finally:
                self._set_source_busy(False)
            self._render_source_manager()
            self._reload_library()
        self._page.run_task(runner)

    def _on_add_url(self, _e) -> None:
        url = (self._source_url.value or "").strip()
        if not url.startswith(("http://", "https://")):
            show_toast(self._page, "请输入以 http(s):// 开头的链接", kind="error")
            return
        self._source_url.value = ""
        self._run_source_op(lib.add_source(url), "已添加")

    def _on_source_enabled(self, source_id: str, e) -> None:
        lib.set_source_enabled(source_id, bool(e.control.value))
        self._reload_library()

    def _on_remove_source(self, source_id: str) -> None:
        lib.remove_source(source_id)
        self._render_source_manager()
        self._reload_library()

    def _on_import_file(self, _e) -> None:
        self._page.run_task(self._import_file_async)

    async def _import_file_async(self) -> None:
        if not hasattr(self, "_import_picker"):
            self._import_picker = ft.FilePicker()
        try:
            picked = await self._import_picker.pick_files(
                dialog_title="选择提示词文件", file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["json", "csv", "tsv", "md", "markdown", "txt"],
            )
        except Exception as e:
            show_toast(self._page, f"无法打开文件选择器：{e}", kind="error")
            return
        if not picked or not picked[0].path:
            return
        try:
            record = lib.import_file(Path(picked[0].path))
            show_toast(self._page, f"已导入：{record['name']}（{record['count']} 条）",
                       kind="success")
        except Exception as e:
            show_toast(self._page, f"导入失败：{_friendly_error(e)}", kind="error", duration=4000)
        self._render_source_manager()
        self._reload_library()

    def _on_export_custom(self, _e) -> None:
        if not lib.list_custom():
            show_toast(self._page, "还没有自己的模板")
            return
        self._page.run_task(self._export_custom_async)

    async def _export_custom_async(self) -> None:
        if not hasattr(self, "_export_picker"):
            self._export_picker = ft.FilePicker()
        try:
            target = await self._export_picker.save_file(
                dialog_title="导出我的模板", file_name="my_prompts.json",
                allowed_extensions=["json"],
            )
        except Exception as e:
            show_toast(self._page, f"无法打开保存对话框：{e}", kind="error")
            return
        if not target:
            return
        try:
            Path(target).write_text(lib.export_custom_json(), encoding="utf-8")
            show_toast(self._page, "已导出，可分享给他人导入", kind="success")
        except OSError as e:
            show_toast(self._page, f"导出失败：{e}", kind="error")


def _friendly_error(e: Exception) -> str:
    import httpx
    if isinstance(e, httpx.HTTPStatusError):
        return f"服务器返回 {e.response.status_code}"
    if isinstance(e, httpx.TimeoutException):
        return "下载超时，请检查网络（GitHub 在部分网络下需要代理）"
    if isinstance(e, httpx.HTTPError):
        return "无法连接，请检查网络或链接（GitHub 在部分网络下需要代理）"
    return str(e) or e.__class__.__name__
