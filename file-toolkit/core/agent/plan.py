"""执行方案：会话里的文件编号、模型规划出的步骤、规划期校验与执行期输入解析。

文件编号：
  f1, f2 …  会话中登记过的真实文件（用户附件、已执行步骤的产物）
  s1, s2 …  当前方案里某一步的产物（执行前还不存在，规划时只能预测类型）

规划阶段模型每调用一次工具，就由 Plan.add_step() 校验并记为一步（不执行）；
用户确认后按顺序执行，每步的 inputs 由 resolve_inputs() 换成真实路径。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.agent.tools import FOLDER, TOOLS_BY_NAME, ToolSpec, validate_args

MAX_STEPS = 12
_REF = re.compile(r"^([fs])(\d+)$")

PENDING, RUNNING, DONE, FAILED, SKIPPED = "pending", "running", "done", "failed", "skipped"


def file_ext(path: Path) -> str:
    return FOLDER if path.is_dir() else path.suffix.lower().lstrip(".")


@dataclass
class FileEntry:
    fid: int
    path: Path
    origin: str = "附件"   # 附件 / 第 N 步产物

    @property
    def ref(self) -> str:
        return f"f{self.fid}"


class FileRegistry:
    """会话内的文件表：编号只增不减，模型用 f 编号引用。"""

    def __init__(self) -> None:
        self._files: dict[int, FileEntry] = {}
        self._next = 1

    def add(self, path: Path, origin: str = "附件") -> FileEntry:
        for entry in self._files.values():
            if entry.path == path:
                return entry
        entry = FileEntry(self._next, path, origin)
        self._files[self._next] = entry
        self._next += 1
        return entry

    def get(self, fid: int) -> FileEntry | None:
        return self._files.get(fid)

    def __len__(self) -> int:
        return len(self._files)

    def entries(self) -> list[FileEntry]:
        return list(self._files.values())


@dataclass
class PlanStep:
    sid: int                 # 会话内唯一的步骤编号（s 编号）
    tool: ToolSpec
    args: dict[str, Any]
    inputs: list[str]
    predicted: set[str] = field(default_factory=set)
    status: str = PENDING
    outputs: list[Path] = field(default_factory=list)
    error: str = ""
    warnings: list[str] = field(default_factory=list)
    duration: float = 0.0

    @property
    def ref(self) -> str:
        return f"s{self.sid}"

    @property
    def summary(self) -> str:
        return self.tool.summary(self.args)


class Plan:
    """一次规划得到的步骤序列。step 编号由会话统一分配，跨方案不重复。"""

    def __init__(self, registry: FileRegistry, first_sid: int = 1) -> None:
        self.registry = registry
        self.steps: list[PlanStep] = []
        self.next_sid = first_sid

    def step(self, sid: int) -> PlanStep | None:
        return next((s for s in self.steps if s.sid == sid), None)

    def index_of(self, step: PlanStep) -> int:
        return self.steps.index(step) + 1

    def reset(self) -> None:
        self.steps.clear()

    # ── 规划期 ──────────────────────────────────────────────────────────
    def add_step(self, tool_name: str, raw: dict[str, Any]) -> tuple[PlanStep | None, str]:
        """校验一次工具调用并加入方案。返回 (步骤, 给模型的反馈文字)。"""
        tool = TOOLS_BY_NAME.get(tool_name)
        if tool is None:
            return None, f"错误：没有名为 {tool_name} 的工具。"
        if len(self.steps) >= MAX_STEPS:
            return None, f"错误：一个方案最多 {MAX_STEPS} 步，请精简方案。"
        if not isinstance(raw, dict):
            return None, "错误：参数必须是 JSON 对象。"
        inputs = raw.get("inputs")
        if isinstance(inputs, str):
            inputs = [inputs]
        if not isinstance(inputs, list) or not inputs or not all(isinstance(i, str) for i in inputs):
            return None, "错误：inputs 必须是非空的文件编号数组，如 [\"f1\"] 或 [\"s1\"]。"
        inputs = [i.strip().lower() for i in inputs]
        args, err = validate_args(tool, raw)
        if err:
            return None, f"参数错误：{err}。请修正后重新调用。"
        exts, count, err = self._predict_inputs(tool, inputs)
        if err:
            return None, f"输入错误：{err}。请修正后重新调用。"
        if count is not None and count < tool.min_inputs:
            return None, f"输入错误：{tool.title}至少需要 {tool.min_inputs} 个文件。"
        step = PlanStep(self.next_sid, tool, args, inputs, tool.outputs(args, exts))
        self.next_sid += 1
        self.steps.append(step)
        produce = "、".join(sorted("文件夹" if e == FOLDER else e for e in step.predicted)) or "文件"
        return step, (f"已加入方案第 {len(self.steps)} 步（产物编号 {step.ref}，预计产出 {produce}）："
                      f"{tool.title}，{step.summary}。注意：方案尚未执行。")

    def _predict_inputs(self, tool: ToolSpec, refs: list[str]) -> tuple[set[str], int | None, str | None]:
        """检查引用是否存在、类型是否匹配。返回 (输入类型集合, 已知文件数或 None, 错误)。"""
        exts: set[str] = set()
        count: int | None = 0
        for ref in refs:
            m = _REF.match(ref)
            if not m:
                return set(), None, f"「{ref}」不是有效编号，附件和已生成文件用 f 编号，方案中的步骤产物用 s 编号"
            kind, num = m.group(1), int(m.group(2))
            if kind == "f":
                entry = self.registry.get(num)
                if entry is None:
                    return set(), None, f"文件 {ref} 不存在"
                ext = file_ext(entry.path)
                if ext == FOLDER:  # 工具不接受文件夹时，执行时展开成其中的文件
                    exts.add(FOLDER if tool.accepts_folders else "*")
                    count = None
                    continue
                if not tool.accepts_ext(ext):
                    return set(), None, f"{ref}（{entry.path.name}）不是{tool.title}支持的类型"
                exts.add(ext)
                if count is not None:
                    count += 1
            else:
                step = self.step(num)
                if step is None:
                    return set(), None, f"步骤产物 {ref} 不存在（只能引用本方案中已加入的步骤）"
                usable = {e for e in step.predicted if e == FOLDER or e == "*" or tool.accepts_ext(e)}
                if not usable:
                    produced = "、".join(sorted(step.predicted))
                    return set(), None, (f"{ref} 预计产出 {produced}，{tool.title}只接受 "
                                         f"{'、'.join(tool.accepts)}，需要先转换格式")
                exts |= usable
                count = None
        return exts, count, None

    def final_steps(self) -> set[int]:
        """没有被后续步骤引用的步骤：它们的产物是最终结果。"""
        used = {int(r[1:]) for s in self.steps for r in s.inputs if r.startswith("s")}
        return {s.sid for s in self.steps if s.sid not in used}

    # ── 执行期 ──────────────────────────────────────────────────────────
    def resolve_inputs(self, step: PlanStep) -> tuple[list[Path], str | None]:
        """把 inputs 换成真实路径；文件夹在工具不接受时展开成其中的文件，再按类型过滤。"""
        paths: list[Path] = []
        for ref in step.inputs:
            kind, num = ref[0], int(ref[1:])
            if kind == "f":
                entry = self.registry.get(num)
                if entry is not None:
                    paths.append(entry.path)
            else:
                prev = self.step(num)
                if prev is None or prev.status != DONE:
                    return [], f"第 {self.index_of(step)} 步依赖的步骤没有成功完成"
                paths.extend(prev.outputs)
        files: list[Path] = []
        for p in paths:
            if p.is_dir() and not step.tool.accepts_folders:
                files.extend(sorted(f for f in p.rglob("*") if f.is_file()))
            else:
                files.append(p)
        missing = [p for p in files if not p.exists()]
        if missing:
            return [], f"文件不存在：{missing[0]}"
        usable = [p for p in files if step.tool.accepts_path(p)]
        if not usable:
            names = "、".join(sorted({file_ext(p) for p in files})) or "无"
            return [], f"没有{step.tool.title}可以处理的文件（收到：{names}）"
        if len(usable) < step.tool.min_inputs:
            return [], f"{step.tool.title}至少需要 {step.tool.min_inputs} 个文件，只有 {len(usable)} 个"
        return usable, None
