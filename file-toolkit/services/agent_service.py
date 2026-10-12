"""AI 智能任务 — 会话：用大模型规划方案，用户确认后在本机按步骤执行。

一轮对话：
    send(text, attachments)
      → 登记附件（f 编号），把需求 + 文件元信息发给模型
      → 模型调用工具 = 往方案里加步骤（只校验、不执行），把校验结果回给模型，循环到模型不再调用工具
      → 返回 AgentReply（模型的说明文字 + 方案）
    execute(...)
      → 按步骤调用 core 函数（task_service 线程池，可取消），产物登记为新的 f 编号
      → 执行结果在下一轮对话时告诉模型，用户可以接着说「再压缩一下」

应用级工具（检查更新、打开某个页面）不进方案：规划时直接执行，结果回给模型，
需要用户点的入口作为回复里的按钮（AgentReply.actions）。

发给模型的只有文字需求和文件元信息（名称、类型、大小、页数、图片尺寸），不含文件内容；
AI 出图这一步执行时会把提示词和参考图发给用户配置的生图服务，界面会提示。
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.agent.plan import (
    DONE,
    FAILED,
    PENDING,
    RUNNING,
    SKIPPED,
    FileRegistry,
    Plan,
    PlanStep,
    file_ext,
)
from core.agent.tools import FOLDER, TOOLS, run_tool
from core.models import TaskResult, TaskStatus
from services import history_service, llm_service, settings_service
from services.llm_service import LlmConfig, LlmError, LlmTurn

MAX_ROUNDS = 8

RESET_TOOL = {
    "name": "reset_plan",
    "description": "清空当前方案中已加入的全部步骤，用于发现方案有误需要从头规划时。",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

# 应用里可以打开的页面：key → (名称, 路由, 说明)
PAGES: dict[str, tuple[str, str, str]] = {
    "home": ("首页", "/", "全部功能入口"),
    "pdf": ("PDF 工具", "/pdf", "合并、拆分、压缩、转换、加密水印"),
    "image": ("图片工具", "/image", "压缩、格式转换、尺寸、水印、转 PDF、批量重命名"),
    "media": ("音视频工具", "/media", "视频转换、压缩、剪辑，提取音频，音频转换"),
    "archive": ("压缩解压", "/archive", "zip / 7z / tar.gz 打包，解压"),
    "ocr": ("OCR 文字识别", "/ocr", "识别图片和扫描 PDF 里的文字"),
    "markdown": ("Markdown", "/markdown", "文档转 Markdown，Markdown 转 Word / PDF / 网页"),
    "prompt_image": ("提示词出图", "/prompt-image", "用模板和风格手动调提示词出图"),
    "history": ("最近操作", "/history", "查看处理记录、打开输出目录"),
    "feedback": ("问题反馈", "/feedback", "反馈问题"),
    "feature_request": ("功能建议", "/feedback?kind=feature", "提功能建议"),
    "settings": ("设置", "/settings", "主题、默认输出目录、AI 模型 / AI 生图的 Key、检查和安装更新、更新渠道"),
}

CHECK_UPDATE_TOOL = {
    "name": "check_update",
    "description": "检查「文件全能王」本身有没有新版本（立即执行，不进方案）。有新版本时会在回复里放一个去设置页更新的按钮。",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

OPEN_PAGE_TOOL = {
    "name": "open_page",
    "description": "在回复里放一个按钮，用户点了就打开应用里的某个页面（立即生效，不进方案）。"
                   "用于需要用户自己操作的功能，例如去设置里填 API Key、手动调提示词、看处理记录、反馈问题。可选页面：\n"
                   + "\n".join(f"- {k}：{v[0]}（{v[2]}）" for k, v in PAGES.items()),
    "parameters": {
        "type": "object",
        "properties": {
            "page": {"type": "string", "enum": list(PAGES), "description": "要打开的页面"},
            "label": {"type": "string", "description": "按钮文字（可选），如「去设置填写 Key」"},
        },
        "required": ["page"],
        "additionalProperties": False,
    },
}

APP_TOOLS = [CHECK_UPDATE_TOOL, OPEN_PAGE_TOOL]

SYSTEM_PROMPT = """你是「文件全能王」桌面应用里的文件处理助手。用户用一句话描述要对本机文件做什么，你负责把需求规划成由应用内置工具组成的执行方案。

