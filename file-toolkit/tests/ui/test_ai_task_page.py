"""AI 智能任务页：配置了模型时，对话 → 方案卡片 → 执行 → 完成。"""
from pathlib import Path

import pypdf
import pytest

from services import history_service, llm_service, settings_service
from services.llm_service import LlmError, LlmTurn, ToolCall
from tests.ui._flet_fake import check_run_task
from ui.components.plan_card import BROKEN, FINISHED, READY, STALE
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


def _script(monkeypatch, turns: list) -> None:
    async def fake(config, system, messages, tools, **_):
        turn = turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn
    monkeypatch.setattr("services.agent_service.llm_service.complete", fake)


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
