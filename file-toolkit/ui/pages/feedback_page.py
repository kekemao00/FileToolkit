"""问题反馈页 — 与 GitHub Issue 表单字段一致，提交时打开预填好的新建 Issue 页面。"""
import flet as ft

from services import feedback_service as fb
from ui import style as s
from ui.palette import c
from ui.utils import show_toast

# 切换页面后保留草稿（应用运行期间有效）
_drafts: dict[str, dict[str, str]] = {}


class FeedbackPage(ft.Column):
    """问题反馈 / 功能建议"""

    def __init__(self, page: ft.Page, initial_kind: str | None = None) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=12)
        self._page = page
        self._kind = initial_kind if initial_kind in fb.FORMS else fb.BUG.key
        self._env = fb.detect_environment()
        self._inputs: dict[str, ft.Control] = {}
        self._tabs = s.Segmented(
            [(f.key, f.name) for f in fb.FORMS.values()], self._kind, on_change=self._switch,
        )
        self._body = ft.Column(spacing=12)
        self.controls = [self._build_header(), self._body, ft.Container(height=12)]
        self._render()

    # ── 页头 ──────────────────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            s.text("反馈与建议", "headline"),
                            s.text("填好后在 GitHub 上提交，方便开发者准确定位问题", "small"),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    self._tabs,
                ],
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            padding=ft.Padding.only(left=s.PAGE_X, top=28, right=s.PAGE_X, bottom=4),
        )

    # ── 表单 ──────────────────────────────────────────────────────────
    @property
    def _form(self) -> fb.Form:
        return fb.FORMS[self._kind]

    def _switch(self, kind: str) -> None:
        self._save_draft()
        self._kind = kind
        self._render()
        self._body.update()

    def _render(self) -> None:
        form = self._form
        draft = _drafts.get(form.key, {})
        self._inputs = {}

        self._title = s.text_field(draft.get("_title", ""), form.title_hint, expand=True)
        manual = [self._row("标题", "", True, self._title)]
        auto: list[ft.Control] = []
        for f in form.fields:
            value = draft.get(f.id) or (self._env.get(f.id, "") if f.auto else "")
            control = self._input(f, value)
            self._inputs[f.id] = control
            (auto if f.auto else manual).append(self._row(f.label, f.hint, f.required, control))

        cards = [self._card(form.heading, ft.Icons.EDIT_NOTE_OUTLINED, form.intro, manual)]
        if form is fb.BUG:
            cards.insert(0, self._example())
        if auto:
            cards.append(self._card("运行环境", ft.Icons.COMPUTER_OUTLINED,
                                    "已自动检测，如有不对可以修改。", auto))
        cards.append(self._actions())
        self._body.controls = cards

    def _input(self, f: fb.Field, value: str) -> ft.Control:
        if f.kind == "dropdown":
            opts = s.field_style()
            opts.pop("label_style", None)
            opts.update(dense=True, text_size=13.5,
                        content_padding=ft.Padding.symmetric(horizontal=12, vertical=9))
            return ft.Dropdown(
                value=value or None,
                hint_text="请选择",
                options=[ft.dropdown.Option(o) for o in f.options],
                expand=True,
                **opts,
            )
        if f.kind == "textarea":
            return s.text_field(
                value, f.placeholder, multiline=True, min_lines=3, max_lines=10, dense=False,
                content_padding=ft.Padding.symmetric(horizontal=12, vertical=10), expand=True,
            )
        return s.text_field(value, f.placeholder, expand=True)

    def _example(self) -> ft.Control:
        return s.card(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=c("ink-2", "fg"), size=16),
                                  s.text("参考写法", "label")],
                        spacing=8,
                    ),
                    s.text(fb.BUG_EXAMPLE, "small", selectable=True),
                ],
                spacing=8,
            ),
            padding=ft.Padding.symmetric(horizontal=20, vertical=14),
            bgcolor=c("surface-2"),
            margin=ft.Margin.symmetric(horizontal=s.PAGE_X),
        )

    def _actions(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            s.button("在 GitHub 提交", self._submit, icon=ft.Icons.OPEN_IN_NEW),
                            s.button("复制内容", self._copy, kind="secondary",
                                     icon=ft.Icons.CONTENT_COPY_OUTLINED),
                            s.button("查看已有反馈", self._open_issues, kind="ghost"),
                        ],
                        spacing=8,
                    ),
                    s.text("会在浏览器打开 GitHub 并填好内容，截图或录屏可以在那里直接拖进去；"
                           "没有 GitHub 账号时，点「复制内容」发给开发者。", "small"),
                ],
                spacing=8,
            ),
            padding=ft.Padding.symmetric(horizontal=s.PAGE_X),
        )

    def will_unmount(self) -> None:
        self._save_draft()

    # ── 操作 ──────────────────────────────────────────────────────────
    def _collect(self) -> dict[str, str]:
        return {k: (ctl.value or "") for k, ctl in self._inputs.items()}

    def _save_draft(self) -> None:
        _drafts[self._kind] = {"_title": self._title.value or "", **self._collect()}

    def _check(self) -> dict[str, str] | None:
        values = self._collect()
        missing = fb.missing_fields(self._form, values)
        if not (self._title.value or "").strip():
            missing.insert(0, "标题")
        if missing:
            show_toast(self._page, f"请先填写：{'、'.join(missing)}", kind="warning")
            return None
        self._save_draft()
        return values

    def _submit(self, _) -> None:
        values = self._check()
        if values is None:
            return
        url = fb.build_issue_url(self._form, self._title.value or "", values)
        self._page.run_task(self._page.launch_url, url)
        show_toast(self._page, "已在浏览器打开，确认内容后点「Create」提交", kind="success")

    def _copy(self, _) -> None:
        values = self._check()
        if values is None:
            return
        text = fb.format_markdown(self._form, self._title.value or "", values)
        self._page.run_task(self._copy_async, text)

    async def _copy_async(self, text: str) -> None:
        try:
            await ft.Clipboard().set(text)
            show_toast(self._page, "已复制到剪贴板", kind="success")
        except Exception as e:
            show_toast(self._page, f"复制失败：{e}", kind="error")

    def _open_issues(self, _) -> None:
        self._page.run_task(self._page.launch_url, fb.ISSUES_URL)

    # ── 通用布局 ──────────────────────────────────────────────────────
    def _card(self, title: str, icon: str, subtitle: str, children: list) -> ft.Control:
        return s.card(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[ft.Icon(icon, color=c("ink-2", "fg"), size=16), s.text(title, "title")],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    s.text(subtitle, "small"),
                    ft.Column(controls=children, spacing=0),
                ],
                spacing=8,
            ),
            padding=ft.Padding.only(left=20, right=20, top=18, bottom=10),
            margin=ft.Margin.symmetric(horizontal=s.PAGE_X),
        )

    def _row(self, label: str, hint: str, required: bool, control: ft.Control) -> ft.Control:
        label_col = ft.Column(
            controls=[s.text(label + (" *" if required else "（可选）"), "body", color="ink-2")],
            spacing=2,
            width=140,
        )
        if hint:
            label_col.controls.append(s.text(hint, "caption"))
        return ft.Container(
            content=ft.Row(
                controls=[label_col, ft.Container(content=control, expand=True)],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=16,
            ),
            padding=ft.Padding.symmetric(vertical=10),
            border=ft.Border.only(top=ft.BorderSide(1, c("line"))),
        )
