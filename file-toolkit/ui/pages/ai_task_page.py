"""AI 智能任务页 — 一句话描述需求，大模型规划方案，确认后在本机自动执行。

两种模式：
  - 已配置大模型：对话式。模型调用工具规划出方案（PlanCard），用户点「开始执行」后按步骤
    在本机处理，上一步的产物自动交给下一步；可以继续对话调整方案或追加处理。
  - 未配置：本地关键词匹配（ui/intent.py），拆成步骤后点「打开」带着附件进入对应工作台。

布局：空状态时居中一列（图标块 + 标题、模型状态、建议任务、输入框、能力说明）；
开始对话后变为顶部标题栏 + 中间对话流 + 底部固定输入框。
"""
import asyncio
from pathlib import Path

import flet as ft

from services import llm_service
from services.agent_service import AgentReply, AgentSession
from services.llm_service import LlmError
from services.task_service import run_task
from ui import style as s
from ui.components.plan_card import BROKEN, CANCELLED, EXECUTING, FINISHED, READY, STALE, PlanCard
from ui.features import Feature
from ui.handoff import set_pending_files
from ui.intent import plan_steps
from ui.palette import c
from ui.utils import is_mounted, notify_task_done, show_toast

# Prompt 建议按钮数据
_PROMPT_SUGGESTIONS = [
    {"icon": ft.Icons.IMAGE_OUTLINED, "label": "图片合成 PDF 并压缩"},
    {"icon": ft.Icons.WATER_DROP_OUTLINED, "label": "PDF 加「内部资料」水印再加密"},
    {"icon": ft.Icons.MOVIE_OUTLINED, "label": "视频压到 720p 并提取音频"},
    {"icon": ft.Icons.ARTICLE_OUTLINED, "label": "合并这些 PDF 再转成 Markdown"},
]

_STATUS_INDICATORS = [
    "支持 50+ 种格式",
    "本地处理，文件不上传",
    "一句话自动完成多步处理",
]

_MAX_WIDTH = 760


def _safe_update(control: ft.Control) -> None:
    if is_mounted(control):
        try:
            control.update()
        except RuntimeError:
            pass


