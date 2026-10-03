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
from ui.palette import c
from ui.utils import open_folder, show_toast

_LIST_LIMIT = 300          # 左栏最多渲染的模板数，超出提示用户搜索
_CHIP_CATEGORY_LIMIT = 14  # 分类不超过这个数用标签，否则改用下拉框
_HISTORY_THUMBS = 12
_KEY_LAST_SOURCE = "prompt_image_last_source"
_KEY_LAST_TEMPLATE = "prompt_image_last_template"
_KEY_MODIFIERS = "prompt_image_modifiers"
_FONT = "42dot Sans"


def _txt(value: str, size: int = 12, color: str = "#455c7f", **kw) -> ft.Text:
    return ft.Text(value, size=size, color=c(color, "fg"), font_family=_FONT, **kw)


def _dropdown(**kw) -> ft.Dropdown:
    """统一风格的下拉框：浅底无边框，聚焦时显示品牌色描边。"""
    kw.setdefault("dense", True)
    kw.setdefault("text_size", 13)
    kw.setdefault("border_radius", 10)
    kw.setdefault("filled", True)
    kw.setdefault("fill_color", c("#f8fafc"))
    kw.setdefault("border_color", "transparent")
    kw.setdefault("focused_border_color", c("#005f98"))
    kw.setdefault("content_padding", ft.padding.symmetric(horizontal=12, vertical=10))
    kw.setdefault("text_style", ft.TextStyle(color=c("#162f50", "fg"), size=13))
    return ft.Dropdown(**kw)


