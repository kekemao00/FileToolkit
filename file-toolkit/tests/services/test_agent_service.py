"""AI 智能任务：用假模型驱动规划，真实执行 core 函数。"""
import asyncio
from pathlib import Path

import pypdf
import pytest
from PIL import Image

from core.agent.plan import DONE, FAILED, SKIPPED, FileRegistry, Plan
from core.agent.tools import TOOLS, TOOLS_BY_NAME, validate_args
from services import agent_service, history_service, settings_service
from services.agent_service import AgentSession, tool_definitions
from services.llm_service import LlmConfig, LlmTurn, ToolCall

CONFIG = LlmConfig("anthropic", "sk-test", "https://api.anthropic.com", "claude-opus-5-5")


@pytest.fixture(autouse=True)
def _settings(tmp_path: Path):
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)


def _pdf(path: Path, pages: int = 2) -> Path:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as f:
        writer.write(f)
    return path


def _img(path: Path, size=(80, 60)) -> Path:
    Image.new("RGB", size, (30, 120, 200)).save(path)
    return path


class ScriptedModel:
    """按脚本依次返回模型回复；记录每次收到的消息。"""

    def __init__(self, turns: list[LlmTurn]) -> None:
        self.turns = list(turns)
        self.calls: list[list[dict]] = []

    async def __call__(self, config, system, messages, tools, **_):
        self.calls.append([dict(m) for m in messages])
        return self.turns.pop(0)


def _call(name: str, n: int = 1, **args) -> ToolCall:
    return ToolCall(f"call_{name}_{n}", name, args)


async def _sync_runner(fn, kwargs, on_progress):
    return fn(progress_callback=on_progress, **kwargs)


