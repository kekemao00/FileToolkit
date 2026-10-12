"""AI 智能任务页：配置了模型时，对话 → 方案卡片 → 执行 → 完成。"""
import asyncio
from pathlib import Path

import flet as ft
import pypdf
import pytest

from services import history_service, llm_service, settings_service
from services.agent_service import AgentReply, ReplyAction
from services.llm_service import LlmError, LlmTurn, ToolCall
from tests.ui._flet_fake import check_run_task
from ui.components.plan_card import BROKEN, CANCELLED, EXECUTING, FINISHED, READY, STALE
from ui.pages import ai_task_page
from ui.pages.ai_task_page import AiTaskPage
from ui.pages.settings_page import SettingsPage


class _FakePage:
    width = 1280
    on_resize = None
    overlay: list = []

    def __init__(self) -> None:
        self.pending: list = []
        self.routes: list[str] = []

    def run_task(self, handler, *args, **kwargs):
        check_run_task(handler)
        self.pending.append((handler, args))

        class _Task:
            def done(self) -> bool:
                return True
        return _Task()

    async def drain(self) -> None:
        while self.pending:
            handler, args = self.pending.pop(0)
            await handler(*args)

    def go(self, route: str) -> None:
        self.routes.append(route)

    def update(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _settings(tmp_path: Path, monkeypatch):
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)
    settings_service.set("after_complete", "silent")
    llm_service.save_config("deepseek", "sk-test", "", "")
    monkeypatch.setattr("ui.pages.ai_task_page.show_toast", lambda *a, **k: None)


def _pdf(path: Path) -> Path:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as f:
        writer.write(f)
    return path


def _script(monkeypatch, turns: list):
    async def fake(config, system, messages, tools, **_):
        turn = turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn
    monkeypatch.setattr("services.agent_service.llm_service.complete", fake)
    return fake


async def test_plan_then_execute(tmp_path: Path, monkeypatch) -> None:
    _script(monkeypatch, [
        LlmTurn("", [ToolCall("a", "pdf_watermark", {"inputs": ["f1"], "text": "内部资料"})]),
        LlmTurn("给合同加上水印。"),
    ])
    page = _FakePage()
    ai = AiTaskPage(page)
    assert ai._online
    ai._attached_files = [_pdf(tmp_path / "合同.pdf")]
    ai._input_field.value = "加内部资料水印"
    ai._on_submit(None)
    assert ai._busy and ai._input_field.value == "" and not ai._attached_files
    await page.drain()

    assert not ai._busy
    card = ai._cards[0]
    assert card.state == READY and card.plan.steps[0].args["text"] == "内部资料"
    assert len(ai._feed.controls) == 3  # 用户气泡、回复、方案卡片（思考中的提示已移除）

    settings_service.set("default_output_dir", str(tmp_path / "out"))
    ai._run_card(card)
    await page.drain()
    assert card.state == FINISHED
    assert card.report and card.report.outputs[0].name.startswith("合同_watermarked")
    assert history_service.get_recent_tasks()[0]["module"] == "ai"


async def test_error_then_retry_and_stale_cards(tmp_path: Path, monkeypatch) -> None:
    _script(monkeypatch, [
        LlmError("请求太频繁或额度不足，请稍后再试", "rate_limit"),
        LlmTurn("", [ToolCall("a", "pdf_compress", {"inputs": ["f1"]})]),
        LlmTurn("压缩。"),
        LlmTurn("", [ToolCall("b", "pdf_to_images", {"inputs": ["f1"]})]),
        LlmTurn("转图片。"),
    ])
    page = _FakePage()
    ai = AiTaskPage(page)
    ai._attached_files = [_pdf(tmp_path / "a.pdf")]
    ai._input_field.value = "压缩"
    ai._on_submit(None)
    await page.drain()
    assert not ai._cards and not ai._busy

    ai._retry()
    await page.drain()
    assert ai._cards[0].state == READY

    ai._input_field.value = "还是转成图片吧"
    ai._on_submit(None)
    await page.drain()
    assert ai._cards[0].state == STALE and ai._cards[1].state == READY
    # 作废的方案不能再执行
    ai._run_card(ai._cards[0])
    assert not page.pending


async def test_failed_step_offers_revise(tmp_path: Path, monkeypatch) -> None:
    _script(monkeypatch, [
        LlmTurn("", [ToolCall("a", "pdf_split", {"inputs": ["f1"], "mode": "range", "page_ranges": "4-6"})]),
        LlmTurn("拆分。"),
        LlmTurn("这份 PDF 只有 1 页，没法拆出 4-6 页。"),
    ])
    page = _FakePage()
    ai = AiTaskPage(page)
    ai._attached_files = [_pdf(tmp_path / "a.pdf")]
    ai._input_field.value = "拆出 4-6 页"
    ai._on_submit(None)
    await page.drain()
    card = ai._cards[0]
    ai._run_card(card)
    await page.drain()
    assert card.state == BROKEN

    ai._revise_card(card)
    await page.drain()
    assert card.state == STALE and len(ai._cards) == 1


