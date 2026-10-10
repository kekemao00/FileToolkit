"""AI 智能任务页 — 一句话找到工具的智能入口

布局：居中的一列 —— 墨黑图标块 + 标题 + 副标题、建议任务、输入框（白卡片）、
附件、拆出来的步骤、三条能力说明。无渐变、无光晕、无阴影；只有发送按钮是墨黑实心。
需求在本地按功能目录匹配（ui/intent.py），不联网；点"打开"带着附件进入对应工作台。
"""
from pathlib import Path

import flet as ft

from ui import style as s
from ui.features import Feature
from ui.handoff import set_pending_files
from ui.intent import plan_steps
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
    "一句话找到对应工具",
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
            content_padding=ft.Padding.symmetric(horizontal=4, vertical=6),
            on_focus=lambda e: self._focus_console(True),
            on_blur=lambda e: self._focus_console(False),
        )

        self._plan = ft.Column(spacing=0, visible=False)

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
                    padding=ft.Padding.only(left=s.PAGE_X, right=s.PAGE_X, top=72, bottom=40),
                    content=ft.Column(
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            self._build_hero_section(),
                            ft.Container(height=28),
                            self._build_prompt_suggestions(),
                            ft.Container(height=12),
                            self._build_input_console(),
                            ft.Container(content=self._attach_list, padding=ft.Padding.only(top=10)),
                            ft.Container(content=self._plan, padding=ft.Padding.only(top=16)),
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
                s.text("想对文件做什么？", "headline", size=24, text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),
                s.text(
                    "用一句话描述需求，我会拆成步骤并找到对应的工具，带着你的文件直接打开。",
                    "body", "ink-2", size=14, text_align=ft.TextAlign.CENTER,
                ),
            ],
        )

    # ── 交互区域 ──────────────────────────────────────
    def _build_prompt_suggestions(self) -> ft.Control:
        buttons = []
        for item in _PROMPT_SUGGESTIONS:
            btn = ft.Container(
                bgcolor=c("surface"),
                border=ft.Border.all(1, c("line")),
                border_radius=999,
                height=32,
                padding=ft.Padding.symmetric(horizontal=12),
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
            border=ft.Border.all(1, c("line")),
            bgcolor=c("surface"),
            padding=ft.Padding.only(left=14, right=10, top=10, bottom=10),
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
        console.border = ft.Border.all(1.5 if on else 1, c("accent" if on else "line"))
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
        self._on_submit(None)

    def _on_submit(self, _) -> None:
        text = (self._input_field.value or "").strip()
        if not text:
            self._show_snack("请先输入任务描述", kind="info")
            return
        steps = plan_steps(text, self._attached_files)
        self._render_plan(steps)
        self._page.update()

    # ── 步骤列表 ──────────────────────────────────────
    def _render_plan(self, steps: list[Feature]) -> None:
        self._plan.visible = True
        if not steps:
            self._plan.controls = [s.card(ft.Column(spacing=6, controls=[
                s.text("没找到对应的工具", "title"),
                s.text("换个说法试试，比如「PDF 转 Word」「压缩视频」「图片加水印」，"
                       "或用顶部搜索框按功能名查找。", "small"),
            ]), padding=ft.Padding.all(16))]
            return
        rows = [self._step_row(i, f, first=i == 0) for i, f in enumerate(steps)]
        note = ("点「打开」进入对应工具，附加的文件会一起带过去。"
                if len(steps) == 1 else
                "按顺序逐步完成：第一步会带上附加的文件，之后每一步选上一步生成的文件。")
        self._plan.controls = [s.card(ft.Column(spacing=0, controls=[
            s.text("我理解的步骤", "title"),
            ft.Container(height=8),
            *rows,
            ft.Container(height=10),
            s.text(note, "small", "ink-3"),
        ]), padding=ft.Padding.only(left=16, right=16, top=14, bottom=14))]

    def _step_row(self, index: int, feature: Feature, first: bool) -> ft.Control:
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=8),
            border=ft.Border.only(top=ft.BorderSide(1, c("line"))) if index else None,
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Container(
                        width=22, height=22, border_radius=11, bgcolor=c("surface-3"),
                        alignment=ft.Alignment(0, 0),
                        content=s.text(str(index + 1), "caption", "ink-2"),
                    ),
                    ft.Icon(feature.icon, color=c("ink-2", "fg"), size=18),
                    ft.Column(spacing=0, expand=True, controls=[
                        s.text(feature.title, "label", "ink"),
                        s.text(feature.group, "caption", "ink-3"),
                    ]),
                    s.button("打开", lambda _, f=feature, carry=first: self._open_step(f, carry),
                             kind="primary" if first else "secondary"),
                ],
            ),
        )

    def _open_step(self, feature: Feature, carry_files: bool) -> None:
        set_pending_files(self._attached_files if carry_files else [])
        self._page.go(feature.route)

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
                border=ft.Border.all(1, c("line")),
                border_radius=999,
                height=30,
                padding=ft.Padding.only(left=10, right=2),
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

    def _show_snack(self, msg: str, color: str | None = None, duration: int = 2200,
                    kind: str | None = None) -> None:
        show_toast(self._page, msg, duration=duration, color=color, kind=kind)