# ── 工具目录 ─────────────────────────────────────────────────────────────
def test_tool_schemas_are_complete() -> None:
    defs = tool_definitions()
    names = [d["name"] for d in defs]
    assert len(names) == len(set(names))
    for d in defs:
        schema = d["parameters"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        for req in schema.get("required", []):
            assert req in schema["properties"]
        for prop in schema["properties"].values():
            assert "default" not in prop


def test_every_tool_has_valid_defaults(monkeypatch) -> None:
    monkeypatch.setattr("services.prompt_image_service.is_configured", lambda: True)
    for tool in TOOLS:
        raw = {k: "x" for k in tool.required}
        if tool.name == "video_cut":
            raw = {"start_time": "00:00:01", "end_time": "00:00:05"}
        if tool.name == "image_convert":
            raw = {"target_format": "png"}
        if tool.name == "image_resize":
            raw = {"width": 100}
        args, err = validate_args(tool, raw)
        assert err is None, (tool.name, err)
        assert tool.summary(args)


def test_validate_args_coerces_and_rejects() -> None:
    split = TOOLS_BY_NAME["pdf_split"]
    args, err = validate_args(split, {"mode": "pages", "pages_per_file": "3"})
    assert err is None and args["pages_per_file"] == 3
    _, err = validate_args(split, {"mode": "range"})
    assert err and "page_ranges" in err
    _, err = validate_args(split, {"mode": "chunks"})
    assert err and "pages" in err
    _, err = validate_args(TOOLS_BY_NAME["pdf_watermark"], {"opacity": 30})
    assert err and "text" in err
    _, err = validate_args(TOOLS_BY_NAME["archive_compress"], {"format": "zip", "password": "1"})
    assert err and "7z" in err
    _, err = validate_args(TOOLS_BY_NAME["pdf_compress"], {"level": "low"})
    assert err and "level" in err


# ── 规划期校验 ───────────────────────────────────────────────────────────
def test_plan_checks_references_and_types(tmp_path: Path) -> None:
    reg = FileRegistry()
    reg.add(_img(tmp_path / "a.png"))
    reg.add(_img(tmp_path / "b.png"))
    plan = Plan(reg)

    step, msg = plan.add_step("images_to_pdf", {"inputs": ["f1", "f2"]})
    assert step is not None and step.ref == "s1" and "s1" in msg
    step, msg = plan.add_step("pdf_compress", {"inputs": ["s1"], "quality": "low"})
    assert step is not None
    # 第 2 步产出 PDF，不能直接交给图片压缩
    step, msg = plan.add_step("image_compress", {"inputs": ["s2"]})
    assert step is None and "输入错误" in msg
    step, msg = plan.add_step("pdf_compress", {"inputs": ["f9"]})
    assert step is None and "不存在" in msg
    step, msg = plan.add_step("pdf_merge", {"inputs": ["f1"]})
    assert step is None
    step, msg = plan.add_step("delete_everything", {"inputs": ["f1"]})
    assert step is None and "没有名为" in msg
    assert [s.tool.name for s in plan.steps] == ["images_to_pdf", "pdf_compress"]
    assert plan.final_steps() == {2}


# ── 端到端：假模型规划 + 真实执行 ──────────────────────────────────────────
async def test_plan_and_execute_images_to_compressed_pdf(tmp_path: Path) -> None:
    imgs = [_img(tmp_path / f"发票{i}.png") for i in range(3)]
    model = ScriptedModel([
        LlmTurn("", [_call("images_to_pdf", inputs=["f1", "f2", "f3"], output_name="发票合集")]),
        LlmTurn("", [_call("pdf_compress", inputs=["s1"], quality="medium")]),
        LlmTurn("先把 3 张图片合成 PDF，再压缩。"),
    ])
    session = AgentSession(CONFIG, model)
    reply = await session.send("把这些发票合成一个 PDF 并压缩", imgs)

    assert reply.plan is not None and len(reply.plan.steps) == 2
    assert reply.text.startswith("先把")
    first = model.calls[0][0]["content"]
    assert "f1：发票0.png" in first and "PNG" in first and "80×60" in first
    # 工具调用的校验结果回给了模型
    assert any(m["role"] == "tool" and "已加入方案第 1 步" in m["content"] for m in session.messages)

    updates: list[tuple[str, str]] = []
    report = await session.execute(_sync_runner, lambda s, d: updates.append((s.status, d)),
                                   out_dir=tmp_path / "out", description="合成并压缩")
    assert report.ok, report.error
    assert [s.status for s in reply.plan.steps] == [DONE, DONE]
    # 最终产物在根目录，中间产物在「中间文件」
    assert len(report.outputs) == 1 and report.outputs[0].parent == tmp_path / "out"
    assert report.outputs[0].name.startswith("发票合集")
    assert len(pypdf.PdfReader(report.outputs[0]).pages) == 3
    assert (tmp_path / "out" / "中间文件").is_dir()
    assert updates and updates[-1][0] == DONE
    # 源文件不动
    assert all(p.exists() for p in imgs)

    rows = history_service.get_recent_tasks()
    assert rows[0]["module"] == "ai" and rows[0]["action"] == "ai_task" and rows[0]["status"] == "success"


async def test_followup_uses_previous_outputs(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path / "合同.pdf")
    model = ScriptedModel([
        LlmTurn("", [_call("pdf_watermark", inputs=["f1"], text="内部资料")]),
        LlmTurn("加水印。"),
        LlmTurn("", [_call("archive_compress", inputs=["f2"], format="zip")]),
        LlmTurn("打成 zip。"),
    ])
    session = AgentSession(CONFIG, model)
    await session.send("加水印", [pdf])
    report = await session.execute(_sync_runner, out_dir=tmp_path / "out1")
    assert report.ok

    reply = await session.send("再打成 zip")
    # 第二轮的用户消息里带有上一轮的执行结果和新文件编号
    second_user = [m for m in model.calls[2] if m["role"] == "user"][-1]["content"]
    assert "上一个方案的执行结果" in second_user and "f2" in second_user
    assert reply.plan is not None and reply.plan.steps[0].ref == "s2"
    report = await session.execute(_sync_runner, out_dir=tmp_path / "out2")
    assert report.ok and report.outputs[0].suffix == ".zip"


async def test_failure_marks_rest_skipped_and_revise_reports_error(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path / "a.pdf")
    model = ScriptedModel([
        LlmTurn("", [_call("pdf_split", inputs=["f1"], mode="range", page_ranges="5-9"),
                     _call("pdf_compress", 2, inputs=["s1"])]),
        LlmTurn("拆分后压缩。"),
        LlmTurn("页码超出了范围，这份 PDF 只有 2 页，请确认要拆哪几页？"),
    ])
    session = AgentSession(CONFIG, model)
    reply = await session.send("拆出 5-9 页再压缩", [pdf])
    report = await session.execute(_sync_runner, out_dir=tmp_path / "out")
    assert not report.ok and report.failed_step is reply.plan.steps[0]
    assert [s.status for s in reply.plan.steps] == [FAILED, SKIPPED]

    reply2 = await session.revise()
    sent = model.calls[2][-1]["content"]
    assert "失败" in sent and reply.plan.steps[0].error in sent
    assert reply2.plan is None and "页" in reply2.text


async def test_invalid_call_is_reported_back_and_fixed(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path / "a.pdf")
    bad = ToolCall("c1", "pdf_compress", {}, parse_error="参数不是合法的 JSON")
    model = ScriptedModel([
        LlmTurn("", [bad, _call("pdf_compress", 2, inputs=["f1"], quality="extreme")]),
        LlmTurn("", [_call("pdf_compress", 3, inputs=["f1"], quality="low")]),
        LlmTurn("强力压缩。"),
    ])
    session = AgentSession(CONFIG, model)
    reply = await session.send("压缩", [pdf])
    tool_msgs = [m for m in session.messages if m["role"] == "tool"]
    assert tool_msgs[0]["is_error"] and tool_msgs[1]["is_error"] and not tool_msgs[2]["is_error"]
    assert reply.plan is not None and len(reply.plan.steps) == 1
    assert reply.plan.steps[0].args["quality"] == "low"


async def test_question_without_plan_and_stale_plan_note(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path / "a.pdf")
    model = ScriptedModel([
        LlmTurn("水印要写什么字？"),
        LlmTurn("", [_call("pdf_watermark", inputs=["f1"], text="机密")]),
        LlmTurn("加水印。"),
        LlmTurn("", [_call("pdf_watermark", 2, inputs=["f1"], text="绝密")]),
        LlmTurn("改好了。"),
    ])
    session = AgentSession(CONFIG, model)
    reply = await session.send("加水印", [pdf])
    assert reply.plan is None and "什么字" in reply.text
    reply = await session.send("机密")
    assert reply.plan is not None
    reply = await session.send("改成绝密")
    last_user = [m for m in model.calls[3] if m["role"] == "user"][-1]["content"]
    assert "已作废" in last_user
    assert reply.plan.steps[0].args["text"] == "绝密"


async def test_reset_plan_tool(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path / "a.pdf")
    model = ScriptedModel([
        LlmTurn("", [_call("pdf_compress", inputs=["f1"])]),
        LlmTurn("", [ToolCall("r", "reset_plan", {}), _call("pdf_to_images", inputs=["f1"])]),
        LlmTurn("转成图片。"),
    ])
    session = AgentSession(CONFIG, model)
    reply = await session.send("每页转图片", [pdf])
    assert [s.tool.name for s in reply.plan.steps] == ["pdf_to_images"]


async def test_extract_output_folder_expands_for_next_step(tmp_path: Path) -> None:
    import zipfile
    src = _img(tmp_path / "p.png")
    archive = tmp_path / "pics.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.write(src, "p.png")
        z.writestr("readme.txt", "hi")
    model = ScriptedModel([
        LlmTurn("", [_call("archive_extract", inputs=["f1"]), _call("image_convert", 2, inputs=["s1"],
                                                                     target_format="webp")]),
        LlmTurn("解压后转 webp。"),
    ])
    session = AgentSession(CONFIG, model)
    await session.send("解压并把图片转 webp", [archive])
    report = await session.execute(_sync_runner, out_dir=tmp_path / "out")
    assert report.ok, report.error
    assert [p.suffix for p in report.outputs] == [".webp"]


def test_task_dir_uses_settings(tmp_path: Path) -> None:
    session = AgentSession(CONFIG, ScriptedModel([]))
    settings_service.set("default_output_dir", str(tmp_path / "custom"))
    assert session.task_dir().parent == tmp_path / "custom"
    assert session.task_dir().name.startswith("AI任务_")


def test_describe_file(tmp_path: Path) -> None:
    assert "3 页" in agent_service.describe_file(_pdf(tmp_path / "x.pdf", 3))
    assert "80×60" in agent_service.describe_file(_img(tmp_path / "y.png"))
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "a.txt").write_text("a")
    assert "1 个文件" in agent_service.describe_file(tmp_path / "d")