def test_new_conversation_resets(tmp_path: Path) -> None:
    page = _FakePage()
    ai = AiTaskPage(page)
    ai._feed.controls.append(ai._assistant_text("hi"))
    ai._render()
    ai._new_conversation()
    assert not ai._feed.controls and ai._session is None


def test_settings_page_saves_model_config() -> None:
    page = _FakePage()
    view = SettingsPage(page)
    view._chat_provider.value = "qwen"
    view._chat_key.value = "sk-q"
    view._chat_base.value = ""
    view._chat_model.value = "qwen-max"
    view._save_ai_chat_config(None)
    cfg = llm_service.get_config()
    assert cfg.provider == "qwen" and cfg.api_key == "sk-q" and cfg.model == "qwen-max"
    assert cfg.base_url.startswith("https://dashscope")


class _LivePage(_FakePage):
    """run_task 真的起 asyncio 任务（能取消），用来测停止。"""

    on_keyboard_event = None

    def run_task(self, handler, *args, **kwargs):
        check_run_task(handler)
        return asyncio.ensure_future(handler(*args))


class _Esc:
    key = "Escape"


def _hang(monkeypatch, started: asyncio.Event):
    async def slow(config, system, messages, tools, **_):
        started.set()
        await asyncio.sleep(60)
    monkeypatch.setattr("services.agent_service.llm_service.complete", slow)
    return slow


async def test_second_message_clears_input_on_screen(tmp_path: Path, monkeypatch) -> None:
    _script(monkeypatch, [LlmTurn("要压缩成多大？"), LlmTurn("好的。")])
    pushed: list = []
    monkeypatch.setattr(ai_task_page, "_safe_update", pushed.append)
    page = _FakePage()
    ai = AiTaskPage(page)
    ai._input_field.value = "压缩 PDF"
    ai._on_submit(None)
    await page.drain()
    pushed.clear()
    ai._input_field.value = "压到 1MB"
    ai._on_submit(None)
    # 之前只刷新了对话流，输入框里的字还留在界面上
    assert ai._input_field.value == "" and ai._input_field in pushed
    await page.drain()


async def test_esc_stops_planning_and_restores_message(tmp_path: Path, monkeypatch) -> None:
    started = asyncio.Event()
    _hang(monkeypatch, started)
    page = _LivePage()
    ai = AiTaskPage(page)
    pdf = _pdf(tmp_path / "合同.pdf")
    ai._attached_files = [pdf]
    ai._input_field.value = "加水印"
    ai._on_submit(None)
    assert ai._busy and ai._input_field.value == ""
    await started.wait()

    ai._on_key(_Esc())
    await asyncio.sleep(0)
    assert not ai._busy
    assert ai._input_field.value == "加水印" and ai._attached_files == [pdf]
    assert not ai._feed.controls and ai._session.messages == []

    # 改一下重新发，正常规划
    ai._session._complete = _script(monkeypatch, [
        LlmTurn("", [ToolCall("a", "pdf_watermark", {"inputs": ["f1"], "text": "机密"})]), LlmTurn("加水印。")])
    ai._input_field.value = "加「机密」水印"
    ai._on_submit(None)
    await ai._conv.pending.task
    assert ai._cards[0].state == READY and ai._cards[0].plan.steps[0].args["text"] == "机密"


async def test_stop_restores_plans_it_made_stale(tmp_path: Path, monkeypatch) -> None:
    _script(monkeypatch, [LlmTurn("", [ToolCall("a", "pdf_compress", {"inputs": ["f1"]})]), LlmTurn("压缩。")])
    page = _LivePage()
    ai = AiTaskPage(page)
    ai._attached_files = [_pdf(tmp_path / "a.pdf")]
    ai._input_field.value = "压缩"
    ai._on_submit(None)
    await ai._conv.pending.task
    card = ai._cards[0]

    started = asyncio.Event()
    ai._session._complete = _hang(monkeypatch, started)
    ai._input_field.value = "算了，换成转图片"
    ai._on_submit(None)
    await started.wait()
    assert card.state == STALE
    ai._stop()
    await asyncio.sleep(0)
    assert card.state == READY and ai._input_field.value == "算了，换成转图片"
    assert len(ai._feed.controls) == 3


