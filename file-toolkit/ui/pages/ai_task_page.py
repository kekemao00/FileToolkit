"""AI 智能任务页 — 一句话描述需求，大模型规划方案，确认后在本机自动执行。

两种模式：
  - 已配置大模型：对话式。模型调用工具规划出方案（PlanCard），用户点「开始执行」后按步骤
    在本机处理，上一步的产物自动交给下一步；可以继续对话调整方案或追加处理。
  - 未配置：本地关键词匹配（ui/intent.py），拆成步骤后点「打开」带着附件进入对应工作台。

布局：空状态时居中一列（图标块 + 标题、模型状态、建议任务、输入框、能力说明）；
开始对话后变为顶部标题栏 + 中间对话流 + 底部固定输入框。
"""
import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import flet as ft

from services import llm_service
from services.agent_service import AgentReply, AgentSession, ReplyAction
from services.llm_service import LlmError
from services.task_service import run_task
from ui import style as s
from ui.components.plan_card import (
    BROKEN,
    CANCELLED,
    EXECUTING,
    FINISHED,
    READY,
    STALE,
    CardModel,
    PlanCard,
)
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


@dataclass(eq=False)
class _Entry:
    kind: str                                   # user / assistant / card / error
    text: str = ""
    files: list[Path] = field(default_factory=list)
    actions: list[ReplyAction] = field(default_factory=list)
    model: CardModel | None = None
    error: LlmError | None = None


@dataclass
class _Pending:
    """正在等模型回复的这次请求：停止时据此把界面恢复成没发过的样子。"""
    task: object
    text: str = ""                              # 要放回输入框的文字（重试时为空）
    files: list[Path] = field(default_factory=list)
    entry: _Entry | None = None                 # 这次请求加进对话的用户气泡
    staled: list[tuple[CardModel, str]] = field(default_factory=list)   # 被它作废的方案及原状态


class _Conversation:
    """AI 页面的对话状态，放在模块里：离开页面再回来、切换主题重建页面都不会丢，
    执行中的方案也会把进度推给当前显示的页面（view）。"""

    def __init__(self) -> None:
        self.session: AgentSession | None = None
        self.entries: list[_Entry] = []
        self.attached: list[Path] = []
        self.draft = ""
        self.last_text = ""
        self.thinking = ""                      # 等模型时的提示文字；空 = 没在等
        self.pending: _Pending | None = None
        self.exec_task = None
        self.view: AiTaskPage | None = None

    @property
    def planning(self) -> bool:
        return bool(self.thinking)

    @property
    def executing(self) -> bool:
        return self.exec_task is not None and not self.exec_task.done()

    @property
    def busy(self) -> bool:
        p = self.pending
        return self.planning or self.executing or (p is not None and _running(p.task))

    def models(self) -> list[CardModel]:
        return [e.model for e in self.entries if e.model is not None]


def _running(task) -> bool:
    return task is not None and not task.done()


_conv: _Conversation | None = None


def conversation() -> _Conversation:
    global _conv
    if _conv is None:
        _conv = _Conversation()
    return _conv


def reset_conversation() -> None:
    global _conv
    _conv = None