工作方式：
- 你调用工具 = 把这一步加入方案，并不会立即执行。工具结果会告诉你这一步是否加入成功、产物编号和预计产出的类型。方案由用户确认后，应用在本机依次执行。
- 文件编号：附件和之前已经生成的文件用 f 编号（如 f1）；本次方案中前面步骤的产物用 s 编号（如 s1）。只能引用对话里出现过的编号，不要编造。
- 多步任务把上一步的产物作为下一步的 inputs，例如先 images_to_pdf 得到 s1，再 pdf_compress 的 inputs 用 ["s1"]。互不依赖的处理可以分别引用原始文件。
- 工具结果以「参数错误」「输入错误」开头时，说明这一步没加入，请按提示修正后重新调用。方案整体有误时先调用 reset_plan 再重新规划。
- 用最少的步骤完成需求，参数尽量取用户说的值；用户没说的用合理默认值。
- 规划完成后，用一两句话向用户说明方案要做什么、结果是什么（不要逐条复述参数，界面会展示每一步）。
- 需求不清楚、缺少必要信息（如水印文字、密码），或者没有附件却需要处理文件时，不要调用工具，直接简短地问用户。
- generate_image 可以凭提示词生成图片（不需要附件），也可以拿图片当参考图；它会联网，提示词要写具体。生成的图片可以接着交给其他工具（如转 PDF、压缩、加水印）。
- check_update 和 open_page 是应用级工具，调用后立即生效、不进方案：用户问版本或更新时调 check_update；需要用户自己去某个页面操作时（如填 API Key、手动调提示词、看处理记录、反馈问题）调 open_page 放一个按钮。
- 现有工具做不到的事（例如阅读、总结、翻译文件内容，或编辑文件里的文字）直接说明做不到，可以给出最接近的替代方案。
- 你看不到文件内容，只知道文件名、类型、大小等信息。
- 用户的语言是什么就用什么语言回复，简洁，不要使用 Markdown 标题。"""


@dataclass
class ReplyAction:
    label: str
    route: str


@dataclass
class AgentReply:
    text: str
    plan: Plan | None = None          # 有步骤时才返回
    actions: list[ReplyAction] = field(default_factory=list)


@dataclass
class ExecutionReport:
    ok: bool
    cancelled: bool
    output_dir: Path | None
    outputs: list[Path] = field(default_factory=list)   # 最终产物
    error: str = ""
    failed_step: PlanStep | None = None
    duration: float = 0.0


def tool_definitions() -> list[dict]:
    return ([{"name": t.name, "description": t.description, "parameters": t.schema()} for t in TOOLS]
            + [RESET_TOOL, *APP_TOOLS])


# ── 文件元信息 ───────────────────────────────────────────────────────────
def _size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 / 1024:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"


def describe_file(path: Path) -> str:
    """文件元信息：类型、大小，PDF 页数、图片尺寸、文件夹文件数。读不到时只给名字。"""
    try:
        if path.is_dir():
            n = sum(1 for f in path.rglob("*") if f.is_file())
            return f"文件夹，含 {n} 个文件"
        parts = [path.suffix.lstrip(".").upper() or "无扩展名", _size(path.stat().st_size)]
    except OSError:
        return "无法读取"
    ext = file_ext(path)
    try:
        if ext == "pdf":
            import pypdf
            parts.append(f"{len(pypdf.PdfReader(str(path)).pages)} 页")
        elif ext in ("jpg", "jpeg", "png", "webp", "bmp", "gif", "tif", "tiff"):
            from PIL import Image
            with Image.open(path) as im:
                parts.append(f"{im.width}×{im.height}")
    except Exception:
        pass
    return "，".join(parts)


class AgentSession:
    """一次对话。界面持有一个实例，「新对话」时换新的。"""

    def __init__(self, config: LlmConfig | None = None,
                 complete: Callable[..., Awaitable[LlmTurn]] | None = None) -> None:
        self.config = config or llm_service.get_config()
        self._complete = complete or llm_service.complete
        self.registry = FileRegistry()
        self.messages: list[dict] = []
        self.plan: Plan | None = None
        self._next_sid = 1
        self._notes: list[str] = []   # 下一轮发给模型的执行结果等说明
        self._actions: list[ReplyAction] = []
        self.tools = tool_definitions()

    def _snapshot(self) -> tuple:
        return len(self.messages), list(self._notes), self.plan, self._next_sid

    def _rollback(self, snap: tuple) -> None:
        """请求被用户停止：回到发送前，就像这条消息没发过（附件编号保留，不影响后续）。"""
        n, notes, plan, next_sid = snap
        del self.messages[n:]
        self._notes, self.plan, self._next_sid = notes, plan, next_sid

    # ── 规划 ────────────────────────────────────────────────────────────
    async def send(self, text: str, attachments: list[Path] | None = None) -> AgentReply:
        """发送用户需求，返回模型的回复和（如有）方案。失败抛 LlmError；被取消时回滚后再抛出。"""
        snap = self._snapshot()
        try:
            return await self._send(text, attachments)
        except asyncio.CancelledError:
            self._rollback(snap)
            raise

    async def _send(self, text: str, attachments: list[Path] | None) -> AgentReply:
        parts = list(self._notes)
        self._notes.clear()
        if self.plan is not None and self.plan.steps and all(s.status == PENDING for s in self.plan.steps):
            parts.append("（上一版方案还没执行，已作废。请根据下面的新要求给出完整方案。）")
        new = [p for p in (attachments or []) if p.exists()]
        if new:
            lines = []
            for p in new:
                entry = self.registry.add(p)
                lines.append(f"- {entry.ref}：{p.name}（{describe_file(p)}）")
            parts.append("本轮附件：\n" + "\n".join(lines))
        elif not len(self.registry):
            parts.append("（用户没有附加文件）")
        parts.append(f"用户需求：{text.strip()}")
        self.messages.append({"role": "user", "content": "\n\n".join(parts)})
        self.plan = Plan(self.registry, self._next_sid)
        return await self._plan_loop()

    async def retry(self) -> AgentReply:
        """上一轮请求失败（网络、额度等）后重试：不重复添加用户消息，接着已有上下文再请求一次。"""
        if not self.messages or self.messages[-1]["role"] == "assistant":
            raise LlmError("没有需要重试的请求", "config")
        snap = self._snapshot()
        if self.plan is None:
            self.plan = Plan(self.registry, self._next_sid)
        try:
            return await self._plan_loop()
        except asyncio.CancelledError:
            self._rollback(snap)
            raise

    async def revise(self) -> AgentReply:
        """执行失败后，把失败原因发回模型，请它调整方案。"""
        return await self.send("上一个方案执行失败了，请根据失败原因调整方案。")

    async def _plan_loop(self) -> AgentReply:
        plan = self.plan
        assert plan is not None
        self._actions = []
        text = ""
        for _ in range(MAX_ROUNDS):
            turn = await self._complete(self.config, SYSTEM_PROMPT, self.messages, self.tools)
            self.messages.append(turn.as_message())
            if turn.text:
                text = turn.text
            if not turn.tool_calls:
                break
            for call in turn.tool_calls:
                result, is_error = await self._handle_call(plan, call)
                self.messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name,
                                      "content": result, "is_error": is_error})
        else:
            if not text:
                text = "方案已规划好。" if plan.steps else "这次没能规划出方案，换个说法试试。"
        self._next_sid = plan.next_sid
        actions = list(self._actions)
        if not plan.steps:
            self.plan = None
            fallback = "好的。" if actions else "我没太明白要做什么，可以再具体说说吗？"
            return AgentReply(text or fallback, actions=actions)
        return AgentReply(text or f"方案共 {len(plan.steps)} 步，确认后开始执行。", plan, actions)

    async def _handle_call(self, plan: Plan, call) -> tuple[str, bool]:
        if call.parse_error:
            return f"错误：{call.parse_error}，请重新调用。", True
        if call.name == RESET_TOOL["name"]:
            plan.reset()
            return "已清空方案，请重新规划。", False
        if call.name == CHECK_UPDATE_TOOL["name"]:
            return await self._check_update(), False
        if call.name == OPEN_PAGE_TOOL["name"]:
            return self._open_page(call.arguments)
        step, message = plan.add_step(call.name, call.arguments)
        return message, step is None

    # ── 应用级工具 ──────────────────────────────────────────────────────
    def _add_action(self, label: str, route: str) -> None:
        if all(a.route != route for a in self._actions):
            self._actions.append(ReplyAction(label, route))

    async def _check_update(self) -> str:
        from core.version import app_version
        from services import update_service
        st = await update_service.check()
        current = app_version()
        channel = "测试版" if update_service.update_channel() == "beta" else "正式版"
        if st.status == "error":
            return f"检查更新失败：{st.error}。当前版本 {current}。"
        rel = st.release
        if st.status in ("available", "ready", "manual", "downloading", "installing") and rel:
            self._add_action(f"去更新到 {rel.version}", "/settings")
            done = "，安装包已下载好，重启即可完成更新" if st.status in ("ready", "manual") else ""
            return (f"当前版本 {current}，有新版本 {rel.version}（{rel.published_at} 发布，更新渠道：{channel}）"
                    f"{done}。已在回复里放了「去更新」按钮，用户点开设置页即可下载安装。")
        latest = rel.version if rel else current
        return f"当前版本 {current}，已是最新（更新渠道：{channel}，最新 {latest}）。"

    def _open_page(self, args: dict) -> tuple[str, bool]:
        key = args.get("page") if isinstance(args, dict) else None
        if key not in PAGES:
            return f"参数错误：page 只能是 {'、'.join(PAGES)} 之一。", True
        title, route, _ = PAGES[key]
        label = str(args.get("label") or "").strip()[:20] or f"打开{title}"
        self._add_action(label, route)
        return f"已在回复里放了「{label}」按钮。", False

    # ── 执行 ────────────────────────────────────────────────────────────
    def task_dir(self) -> Path:
        """本次执行的输出目录：<默认输出目录 或 第一个附件旁的 output>/AI任务_时间。"""
        base = settings_service.get("default_output_dir", "")
        if base:
            root = Path(base)
        else:
            first = next((e.path for e in self.registry.entries() if e.origin == "附件"), None)
            root = settings_service.resolve_output_dir(first) if first else Path.home() / "FileToolkit"
        return root / f"AI任务_{datetime.now():%Y%m%d_%H%M%S}"

    async def execute(
        self,
        runner: Callable[[Callable, dict, Callable[[int, int, str], None]], Awaitable[TaskResult]],
        on_update: Callable[[PlanStep, str], None] | None = None,
        out_dir: Path | None = None,
        description: str = "",
    ) -> ExecutionReport:
        """按顺序执行当前方案。

        runner(fn, kwargs, on_progress) 负责在工作线程里跑 fn(**kwargs) 并返回 TaskResult
        （界面用 task_service.run_task 包装；测试里直接同步调用）。
        on_update(step, desc) 在步骤开始、进度变化、结束时回调。
        """
        plan = self.plan
        if plan is None or not plan.steps:
            return ExecutionReport(False, False, None, error="没有可执行的方案")
        out_dir = out_dir or self.task_dir()
        finals = plan.final_steps()
        t0 = time.time()
        report = ExecutionReport(True, False, out_dir)
        notify = on_update or (lambda _s, _d: None)

        try:
            await self._run_steps(plan, runner, notify, out_dir, finals, report)
        except asyncio.CancelledError:
            # 界面取消了执行：正在跑的一步记为取消，后面的不再执行；结果照常记录后再把取消抛回去
            for st in plan.steps:
                if st.status == RUNNING:
                    st.status, st.error = FAILED, "已取消"
                    report.failed_step = st
                elif st.status == PENDING:
                    st.status = SKIPPED
            report.ok, report.cancelled, report.error = False, True, "已取消"
            self._finish(plan, report, finals, t0, description)
            raise
        self._finish(plan, report, finals, t0, description)
        return report

    def _finish(self, plan: Plan, report: ExecutionReport, finals: set[int], t0: float,
                description: str) -> None:
        report.duration = time.time() - t0
        report.outputs = [p for s in plan.steps if s.sid in finals and s.status == DONE for p in s.outputs]
        self._notes.append(self._execution_note(plan, report))
        self._save_history(report, description)

    async def _run_steps(self, plan: Plan, runner, notify, out_dir: Path, finals: set[int],
                         report: ExecutionReport) -> None:
        for index, step in enumerate(plan.steps, start=1):
            if step.status == DONE:
                continue
            files, err = plan.resolve_inputs(step)
            if err:
                result = TaskResult(status=TaskStatus.FAILED, error_message=err)
            else:
                step_dir = out_dir if step.sid in finals else out_dir / "中间文件" / f"第{index}步_{step.tool.title}"
                step.status = RUNNING
                notify(step, "准备中…")

                def progress(cur: int, total: int, desc: str, _step: PlanStep = step) -> None:
                    pct = f"{int(cur * 100 / total)}% · " if total else ""
                    notify(_step, pct + desc)

                started = time.time()
                result = await runner(run_tool, {"tool": step.tool, "files": files, "args": step.args,
                                                 "out_dir": step_dir}, progress)
                step.duration = time.time() - started
            if result.status == TaskStatus.SUCCESS:
                step.status = DONE
                step.outputs = list(result.output_files)
                step.warnings = list(result.warnings)
                for p in step.outputs:
                    self.registry.add(p, f"第 {index} 步产物")
                notify(step, "")
                continue
            step.status = FAILED
            step.error = result.error_message or "处理失败"
            report.ok = False
            report.cancelled = result.status == TaskStatus.CANCELLED
            report.error = step.error
            report.failed_step = step
            notify(step, "")
            for rest in plan.steps[index:]:
                rest.status = SKIPPED
                notify(rest, "")
            break

    def _execution_note(self, plan: Plan, report: ExecutionReport) -> str:
        lines = ["上一个方案的执行结果："]
        refs = {e.path: e.ref for e in self.registry.entries()}
        for i, s in enumerate(plan.steps, start=1):
            if s.status == DONE:
                outs = "、".join(f"{refs.get(p, '?')} {p.name}" + ("（文件夹）" if file_ext(p) == FOLDER else "")
                                for p in s.outputs[:20])
                more = f" 等 {len(s.outputs)} 个" if len(s.outputs) > 20 else ""
                lines.append(f"- 第 {i} 步 {s.tool.title}（{s.ref}）完成，生成：{outs or '无文件'}{more}")
            elif s.status == FAILED:
                lines.append(f"- 第 {i} 步 {s.tool.title}（{s.ref}）{'已取消' if report.cancelled else '失败'}：{s.error}")
            elif s.status == SKIPPED:
                lines.append(f"- 第 {i} 步 {s.tool.title}（{s.ref}）未执行")
        lines.append("之后如需继续处理这些产物，请用上面的 f 编号引用。")
        return "\n".join(lines)

    def _save_history(self, report: ExecutionReport, description: str) -> None:
        status = TaskStatus.SUCCESS if report.ok else (TaskStatus.CANCELLED if report.cancelled else TaskStatus.FAILED)
        result = TaskResult(status=status, output_files=report.outputs, output_dir=report.output_dir,
                            error_message=report.error or None, duration_seconds=report.duration)
        desc = (description or "AI 任务").strip().replace("\n", " ")
        try:
            history_service.save_task("ai", "ai_task", result, desc[:80])
        except Exception:
            pass
