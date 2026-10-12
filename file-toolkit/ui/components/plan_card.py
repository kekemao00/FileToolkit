"""AI 智能任务的方案卡片 — 展示步骤，原地切换为执行中 / 完成 / 失败。

状态：ready（等确认）→ running → done / failed / cancelled；用户发了新消息后旧方案变为 stale。
"""
from collections.abc import Callable
from pathlib import Path

import flet as ft

from core.agent.plan import DONE, FAILED, PENDING, RUNNING, SKIPPED, Plan, PlanStep
from services.agent_service import ExecutionReport
from ui import style as s
from ui.features import FEATURES
from ui.palette import c
from ui.utils import is_mounted, open_folder, reveal_file

_ICONS = {f.route: f.icon for f in FEATURES}
READY, EXECUTING, FINISHED, BROKEN, CANCELLED, STALE = "ready", "running", "done", "failed", "cancelled", "stale"


def _safe_update(control: ft.Control) -> None:
    if is_mounted(control):
        try:
            control.update()
        except RuntimeError:
            pass


class PlanCard(ft.Container):
    def __init__(
        self,
        plan: Plan,
        on_run: Callable[["PlanCard"], None],
        on_cancel: Callable[["PlanCard"], None],
        on_revise: Callable[["PlanCard"], None],
    ) -> None:
        self.plan = plan
        self.state = READY
        self.report: ExecutionReport | None = None
        self.out_dir: Path | None = None
        self._on_run = on_run
        self._on_cancel = on_cancel
        self._on_revise = on_revise
        self._progress: dict[int, str] = {}
        self._rows: dict[int, ft.Container] = {}
        self._steps = ft.Column(spacing=0)
        self._footer = ft.Container()
        self._title = s.text("", "title", expand=True)
        super().__init__(
            bgcolor=c("surface"),
            border=ft.Border.all(1, c("line")),
            border_radius=s.R_PANEL,
            padding=ft.Padding.only(left=16, right=16, top=14, bottom=14),
            animate=s.snappy(),
            content=ft.Column(spacing=8, controls=[
                ft.Row(controls=[
                    ft.Icon(ft.Icons.ACCOUNT_TREE_OUTLINED, size=16, color=c("ink-2", "fg")),
                    self._title,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self._steps,
                self._footer,
            ]),
        )
        self.render()

    # ── 渲染 ────────────────────────────────────────────────────────────
    def render(self) -> None:
        n = len(self.plan.steps)
        self._title.value = {
            READY: f"执行方案 · {n} 步",
            EXECUTING: f"正在执行 · {sum(st.status == DONE for st in self.plan.steps)}/{n}",
            FINISHED: "已完成",
            BROKEN: "执行失败",
            CANCELLED: "已取消",
            STALE: f"执行方案 · {n} 步（已被新方案替代）",
        }[self.state]
        self._steps.controls = [self._row(i, st) for i, st in enumerate(self.plan.steps)]
        self._footer.content = self._build_footer()
        self.opacity = 0.55 if self.state == STALE else 1

    def update_step(self, step: PlanStep, desc: str) -> None:
        if desc:
            self._progress[step.sid] = desc
        else:
            self._progress.pop(step.sid, None)
        row = self._rows.get(step.sid)
        if row is None:
            return
        i = self.plan.steps.index(step)
        new = self._row(i, step)
        self._rows[step.sid] = row  # _row() 登记的是新容器，界面上挂着的仍是旧的
        row.content = new.content
        row.border = new.border
        n = len(self.plan.steps)
        self._title.value = f"正在执行 · {sum(st.status == DONE for st in self.plan.steps)}/{n}"
        _safe_update(row)
        _safe_update(self._title)

    def set_state(self, state: str, report: ExecutionReport | None = None) -> None:
        self.state = state
        if report is not None:
            self.report = report
        if state != EXECUTING:
            self._progress.clear()
        self.render()
        _safe_update(self)

    def _inputs_text(self, step: PlanStep) -> str:
        names: list[str] = []
        for ref in step.inputs:
            if ref.startswith("s"):
                prev = self.plan.step(int(ref[1:]))
                names.append(f"第 {self.plan.index_of(prev)} 步的结果" if prev else ref)
            else:
                entry = self.plan.registry.get(int(ref[1:]))
                names.append(entry.path.name if entry else ref)
        files = [n for n in names if not n.startswith("第 ")]
        steps = [n for n in names if n.startswith("第 ")]
        parts = steps[:]
        if files:
            parts.append(files[0] + (f" 等 {len(files)} 个文件" if len(files) > 1 else ""))
        return "输入：" + "、".join(parts)

    def _status_badge(self, index: int, step: PlanStep) -> ft.Control:
        box = dict(width=22, height=22, border_radius=11, alignment=ft.Alignment(0, 0))
        if step.status == RUNNING:
            return ft.Container(content=ft.ProgressRing(width=14, height=14, stroke_width=2, color=c("ink")), **box)
        if step.status == DONE:
            return ft.Container(content=ft.Icon(ft.Icons.CHECK_ROUNDED, size=14, color=c("on-ink", "fg")),
                                bgcolor=c("ink"), **box)
        if step.status == FAILED:
            return ft.Container(content=ft.Icon(ft.Icons.PRIORITY_HIGH_ROUNDED, size=14, color="#FFFFFF"),
                                bgcolor=c("danger"), **box)
        return ft.Container(content=s.text(str(index + 1), "caption", "ink-2"), bgcolor=c("surface-3"), **box)

    def _row(self, index: int, step: PlanStep) -> ft.Container:
        detail: list[ft.Control] = [
            ft.Row(controls=[
                s.text(step.tool.title, "label", "ink-3" if step.status == SKIPPED else "ink"),
                s.text(step.summary, "small", "ink-2", expand=True, max_lines=2,
                       overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            s.text(self._inputs_text(step), "caption", "ink-3", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ]
        if step.status == RUNNING:
            detail.append(s.text(self._progress.get(step.sid, "处理中…"), "small", "ink-2", max_lines=1,
                                 overflow=ft.TextOverflow.ELLIPSIS))
        elif step.status == DONE:
            detail.append(s.text(f"生成 {len(step.outputs)} 个文件 · {step.duration:.1f} 秒", "small", "ink-2"))
        elif step.status == FAILED:
            detail.append(s.text(step.error, "small", "danger", selectable=True))
        elif step.status == SKIPPED:
            detail.append(s.text("未执行", "small", "ink-3"))
        row = ft.Container(
            padding=ft.Padding.symmetric(vertical=9),
            border=ft.Border.only(top=ft.BorderSide(1, c("line"))) if index else None,
            content=ft.Row(controls=[
                self._status_badge(index, step),
                ft.Icon(_ICONS.get(step.tool.route, ft.Icons.TASK_ALT_OUTLINED), size=18, color=c("ink-2", "fg")),
                ft.Column(controls=detail, spacing=2, expand=True),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
        )
        self._rows[step.sid] = row
        return row

    # ── 底部操作区 ───────────────────────────────────────────────────────
    def _build_footer(self) -> ft.Control:
        privacy = ft.Row(controls=[
            ft.Icon(ft.Icons.LOCK_OUTLINE, size=13, color=c("ink-3", "fg")),
            s.text("全部在本机处理，文件不会上传", "small", "ink-3"),
        ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        if self.state == READY:
            return ft.Column(spacing=8, controls=[
                ft.Row(controls=[
                    privacy, ft.Container(expand=True),
                    s.button("开始执行", lambda _: self._on_run(self), icon=ft.Icons.PLAY_ARROW_ROUNDED),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                s.text("想调整？直接在下方说，比如「水印改成机密」「压缩得再小一点」", "caption", "ink-3"),
            ])
        if self.state == EXECUTING:
            return ft.Row(controls=[
                privacy, ft.Container(expand=True),
                s.button("取消", lambda _: self._on_cancel(self), kind="secondary"),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        if self.state == STALE:
            return ft.Container()

        report = self.report
        controls: list[ft.Control] = []
        if self.state == FINISHED and report:
            controls.append(s.text(
                f"用时 {report.duration:.1f} 秒 · 生成 {len(report.outputs)} 个文件", "small", "ink-2"))
            controls.append(self._file_chips(report.outputs))
            warnings = [w for st in self.plan.steps for w in st.warnings]
            if warnings:
                controls.append(s.text("部分文件未处理：" + "；".join(warnings[:3]), "small", "ink-2"))
            buttons = [s.button("打开文件夹", lambda _: self._open_dir(), icon=ft.Icons.FOLDER_OPEN_OUTLINED)]
        elif self.state == BROKEN:
            controls.append(s.text("已完成的步骤产物会保留。可以让 AI 根据失败原因调整方案，或修正问题后重新执行。",
                                   "small", "ink-2"))
            buttons = [
                s.button("让 AI 调整方案", lambda _: self._on_revise(self), icon=ft.Icons.AUTO_AWESOME_OUTLINED),
                s.button("重新执行", lambda _: self._on_run(self), kind="secondary", icon=ft.Icons.REFRESH_ROUNDED),
            ]
        else:  # 已取消
            controls.append(s.text("已经生成的文件会保留。", "small", "ink-2"))
            buttons = [s.button("重新执行", lambda _: self._on_run(self), kind="secondary",
                                icon=ft.Icons.REFRESH_ROUNDED)]
        if self.out_dir and self.out_dir.exists() and self.state != FINISHED:
            buttons.append(s.button("打开文件夹", lambda _: self._open_dir(), kind="ghost",
                                    icon=ft.Icons.FOLDER_OPEN_OUTLINED))
        controls.append(ft.Row(controls=[ft.Container(expand=True), *buttons], spacing=8))
        return ft.Column(controls=controls, spacing=10)

    def _file_chips(self, files: list[Path]) -> ft.Control:
        chips: list[ft.Control] = []
        for p in files[:12]:
            chip = ft.Container(
                bgcolor=c("surface"), border=ft.Border.all(1, c("line")), border_radius=999, height=30,
                padding=ft.Padding.symmetric(horizontal=10), tooltip=str(p),
                on_click=lambda _, path=p: reveal_file(path),
                content=ft.Row(controls=[
                    ft.Icon(ft.Icons.FOLDER_OUTLINED if p.is_dir() else ft.Icons.INSERT_DRIVE_FILE_OUTLINED,
                            size=14, color=c("ink-2", "fg")),
                    s.text(p.name, "small", "ink", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            chips.append(s.hover_surface(chip))
        if len(files) > 12:
            chips.append(s.text(f"等 {len(files)} 个", "small", "ink-3"))
        return ft.Row(controls=chips, wrap=True, spacing=6, run_spacing=6)

    def _open_dir(self) -> None:
        target = self.out_dir
        if self.report and self.report.output_dir:
            target = self.report.output_dir
        if target:
            open_folder(target)

    def reset_failed(self) -> None:
        """重新执行前：失败 / 跳过的步骤回到待执行，已完成的保留。"""
        for st in self.plan.steps:
            if st.status in (FAILED, SKIPPED, RUNNING):
                st.status = PENDING
                st.error = ""