async def test_esc_during_execution_asks_before_stopping(tmp_path: Path, monkeypatch) -> None:
    _script(monkeypatch, [LlmTurn("", [ToolCall("a", "pdf_compress", {"inputs": ["f1"]})]), LlmTurn("压缩。")])
    confirms: list = []
    monkeypatch.setattr(ai_task_page.s, "confirm", lambda page, title, body="", **kw: confirms.append((title, kw)))
    page = _LivePage()
    ai = AiTaskPage(page)
    ai._attached_files = [_pdf(tmp_path / "a.pdf")]
    ai._input_field.value = "压缩"
    ai._on_submit(None)
    await ai._conv.pending.task
    card = ai._cards[0]

    gate = asyncio.Event()

    async def blocked_execute(runner, on_update=None, out_dir=None, description=""):
        await gate.wait()

    monkeypatch.setattr(ai._session, "execute", blocked_execute)
    settings_service.set("default_output_dir", str(tmp_path / "out"))
    ai._run_card(card)
    await asyncio.sleep(0)
    assert card.state == EXECUTING and ai._busy

    ai._on_key(_Esc())
    assert len(confirms) == 1 and confirms[0][0] == "停止执行？"
    assert card.state == EXECUTING   # 没确认就不停
    confirms[0][1]["on_confirm"]()
    await asyncio.sleep(0.01)
    assert card.state == CANCELLED and not ai._busy


async def test_conversation_survives_leaving_the_page(tmp_path: Path, monkeypatch) -> None:
    _script(monkeypatch, [LlmTurn("", [ToolCall("a", "pdf_compress", {"inputs": ["f1"]})]), LlmTurn("压缩。")])
    page = _FakePage()
    ai = AiTaskPage(page)
    ai._attached_files = [_pdf(tmp_path / "a.pdf")]
    ai._input_field.value = "压缩"
    ai._on_submit(None)
    await page.drain()
    ai._input_field.value = "还没发的草稿"
    ai._on_input_change(None)

    # 去设置页改了模型再回来：对话、方案、草稿都在，新的模型配置直接生效
    llm_service.save_config("qwen", "sk-q", "", "qwen-max")
    back = AiTaskPage(page)
    assert len(back._feed.controls) == 3 and back._cards[0].state == READY
    assert back._input_field.value == "还没发的草稿"
    assert back._session.config.provider == "qwen"

    settings_service.set("default_output_dir", str(tmp_path / "out"))
    back._run_card(back._cards[0])
    await page.drain()
    assert back._cards[0].state == FINISHED


def test_reply_actions_render_as_buttons() -> None:
    page = _FakePage()
    ai = AiTaskPage(page)
    ai._conv.session = None
    ai._on_reply(AgentReply("有新版本 2.0.0。", actions=[ReplyAction("去更新到 2.0.0", "/settings")]))
    row = ai._feed.controls[-1]
    buttons = [c for c in _walk(row) if getattr(c, "on_click", None)]
    assert len(buttons) == 1
    buttons[0].on_click(None)
    assert page.routes == ["/settings"]


def _walk(control):
    yield control
    for attr in ("content", "controls"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for c in child:
                yield from _walk(c)
        elif isinstance(child, ft.Control):
            yield from _walk(child)


async def test_plan_card_warns_when_a_step_goes_online(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("services.prompt_image_service.is_configured", lambda: True)
    _script(monkeypatch, [LlmTurn("", [ToolCall("a", "generate_image", {"prompt": "海边日落"})]), LlmTurn("出图。")])
    page = _FakePage()
    ai = AiTaskPage(page)
    ai._input_field.value = "画一张海边日落"
    ai._on_submit(None)
    await page.drain()
    icon, note = ai._cards[0]._privacy_text()
    assert "第 1 步" in note and "提示词" in note and "参考图" not in note


async def test_running_task_is_still_there_after_switching_tabs(tmp_path: Path, monkeypatch) -> None:
    _script(monkeypatch, [LlmTurn("", [ToolCall("a", "pdf_compress", {"inputs": ["f1"]})]), LlmTurn("压缩。")])
    page = _LivePage()
    ai = AiTaskPage(page)
    ai._attached_files = [_pdf(tmp_path / "a.pdf")]
    ai._input_field.value = "压缩"
    ai._on_submit(None)
    await ai._conv.pending.task
    settings_service.set("default_output_dir", str(tmp_path / "out"))

    gate = asyncio.Event()
    real_execute = ai._session.execute

    async def slow_execute(runner, on_update=None, out_dir=None, description=""):
        await gate.wait()
        return await real_execute(runner, on_update, out_dir, description)

    monkeypatch.setattr(ai._session, "execute", slow_execute)
    ai._run_card(ai._cards[0])
    await asyncio.sleep(0)

    back = AiTaskPage(page)           # 切到别的页面再回来
    assert back._cards[0].state == EXECUTING and back._busy
    gate.set()
    await ai._conv.exec_task
    assert back._cards[0].state == FINISHED and not back._busy
    assert back._cards[0].report.outputs