def _card(content: ft.Control, **kw) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=c("#ffffff"),
        border_radius=16,
        shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.05, c("#000000", "fg")),
                            offset=ft.Offset(0, 2)),
        **kw,
    )


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

        # ── 左栏控件 ────────────────────────────────────────────────────
        self._source_dd = _dropdown(
            value=self._source, options=[], dense=True, border_radius=10, expand=True,
            text_size=13, on_select=self._on_source_change,
        )
        self._search = ft.TextField(
            hint_text="搜索名称 / 标签 / 提示词",
            hint_style=ft.TextStyle(color=c("#94a3b8", "fg"), size=13),
            prefix_icon=ft.Icons.SEARCH, dense=True, text_size=13,
            border_radius=10, bgcolor=c("#f8fafc"), border_color="transparent",
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            on_change=self._on_search_change,
        )
        self._category_area = ft.Container()
        self._count_text = _txt("", 11, "#94a3b8")
        self._template_list = ft.ListView(expand=True, spacing=6, padding=ft.padding.only(right=6))

        # ── 中栏控件 ────────────────────────────────────────────────────
        self._tpl_header = ft.Column(spacing=6)
        self._form_area = ft.Column(spacing=12)
        self._modifier_area = ft.Column(spacing=10, visible=bool(self._modifiers))
        self._modifier_toggle_icon = ft.Icon(
            ft.Icons.EXPAND_LESS if self._modifiers else ft.Icons.EXPAND_MORE,
            size=18, color=c("#455c7f", "fg"),
        )
        self._modifier_count = _txt("", 11, "#005f98")
        self._negative = ft.TextField(
            hint_text="避免出现的内容（可选），如：文字水印、多余手指、模糊",
            hint_style=ft.TextStyle(color=c("#94a3b8", "fg"), size=12),
            dense=True, text_size=13, border_radius=10, bgcolor=c("#f8fafc"),
            border_color="transparent", on_change=lambda _e: self._refresh_prompt(),
        )
        self._prompt_state = _txt("自动生成", 11, "#94a3b8")
        self._restore_btn = ft.TextButton(
            "恢复自动", visible=False, on_click=self._on_restore_prompt,
            style=ft.ButtonStyle(color=c("#005f98", "fg"), padding=ft.padding.all(4)),
        )
        self._prompt_field = ft.TextField(
            multiline=True, min_lines=4, max_lines=10, text_size=13,
            text_style=ft.TextStyle(color=c("#162f50", "fg")),
            border_radius=12, bgcolor=c("#f8fafc"), border_color="transparent",
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
        self._generate_label = _txt("生成图片", 15, "#ffffff", weight=ft.FontWeight.W_600)
        self._generate_btn = self._build_generate_button()
        self._config_hint = self._build_config_hint()

        # ── 右栏控件 ────────────────────────────────────────────────────
        self._preview = ft.Container(
            expand=True, border_radius=12, bgcolor=c("#f8fafc"),
            border=ft.border.all(1, c("#e2e8f0")), alignment=ft.Alignment(0, 0),
            padding=8,
        )
        self._result_meta = _txt("", 11, "#94a3b8", max_lines=2,
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
            padding=ft.padding.only(left=24, top=16, right=32, bottom=12),
            content=ft.Row(
                controls=[
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_color=c("#455c7f", "fg"),
                                  on_click=lambda _e: self._page.go("/")),
                    ft.Container(
                        content=ft.Icon(ft.Icons.AUTO_FIX_HIGH, color=c("#e11d48", "fg"), size=20),
                        width=40, height=40, bgcolor=c("#fff1f2"), border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            _txt("提示词出图", 20, "#162f50", weight=ft.FontWeight.W_600),
                            _txt("挑一个模板，填几个关键词，AI 帮你出图", 12, "#455c7f"),
                        ],
                        spacing=0, tight=True,
                    ),
                    ft.Container(expand=True),
                    self._pill_button("提示词源", ft.Icons.HUB_OUTLINED, self._open_source_manager),
                    self._pill_button("新建模板", ft.Icons.ADD, lambda _e: self._open_template_editor()),
                ],
                spacing=12,
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
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TUNE, size=16, color=c("#e11d48", "fg")),
                            _txt("风格增强", 14, "#162f50", weight=ft.FontWeight.W_600),
                            self._modifier_count,
                            ft.Container(expand=True),
                            self._modifier_toggle_icon,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    on_click=self._toggle_modifiers,
                    ink=True, border_radius=8, padding=ft.padding.symmetric(vertical=4),
                ),
                self._modifier_area,
                self._negative,
                self._divider(),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SUBJECT, size=16, color=c("#e11d48", "fg")),
                        _txt("最终提示词", 14, "#162f50", weight=ft.FontWeight.W_600),
                        self._prompt_state,
                        self._restore_btn,
                        ft.Container(expand=True),
                        ft.IconButton(ft.Icons.COPY_ALL_OUTLINED, icon_size=18, tooltip="复制提示词",
                                      icon_color=c("#455c7f", "fg"), on_click=self._on_copy_prompt),
                        ft.IconButton(ft.Icons.BOOKMARK_ADD_OUTLINED, icon_size=18,
                                      tooltip="存为我的模板", icon_color=c("#455c7f", "fg"),
                                      on_click=self._on_save_as_template),
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
            border=ft.border.only(top=ft.BorderSide(1, c("#e2e8f0"))),
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
                            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=16, color=c("#e11d48", "fg")),
                            _txt("生成结果", 14, "#162f50", weight=ft.FontWeight.W_600),
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
            padding=ft.padding.only(left=24, right=24, bottom=24),
            expand=True,
        )

    def _divider(self) -> ft.Control:
        return ft.Divider(height=1, thickness=1, color=c("#e2e8f0"))

    def _section_title(self, title: str, icon: str) -> ft.Control:
        return ft.Row(
            controls=[ft.Icon(icon, size=16, color=c("#e11d48", "fg")),
                      _txt(title, 14, "#162f50", weight=ft.FontWeight.W_600)],
            spacing=6,
        )

    def _labeled(self, label: str, body: ft.Control) -> ft.Control:
        return ft.Column([_txt(label, 11), body], spacing=4, expand=True)

    def _pill_button(self, label: str, icon: str, on_click) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[ft.Icon(icon, size=16, color=c("#005f98", "fg")),
                          _txt(label, 13, "#005f98", weight=ft.FontWeight.W_500)],
                spacing=6, tight=True,
            ),
            bgcolor=c("#ffffff"), border=ft.border.all(1, c("#d5e3ff")), border_radius=9999,
            padding=ft.padding.symmetric(horizontal=14, vertical=8), on_click=on_click, ink=True,
        )

    def _small_button(self, label: str, icon: str, on_click, primary: bool = False) -> ft.Control:
        fg = "#ffffff" if primary else "#005f98"
        return ft.Container(
            content=ft.Row(
                controls=[ft.Icon(icon, size=14, color=c(fg, "fg")), _txt(label, 12, fg)],
                spacing=4, tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=c("#005f98") if primary else c("#ffffff"),
            border=None if primary else ft.border.all(1, c("#d5e3ff")),
            border_radius=8, padding=ft.padding.symmetric(horizontal=10, vertical=6),
            on_click=on_click, ink=True,
        )

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
                chips.append(ft.Container(
                    content=_txt(cat, 12, "#ffffff" if active else "#455c7f",
                                 weight=ft.FontWeight.W_500),
                    bgcolor=c("#005f98") if active else c("#f1f5f9"),
                    border_radius=9999,
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    on_click=lambda _e, cat=cat: self._on_category_change(cat),
                    ink=True,
                ))
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
                content=_txt(hint, 12, "#94a3b8", text_align=ft.TextAlign.CENTER),
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
        icon = getattr(ft.Icons, t.get("icon") or "AUTO_AWESOME", ft.Icons.AUTO_AWESOME)
        sub = t.get("author") or (lib.source_label(t["source"])
                                  if t.get("source") not in (tpl.BUILTIN_SOURCE, None) else "")
        texts: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Text(t["name"], size=13, weight=ft.FontWeight.W_600,
                            color=c("#162f50", "fg"), font_family=_FONT, expand=True,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Icon(ft.Icons.STAR, size=13, color=c("#d97706", "fg"), visible=favorite),
                ],
                spacing=4,
            ),
            _txt(t.get("description", ""), 11, "#61789c", max_lines=1,
                 overflow=ft.TextOverflow.ELLIPSIS),
        ]
        if sub:
            texts.append(_txt(sub, 10, "#94a3b8", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, size=18, color=c("#e11d48", "fg")),
                        width=34, height=34, border_radius=10, bgcolor=c("#fff1f2"),
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(texts, spacing=1, expand=True, tight=True),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=c("#f0f7ff") if selected else None,
            border=ft.border.all(1, c("#005f98") if selected else "transparent"),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=8, vertical=8),
            on_click=lambda _e, t=t: self._select_template(t),
            ink=True,
        )

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
        icon = getattr(ft.Icons, t.get("icon") or "AUTO_AWESOME", ft.Icons.AUTO_AWESOME)
        actions: list[ft.Control] = [
            ft.IconButton(
                ft.Icons.STAR if fav else ft.Icons.STAR_BORDER, icon_size=20,
                icon_color=c("#d97706", "fg") if fav else c("#94a3b8", "fg"),
                tooltip="取消收藏" if fav else "收藏", on_click=self._on_toggle_favorite,
            ),
        ]
        if t.get("source") == lib.CUSTOM_SOURCE:
            actions += [
                ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_size=18, tooltip="编辑模板",
                              icon_color=c("#455c7f", "fg"),
                              on_click=lambda _e: self._open_template_editor(self._current)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18, tooltip="删除模板",
                              icon_color=c("#b91c1c", "fg"), on_click=self._on_delete_custom),
            ]
        credit: list[ft.Control] = [
            self._badge(t.get("category") or "未分类", "#dee9ff", "#005f98"),
            self._badge(lib.source_label(t.get("source") or tpl.BUILTIN_SOURCE), "#f1f5f9", "#455c7f"),
        ]
        if t.get("author"):
            credit.append(_txt(f"作者 {t['author']}", 11, "#61789c"))
        if t.get("license"):
            credit.append(_txt(t["license"], 11, "#61789c"))
        if t.get("link"):
            credit.append(ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_NEW, size=12, color=c("#005f98", "fg")),
                                _txt("原文", 11, "#005f98")], spacing=2, tight=True),
                on_click=lambda _e, url=t["link"]: self._launch(url), ink=True, border_radius=6,
                padding=ft.padding.symmetric(horizontal=4, vertical=2),
            ))
        self._tpl_header.controls = [
            ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, size=22, color=c("#e11d48", "fg")),
                        width=42, height=42, border_radius=12, bgcolor=c("#fff1f2"),
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(t["name"], size=17, weight=ft.FontWeight.W_600,
                                    color=c("#162f50", "fg"), font_family=_FONT,
                                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            _txt(t.get("description", ""), 12, "#455c7f", max_lines=2,
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

    def _badge(self, text: str, bg: str, fg: str) -> ft.Control:
        return ft.Container(
            content=_txt(text, 10, fg, weight=ft.FontWeight.W_500),
            bgcolor=c(bg), border_radius=9999,
            padding=ft.padding.symmetric(horizontal=8, vertical=2),
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
                12, "#94a3b8"))
        for var in variables:
            name = var["name"]
            var_type = var.get("type", "text")
            default = var.get("default", "")
            if var_type == "select" and var.get("options"):
                ctrl: ft.Control = _dropdown(
                    value=default or var["options"][0], dense=True, text_size=13,
                    options=[ft.dropdown.Option(o, option_label(o)) for o in var["options"]],
                    border_radius=10, expand=True,
                    on_select=lambda _e: self._refresh_prompt(),
                )
            else:
                multiline = var_type == "textarea"
                ctrl = ft.TextField(
                    value=default, hint_text=var.get("placeholder", ""),
                    hint_style=ft.TextStyle(color=c("#94a3b8", "fg"), size=12),
                    multiline=multiline, min_lines=4 if multiline else None,
                    max_lines=10 if multiline else 1, dense=not multiline, text_size=13,
                    border_radius=10, bgcolor=c("#f8fafc"), border_color="transparent",
                    on_change=lambda _e: self._refresh_prompt(),
                )
            self._var_controls[name] = ctrl
            label = var.get("label") or name
            self._form_area.controls.append(ft.Column(
                controls=[
                    ft.Row([_txt(label, 12),
                            _txt("*", 12, "#e11d48", visible=bool(var.get("required")))], spacing=2),
                    ctrl,
                ],
                spacing=4,
            ))
        self._update(self._form_area)

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
                chips.append(ft.Container(
                    content=_txt(label, 12, "#ffffff" if on else "#455c7f"),
                    bgcolor=c("#e11d48", "fg") if on else c("#f1f5f9"),
                    border_radius=9999,
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    on_click=lambda _e, mid=mid: self._on_toggle_modifier(mid),
                    ink=True,
                ))
            groups.append(ft.Column(
                controls=[_txt(group, 11, "#94a3b8"),
                          ft.Row(chips, spacing=6, run_spacing=6, wrap=True)],
                spacing=4,
            ))
        self._modifier_area.controls = groups
        self._modifier_count.value = f"已选 {len(self._modifiers)} 项" if self._modifiers else ""
        self._update(self._modifier_area, self._modifier_count)

    def _toggle_modifiers(self, _e) -> None:
        self._modifier_area.visible = not self._modifier_area.visible
        self._modifier_toggle_icon.icon = (ft.Icons.EXPAND_LESS if self._modifier_area.visible
                                           else ft.Icons.EXPAND_MORE)
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

    def _refresh_prompt(self) -> None:
        """变量 / 增强项变化后刷新最终提示词（用户手改过则不覆盖）。"""
        if self._manual_prompt:
            self._prompt_state.value = "已手动修改，上方改动不会自动同步"
            self._update(self._prompt_state)
            return
        self._prompt_field.value = self._build_prompt()
        self._prompt_state.value = "根据上方内容自动生成，可直接修改"
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
        show_toast(self._page, "已收藏" if on else "已取消收藏", color="#047857" if on else None)
        self._render_template_header()
        self._reload_library()

    # ═════════════════════════════════════════════════════════════════
    # 生成
    # ═════════════════════════════════════════════════════════════════
    def _build_generate_button(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.AUTO_FIX_HIGH, color=c("#ffffff", "fg"), size=18),
                          self._generate_label],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=[c("#005f98"), c("#6b1ef3")],
            ),
            border_radius=12,
            padding=ft.padding.symmetric(vertical=13),
            shadow=ft.BoxShadow(blur_radius=15, spread_radius=-3,
                                color=ft.Colors.with_opacity(0.25, c("#005f98", "fg")),
                                offset=ft.Offset(0, 6)),
            on_click=self._on_generate,
            ink=True,
            animate_opacity=150,
        )

    def _build_config_hint(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, color=c("#b45309", "fg"), size=16),
                    _txt("尚未配置 AI 生图 API Key", 12, "#92400e", expand=True),
                    ft.TextButton("去设置", on_click=lambda _e: self._page.go("/settings"),
                                  style=ft.ButtonStyle(color=c("#b45309", "fg"))),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            bgcolor=c("#fffbeb"),
            border=ft.border.all(1, c("#fcd34d")),
            border_radius=10,
            padding=ft.padding.only(left=12, right=4, top=2, bottom=2),
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
                show_toast(self._page, f"请填写：{'、'.join(missing)}", color="#b91c1c")
                return
            self._refresh_prompt()
        prompt = (self._prompt_field.value or "").strip()
        if not prompt:
            show_toast(self._page, "提示词为空", color="#b91c1c")
            return
        if not prompt_image_service.is_configured():
            self._config_hint.visible = True
            self._update(self._config_hint)
            show_toast(self._page, "请先在设置中配置 AI 生图 API Key", color="#b45309")
            return

        size = self._size_dd.value or "1024x1024"
        quality = self._quality_dd.value or "high"
        self._set_generating(True)
        self._page.run_task(self._generate_task, prompt, size, quality)

    async def _generate_task(self, prompt: str, size: str, quality: str) -> None:
        self._gen_started = time.time()
        self._show_loading(prompt)
        self._page.run_task(self._tick_loading)
        try:
            result = await prompt_image_service.generate_image(prompt=prompt, size=size,
                                                               quality=quality)
        except Exception as e:  # 服务层已兜底，这里防御未知异常，避免界面卡在生成中
            result = {"success": False, "error": str(e)}
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
            show_toast(self._page, f"保存失败：{e}", color="#b91c1c")

        self._last_bytes = image_bytes
        self._last_path = saved_path
        self._last_prompt = prompt
        meta = [f"{size}", f"耗时 {elapsed:.1f}s"]
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

    def _set_generating(self, on: bool) -> None:
        self._generating = on
        self._generate_btn.disabled = on
        self._generate_btn.opacity = 0.6 if on else 1.0
        self._generate_label.value = "生成中…" if on else "生成图片"
        self._update(self._generate_btn)

    # ── 右栏状态 ─────────────────────────────────────────────────────
    def _preview_state(self, icon: str, title: str, detail: str = "",
                       color: str = "#94a3b8", extra: ft.Control | None = None) -> ft.Control:
        controls: list[ft.Control] = [
            ft.Icon(icon, size=40, color=c(color, "fg")),
            _txt(title, 13, "#455c7f", weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
        ]
        if detail:
            controls.append(_txt(detail, 11, "#94a3b8", text_align=ft.TextAlign.CENTER))
        if extra:
            controls.append(extra)
        return ft.Column(controls, spacing=8, tight=True,
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _show_empty(self) -> None:
        self._preview.data = None
        self._preview.on_click = None
        self._preview.content = self._preview_state(
            ft.Icons.AUTO_FIX_HIGH_OUTLINED, "生成的图片会显示在这里",
            "选好模板、填写内容后点「生成图片」")
        self._result_actions.visible = False
        self._result_meta.value = ""
        self._update(self._preview, self._result_actions, self._result_meta)

    def _show_loading(self, prompt: str) -> None:
        waited = _txt("已等待 0 秒", 11, "#94a3b8")
        self._preview.data = waited
        self._preview.on_click = None
        self._preview.content = ft.Column(
            controls=[
                ft.ProgressRing(width=36, height=36, stroke_width=3, color=c("#005f98", "fg")),
                _txt("AI 正在创作中…", 13, "#455c7f", weight=ft.FontWeight.W_500),
                waited,
                ft.Container(
                    content=_txt(prompt, 11, "#94a3b8", max_lines=4,
                                 overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.CENTER),
                    padding=ft.padding.symmetric(horizontal=16),
                ),
            ],
            spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._result_actions.visible = False
        self._result_meta.value = "高质量通常需要 20–60 秒"
        self._update(self._preview, self._result_actions, self._result_meta)

    def _show_error(self, error: str) -> None:
        self._preview.data = None
        self._preview.on_click = None
        self._preview.content = self._preview_state(
            ft.Icons.ERROR_OUTLINE, "生成失败", error[:300], color="#b91c1c",
            extra=self._small_button("重试", ft.Icons.REFRESH, self._on_generate, primary=True),
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
                controls=[ft.Icon(ft.Icons.BROKEN_IMAGE_OUTLINED, color=c("#b91c1c", "fg")),
                          _txt("预览加载失败，图片已保存，可点「打开图片」查看", 11, "#b91c1c")],
                tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            **kw,
        )

    def _show_image(self, image_bytes: bytes | None, path: Path | None, meta: str) -> None:
        self._preview.data = None
        self._preview.content = ft.Stack(
            controls=[
                ft.Container(self._image_control(image_bytes, path), alignment=ft.Alignment(0, 0),
                             expand=True),
                ft.Container(
                    content=ft.Icon(ft.Icons.ZOOM_OUT_MAP, size=16, color=c("#ffffff", "fg")),
                    bgcolor=ft.Colors.with_opacity(0.45, "#000000"), border_radius=8, padding=6,
                    right=6, top=6, tooltip="查看大图",
                ),
            ],
            expand=True,
        )
        self._preview.on_click = lambda _e: self._open_lightbox()
        self._result_meta.value = meta
        self._result_actions.controls = [
            self._small_button("打开图片", ft.Icons.OPEN_IN_NEW, self._on_open_image),
            self._small_button("打开目录", ft.Icons.FOLDER_OPEN, self._on_open_dir),
            self._small_button("另存为", ft.Icons.DOWNLOAD, self._on_download),
            self._small_button("复用提示词", ft.Icons.REPLAY, self._on_reuse_prompt),
            self._small_button("再来一张", ft.Icons.REFRESH, self._on_generate, primary=True),
        ]
        self._result_actions.visible = True
        self._update(self._preview, self._result_meta, self._result_actions)

    # ── 最近作品 ─────────────────────────────────────────────────────
    def _render_history(self) -> None:
        history = lib.list_history()[:_HISTORY_THUMBS]
        self._history_row.controls = [self._history_thumb(h) for h in history]
        self._history_section.controls = [
            ft.Row([_txt("最近作品", 12, "#455c7f", weight=ft.FontWeight.W_500),
                    _txt(f"{len(history)}", 11, "#94a3b8")], spacing=6),
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
            border=ft.border.all(2, c("#e11d48", "fg") if current else "transparent"),
            tooltip=f"{h.get('template') or '提示词出图'} · {stamp}",
            on_click=lambda _e, h=h: self._show_history_item(h),
            ink=True,
        )

    def _show_history_item(self, h: dict) -> None:
        path = Path(h["path"])
        if not path.exists():
            show_toast(self._page, "图片文件已不存在", color="#b91c1c")
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
        if not (self._last_path or self._last_bytes):
            return
        width = (self._page.width or 1280) * 0.82
        height = (self._page.height or 800) * 0.78
        dlg = ft.AlertDialog(
            content=ft.Container(
                self._image_control(self._last_bytes, self._last_path),
                width=width, height=height, alignment=ft.Alignment(0, 0),
            ),
            content_padding=12,
            actions=[
                ft.TextButton("打开目录", on_click=self._on_open_dir),
                ft.TextButton("关闭", on_click=lambda _e: self._page.pop_dialog()),
            ],
        )
        self._page.show_dialog(dlg)

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

    async def _download_async(self) -> None:
        data = self._current_image_bytes()
        if not data:
            return
        if not hasattr(self, "_save_picker"):
            self._save_picker = ft.FilePicker()
        ext = self._last_path.suffix.lstrip(".") if self._last_path else "png"
        try:
            target = await self._save_picker.save_file(
                dialog_title="保存图片",
                file_name=f"prompt_image_{int(time.time())}.{ext or 'png'}",
                initial_directory=settings_service.get("default_output_dir", "") or str(Path.home()),
            )
        except Exception as e:
            show_toast(self._page, f"无法打开保存对话框：{e}", color="#b91c1c")
            return
        if not target:
            return
        try:
            Path(target).write_bytes(data)
            show_toast(self._page, "已保存", color="#047857")
        except OSError as e:
            show_toast(self._page, f"保存失败：{e}", color="#b91c1c")

    def _on_copy_prompt(self, _e) -> None:
        text = self._prompt_field.value or ""
        if text:
            self._page.run_task(self._copy_async, text)

    async def _copy_async(self, text: str) -> None:
        try:
            await ft.Clipboard().set(text)
            show_toast(self._page, "提示词已复制", color="#047857")
        except Exception as e:
            show_toast(self._page, f"复制失败：{e}", color="#b91c1c")

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
        name = ft.TextField(label="模板名称", value=template.get("name", ""), dense=True,
                            border_radius=10, text_size=13)
        category = ft.TextField(label="分类", value=template.get("category") or "我的模板",
                                dense=True, border_radius=10, text_size=13)
        prompt = ft.TextField(
            label="提示词", value=template.get("prompt_template", ""), multiline=True,
            min_lines=6, max_lines=12, border_radius=10, text_size=13,
            hint_text="例如：A cozy {房间} interior in {风格} style, warm light",
        )
        detected = _txt("", 11, "#005f98")

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
                show_toast(self._page, "提示词不能为空", color="#b91c1c")
                return
            item = lib.save_custom(name.value or "", prompt.value or "",
                                   category=category.value or "我的模板",
                                   default_size=template.get("default_size", "1024x1024"),
                                   template_id=editing_id)
            self._page.pop_dialog()
            show_toast(self._page, "模板已保存", color="#047857")
            self._source = lib.CUSTOM_SOURCE
            settings_service.set(_KEY_LAST_SOURCE, self._source)
            self._category = "全部"
            self._reload_library(select_id=item["id"])

        dlg = ft.AlertDialog(
            modal=True,
            title=_txt("编辑模板" if editing_id else "保存为我的模板", 16, "#162f50",
                       weight=ft.FontWeight.W_600),
            content=ft.Container(
                ft.Column([name, category, prompt, detected], spacing=12, tight=True,
                          scroll=ft.ScrollMode.AUTO,
                          horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                width=520,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _e: self._page.pop_dialog()),
                ft.FilledButton("保存", on_click=save),
            ],
        )
        self._page.show_dialog(dlg)

    def _on_delete_custom(self, _e) -> None:
        t = self._current
        if not t:
            return

        def confirm(_e) -> None:
            lib.delete_custom(t["id"])
            self._page.pop_dialog()
            self._current = None
            self._reload_library()
            show_toast(self._page, "模板已删除")

        self._page.show_dialog(ft.AlertDialog(
            modal=True,
            title=_txt("删除模板", 16, "#162f50", weight=ft.FontWeight.W_600),
            content=_txt(f"确定删除「{t['name']}」吗？此操作不可撤销。", 13),
            actions=[
                ft.TextButton("取消", on_click=lambda _e: self._page.pop_dialog()),
                ft.FilledButton("删除", on_click=confirm,
                                style=ft.ButtonStyle(bgcolor=c("#b91c1c", "fg"))),
            ],
        ))

    # ═════════════════════════════════════════════════════════════════
    # 提示词源管理
    # ═════════════════════════════════════════════════════════════════
    def _open_source_manager(self, _e=None) -> None:
        self._source_body = ft.Column(spacing=14, tight=True, scroll=ft.ScrollMode.AUTO)
        self._source_url = ft.TextField(
            hint_text="粘贴 JSON / CSV / Markdown 提示词集合的链接（支持 GitHub 文件页地址）",
            hint_style=ft.TextStyle(size=12, color=c("#94a3b8", "fg")),
            dense=True, text_size=13, border_radius=10, expand=True,
        )
        self._source_busy = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
        self._render_source_manager()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.HUB_OUTLINED, color=c("#e11d48", "fg")),
                _txt("提示词源", 16, "#162f50", weight=ft.FontWeight.W_600),
                self._source_busy,
            ], spacing=8),
            content=ft.Container(self._source_body, width=600, height=520),
            actions=[ft.TextButton("完成", on_click=self._close_source_manager)],
        )
        self._page.show_dialog(dlg)

    def _close_source_manager(self, _e) -> None:
        self._page.pop_dialog()
        self._reload_library()

    def _render_source_manager(self) -> None:
        sources = lib.list_sources()
        added_urls = {s.get("url") for s in sources}
        body: list[ft.Control] = []

        body.append(_txt("已添加", 13, "#162f50", weight=ft.FontWeight.W_600))
        if not sources:
            body.append(_txt("还没有添加外部提示词源。可从下方推荐里一键添加，或粘贴链接 / 导入本地文件。",
                             12, "#94a3b8"))
        for s in sources:
            updated = datetime.fromtimestamp(s.get("updated_at", 0)).strftime("%Y-%m-%d")
            info = f"{s.get('count', 0)} 条 · 更新于 {updated}"
            if s.get("license"):
                info += f" · {s['license']}"
            body.append(ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column([
                            _txt(s["name"], 13, "#162f50", weight=ft.FontWeight.W_500,
                                 max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            _txt(info, 11, "#94a3b8"),
                        ], spacing=2, expand=True, tight=True),
                        ft.Switch(value=s.get("enabled", True), scale=0.8, tooltip="在模板库中显示",
                                  on_change=lambda e, sid=s["id"]: self._on_source_enabled(sid, e)),
                        ft.IconButton(ft.Icons.REFRESH, icon_size=18, tooltip="重新下载",
                                      on_click=lambda _e, sid=s["id"]: self._run_source_op(
                                          lib.refresh_source(sid), "已更新")),
                        ft.IconButton(ft.Icons.OPEN_IN_NEW, icon_size=18, tooltip="打开主页",
                                      visible=bool(s.get("homepage") or s["url"].startswith("http")),
                                      on_click=lambda _e, u=s.get("homepage") or s["url"]: self._launch(u)),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18, tooltip="移除",
                                      icon_color=c("#b91c1c", "fg"),
                                      on_click=lambda _e, sid=s["id"]: self._on_remove_source(sid)),
                    ],
                    spacing=2,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=c("#f8fafc"), border_radius=10,
                padding=ft.padding.only(left=12, right=4, top=4, bottom=4),
            ))

        body.append(ft.Container(height=4))
        body.append(_txt("推荐的开源提示词库", 13, "#162f50", weight=ft.FontWeight.W_600))
        body.append(_txt("内容从 GitHub 下载到本机，版权归原作者，使用时请遵守对应许可证并保留署名。",
                         11, "#94a3b8"))
        for rec in src.RECOMMENDED_SOURCES:
            added = rec["url"] in added_urls
            body.append(ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column([
                            ft.Row([_txt(rec["name"], 13, "#162f50", weight=ft.FontWeight.W_500),
                                    self._badge(rec["license"], "#dcfce7", "#047857")], spacing=6),
                            _txt(rec["description"], 11, "#61789c"),
                        ], spacing=2, expand=True, tight=True),
                        ft.IconButton(ft.Icons.OPEN_IN_NEW, icon_size=18, tooltip="查看仓库",
                                      on_click=lambda _e, u=rec["homepage"]: self._launch(u)),
                        ft.FilledButton(
                            "已添加" if added else "添加", disabled=added,
                            on_click=lambda _e, rec=rec: self._run_source_op(
                                lib.add_source(rec["url"], rec["name"], rec["homepage"],
                                               rec["license"]), "已添加"),
                        ),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                border=ft.border.all(1, c("#e2e8f0")), border_radius=10,
                padding=ft.padding.only(left=12, right=8, top=6, bottom=6),
            ))

        body.append(ft.Container(height=4))
        body.append(_txt("添加其他来源", 13, "#162f50", weight=ft.FontWeight.W_600))
        body.append(ft.Row([
            self._source_url,
            ft.FilledButton("添加", on_click=self._on_add_url),
        ], spacing=8))
        body.append(ft.Row([
            self._small_button("从本地文件导入", ft.Icons.UPLOAD_FILE, self._on_import_file),
            self._small_button("导出我的模板", ft.Icons.IOS_SHARE, self._on_export_custom),
        ], spacing=8))
        body.append(_txt(
            "支持格式：① JSON：{\"name\": \"库名\", \"templates\": [{\"name\": ..., \"prompt\": ..., "
            "\"category\": ...}]}；② CSV：含 prompt 列，可选 title / category / tags；"
            "③ Markdown：每个标题下第一个代码块为一条提示词。提示词中的 {变量} 或 [变量] 会变成可填写项。",
            11, "#94a3b8"))
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
                           color="#047857")
            except Exception as e:
                show_toast(self._page, f"操作失败：{_friendly_error(e)}", color="#b91c1c",
                           duration=4000)
            finally:
                self._set_source_busy(False)
            self._render_source_manager()
            self._reload_library()
        self._page.run_task(runner)

    def _on_add_url(self, _e) -> None:
        url = (self._source_url.value or "").strip()
        if not url.startswith(("http://", "https://")):
            show_toast(self._page, "请输入以 http(s):// 开头的链接", color="#b91c1c")
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
            show_toast(self._page, f"无法打开文件选择器：{e}", color="#b91c1c")
            return
        if not picked or not picked[0].path:
            return
        try:
            record = lib.import_file(Path(picked[0].path))
            show_toast(self._page, f"已导入：{record['name']}（{record['count']} 条）",
                       color="#047857")
        except Exception as e:
            show_toast(self._page, f"导入失败：{_friendly_error(e)}", color="#b91c1c", duration=4000)
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
            show_toast(self._page, f"无法打开保存对话框：{e}", color="#b91c1c")
            return
        if not target:
            return
        try:
            Path(target).write_text(lib.export_custom_json(), encoding="utf-8")
            show_toast(self._page, "已导出，可分享给他人导入", color="#047857")
        except OSError as e:
            show_toast(self._page, f"导出失败：{e}", color="#b91c1c")


def _friendly_error(e: Exception) -> str:
    import httpx
    if isinstance(e, httpx.HTTPStatusError):
        return f"服务器返回 {e.response.status_code}"
    if isinstance(e, httpx.TimeoutException):
        return "下载超时，请检查网络（GitHub 在部分网络下需要代理）"
    if isinstance(e, httpx.HTTPError):
        return "无法连接，请检查网络或链接（GitHub 在部分网络下需要代理）"
    return str(e) or e.__class__.__name__