class AiTaskPage(ft.Column):
    """AI 智能任务：对话式规划 + 本地执行。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._config = llm_service.get_config()
        self._session: AgentSession | None = None
        self._attached_files: list[Path] = []
        self._cards: list[PlanCard] = []
        self._busy = False
        self._exec_task = None
        self._thinking: ft.Control | None = None
        self._last_text = ""
        self._scroller: ft.Column | None = None

        self._input_field = ft.TextField(
            hint_text="描述您想完成的任务，例如「把这些照片合成 PDF，压缩到 5MB 以内」",
            hint_style=ft.TextStyle(color=c("ink-3", "fg"), size=14, font_family=s.FONT),
            text_style=ft.TextStyle(color=c("ink", "fg"), size=14, font_family=s.FONT),
            border=ft.InputBorder.NONE,
            cursor_color=c("ink"),
            selection_color=ft.Colors.with_opacity(0.3, c("accent")),
            expand=True,
            multiline=True,
            shift_enter=True,
            min_lines=2,
            max_lines=6,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=4, vertical=6),
            on_submit=self._on_submit,
            on_focus=lambda e: self._focus_console(True),
            on_blur=lambda e: self._focus_console(False),
        )
        self._plan = ft.Column(spacing=0, visible=False)   # 离线模式的步骤列表
        self._attach_list = ft.Row(controls=[], wrap=True, spacing=6, run_spacing=6, visible=False)
        self._feed = ft.Column(spacing=16)
        self._console = self._build_input_console()
        self._render()

    @property
    def _online(self) -> bool:
        return self._config.ready

    # ── 布局 ────────────────────────────────────────────────────────────
    def _render(self) -> None:
        if self._feed.controls:
            self.controls = [self._build_conversation()]
        else:
            self.controls = [self._build_empty()]

    def _column(self, *controls: ft.Control, top: float = 0, bottom: float = 0) -> ft.Control:
        """居中、限宽的一列。"""
        return ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[
            ft.Container(
                width=_MAX_WIDTH,
                padding=ft.Padding.only(left=s.PAGE_X, right=s.PAGE_X, top=top, bottom=bottom),
                content=ft.Column(spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                  controls=list(controls)),
            ),
        ])

    def _build_empty(self) -> ft.Control:
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[self._column(
                self._build_hero_section(),
                ft.Container(height=14),
                self._build_model_status(),
                ft.Container(height=22),
                self._build_prompt_suggestions(),
                ft.Container(height=12),
                ft.Container(content=self._attach_list, padding=ft.Padding.only(bottom=8)),
                self._console,
                ft.Container(content=self._plan, padding=ft.Padding.only(top=16)),
                ft.Container(height=20),
                self._build_status_indicators(),
                top=64, bottom=40,
            )],
        )

    def _build_conversation(self) -> ft.Control:
        header = ft.Container(
            padding=ft.Padding.only(left=s.PAGE_X, right=s.PAGE_X - 8, top=18, bottom=10),
            border=ft.Border.only(bottom=ft.BorderSide(1, c("line"))),
            content=ft.Row(controls=[
                ft.Container(
                    width=28, height=28, border_radius=8, bgcolor=c("ink"), alignment=ft.Alignment(0, 0),
                    content=ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED, color=c("on-ink", "fg"), size=15),
                ),
                s.text("AI 智能任务", "title"),
                self._model_chip(),
                ft.Container(expand=True),
                s.button("新对话", self._new_conversation, kind="ghost", icon=ft.Icons.ADD_COMMENT_OUTLINED),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )
        body = self._scroller = ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO,
            controls=[self._column(self._feed, top=20, bottom=20)],
        )
        footer = self._column(
            ft.Container(content=self._attach_list, padding=ft.Padding.only(bottom=8)),
            self._console,
            ft.Container(height=6),
            s.text("只发送文字需求和文件名、类型、大小等信息给模型，文件内容不会上传", "caption", "ink-3",
                   text_align=ft.TextAlign.CENTER),
            top=8, bottom=16,
        )
        return ft.Column(expand=True, spacing=0, controls=[header, body, footer])

    # ── 标题区 / 模型状态 ─────────────────────────────────────────────────
    def _build_hero_section(self) -> ft.Control:
        sub = ("用一句话描述需求，AI 会规划好每一步，确认后在本机自动处理，上一步的结果直接交给下一步。"
               if self._online else
               "用一句话描述需求，我会拆成步骤并找到对应的工具，带着你的文件直接打开。")
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
                s.text(sub, "body", "ink-2", size=14, text_align=ft.TextAlign.CENTER),
            ],
        )

    def _model_chip(self) -> ft.Control:
        cfg = self._config
        return ft.Container(
            bgcolor=c("surface-2"), border_radius=999, padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            tooltip="在「设置 → AI 模型」中更换",
            on_click=lambda _: self._page.go("/settings"),
            content=ft.Row(controls=[
                ft.Container(width=6, height=6, border_radius=3, bgcolor=c("accent")),
                s.text(f"{cfg.label} · {cfg.model}", "caption", "ink-2", max_lines=1,
                       overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _build_model_status(self) -> ft.Control:
        if self._online:
            return ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[self._model_chip()])
        return ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[
            ft.Container(
                bgcolor=c("surface-2"), border_radius=999, padding=ft.Padding.only(left=12, right=4, top=2, bottom=2),
                content=ft.Row(controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=c("ink-3", "fg")),
                    s.text("未配置大模型，当前为本地匹配模式", "small", "ink-2"),
                    ft.TextButton("去配置", on_click=lambda _: self._page.go("/settings"),
                                  style=ft.ButtonStyle(color=c("accent-fg"), padding=ft.Padding.symmetric(horizontal=8),
                                                       text_style=ft.TextStyle(size=12, font_family=s.FONT))),
                ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ),
        ])

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
        return ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=8, controls=buttons, wrap=True, run_spacing=8)

    def _build_input_console(self) -> ft.Container:
        """白色输入卡片：文本区在上，附件 / 发送在下。聚焦时描边换成强调色。"""
        self._send_btn = ft.Container(
            width=34, height=34,
            border_radius=17,
            bgcolor=c("ink"),
            alignment=ft.Alignment(0, 0),
            tooltip="发送（Enter）",
            on_click=self._on_submit,
            animate=s.snappy(),
            content=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED, color=c("on-ink", "fg"), size=18),
        )
        self._send_btn.on_hover = lambda e: self._send_hover(self._send_btn, e)
        return ft.Container(
            border_radius=s.R_PANEL,
            border=ft.Border.all(1, c("line")),
            bgcolor=c("surface"),
            padding=ft.Padding.only(left=14, right=10, top=10, bottom=10),
            animate=s.snappy(),
            content=ft.Column(spacing=6, controls=[
                self._input_field,
                ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, controls=[
                    s.icon_button(ft.Icons.ATTACH_FILE_OUTLINED, self._on_attach, "附加文件"),
                    s.icon_button(ft.Icons.CREATE_NEW_FOLDER_OUTLINED, self._on_attach_folder, "附加文件夹"),
                    ft.Container(expand=True),
                    self._send_btn,
                ]),
            ]),
        )

    def _build_status_indicators(self) -> ft.Control:
        items = []
        for label in _STATUS_INDICATORS:
            items.append(ft.Row(spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Icon(ft.Icons.CHECK_ROUNDED, size=13, color=c("ink-3", "fg")),
                s.text(label, "small", "ink-3"),
            ]))
        return ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=18, wrap=True, run_spacing=6, controls=items)

    # ── 对话流里的元素 ───────────────────────────────────────────────────
    @staticmethod
    def _avatar() -> ft.Control:
        return ft.Container(
            width=26, height=26, border_radius=8, bgcolor=c("ink"), alignment=ft.Alignment(0, 0),
            content=ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED, color=c("on-ink", "fg"), size=14),
        )

    def _assistant_row(self, content: ft.Control) -> ft.Control:
        return ft.Row(controls=[self._avatar(), ft.Container(content=content, expand=True)],
                      spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)

    def _user_bubble(self, text: str, files: list[Path]) -> ft.Control:
        controls: list[ft.Control] = [s.text(text, "body", selectable=True)]
        if files:
            names = "、".join(p.name for p in files[:3]) + (f" 等 {len(files)} 个" if len(files) > 3 else "")
            controls.append(ft.Row(controls=[
                ft.Icon(ft.Icons.ATTACH_FILE_OUTLINED, size=13, color=c("ink-3", "fg")),
                s.text(names, "caption", "ink-2", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.START))
        return ft.Row(alignment=ft.MainAxisAlignment.END, controls=[
            ft.Container(
                content=ft.Column(controls=controls, spacing=6, tight=True),
                bgcolor=c("surface-3"),
                border_radius=ft.BorderRadius.only(top_left=14, top_right=14, bottom_left=14, bottom_right=4),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                width=min(520, max(160, 26 + s.text_width(text, 13.5))),
            ),
        ])

    def _assistant_text(self, text: str) -> ft.Control:
        return self._assistant_row(ft.Container(
            content=s.text(text, "body", selectable=True), padding=ft.Padding.only(top=3)))

    def _thinking_row(self, label: str) -> ft.Control:
        return self._assistant_row(ft.Row(controls=[
            ft.ProgressRing(width=14, height=14, stroke_width=2, color=c("ink-2")),
            s.text(label, "small", "ink-2"),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def _error_row(self, err: LlmError) -> ft.Control:
        buttons: list[ft.Control] = []
        if err.kind in ("auth", "not_found", "no_tools", "config", "bad_request"):
            buttons.append(s.button("去设置", lambda _: self._page.go("/settings"), kind="secondary",
                                    icon=ft.Icons.SETTINGS_OUTLINED, height=30))
        if err.kind not in ("config",) and self._last_text:
            buttons.append(s.button("重试", lambda _: self._retry(), kind="secondary",
                                    icon=ft.Icons.REFRESH_ROUNDED, height=30))
        return self._assistant_row(ft.Container(
            bgcolor=c("danger-soft"), border_radius=12, padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            content=ft.Column(spacing=8, tight=True, controls=[
                ft.Row(controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=16, color=c("danger", "fg")),
                    s.text(str(err), "body", "ink", expand=True, selectable=True),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
                *([ft.Row(controls=buttons, spacing=8)] if buttons else []),
            ]),
        ))

    def _append(self, control: ft.Control) -> None:
        first = not self._feed.controls
        self._feed.controls.append(control)
        if first:
            self._render()
            self._page.update()
        else:
            _safe_update(self._feed)
        self._scroll_to_end()

    def _scroll_to_end(self) -> None:
        # 新消息加在内层 feed 里，外层的 auto_scroll 感知不到，得主动滚到底
        if self._scroller is not None and is_mounted(self._scroller):
            self._page.run_task(self._scroll_end_async)

    async def _scroll_end_async(self) -> None:
        await asyncio.sleep(0.1)  # 等新内容完成布局，否则滚到的是旧的底部
        try:
            if self._scroller is not None:
                await self._scroller.scroll_to(offset=-1, duration=250)
        except Exception:
            pass

    def _remove_thinking(self) -> None:
        if self._thinking is not None and self._thinking in self._feed.controls:
            self._feed.controls.remove(self._thinking)
        self._thinking = None

    # ── 事件：输入与发送 ─────────────────────────────────────────────────
    def _focus_console(self, on: bool) -> None:
        console = getattr(self, "_console", None)
        if console is None:
            return
        console.border = ft.Border.all(1.5 if on else 1, c("accent" if on else "line"))
        _safe_update(console)

    @staticmethod
    def _send_hover(btn: ft.Container, e: ft.ControlEvent) -> None:
        on = e.data in (True, "true")
        btn.bgcolor = c("ink-hover" if on else "ink")
        btn.update()

    def _use_suggestion(self, label: str) -> None:
        self._input_field.value = label
        _safe_update(self._input_field)
        self._on_submit(None)

    def _on_submit(self, _) -> None:
        text = (self._input_field.value or "").strip()
        if not text:
            self._show_snack("请先输入任务描述", kind="info")
            return
        if not self._online:
            steps = plan_steps(text, self._attached_files)
            self._render_plan(steps)
            self._page.update()
            return
        if self._busy:
            self._show_snack("请等当前任务完成", kind="info")
            return
        files = list(self._attached_files)
        self._input_field.value = ""
        self._attached_files.clear()
        self._rebuild_attach_list()
        self._ask(text, files)

    def _ask(self, text: str, files: list[Path]) -> None:
        if self._session is None:
            self._session = AgentSession(self._config)
        for card in self._cards:
            if card.state in (READY, BROKEN, CANCELLED):
                card.set_state(STALE)
        self._last_text = text
        self._append(self._user_bubble(text, files))
        self._start_thinking("正在规划…")

        session = self._session
        self._page.run_task(self._await_reply, lambda: session.send(text, files))

    async def _await_reply(self, request) -> None:
        try:
            reply = await request()
        except LlmError as e:
            self._on_error(e)
            return
        except Exception as e:  # 网络库等意外错误也要回到可用状态
            self._on_error(LlmError(f"规划失败：{e}"))
            return
        self._on_reply(reply)

    def _retry(self) -> None:
        session = self._session
        if self._busy or session is None:
            return
        self._start_thinking("正在重试…")
        self._page.run_task(self._await_reply, session.retry)

    def _start_thinking(self, label: str) -> None:
        self._busy = True
        self._set_input_enabled(False)
        self._thinking = self._thinking_row(label)
        self._append(self._thinking)

    def _done_thinking(self) -> None:
        self._busy = False
        self._remove_thinking()
        self._set_input_enabled(True)

    def _set_input_enabled(self, on: bool) -> None:
        self._send_btn.opacity = 1 if on else 0.4
        _safe_update(self._send_btn)

    def _on_reply(self, reply: AgentReply) -> None:
        self._done_thinking()
        if reply.text:
            self._feed.controls.append(self._assistant_text(reply.text))
        if reply.plan is not None:
            card = PlanCard(reply.plan, self._run_card, self._cancel_card, self._revise_card)
            self._cards.append(card)
            self._feed.controls.append(ft.Container(content=card, padding=ft.Padding.only(left=38)))
        _safe_update(self._feed)
        self._scroll_to_end()

    def _on_error(self, err: LlmError) -> None:
        self._done_thinking()
        self._feed.controls.append(self._error_row(err))
        _safe_update(self._feed)
        self._scroll_to_end()

    def _new_conversation(self, _=None) -> None:
        if self._exec_task is not None and not self._exec_task.done():
            self._show_snack("正在执行，请先取消或等待完成", kind="info")
            return
        self._session = None
        self._cards.clear()
        self._feed.controls.clear()
        self._attached_files.clear()
        self._rebuild_attach_list()
        self._busy = False
        self._config = llm_service.get_config()
        self._render()
        self._page.update()

    # ── 执行方案 ────────────────────────────────────────────────────────
    def _run_card(self, card: PlanCard) -> None:
        session = self._session
        if session is None or session.plan is not card.plan or self._busy:
            if card.state != STALE:
                self._show_snack("请等当前任务完成" if self._busy else "这个方案已经失效，请重新描述需求",
                                 kind="info")
            return
        card.reset_failed()
        self._busy = True
        self._set_input_enabled(False)
        card.out_dir = card.out_dir or session.task_dir()
        card.set_state(EXECUTING)

        async def runner(fn, kwargs, on_progress):
            box: dict = {}
            await run_task(fn, kwargs, on_progress, lambda r: box.setdefault("r", r))
            return box["r"]

        async def _run() -> None:
            try:
                report = await session.execute(runner, card.update_step, card.out_dir, self._last_text)
            except asyncio.CancelledError:
                card.set_state(CANCELLED)
                self._busy = False
                self._set_input_enabled(True)
                raise
            self._busy = False
            self._set_input_enabled(True)
            if report.ok:
                card.set_state(FINISHED, report)
                notify_task_done(self._page, report.output_dir)
            else:
                card.set_state(CANCELLED if report.cancelled else BROKEN, report)
            if card is self._cards[-1]:
                self._scroll_to_end()  # 结果区让卡片变高了

        self._exec_task = self._page.run_task(_run)

    def _cancel_card(self, card: PlanCard) -> None:
        if self._exec_task is not None and not self._exec_task.done():
            self._exec_task.cancel()
        show_toast(self._page, "已取消，已经生成的文件会保留")

    def _revise_card(self, card: PlanCard) -> None:
        session = self._session
        if session is None or self._busy:
            return
        card.set_state(STALE)
        self._append(self._user_bubble("让 AI 根据失败原因调整方案", []))
        self._start_thinking("正在调整方案…")
        self._page.run_task(self._await_reply, session.revise)

    # ── 离线模式：本地匹配的步骤列表 ─────────────────────────────────────
    def _render_plan(self, steps: list[Feature]) -> None:
        self._plan.visible = True
        if not steps:
            self._plan.controls = [s.card(ft.Column(spacing=6, controls=[
                s.text("没找到对应的工具", "title"),
                s.text("换个说法试试，比如「PDF 转 Word」「压缩视频」「图片加水印」，"
                       "或用顶部搜索框按功能名查找。配置大模型后可以理解更复杂的需求并自动执行。", "small"),
            ]), padding=ft.Padding.all(16))]
            return
        rows = [self._step_row(i, f, first=i == 0) for i, f in enumerate(steps)]
        note = ("点「打开」进入对应工具，附加的文件会一起带过去。"
                if len(steps) == 1 else
                "按顺序逐步完成：第一步会带上附加的文件，之后每一步选上一步生成的文件。"
                "配置大模型后可以一键自动执行全部步骤。")
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

    # ── 附件 ────────────────────────────────────────────────────────────
    def _on_attach(self, _) -> None:
        self._page.run_task(self._pick_attach_async)

    def _on_attach_folder(self, _) -> None:
        self._page.run_task(self._pick_folder_async)

    def _picker(self) -> ft.FilePicker:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        return self._file_picker

    async def _pick_attach_async(self) -> None:
        try:
            files = await self._picker().pick_files(dialog_title="选择附件", allow_multiple=True)
        except RuntimeError:
            self._show_snack("无法打开文件选择器，请检查系统环境", kind="error")
            return
        if files:
            self._add_attachments([Path(f.path) for f in files if f.path])
        self._page.update()

    async def _pick_folder_async(self) -> None:
        try:
            path = await self._picker().get_directory_path(dialog_title="选择文件夹")
        except RuntimeError:
            self._show_snack("无法打开文件选择器，请检查系统环境", kind="error")
            return
        if path:
            self._add_attachments([Path(path)])
        self._page.update()

    def _add_attachments(self, paths: list[Path]) -> None:
        for p in paths:
            if p not in self._attached_files:
                self._attached_files.append(p)
        self._rebuild_attach_list()

    def _rebuild_attach_list(self) -> None:
        self._attach_list.controls.clear()
        self._attach_list.visible = bool(self._attached_files)
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
                        ft.Icon(ft.Icons.FOLDER_OUTLINED if f.is_dir() else ft.Icons.INSERT_DRIVE_FILE_OUTLINED,
                                color=c("ink-2", "fg"), size=14),
                        s.text(f.name, "small", "ink", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        s.icon_button(ft.Icons.CLOSE_ROUNDED, lambda _, path=f: self._remove_attach(path),
                                      "移除", size=26, color="ink-3"),
                    ],
                ),
            )
            self._attach_list.controls.append(chip)
        _safe_update(self._attach_list)

    def _remove_attach(self, path: Path) -> None:
        if path in self._attached_files:
            self._attached_files.remove(path)
        self._rebuild_attach_list()
        self._page.update()

    def _show_snack(self, msg: str, color: str | None = None, duration: int = 2200,
                    kind: str | None = None) -> None:
        show_toast(self._page, msg, duration=duration, color=color, kind=kind)