# ── 停止规划 ─────────────────────────────────────────────────────────────
async def test_cancelled_send_rolls_back(tmp_path: Path) -> None:
    started = asyncio.Event()

    async def slow(config, system, messages, tools, **_):
        started.set()
        await asyncio.sleep(60)

    session = AgentSession(CONFIG, complete=slow)
    session._notes.append("上一个方案的执行结果：…")
    task = asyncio.ensure_future(session.send("压缩", [_pdf(tmp_path / "a.pdf")]))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert session.messages == [] and session.plan is None
    assert session._notes == ["上一个方案的执行结果：…"]   # 下次发送时照常带上

    # 停止后再发，模型看到的是干净的上下文
    session._complete = ScriptedModel([LlmTurn("要压缩成多大？")])
    reply = await session.send("压缩到 1MB")
    assert reply.text == "要压缩成多大？"
    assert [m["role"] for m in session.messages] == ["user", "assistant"]
    assert "执行结果" in session.messages[0]["content"]


# ── AI 出图 ──────────────────────────────────────────────────────────────
async def test_generate_image_needs_no_inputs_and_chains(tmp_path: Path, monkeypatch) -> None:
    import io
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "PNG")
    calls = []

    async def fake_generate(prompt, size="1024x1024", quality="high", **_):
        calls.append((prompt, size, quality))
        return {"success": True, "image_bytes": buf.getvalue(), "error": ""}

    monkeypatch.setattr("services.prompt_image_service.is_configured", lambda: True)
    monkeypatch.setattr("services.prompt_image_service.generate_image", fake_generate)
    model = ScriptedModel([
        LlmTurn("", [_call("generate_image", prompt="红色圆形徽章，扁平风格", size="1024x1024",
                           output_name="徽章"),
                     _call("images_to_pdf", 2, inputs=["s1"])]),
        LlmTurn("先出图再转 PDF。"),
    ])
    session = AgentSession(CONFIG, complete=model)
    reply = await session.send("画个徽章再转成 PDF")
    assert [s.tool.name for s in reply.plan.steps] == ["generate_image", "images_to_pdf"]
    assert reply.plan.steps[0].tool.network and not reply.plan.steps[1].tool.network

    report = await session.execute(_sync_runner, out_dir=tmp_path / "out")
    assert report.ok, report.error
    assert calls == [("红色圆形徽章，扁平风格", "1024x1024", "high")]
    gen = reply.plan.steps[0].outputs[0]
    assert gen.name == "徽章.png" and gen.read_bytes() == buf.getvalue()
    assert report.outputs[0].suffix == ".pdf"


