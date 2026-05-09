"""提示词出图页 — 从模板选择 → 填表 → AI 生图 → 预览下载。

布局：
  Header（SubPageHeader）
  ├── 左侧 380px：搜索 + 分类标签 + 模板卡片网格（2 列）
  └── 右侧 expand：
        表单（变量输入）→ 预览（组装后的完整 prompt）→ 生成按钮 → 结果图

视觉：
  主色 #005F98 / 激活 #00A3FF，卡片 r=16，选中态 #F0F7FF + #005F98 边框。
"""
from __future__ import annotations

import base64
import subprocess
import sys
import time
from pathlib import Path

import flet as ft

from core.prompt_image import templates as tpl
from services import prompt_image_service, settings_service
from ui.components.sub_page_header import SubPageHeader
from ui.utils import show_toast


class PromptImagePage(ft.Column):
    """提示词出图主页面。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self._current_template: dict | None = None
        self._current_category: str = "全部"
        self._search_keyword: str = ""
        self._var_controls: dict[str, ft.Control] = {}
        self._generating: bool = False
        self._last_image_bytes: bytes | None = None
        self._last_image_path: Path | None = None

        # 先构建各动态区域，后续事件回调直接访问
        self._search_field = ft.TextField(
            hint_text="搜索模板（名称 / 标签）",
            hint_style=ft.TextStyle(color="#94a3b8", size=13),
            prefix_icon=ft.Icons.SEARCH,
            border_radius=12,
            bgcolor="#f8fafc",
            border_color="transparent",
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            on_change=self._on_search_change,
        )
        self._category_bar = ft.Row(spacing=8, wrap=True, run_spacing=8)
        self._template_grid = ft.Column(spacing=12)

        self._form_area = ft.Column(spacing=12)
        self._prompt_preview = ft.TextField(
            value="",
            read_only=True,
            multiline=True,
            min_lines=4,
            max_lines=8,
            text_style=ft.TextStyle(
                font_family="JetBrains Mono", size=13, color="#162f50",
            ),
            border_radius=12,
            bgcolor="#f8fafc",
            border_color="transparent",
        )
        self._size_dropdown = ft.Dropdown(
            value="1024x1024",
            options=[
                ft.dropdown.Option("1024x1024", "1:1 方形 (1024×1024)"),
                ft.dropdown.Option("1024x1536", "2:3 竖版 (1024×1536)"),
                ft.dropdown.Option("1536x1024", "3:2 横版 (1536×1024)"),
                ft.dropdown.Option("auto", "自动"),
            ],
            border_radius=12,
            expand=True,
        )
        self._quality_dropdown = ft.Dropdown(
            value="high",
            options=[
                ft.dropdown.Option("low", "低（快速）"),
                ft.dropdown.Option("medium", "中（平衡）"),
                ft.dropdown.Option("high", "高（精细）"),
                ft.dropdown.Option("auto", "自动"),
            ],
            border_radius=12,
            expand=True,
        )

        self._generate_btn = self._build_generate_button()
        self._loading_row = ft.Row(
            controls=[
                ft.ProgressRing(width=20, height=20, stroke_width=2, color="#005f98"),
                ft.Text("AI 正在创作中...", size=13, color="#455c7f",
                        font_family="42dot Sans"),
            ],
            spacing=10,
            visible=False,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._config_hint = self._build_config_hint()

        # 结果区
        self._result_image = ft.Image(
            src_base64=None,
            width=800, height=600,
            fit=ft.ImageFit.CONTAIN,
            border_radius=12,
            visible=False,
        )
        self._result_meta = ft.Text("", size=12, color="#455c7f",
                                    font_family="42dot Sans")
        self._result_actions = ft.Row(spacing=10, visible=False)
        self._result_area = ft.Container(
            content=ft.Column(
                controls=[
                    self._result_image,
                    self._result_meta,
                    self._result_actions,
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            visible=False,
        )
        self._result_empty = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.AUTO_FIX_HIGH_OUTLINED, size=36, color="#94a3b8"),
                    ft.Text("尚未生成，点击上方按钮开始创作",
                            size=13, color="#94a3b8", font_family="42dot Sans"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=24),
            alignment=ft.Alignment(0, 0),
        )

        self.controls = [
            SubPageHeader(
                title="提示词出图",
                icon=ft.Icons.AUTO_FIX_HIGH,
                icon_color="#e11d48",
                icon_bg="#fff1f2",
                on_back=lambda: self._page.go("/"),
            ),
            ft.Container(
                content=ft.Text(
                    "选择模板，填写关键信息，AI 自动生成精美图片",
                    size=14, color="#455c7f", font_family="42dot Sans",
                ),
                padding=ft.padding.only(left=32, right=32, bottom=16),
            ),
            self._build_body(),
        ]

        self._render_category_bar()
        self._render_template_grid()
        # 默认选中第一个模板
        if tpl.TEMPLATES:
            self._select_template(tpl.TEMPLATES[0])

    # ── 主体布局 ──────────────────────────────────────────────────────
    def _build_body(self) -> ft.Control:
        left = ft.Container(
            content=ft.Column(
                controls=[
                    self._search_field,
                    self._category_bar,
                    self._template_grid,
                ],
                spacing=16,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=380,
            padding=ft.padding.all(16),
            bgcolor="#ffffff",
            border_radius=16,
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 2),
            ),
        )

        right = ft.Container(
            content=ft.Column(
                controls=[
                    self._section("变量", self._form_area),
                    self._section("提示词预览", self._prompt_preview),
                    self._section(
                        "生成参数",
                        ft.Row(
                            controls=[
                                self._labeled("图片尺寸", self._size_dropdown),
                                self._labeled("生成质量", self._quality_dropdown),
                            ],
                            spacing=16,
                        ),
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._config_hint,
                                self._generate_btn,
                                self._loading_row,
                            ],
                            spacing=12,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    self._section("生成结果",
                                  ft.Stack(controls=[
                                      self._result_empty,
                                      self._result_area,
                                  ])),
                ],
                spacing=24,
                expand=True,
            ),
            expand=True,
            padding=ft.padding.all(24),
            bgcolor="#ffffff",
            border_radius=16,
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 2),
            ),
        )

        return ft.Container(
            content=ft.Row(
                controls=[left, right],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
                expand=True,
            ),
            padding=ft.padding.only(left=32, right=32, bottom=32),
            expand=True,
        )

    def _section(self, title: str, body: ft.Control) -> ft.Control:
        return ft.Column(
            controls=[
                ft.Text(
                    title, size=14, weight=ft.FontWeight.W_600,
                    color="#162f50", font_family="42dot Sans",
                ),
                body,
            ],
            spacing=8,
        )

    def _labeled(self, label: str, body: ft.Control) -> ft.Control:
        return ft.Column(
            controls=[
                ft.Text(label, size=12, color="#455c7f", font_family="42dot Sans"),
                body,
            ],
            spacing=4,
            expand=True,
        )

    # ── 分类栏 ────────────────────────────────────────────────────────
    def _render_category_bar(self) -> None:
        self._category_bar.controls.clear()
        for cat in tpl.CATEGORIES:
            is_active = cat == self._current_category
            chip = ft.Container(
                content=ft.Text(
                    cat, size=12,
                    color="#ffffff" if is_active else "#455c7f",
                    font_family="42dot Sans",
                    weight=ft.FontWeight.W_500,
                ),
                bgcolor="#005f98" if is_active else "#f1f5f9",
                border_radius=9999,
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                on_click=lambda e, c=cat: self._on_category_change(c),
                ink=True,
            )
            self._category_bar.controls.append(chip)
        if self._category_bar.page:
            self._category_bar.update()

    def _on_category_change(self, cat: str) -> None:
        self._current_category = cat
        self._render_category_bar()
        self._render_template_grid()

    def _on_search_change(self, e: ft.ControlEvent) -> None:
        self._search_keyword = (e.data or "").strip()
        self._render_template_grid()

    # ── 模板网格 ──────────────────────────────────────────────────────
    def _render_template_grid(self) -> None:
        self._template_grid.controls.clear()
        items = tpl.get_templates(self._current_category, self._search_keyword)
        if not items:
            self._template_grid.controls.append(
                ft.Container(
                    content=ft.Text(
                        "没有匹配的模板", size=12, color="#94a3b8",
                        font_family="42dot Sans",
                    ),
                    padding=ft.padding.symmetric(vertical=16),
                    alignment=ft.Alignment(0, 0),
                )
            )
        else:
            # 2 列网格
            for i in range(0, len(items), 2):
                row_items = items[i:i + 2]
                row = ft.Row(
                    controls=[self._build_template_card(t) for t in row_items],
                    spacing=10,
                )
                # 单行不足 2 项时补空位保持对齐
                if len(row_items) == 1:
                    row.controls.append(ft.Container(expand=True))
                self._template_grid.controls.append(row)
        if self._template_grid.page:
            self._template_grid.update()

    def _build_template_card(self, template: dict) -> ft.Control:
        is_selected = (self._current_template is not None
                       and self._current_template["id"] == template["id"])
        icon_name = getattr(ft.Icons, template.get("icon", "IMAGE"), ft.Icons.IMAGE)

        tag_row = ft.Row(
            spacing=4,
            controls=[
                ft.Container(
                    content=ft.Text(
                        tag, size=9, color="#005f98",
                        font_family="42dot Sans", weight=ft.FontWeight.W_500,
                    ),
                    bgcolor="#dee9ff",
                    border_radius=9999,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                )
                for tag in template.get("tags", [])[:2]
            ],
            wrap=True,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon_name, color="#e11d48", size=22),
                        width=36, height=36,
                        bgcolor="#fff1f2",
                        border_radius=10,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        template["name"], size=13,
                        weight=ft.FontWeight.W_600,
                        color="#162f50", font_family="42dot Sans",
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        template["description"], size=11, color="#455c7f",
                        font_family="42dot Sans",
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    tag_row,
                ],
                spacing=6,
                tight=True,
            ),
            bgcolor="#f0f7ff" if is_selected else "#ffffff",
            border=ft.border.all(
                2 if is_selected else 1,
                "#005f98" if is_selected else "#e2e8f0",
            ),
            border_radius=12,
            padding=ft.padding.all(12),
            on_click=lambda e, t=template: self._select_template(t),
            ink=True,
            expand=True,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    # ── 模板选中 → 渲染表单 ──────────────────────────────────────────
    def _select_template(self, template: dict) -> None:
        self._current_template = template
        self._var_controls.clear()
        # 用模板默认尺寸回填 size 下拉
        default_size = template.get("default_size", "1024x1024")
        if default_size in [o.key for o in self._size_dropdown.options]:
            self._size_dropdown.value = default_size
        self._render_form()
        self._render_template_grid()
        self._update_prompt_preview()
        if self._size_dropdown.page:
            self._size_dropdown.update()

    def _render_form(self) -> None:
        self._form_area.controls.clear()
        if not self._current_template:
            return

        for var in self._current_template["variables"]:
            name = var["name"]
            var_type = var.get("type", "text")
            label = var["label"]
            required = var.get("required", False)
            default = var.get("default", "")
            placeholder = var.get("placeholder", "")

            if var_type == "select":
                ctrl = ft.Dropdown(
                    value=default or (var.get("options") or [""])[0],
                    options=[ft.dropdown.Option(o) for o in var.get("options", [])],
                    border_radius=12,
                    expand=True,
                    on_change=lambda _e: self._update_prompt_preview(),
                )
            elif var_type == "textarea":
                ctrl = ft.TextField(
                    value=default,
                    hint_text=placeholder,
                    multiline=True,
                    min_lines=3, max_lines=6,
                    border_radius=12,
                    bgcolor="#f8fafc",
                    border_color="transparent",
                    on_change=lambda _e: self._update_prompt_preview(),
                )
            else:  # text
                ctrl = ft.TextField(
                    value=default,
                    hint_text=placeholder,
                    border_radius=12,
                    bgcolor="#f8fafc",
                    border_color="transparent",
                    on_change=lambda _e: self._update_prompt_preview(),
                )

            self._var_controls[name] = ctrl

            label_text = f"{label}{' *' if required else ''}"
            self._form_area.controls.append(
                ft.Column(
                    controls=[
                        ft.Text(label_text, size=12, color="#455c7f",
                                font_family="42dot Sans"),
                        ctrl,
                    ],
                    spacing=4,
                )
            )

        if self._form_area.page:
            self._form_area.update()

    def _collect_values(self) -> dict:
        values = {}
        for name, ctrl in self._var_controls.items():
            values[name] = (ctrl.value or "").strip() if isinstance(ctrl.value, str) else (ctrl.value or "")
        return values

    def _update_prompt_preview(self) -> None:
        if not self._current_template:
            return
        prompt = tpl.assemble_prompt(self._current_template, self._collect_values())
        self._prompt_preview.value = prompt
        if self._prompt_preview.page:
            self._prompt_preview.update()

    # ── 生成按钮 & 配置提示 ──────────────────────────────────────────
    def _build_generate_button(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_FIX_HIGH, color="#ffffff", size=18),
                    ft.Text(
                        "生成图片", size=15, color="#ffffff",
                        font_family="42dot Sans", weight=ft.FontWeight.W_600,
                    ),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=["#005f98", "#6b1ef3"],
            ),
            border_radius=12,
            padding=ft.padding.symmetric(vertical=12, horizontal=40),
            shadow=ft.BoxShadow(
                blur_radius=15, spread_radius=-3,
                color=ft.Colors.with_opacity(0.25, "#005f98"),
                offset=ft.Offset(0, 6),
            ),
            on_click=self._on_generate,
            ink=True,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    def _build_config_hint(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, color="#b45309", size=16),
                    ft.Text(
                        "尚未配置 AI 生图 API Key，点击右侧按钮前往设置",
                        size=12, color="#92400e", font_family="42dot Sans",
                    ),
                    ft.Container(expand=True),
                    ft.TextButton(
                        "去设置",
                        on_click=lambda _e: self._page.go("/settings"),
                        style=ft.ButtonStyle(color="#b45309"),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            bgcolor="#fffbeb",
            border=ft.border.all(1, "#fcd34d"),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            visible=not prompt_image_service.is_configured(),
        )

    # ── 生成流程 ──────────────────────────────────────────────────────
    def _on_generate(self, _e) -> None:
        if self._generating:
            return
        if not self._current_template:
            show_toast(self._page, "请先选择一个模板")
            return

        # 必填校验
        values = self._collect_values()
        missing = [
            v["label"] for v in self._current_template["variables"]
            if v.get("required") and not values.get(v["name"])
        ]
        if missing:
            show_toast(self._page, f"请填写必填项：{', '.join(missing)}", color="#b91c1c")
            return

        if not prompt_image_service.is_configured():
            self._config_hint.visible = True
            self._config_hint.update()
            show_toast(self._page, "请先在设置中配置 AI 生图 API Key", color="#b45309")
            return

        self._update_prompt_preview()
        prompt = self._prompt_preview.value or ""
        size = self._size_dropdown.value or "1024x1024"
        quality = self._quality_dropdown.value or "high"

        self._set_generating(True)
        self._page.run_task(self._generate_task, prompt, size, quality)

    async def _generate_task(self, prompt: str, size: str, quality: str) -> None:
        started_at = time.time()
        result = await prompt_image_service.generate_image(
            prompt=prompt, size=size, quality=quality,
        )
        elapsed = time.time() - started_at

        self._set_generating(False)

        if not result.get("success"):
            show_toast(
                self._page,
                f"生成失败：{result.get('error', '未知错误')}",
                color="#b91c1c", duration=4000,
            )
            return

        image_bytes = result.get("image_bytes") or b""
        if not image_bytes:
            show_toast(self._page, "生成失败：未获取到图片数据", color="#b91c1c")
            return

        # 保存到本地
        try:
            saved_path = prompt_image_service.save_image(image_bytes)
        except Exception as e:
            saved_path = None
            show_toast(self._page, f"保存失败：{e}", color="#b91c1c")

        self._last_image_bytes = image_bytes
        self._last_image_path = saved_path
        self._show_result(image_bytes, saved_path, size, elapsed)

    def _set_generating(self, on: bool) -> None:
        self._generating = on
        self._loading_row.visible = on
        self._generate_btn.disabled = on
        self._generate_btn.opacity = 0.6 if on else 1.0
        self._page.update()

    def _show_result(
        self,
        image_bytes: bytes,
        saved_path: Path | None,
        size: str,
        elapsed: float,
    ) -> None:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        self._result_image.src_base64 = b64
        self._result_image.visible = True
        self._result_empty.visible = False
        self._result_area.visible = True

        meta_parts = [f"尺寸：{size}", f"耗时：{elapsed:.1f}s"]
        if saved_path:
            meta_parts.append(f"保存至：{saved_path}")
        self._result_meta.value = "  ·  ".join(meta_parts)

        self._result_actions.controls = [
            self._action_btn("下载", ft.Icons.DOWNLOAD, self._on_download),
            self._action_btn("打开目录", ft.Icons.FOLDER_OPEN, self._on_open_dir),
            self._action_btn("复制提示词", ft.Icons.COPY_ALL, self._on_copy_prompt),
            self._action_btn("重新生成", ft.Icons.REFRESH, self._on_generate),
        ]
        self._result_actions.visible = True
        self._page.update()

    def _action_btn(self, label: str, icon: str, on_click) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color="#005f98", size=14),
                    ft.Text(label, size=12, color="#005f98",
                            font_family="42dot Sans"),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#ffffff",
            border=ft.border.all(1, "#d5e3ff"),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            on_click=on_click,
            ink=True,
        )

    # ── 结果区操作 ────────────────────────────────────────────────────
    def _on_download(self, _e) -> None:
        if not self._last_image_bytes:
            return
        self._page.run_task(self._download_async)

    async def _download_async(self) -> None:
        picker = ft.FilePicker()
        self._page.overlay.append(picker)
        self._page.update()
        try:
            default_dir = settings_service.get("default_output_dir", "") or str(Path.home())
            try:
                target = await picker.save_file_async(
                    dialog_title="保存图片",
                    file_name=f"prompt_image_{int(time.time())}.png",
                    initial_directory=default_dir,
                )
            except AttributeError:
                target = await picker.save_file(
                    dialog_title="保存图片",
                    file_name=f"prompt_image_{int(time.time())}.png",
                    initial_directory=default_dir,
                )
        except Exception as e:
            show_toast(self._page, f"无法打开保存对话框：{e}", color="#b91c1c")
            target = None
        finally:
            try:
                self._page.overlay.remove(picker)
                self._page.update()
            except Exception:
                pass

        if not target:
            return
        try:
            Path(target).write_bytes(self._last_image_bytes or b"")
            show_toast(self._page, "已保存", color="#047857")
        except Exception as e:
            show_toast(self._page, f"保存失败：{e}", color="#b91c1c")

    def _on_open_dir(self, _e) -> None:
        target = self._last_image_path
        if not target:
            return
        directory = str(target.parent)
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", directory])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", directory])
            else:
                subprocess.Popen(["xdg-open", directory])
        except Exception:
            show_toast(self._page, "无法打开目录", color="#b91c1c")

    def _on_copy_prompt(self, _e) -> None:
        text = self._prompt_preview.value or ""
        if not text:
            return
        try:
            self._page.set_clipboard(text)
            show_toast(self._page, "提示词已复制", color="#047857")
        except Exception as e:
            show_toast(self._page, f"复制失败：{e}", color="#b91c1c")
