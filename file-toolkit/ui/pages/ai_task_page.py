"""AI 智能任务页 — 暖灰黑白风格

布局：居中的一列 —— 墨黑图标块 + 标题 + 副标题、建议任务、输入框（白卡片）、
附件、三条能力说明。无渐变、无光晕、无阴影；只有发送按钮是墨黑实心。
AI 服务未配置时给出明确提示，不使用"即将上线"。
"""
from pathlib import Path

import flet as ft

from services import settings_service
from ui import style as s
from ui.palette import c
from ui.utils import show_toast

# Prompt 建议按钮数据
_PROMPT_SUGGESTIONS = [
    {"icon": ft.Icons.IMAGE_OUTLINED, "label": "图片转PDF并加水印"},
    {"icon": ft.Icons.MOVIE_OUTLINED, "label": "压缩视频并提取音频"},
    {"icon": ft.Icons.DRIVE_FILE_RENAME_OUTLINE, "label": "批量重命名图片"},
]

# 底部能力说明
_STATUS_INDICATORS = [
    "支持 50+ 种格式",
    "本地处理，文件不上传",
    "自动编排多步流程",
]

_MAX_WIDTH = 680


class AiTaskPage(ft.Column):
    """AI 智能任务：标题区 + 输入框 + 能力说明。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._attached_files: list[Path] = []

        self._input_field = ft.TextField(
            hint_text="描述您想完成的任务…",
            hint_style=ft.TextStyle(color=c("ink-3", "fg"), size=14, font_family=s.FONT),
            text_style=ft.TextStyle(color=c("ink", "fg"), size=14, font_family=s.FONT),
            border=ft.InputBorder.NONE,
            cursor_color=c("ink"),
            selection_color=ft.Colors.with_opacity(0.3, c("accent")),
            expand=True,
            multiline=True,
            min_lines=2,
            max_lines=6,
            dense=True,
            content_padding=ft.padding.symmetric(horizontal=4, vertical=6),
            on_focus=lambda e: self._focus_console(True),
            on_blur=lambda e: self._focus_console(False),
        )

        self._attach_list = ft.Row(
            controls=[],
            wrap=True,
            spacing=6,
            run_spacing=6,
            visible=False,
        )

        self.controls = [self._build_content()]

    # ── 整体内容 ──────────────────────────────────────
    def _build_content(self) -> ft.Control:
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=_MAX_WIDTH,
                    padding=ft.padding.only(left=s.PAGE_X, right=s.PAGE_X, top=72, bottom=40),
                    content=ft.Column(
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            self._build_hero_section(),
                            ft.Container(height=28),
                            self._build_prompt_suggestions(),
                            ft.Container(height=12),
                            self._build_input_console(),
                            ft.Container(content=self._attach_list, padding=ft.padding.only(top=10)),
                            ft.Container(height=20),
                            self._build_status_indicators(),
                        ],
                    ),
                ),
            ],
        )

    # ── 标题区 ──────────────────────────────────────
    def _build_hero_section(self) -> ft.Control:
        return ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            controls=[
                ft.Container(
                    width=48, height=48, border_radius=14, bgcolor=c("ink"),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED, color=c("on-ink", "fg"), size=22),
                ),
                ft.Container(height=20),
                s.text("你好，我是文件全能王 AI 助手", "headline", size=24,
                       text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),
                s.text(
                    "告诉我您的需求，我会把它拆成步骤，调用本机的 PDF、图片、音视频等工具自动完成。",
                    "body", "ink-2", size=14, text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=12),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(width=6, height=6, border_radius=3, bgcolor=c("line-strong")),
                            s.text("功能开发中，配置 API Key 后可试用", "caption", "ink-2"),
                        ],
                        spacing=7, tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    border=ft.border.all(1, c("line")),
                    border_radius=999,
                ),
            ],
        )

    # ── 交互区域 ──────────────────────────────────────
    def _build_prompt_suggestions(self) -> ft.Control:
        buttons = []
        for item in _PROMPT_SUGGESTIONS:
            btn = ft.Container(
                bgcolor=c("surface"),
                border=ft.border.all(1, c("line")),
                border_radius=999,
                height=32,
                padding=ft.padding.symmetric(horizontal=12),
                on_click=lambda _, lbl=item["label"]: self._use_suggestion(lbl),
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(item["icon"], color=c("ink-2", "fg"), size=14),
                        s.text(item["label"], "label", "ink", size=12.5),
                    ],
                ),
            )
            buttons.append(s.hover_surface(btn))

        return ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
            controls=buttons,
            wrap=True,
            run_spacing=8,
        )

    def _build_input_console(self) -> ft.Control:
        """白色输入卡片：文本区在上，附件 / 语音 / 发送在下。聚焦时描边换成强调色。"""
        send_btn = ft.Container(
            width=34, height=34,
            border_radius=17,
            bgcolor=c("ink"),
            alignment=ft.Alignment(0, 0),
            tooltip="发送",
            on_click=self._on_submit,
            animate=s.snappy(),
            content=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED, color=c("on-ink", "fg"), size=18),
        )
        send_btn.on_hover = lambda e: self._send_hover(send_btn, e)

        self._console = ft.Container(
            border_radius=s.R_PANEL,
            border=ft.border.all(1, c("line")),
            bgcolor=c("surface"),
            padding=ft.padding.only(left=14, right=10, top=10, bottom=10),
            animate=s.snappy(),
            content=ft.Column(
                spacing=6,
                controls=[
                    self._input_field,
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                        controls=[
                            s.icon_button(ft.Icons.ATTACH_FILE_OUTLINED, self._on_attach, "附加文件"),
                            s.icon_button(ft.Icons.MIC_NONE_OUTLINED, self._on_mic, "语音输入"),
                            ft.Container(expand=True),
                            send_btn,
                        ],
                    ),
                ],
            ),
        )
        return self._console

    def _build_status_indicators(self) -> ft.Control:
        items = []
        for label in _STATUS_INDICATORS:
            items.append(ft.Row(
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.CHECK_ROUNDED, size=13, color=c("ink-3", "fg")),
                    s.text(label, "small", "ink-3"),
                ],
            ))
        return ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=18,
            wrap=True,
            run_spacing=6,
            controls=items,
        )

    # ── 事件处理 ──────────────────────────────────────
    def _focus_console(self, on: bool) -> None:
        console = getattr(self, "_console", None)
        if console is None:
            return
        console.border = ft.border.all(1.5 if on else 1, c("accent" if on else "line"))
        try:
            console.update()
        except RuntimeError:
            pass

    @staticmethod
    def _send_hover(btn: ft.Container, e: ft.ControlEvent) -> None:
        on = e.data in (True, "true")
        btn.bgcolor = c("ink-hover" if on else "ink")
        btn.update()

    def _use_suggestion(self, label: str) -> None:
        self._input_field.value = label
        self._input_field.update()

    def _on_submit(self, _) -> None:
        text = (self._input_field.value or "").strip()
        if not text:
            self._show_snack("请先输入任务描述", kind="info")
            return

        # 检查 AI 服务配置
        api_key = settings_service.get_ai_api_key() if hasattr(
            settings_service, "get_ai_api_key") else None
        if not api_key:
            self._show_snack(
                "AI 服务配置中，请在「设置」中配置 API Key 后使用",
                kind="warning",
                duration=3000,
            )
            return

        # 已配置时的处理入口（后端服务就绪后接入）
        self._show_snack("正在解析任务…", kind="info")

    def _on_attach(self, _) -> None:
        self._page.run_task(self._pick_attach_async)

    async def _pick_attach_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        try:
            files = await picker.pick_files(
                dialog_title="选择附件",
                allow_multiple=True,
            )
        except RuntimeError:
            self._show_snack("无法打开文件选择器，请检查系统环境", kind="error")
            return
        if not files:
            self._page.update()
            return
        paths = [Path(f.path) for f in files if f.path]
        if paths:
            self._attached_files.extend(paths)
            self._rebuild_attach_list()
        self._page.update()

    def _rebuild_attach_list(self) -> None:
        self._attach_list.controls.clear()
        has_files = bool(self._attached_files)
        self._attach_list.visible = has_files
        for f in self._attached_files:
            chip = ft.Container(
                bgcolor=c("surface"),
                border=ft.border.all(1, c("line")),
                border_radius=999,
                height=30,
                padding=ft.padding.only(left=10, right=2),
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, color=c("ink-2", "fg"), size=14),
                        s.text(f.name, "small", "ink", max_lines=1,
                               overflow=ft.TextOverflow.ELLIPSIS),
                        s.icon_button(ft.Icons.CLOSE_ROUNDED, lambda _, path=f: self._remove_attach(path),
                                      "移除", size=26, color="ink-3"),
                    ],
                ),
            )
            self._attach_list.controls.append(chip)

    def _remove_attach(self, path: Path) -> None:
        if path in self._attached_files:
            self._attached_files.remove(path)
        self._rebuild_attach_list()
        self._page.update()

    def _on_mic(self, _) -> None:
        self._show_snack("语音输入需要系统麦克风权限，请在系统设置中授权后重试")

    def _show_snack(self, msg: str, color: str | None = None, duration: int = 2200,
                    kind: str | None = None) -> None:
        show_toast(self._page, msg, duration=duration, color=color, kind=kind)