async def test_generate_image_uses_references_and_reports_failure(tmp_path: Path, monkeypatch) -> None:
    seen = {}

    async def fake_edit(prompt, images, **_):
        seen["images"] = [p.name for p in images]
        return {"success": False, "image_bytes": None, "error": "额度不足"}

    monkeypatch.setattr("services.prompt_image_service.is_configured", lambda: True)
    monkeypatch.setattr("services.prompt_image_service.edit_image", fake_edit)
    model = ScriptedModel([
        LlmTurn("", [_call("generate_image", inputs=["f1"], prompt="改成水彩风格")]),
        LlmTurn("按参考图生成。"),
    ])
    session = AgentSession(CONFIG, complete=model)
    await session.send("改成水彩", [_img(tmp_path / "photo.png")])
    report = await session.execute(_sync_runner, out_dir=tmp_path / "out")
    assert not report.ok and "额度不足" in report.error
    assert seen["images"] == ["photo.png"]


async def test_generate_image_without_key_is_rejected_at_planning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("services.prompt_image_service.is_configured", lambda: False)
    model = ScriptedModel([
        LlmTurn("", [_call("generate_image", prompt="猫")]),
        LlmTurn("需要先在设置里填写 AI 生图的 Key。", [_call("open_page", page="settings", label="去设置填写 Key")]),
        LlmTurn("需要先在设置里填写 AI 生图的 Key。"),
    ])
    session = AgentSession(CONFIG, complete=model)
    reply = await session.send("画只猫")
    assert reply.plan is None
    tool_msg = model.calls[1][-1]
    assert tool_msg["is_error"] and "AI 生图" in tool_msg["content"]
    assert [(a.label, a.route) for a in reply.actions] == [("去设置填写 Key", "/settings")]


# ── 应用级工具 ───────────────────────────────────────────────────────────
async def test_check_update_tool(monkeypatch) -> None:
    from services import update_service
    from services.update_service import Release, UpdateState

    rel = Release(version="2.0.0", tag="v2.0.0", name="v2.0.0", notes="", html_url="", published_at="2026-10-12",
                  assets={})

    async def fake_check():
        return UpdateState(status="available", release=rel)

    monkeypatch.setattr(update_service, "check", fake_check)
    monkeypatch.setattr("core.version.app_version", lambda: "1.9.0")
    model = ScriptedModel([
        LlmTurn("", [_call("check_update")]),
        LlmTurn("有新版本 2.0.0，点下面的按钮去更新。"),
    ])
    session = AgentSession(CONFIG, complete=model)
    reply = await session.send("检查一下更新")
    result = model.calls[1][-1]["content"]
    assert "1.9.0" in result and "2.0.0" in result
    assert reply.plan is None and [a.route for a in reply.actions] == ["/settings"]

    async def latest():
        return UpdateState(status="latest", release=Release(version="1.9.0", tag="v1.9.0", name="", notes="",
                                                             html_url="", published_at="", assets={}))

    monkeypatch.setattr(update_service, "check", latest)
    model.turns = [LlmTurn("", [_call("check_update", 2)]), LlmTurn("已是最新版本。")]
    reply = await session.send("再查一次")
    assert "已是最新" in model.calls[-1][-1]["content"] and not reply.actions


async def test_open_page_tool_validates_page() -> None:
    model = ScriptedModel([
        LlmTurn("", [_call("open_page", page="nowhere"), _call("open_page", 2, page="history")]),
        LlmTurn("可以在最近操作里查看。"),
    ])
    session = AgentSession(CONFIG, complete=model)
    reply = await session.send("我之前处理过哪些文件")
    results = [m for m in model.calls[1] if m["role"] == "tool"]
    assert results[0]["is_error"] and not results[1]["is_error"]
    assert [(a.label, a.route) for a in reply.actions] == [("打开最近操作", "/history")]