class AiTaskPage(ft.Column):
    """AI 智能任务：对话式规划 + 本地执行。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._conv = conversation()
        self._conv.view = self
        self._config = llm_service.get_config()
        if self._conv.session is not None:
            self._conv.session.config = self._config   # 在设置里改了 Key / 模型，回来后直接生效
        self._card_views: dict[CardModel, PlanCard] = {}
        self._thinking: ft.Control | None = None
        self._scroller: ft.Column | None = None
        self._prev_key = None

        self._input_field = ft.TextField(
            value=self._conv.draft,
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
            on_change=s.quiet(self._on_input_change),   # 只记草稿，不用每个字都整页刷新
            on_focus=lambda e: self._focus_console(True),
            on_blur=lambda e: self._focus_console(False),
        )
        self._plan = ft.Column(spacing=0, visible=False)   # 离线模式的步骤列表
        self._attach_list = ft.Row(controls=[], wrap=True, spacing=6, run_spacing=6, visible=False)
        self._feed = ft.Column(spacing=16)
        self._console = self._build_input_console()
        self._rebuild_attach_list()
        self._build_feed()
        self._render()

    # 测试和旧代码用到的状态，实际存在 _conv 里
    @property
    def _online(self) -> bool:
        return self._config.ready

    @property
    def _session(self) -> AgentSession | None:
        return self._conv.session

    @property
    def _busy(self) -> bool:
        return self._conv.busy

    @property
    def _attached_files(self) -> list[Path]:
        return self._conv.attached

    @_attached_files.setter
    def _attached_files(self, files: list[Path]) -> None:
        self._conv.attached = list(files)
        self._rebuild_attach_list()

    @property
    def _cards(self) -> list[PlanCard]:
        return [self._card_views[m] for m in self._conv.models() if m in self._card_views]

    @property
    def _last_text(self) -> str:
        return self._conv.last_text

    # ── Esc：停止 ────────────────────────────────────────────────────────
    def did_mount(self) -> None:
        self._prev_key = self._page.on_keyboard_event
        self._page.on_keyboard_event = self._on_key
        self._scroll_to_end()

    def will_unmount(self) -> None:
        if self._page.on_keyboard_event == self._on_key:
            self._page.on_keyboard_event = None

    def _on_key(self, e: ft.KeyboardEvent) -> None:
        if e.key == "Escape":
            self._stop()
        else:
            ft.context.disable_auto_update()   # 打字时每个键都会来，别每次都整页刷新

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
            on_click=self._on_send_click,
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

    def _actions_row(self, actions: list[ReplyAction]) -> ft.Control:
        return ft.Row(wrap=True, spacing=8, run_spacing=8, controls=[
            s.button(a.label, lambda _, r=a.route: self._page.go(r), kind="secondary",
                     icon=ft.Icons.ARROW_OUTWARD_ROUNDED, height=30)
            for a in actions
        ])

    def _entry_control(self, entry: _Entry) -> ft.Control:
        if entry.kind == "user":
            return self._user_bubble(entry.text, entry.files)
        if entry.kind == "error" and entry.error is not None:
            return self._error_row(entry.error)
        if entry.kind == "card" and entry.model is not None:
            card = PlanCard(entry.model, self._run_card, self._cancel_card, self._revise_card)
            self._card_views[entry.model] = card
            return ft.Container(content=card, padding=ft.Padding.only(left=38))
        body: list[ft.Control] = [ft.Container(content=s.text(entry.text, "body", selectable=True),
                                               padding=ft.Padding.only(top=3))]
        if entry.actions:
            body.append(self._actions_row(entry.actions))
        return self._assistant_row(ft.Column(controls=body, spacing=10, tight=True))

    def _build_feed(self) -> None:
        self._card_views.clear()
        self._feed.controls = [self._entry_control(e) for e in self._conv.entries]
        if self._conv.planning:
            self._thinking = self._thinking_row(self._conv.thinking)
            self._feed.controls.append(self._thinking)

    def _add_entry(self, entry: _Entry) -> None:
        self._conv.entries.append(entry)
        self._append(self._entry_control(entry))

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

    def _send_hover(self, btn: ft.Container, e: ft.ControlEvent) -> None:
        on = e.data in (True, "true")
        btn.bgcolor = c("ink-hover" if on else "ink")
        btn.update()

    def _on_input_change(self, e) -> None:
        self._conv.draft = self._input_field.value or ""

    def _set_input(self, text: str) -> None:
        self._input_field.value = text
        self._conv.draft = text
        _safe_update(self._input_field)

    def _use_suggestion(self, label: str) -> None:
        self._set_input(label)
        self._on_submit(None)

    def _on_send_click(self, _) -> None:
        if self._conv.busy:
            self._stop()
        else:
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
        if self._conv.busy:
            self._show_snack("正在处理上一个请求，按 Esc 可以停止", kind="info")
            return
        files = list(self._conv.attached)
        self._set_input("")
        self._conv.attached.clear()
        self._rebuild_attach_list()
        self._ask(text, files)

    def _ask(self, text: str, files: list[Path]) -> None:
        conv = self._conv
        if conv.session is None:
            conv.session = AgentSession(self._config)
        staled = self._stale_cards()
        conv.last_text = text
        entry = _Entry("user", text, files)
        self._add_entry(entry)
        session = conv.session
        self._request(lambda: session.send(text, files), "正在规划…",
                      _Pending(None, text, files, entry, staled))

    def _stale_cards(self) -> list[tuple[CardModel, str]]:
        """发新消息后，还没执行完的旧方案作废。返回被作废的方案和原状态，停止时用来恢复。"""
        staled = []
        for model in self._conv.models():
            if model.state in (READY, BROKEN, CANCELLED):
                staled.append((model, model.state))
                self._set_card_state(model, STALE)
        return staled

    def _request(self, call, label: str, pending: _Pending) -> None:
        self._start_thinking(label)
        pending.task = self._page.run_task(self._await_reply, call)
        self._conv.pending = pending

    async def _await_reply(self, request) -> None:
        conv = self._conv
        try:
            reply = await request()
        except LlmError as e:
            conv.pending = None
            (conv.view or self)._on_error(e)
            return
        except Exception as e:  # 网络库等意外错误也要回到可用状态
            conv.pending = None
            (conv.view or self)._on_error(LlmError(f"规划失败：{e}"))
            return
        conv.pending = None
        (conv.view or self)._on_reply(reply)

    def _retry(self) -> None:
        session = self._conv.session
        if self._conv.busy or session is None:
            return
        self._request(session.retry, "正在重试…", _Pending(None))

    def _start_thinking(self, label: str) -> None:
        self._conv.thinking = label
        self._sync_send_button()
        self._thinking = self._thinking_row(label)
        self._append(self._thinking)

    def _done_thinking(self) -> None:
        self._conv.thinking = ""
        self._remove_thinking()
        self._sync_send_button()

    def _sync_send_button(self) -> None:
        """忙的时候发送键变成停止键（等同 Esc）。"""
        busy = self._conv.busy
        btn = self._send_btn
        btn.tooltip = "停止（Esc）" if busy else "发送（Enter）"
        icon = btn.content
        if isinstance(icon, ft.Icon):
            icon.icon = ft.Icons.STOP_ROUNDED if busy else ft.Icons.ARROW_UPWARD_ROUNDED
        _safe_update(btn)

    def _on_reply(self, reply: AgentReply) -> None:
        self._done_thinking()
        if reply.text or reply.actions:
            self._conv.entries.append(_Entry("assistant", reply.text, actions=list(reply.actions)))
            self._feed.controls.append(self._entry_control(self._conv.entries[-1]))
        if reply.plan is not None:
            entry = _Entry("card", model=CardModel(reply.plan))
            self._conv.entries.append(entry)
            self._feed.controls.append(self._entry_control(entry))
        _safe_update(self._feed)
        self._scroll_to_end()

    def _on_error(self, err: LlmError) -> None:
        self._done_thinking()
        entry = _Entry("error", error=err)
        self._conv.entries.append(entry)
        self._feed.controls.append(self._entry_control(entry))
        _safe_update(self._feed)
        self._scroll_to_end()

    # ── 停止 ────────────────────────────────────────────────────────────
    def _stop(self) -> None:
        """Esc / 停止键：规划中直接停下并撤回这条消息；执行中先确认。"""
        conv = self._conv
        if conv.planning:
            self._cancel_request()
        elif conv.executing:
            s.confirm(self._page, "停止执行？", "正在处理的这一步会中止，已经完成的步骤产物会保留。",
                      confirm_label="停止执行", danger=True, cancel_label="继续执行",
                      on_confirm=self._cancel_execution)

    def _cancel_request(self) -> None:
        conv = self._conv
        pending, conv.pending = conv.pending, None
        if pending is None:
            return
        if _running(pending.task):
            pending.task.cancel()   # 会话那边会撤回这条消息，模型不会看到
        self._done_thinking()
        if pending.entry is not None and pending.entry in conv.entries:
            conv.entries.remove(pending.entry)
        for model, state in pending.staled:
            self._set_card_state(model, state)
        if pending.files:
            for p in pending.files:
                if p not in conv.attached:
                    conv.attached.append(p)
            self._rebuild_attach_list()
        if pending.text and not (self._input_field.value or "").strip():
            self._set_input(pending.text)
        self._build_feed()
        if not self._feed.controls:
            self._render()
            self._page.update()
        else:
            _safe_update(self._feed)
        self._show_snack("已停止，可以修改后重新发送", kind="info")

    def _cancel_execution(self) -> None:
        task = self._conv.exec_task
        if _running(task):
            task.cancel()
            show_toast(self._page, "已停止，已经生成的文件会保留")

    def _new_conversation(self, _=None) -> None:
        conv = self._conv
        if conv.executing:
            self._show_snack("正在执行，请先停止或等待完成", kind="info")
            return
        if conv.pending is not None and _running(conv.pending.task):
            conv.pending.task.cancel()
        conv.pending = None
        conv.thinking = ""
        conv.session = None
        conv.entries.clear()
        conv.attached.clear()
        conv.last_text = ""
        self._card_views.clear()
        self._feed.controls.clear()
        self._thinking = None
        self._rebuild_attach_list()
        self._config = llm_service.get_config()
        self._sync_send_button()
        self._render()
        self._page.update()

    # ── 执行方案 ────────────────────────────────────────────────────────
    def _card_for(self, model: CardModel) -> PlanCard | None:
        view = self._conv.view or self
        return view._card_views.get(model)

    def _set_card_state(self, model: CardModel, state: str, report=None) -> None:
        card = self._card_for(model)
        if card is not None:
            card.set_state(state, report)
        else:
            model.state = state
            if report is not None:
                model.report = report

    def _run_card(self, card: PlanCard) -> None:
        conv = self._conv
        session = conv.session
        model = card.model
        if session is None or session.plan is not model.plan or conv.busy:
            if model.state != STALE:
                self._show_snack("请等当前任务完成" if conv.busy else "这个方案已经失效，请重新描述需求",
                                 kind="info")
            return
        card.reset_failed()
        model.out_dir = model.out_dir or session.task_dir()
        self._set_card_state(model, EXECUTING)

        async def runner(fn, kwargs, on_progress):
            box: dict = {}
            await run_task(fn, kwargs, on_progress, lambda r: box.setdefault("r", r))
            return box["r"]

        def on_update(step, desc: str) -> None:
            view_card = self._card_for(model)
            if view_card is not None:
                view_card.update_step(step, desc)

        async def _run() -> None:
            try:
                report = await session.execute(runner, on_update, model.out_dir, conv.last_text)
            except asyncio.CancelledError:
                self._set_card_state(model, CANCELLED)
                self._after_execution()
                raise
            if report.ok:
                self._set_card_state(model, FINISHED, report)
                notify_task_done(self._page, report.output_dir)
            else:
                self._set_card_state(model, CANCELLED if report.cancelled else BROKEN, report)
            self._after_execution()
            models = conv.models()
            if models and models[-1] is model:
                (conv.view or self)._scroll_to_end()  # 结果区让卡片变高了

        conv.exec_task = self._page.run_task(_run)
        self._sync_send_button()

    def _after_execution(self) -> None:
        self._conv.exec_task = None
        (self._conv.view or self)._sync_send_button()

    def _cancel_card(self, card: PlanCard) -> None:
        self._cancel_execution()

    def _revise_card(self, card: PlanCard) -> None:
        conv = self._conv
        session = conv.session
        if session is None or conv.busy:
            return
        prev = card.model.state
        self._set_card_state(card.model, STALE)
        entry = _Entry("user", "让 AI 根据失败原因调整方案")
        self._add_entry(entry)
        self._request(session.revise, "正在调整方案…", _Pending(None, entry=entry, staled=[(card.model, prev)]))

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
            if p not in self._conv.attached:
                self._conv.attached.append(p)
        self._rebuild_attach_list()

    def _rebuild_attach_list(self) -> None:
        self._attach_list.controls.clear()
        self._attach_list.visible = bool(self._conv.attached)
        for f in self._conv.attached:
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
        if path in self._conv.attached:
            self._conv.attached.remove(path)
        self._rebuild_attach_list()
        self._page.update()

    def _show_snack(self, msg: str, color: str | None = None, duration: int = 2200,
                    kind: str | None = None) -> None:
        show_toast(self._page, msg, duration=duration, color=color, kind=kind)
