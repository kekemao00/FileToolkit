"""OCR 文字识别 — 基于 Figma 设计稿 1:1 还原

布局：左侧主内容区（标题+拖拽区+文件信息/进度/结果） + 右侧参数面板
遵循核心模式：三视图互斥切换、并排按钮、文件列表、拖拽区
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import flet as ft

from core.ocr.client import recognize
from services import history_service, settings_service
from services.task_service import run_task

# 语言选项（并排按钮）
_LANGUAGES = [
    {"key": "chi_sim", "label": "简体中文"},
    {"key": "eng", "label": "English"},
    {"key": "chi_sim+eng", "label": "中英混合"},
    {"key": "jpn", "label": "日本語"},
]

_INPUT_EXTS = {"png", "jpg", "jpeg", "bmp", "tiff", "tif", "pdf"}


class OcrPage(ft.Column):
    """OCR 文字识别 — 工作台布局。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._input_file: Path | None = None
        self._task: asyncio.Task | None = None
        self._output_file: Path | None = None
        self._result_text_value: str = ""

        # 处理中视图组件
        self._progress_title = ft.Text(
            "", size=30, weight=ft.FontWeight.W_600, color="#162f50",
            font_family="42dot Sans",
        )
        self._progress_pct = ft.Text(
            "0%", size=30, weight=ft.FontWeight.BOLD, color="#005f98",
            font_family="42dot Sans",
        )
        self._progress_bar = ft.ProgressBar(
            value=0, color="#005f98", bgcolor="#d5e3ff", bar_height=10,
            border_radius=5,
        )
        self._progress_desc = ft.Text(
            "", size=13, color="#455c7f", font_family="42dot Sans",
        )
        self._progress_cancel_btn = ft.FilledButton(
            "取消识别",
            style=ft.ButtonStyle(bgcolor="#be123c", color="#ffffff"),
            on_click=lambda _: self._cancel(),
        )

        # 结果视图组件
        self._result_title = ft.Text(
            "", size=30, weight=ft.FontWeight.W_600, color="#162f50",
            font_family="42dot Sans",
        )
        self._result_text = ft.TextField(
            multiline=True,
            min_lines=10,
            max_lines=18,
            read_only=False,
            border_radius=12,
            border_color="#e2e8f0",
            text_size=14,
            color="#162f50",
            value="",
        )
        # 摘要字段
        self._sum_lang = ft.Text("--", size=13, color="#162f50",
                                 weight=ft.FontWeight.W_500, font_family="42dot Sans")
        self._sum_chars = ft.Text("--", size=13, color="#162f50",
                                  weight=ft.FontWeight.W_500, font_family="42dot Sans")
        self._sum_paras = ft.Text("--", size=13, color="#162f50",
                                  weight=ft.FontWeight.W_500, font_family="42dot Sans")
        self._sum_status = ft.Text("--", size=13, color="#162f50",
                                   weight=ft.FontWeight.W_500, font_family="42dot Sans")

        # 语言选择（并排按钮）
        self._language_value = "chi_sim"
        self._lang_btns: list[ft.Container] = []
        for lang in _LANGUAGES:
            self._lang_btns.append(self._make_lang_btn(lang["key"], lang["label"]))

        # 文件名显示
        self._file_name = ft.Text("", size=14, color="#162f50",
                                  font_family="42dot Sans")
        self._file_info_container = ft.Container(visible=False)

        # 运行按钮
        self._run_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DOCUMENT_SCANNER, color="#ffffff", size=20),
                    ft.Text("开始识别", size=18, color="#ffffff",
                            font_family="42dot Sans"),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#005f98",
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=["#005f98", "#00a3ff"],
            ),
            border_radius=16,
            padding=ft.padding.symmetric(vertical=16),
            shadow=ft.BoxShadow(
                blur_radius=25, spread_radius=-5,
                color=ft.Colors.with_opacity(0.2, "#005f98"),
                offset=ft.Offset(0, 20),
            ),
            on_click=self._start_task,
            ink=True,
            opacity=0.4,
        )

        self._main_content = self._build_main_content()
        self._build_param_panel()

        self._NARROW_BREAKPOINT = 800
        self._is_narrow = None
        self._body_container: ft.Control = ft.Container()
        self._topbar = self._build_topbar()

        self.controls = [self._topbar, self._body_container]
        self._apply_responsive_layout(update=False)

        self._prev_on_resize = None

    def did_mount(self) -> None:
        self._prev_on_resize = self._page.on_resize
        self._page.on_resize = self._on_page_resized

    def will_unmount(self) -> None:
        if self._page.on_resize == self._on_page_resized:
            self._page.on_resize = self._prev_on_resize

    def _build_topbar(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.SEARCH, color="#94a3b8", size=15),
                                            ft.Container(
                                                content=ft.Text("搜索功能或指令...", size=13, color="#94a3b8"),
                                                padding=ft.padding.only(left=8),
                                                expand=True,
                                            ),
                                        ],
                                        spacing=0,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    width=288, height=54,
                                    bgcolor=ft.Colors.with_opacity(0.5, "#f8fafc"),
                                    border=ft.border.all(1, ft.Colors.with_opacity(0.6, "#e2e8f0")),
                                    border_radius=9999,
                                    padding=ft.padding.symmetric(horizontal=15),
                                    opacity=0.45,
                                    tooltip="搜索",
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                                    icon_color="#475569", icon_size=20,
                                    disabled=True, opacity=0.45,
                                    tooltip="通知",
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SETTINGS_OUTLINED,
                                    icon_color="#475569", icon_size=20,
                                    on_click=lambda _: self._page.go("/settings"),
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=80,
            bgcolor="#ffffff",
            shadow=ft.BoxShadow(
                blur_radius=2, color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
            padding=ft.padding.symmetric(horizontal=32),
        )

    def _build_main_content(self) -> ft.Control:
        self._workspace_view = self._build_workspace_view()
        self._processing_view = self._build_processing_view()
        self._complete_view = self._build_complete_view()
        self._processing_view.visible = False
        self._complete_view.visible = False

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._workspace_view,
                    self._processing_view,
                    self._complete_view,
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )

    def _build_workspace_view(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "OCR 文字识别", size=30,
                                            weight=ft.FontWeight.W_500,
                                            color="#005f98",
                                            font_family="42dot Sans",
                                        ),
                                        ft.Text(
                                            "图片 / 扫描件 / PDF 文字识别",
                                            size=16, color="#455c7f",
                                            font_family="42dot Sans",
                                        ),
                                    ],
                                    spacing=4,
                                ),
                                ft.Container(expand=True),
                                self._build_engine_badge(),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                        padding=ft.padding.only(left=32, right=32, top=32),
                    ),
                    self._build_drop_zone(),
                    self._build_file_info(),
                ],
                spacing=24,
            ),
        )

    def _build_engine_badge(self) -> ft.Control:
        """本地引擎就绪徽章（Tesseract + pypdf 都走本地）。"""
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.VERIFIED, color="#006571", size=12),
                    ft.Text(
                        "本地引擎就绪", size=10, color="#006571",
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.2, "#00e3fd"),
            border_radius=9999,
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
        )

    def _build_drop_zone(self) -> ft.Control:
        dash_color = ft.Colors.with_opacity(0.3, "#005f98")

        def dash_segment() -> ft.Container:
            return ft.Container(
                width=16, height=2, bgcolor=dash_color, border_radius=9999,
            )

        def dash_column() -> ft.Container:
            return ft.Container(
                width=2, height=16, bgcolor=dash_color, border_radius=9999,
            )
        top_dash = ft.Row(
            controls=[dash_segment() for _ in range(30)],
            spacing=8,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        side_dash = ft.Column(
            controls=[dash_column() for _ in range(10)],
            spacing=8,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        body = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.DOCUMENT_SCANNER,
                                        color="#005f98", size=40),
                        width=72, height=72,
                        bgcolor=ft.Colors.with_opacity(0.12, "#005f98"),
                        border_radius=9999,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "拖放文件或点击扫描",
                        size=18, color="#005f98",
                        font_family="42dot Sans",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "支持 JPG / PNG / BMP / TIFF / PDF",
                        size=14, color="#455c7f",
                        font_family="42dot Sans",
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=36, horizontal=24),
            expand=True,
            on_click=self._pick_file,
            ink=True,
        )
        self._drop_zone_body = ft.Container(
            content=ft.Stack(
                controls=[
                    ft.Container(content=body, expand=True, padding=ft.padding.all(0)),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                top_dash,
                                ft.Row(
                                    controls=[
                                        side_dash,
                                        ft.Container(expand=True),
                                        side_dash,
                                    ],
                                    expand=True,
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                top_dash,
                            ],
                            spacing=10,
                            expand=True,
                        ),
                        padding=ft.padding.all(12),
                        ignore_interactions=True,
                        expand=True,
                    ),
                ],
            ),
            border_radius=20,
            bgcolor="#F4F6FF",
            on_hover=self._on_drop_zone_hover,
            ink=False,
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        self._drop_zone_wrapper = ft.Container(
            content=self._drop_zone_body,
            padding=ft.padding.symmetric(horizontal=32),
            height=260,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )
        return self._drop_zone_wrapper

    def _on_drop_zone_hover(self, e: ft.ControlEvent) -> None:
        self._drop_zone_body.bgcolor = (
            ft.Colors.with_opacity(0.06, "#005f98") if e.data == "true"
            else "#F4F6FF"
        )
        self._drop_zone_body.update()

    def _build_file_info(self) -> ft.Control:
        self._file_info_container = ft.Container(
            visible=False,
            padding=ft.padding.symmetric(horizontal=32),
            content=ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.INSERT_DRIVE_FILE, color="#005f98", size=18,
                            ),
                            width=36, height=36,
                            bgcolor=ft.Colors.with_opacity(0.15, "#005f98"),
                            border_radius=10,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(
                            controls=[
                                self._file_name,
                                ft.Text("准备识别", size=11, color="#455c7f"),
                            ],
                            spacing=2, tight=True, expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_color="#94a3b8",
                            icon_size=16,
                            tooltip="移除",
                            on_click=self._remove_file,
                        ),
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#ffffff",
                border_radius=16,
                border=ft.border.all(1, "#e2e8f0"),
                padding=ft.padding.all(16),
            ),
        )
        return self._file_info_container

    def _build_param_panel(self) -> ft.Control:
        self._param_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "参数设置", size=20, weight=ft.FontWeight.W_500,
                        color="#005f98", font_family="42dot Sans",
                    ),
                    self._section("识别语言", ft.Column(
                        controls=[
                            ft.Row(controls=[self._lang_btns[0], self._lang_btns[1]],
                                   spacing=8),
                            ft.Row(controls=[self._lang_btns[2], self._lang_btns[3]],
                                   spacing=8),
                        ],
                        spacing=8,
                    )),
                    self._run_btn,
                    ft.Text("本地处理 • 隐私保护已开启", size=10, color="#455c7f",
                            font_family="42dot Sans", text_align=ft.TextAlign.CENTER),
                ],
                spacing=24,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            width=320,
            bgcolor="#f4f6ff",
            border_radius=16,
            border=ft.border.only(left=ft.BorderSide(1, "#d5e3ff")),
            padding=ft.padding.all(24),
        )
        return self._param_panel

    def _section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(controls=[
            ft.Text(label.upper(), size=12, color="#455c7f",
                    font_family="42dot Sans"),
            content,
        ], spacing=12)

    def _make_lang_btn(self, key: str, label: str) -> ft.Container:
        active = key == getattr(self, "_language_value", "chi_sim")
        return ft.Container(
            content=ft.Text(
                label, size=13, weight=ft.FontWeight.W_600,
                color="#ffffff" if active else "#162f50",
                text_align=ft.TextAlign.CENTER,
                font_family="42dot Sans",
            ),
            bgcolor="#005f98" if active else "#ffffff",
            border=ft.border.all(1, "#005f98" if active else "#e2e8f0"),
            border_radius=10,
            padding=ft.padding.symmetric(vertical=10),
            on_click=lambda _, k=key: self._select_lang(k),
            ink=True,
            data=key,
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

    def _select_lang(self, key: str) -> None:
        self._language_value = key
        for btn in self._lang_btns:
            active = btn.data == key
            btn.bgcolor = "#005f98" if active else "#ffffff"
            btn.border = ft.border.all(1, "#005f98" if active else "#e2e8f0")
            btn.content.color = "#ffffff" if active else "#162f50"
        self.update()

    def _build_processing_view(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                self._progress_title,
                                ft.Container(expand=True),
                                self._progress_pct,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.only(bottom=8),
                    ),
                    self._progress_bar,
                    self._progress_desc,
                    ft.Row(controls=[ft.Container(expand=True),
                                     self._progress_cancel_btn]),
                ],
                spacing=12,
            ),
            bgcolor="#ffffff",
            border=ft.border.all(1, "#e2e8f0"),
            border_radius=16,
            padding=ft.padding.all(24),
            margin=ft.margin.symmetric(horizontal=32),
        )

    def _build_complete_view(self) -> ft.Container:
        summary_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "文档摘要", size=16,
                        weight=ft.FontWeight.W_600,
                        color="#162f50", font_family="42dot Sans",
                    ),
                    ft.Divider(height=1, color="#e2e8f0"),
                    self._build_summary_row("识别语言", self._sum_lang),
                    self._build_summary_row("字符数", self._sum_chars),
                    self._build_summary_row("段落数", self._sum_paras),
                    self._build_summary_row("状态", self._sum_status),
                    ft.Container(expand=True),
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "复制文本",
                                style=ft.ButtonStyle(
                                    bgcolor="#f1f5f9", color="#005f98"),
                                on_click=self._copy_result,
                            ),
                            ft.FilledButton(
                                "保存 TXT",
                                style=ft.ButtonStyle(
                                    bgcolor="#005f98", color="#ffffff"),
                                on_click=self._save_result,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.FilledButton(
                        "打开所在文件夹",
                        style=ft.ButtonStyle(color="#455c7f"),
                        on_click=self._open_output_folder,
                    ),
                    ft.TextButton(
                        "继续识别",
                        style=ft.ButtonStyle(color="#455c7f"),
                        on_click=lambda _: self._reset(),
                    ),
                ],
                spacing=8,
            ),
            bgcolor="#ffffff",
            border=ft.border.all(1, "#d1fae5"),
            border_radius=16,
            padding=ft.padding.all(16),
            width=260,
        )

        result_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.CHECK_CIRCLE,
                                                color="#16a34a", size=22),
                                width=36, height=36,
                                bgcolor="#d1fae5",
                                border_radius=9999,
                                alignment=ft.Alignment(0, 0),
                            ),
                            self._result_title,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self._result_text,
                ],
                spacing=12,
            ),
            bgcolor="#ffffff",
            border=ft.border.all(1, "#e2e8f0"),
            border_radius=16,
            padding=ft.padding.all(16),
            expand=True,
        )

        return ft.Container(
            content=ft.Row(
                controls=[result_panel, summary_panel],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            margin=ft.margin.symmetric(horizontal=32),
        )

    def _build_summary_row(self, label: str, value_text: ft.Text) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(label, size=13, color="#455c7f",
                            font_family="42dot Sans"),
                    ft.Container(expand=True),
                    value_text,
                ],
            ),
            padding=ft.padding.symmetric(vertical=8),
            border=ft.border.only(
                bottom=ft.BorderSide(
                    1, ft.Colors.with_opacity(0.3, "#e2e8f0")),
            ),
        )

    # ── 响应式 ──────────────────────────────────────────────
    def _apply_responsive_layout(self, update: bool = True) -> None:
        width = self._page.width or 1000
        narrow = width < self._NARROW_BREAKPOINT
        if narrow == self._is_narrow:
            return
        self._is_narrow = narrow
        if narrow:
            self._param_panel.width = None
            self._param_panel.border_radius = 0
            self._param_panel.border = ft.border.only(
                top=ft.BorderSide(1, "#d5e3ff"))
            new_body = ft.Column(
                controls=[self._main_content, self._param_panel],
                expand=True, spacing=0, scroll=ft.ScrollMode.AUTO,
            )
        else:
            self._param_panel.width = 320
            self._param_panel.border_radius = 16
            self._param_panel.border = ft.border.only(
                left=ft.BorderSide(1, "#d5e3ff"))
            new_body = ft.Row(
                controls=[self._main_content, self._param_panel],
                expand=True, spacing=0,
            )
        self._body_container = new_body
        self.controls[1] = new_body
        if update:
            self.update()

    def _on_page_resized(self, e) -> None:
        self._apply_responsive_layout()

    # ── 事件处理 ────────────────────────────────────────────
    def _pick_file(self, _) -> None:
        self._page.run_task(self._pick_file_async)

    async def _pick_file_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        try:
            files = await picker.pick_files(
                dialog_title="选择图片或扫描件",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=list(_INPUT_EXTS),
                allow_multiple=False,
            )
        except RuntimeError:
            self._show_snack("无法打开文件选择器，请检查系统环境")
            return
        if not files:
            self._page.update()
            return
        paths = [Path(f.path) for f in files if f.path]
        if paths:
            self._input_file = paths[0]
            self._file_name.value = self._input_file.name
            self._file_info_container.visible = True
            self._run_btn.opacity = 1.0
            self._drop_zone_wrapper.height = 140
        self._page.update()

    def _remove_file(self, _) -> None:
        self._input_file = None
        self._file_info_container.visible = False
        self._run_btn.opacity = 0.4
        self._drop_zone_wrapper.height = 260
        self.update()

    def _start_task(self, _) -> None:
        if not self._input_file:
            self._show_snack("请先选择要识别的文件")
            return
        kwargs = {
            "input_file": self._input_file,
            "language": self._language_value,
        }
        self._show_processing(self._input_file.name)

        async def _run():
            await run_task(recognize, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, current, total, desc):
        if total > 0:
            self._progress_bar.value = current / total
            pct = int(current / total * 100)
            self._progress_pct.value = f"{pct}%"
        self._progress_desc.value = desc or "正在处理..."
        self._processing_view.update()

    def _on_complete(self, result):
        from core.models import TaskResult, TaskStatus

        if isinstance(result, TaskResult):
            if result.status == TaskStatus.FAILED:
                text = ""
                err = result.error_message or "识别失败"
                self._result_title.value = f"识别失败：{err[:60]}"
                self._result_title.color = "#dc2626"
                self._sum_status.value = "失败"
                self._sum_status.color = "#dc2626"
            else:
                # 优先从保存的 txt 读取
                text = ""
                if result.output_files:
                    self._output_file = result.output_files[0]
                    try:
                        text = self._output_file.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        text = ""
                if not text and result.error_message:
                    # 客户端将文本存在 error_message 供 UI 读取（已在 client 约定）
                    text = result.error_message
                self._result_title.value = "识别完成！"
                self._result_title.color = "#16a34a"
                self._sum_status.value = "成功"
                self._sum_status.color = "#16a34a"
        elif isinstance(result, dict):
            text = result.get("text", "")
            self._result_title.value = "识别完成！"
            self._result_title.color = "#16a34a"
        else:
            text = str(result) if result else ""
            self._result_title.value = "识别完成！"
            self._result_title.color = "#16a34a"

        self._result_text_value = text
        self._result_text.value = text

        # 摘要
        lang_label = next((lg["label"] for lg in _LANGUAGES
                           if lg["key"] == self._language_value), "--")
        self._sum_lang.value = lang_label
        self._sum_chars.value = str(len(text))
        self._sum_paras.value = str(len([p for p in text.split("\n") if p.strip()]))

        history_service.save_task(
            "ocr", "recognize", result,
            input_desc=self._input_file.name if self._input_file else "",
        )
        self._show_complete()

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._reset_to_workspace()

    def _reset(self) -> None:
        self._input_file = None
        self._output_file = None
        self._result_text_value = ""
        self._result_text.value = ""
        self._file_info_container.visible = False
        self._drop_zone_wrapper.height = 260
        self._run_btn.opacity = 0.4
        self._reset_to_workspace()

    def _reset_to_workspace(self) -> None:
        self._workspace_view.visible = True
        self._processing_view.visible = False
        self._complete_view.visible = False
        self.update()

    def _show_processing(self, file_label: str) -> None:
        self._progress_title.value = f"正在识别 {file_label}…"
        self._progress_pct.value = "0%"
        self._progress_bar.value = 0
        self._progress_desc.value = "初始化引擎…"
        self._workspace_view.visible = False
        self._processing_view.visible = True
        self._complete_view.visible = False
        self.update()

    def _show_complete(self) -> None:
        self._workspace_view.visible = False
        self._processing_view.visible = False
        self._complete_view.visible = True
        self.update()

    def _copy_result(self, _) -> None:
        if self._result_text.value:
            self._page.set_clipboard(self._result_text.value)
            self._show_snack("已复制到剪贴板")

    def _save_result(self, _) -> None:
        if not self._result_text.value or not self._input_file:
            self._show_snack("无可保存的识别结果")
            return
        out_dir = settings_service.resolve_output_dir(self._input_file)
        out_path = out_dir / f"{self._input_file.stem}_ocr.txt"
        try:
            out_path.write_text(self._result_text.value, encoding="utf-8")
            self._output_file = out_path
            self._show_snack(f"已保存到 {out_path}")
        except OSError as exc:
            self._show_snack(f"保存失败：{exc}", color="#be123c")

    def _open_output_folder(self, _) -> None:
        target = self._output_file
        if not target or not target.exists():
            self._show_snack("输出文件不存在或尚未保存")
            return
        folder = target.parent
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(target)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _show_snack(self, msg: str, color: str = "#005f98") -> None:
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text(msg), bgcolor=color, duration=2200,
        )
        self._page.snack_bar.open = True
        self._page.update()
