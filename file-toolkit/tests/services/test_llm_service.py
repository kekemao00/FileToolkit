"""大模型服务：两种协议的消息转换、响应解析、错误映射与配置。"""
import json
from pathlib import Path

import httpx
import pytest

from services import history_service, llm_service, settings_service
from services.llm_service import (
    LlmConfig,
    LlmError,
    ToolCall,
    parse_anthropic_content,
    parse_openai_message,
    to_anthropic_messages,
    to_openai_messages,
)


@pytest.fixture(autouse=True)
def _settings(tmp_path: Path):
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)


CONVERSATION = [
    {"role": "user", "content": "压缩 f1"},
    {"role": "assistant", "content": "好的", "tool_calls": [ToolCall("c1", "pdf_compress", {"inputs": ["f1"]}),
                                                          ToolCall("c2", "pdf_to_images", {"inputs": ["f1"]})]},
    {"role": "tool", "tool_call_id": "c1", "name": "pdf_compress", "content": "已加入", "is_error": False},
    {"role": "tool", "tool_call_id": "c2", "name": "pdf_to_images", "content": "参数错误", "is_error": True},
    {"role": "assistant", "content": "方案好了", "tool_calls": []},
    {"role": "user", "content": "执行结果…\n\n再打包"},
]


def test_anthropic_messages_group_tool_results() -> None:
    msgs = to_anthropic_messages(CONVERSATION)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user"]
    uses = [b for b in msgs[1]["content"] if b["type"] == "tool_use"]
    assert [u["id"] for u in uses] == ["c1", "c2"]
    results = msgs[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["c1", "c2"]
    assert results[1]["is_error"] is True and "is_error" not in results[0]


def test_anthropic_raw_blocks_are_replayed_verbatim() -> None:
    raw = [{"type": "thinking", "thinking": "", "signature": "sig"},
           {"type": "tool_use", "id": "c9", "name": "ocr", "input": {"inputs": ["f1"]}}]
    turn = parse_anthropic_content(raw, "tool_use")
    assert turn.tool_calls[0].name == "ocr" and turn.tool_calls[0].arguments == {"inputs": ["f1"]}
    msgs = to_anthropic_messages([{"role": "user", "content": "x"}, turn.as_message()])
    assert msgs[1]["content"] == raw


def test_openai_messages_round_trip() -> None:
    msgs = to_openai_messages("sys", CONVERSATION)
    assert msgs[0] == {"role": "system", "content": "sys"}
    assistant = msgs[2]
    assert assistant["tool_calls"][0]["function"]["name"] == "pdf_compress"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"inputs": ["f1"]}
    assert msgs[3] == {"role": "tool", "tool_call_id": "c1", "content": "已加入"}


def test_parse_openai_message_handles_bad_json_and_missing_id() -> None:
    turn = parse_openai_message({
        "role": "assistant", "content": None, "reasoning_content": "想一想",
        "tool_calls": [
            {"id": "a", "type": "function", "function": {"name": "ocr", "arguments": "{\"inputs\": [\"f1\"]}"}},
            {"type": "function", "function": {"name": "ocr", "arguments": "{oops"}},
        ],
    })
    assert turn.tool_calls[0].arguments == {"inputs": ["f1"]}
    assert turn.tool_calls[1].parse_error and turn.tool_calls[1].id
    # 原生消息原样保留（DeepSeek 等需要回传自己的字段）
    assert turn.raw["reasoning_content"] == "想一想" and turn.raw["content"] == ""
    assert to_openai_messages("s", [turn.as_message()])[1] is turn.raw


async def test_openai_complete_posts_tools(monkeypatch) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": "",
            "tool_calls": [{"id": "x", "type": "function",
                            "function": {"name": "ocr", "arguments": "{\"inputs\":[\"f1\"]}"}}]}}]})

    _mock_httpx(monkeypatch, handler)
    cfg = LlmConfig("deepseek", "sk-1", "https://api.deepseek.com/v1/", "deepseek-chat")
    turn = await llm_service.complete(cfg, "sys", [{"role": "user", "content": "hi"}],
                                      [{"name": "ocr", "description": "d", "parameters": {"type": "object"}}])
    assert seen["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-1"
    assert seen["body"]["tools"][0]["function"]["name"] == "ocr"
    assert "max_tokens" not in seen["body"] and "temperature" not in seen["body"]
    assert turn.tool_calls[0].name == "ocr" and turn.stop_reason == "tool_calls"


@pytest.mark.parametrize("status,body,kind", [
    (401, {"error": {"message": "bad key"}}, "auth"),
    (404, {"error": {"message": "The model `x` does not exist"}}, "not_found"),
    (429, {"error": {"message": "quota"}}, "rate_limit"),
    (400, {"error": {"message": "this model does not support tools"}}, "no_tools"),
    (502, {"error": "upstream"}, "server"),
])
async def test_openai_errors_are_readable(monkeypatch, status, body, kind) -> None:
    _mock_httpx(monkeypatch, lambda r: httpx.Response(status, json=body))
    cfg = LlmConfig("openai", "sk", "https://api.openai.com/v1", "x")
    with pytest.raises(LlmError) as exc:
        await llm_service.complete(cfg, "s", [{"role": "user", "content": "hi"}], [])
    assert exc.value.kind == kind


async def test_check_connection_reports_failure(monkeypatch) -> None:
    _mock_httpx(monkeypatch, lambda r: httpx.Response(401, json={}))
    ok, msg = await llm_service.check_connection(LlmConfig("openai", "sk", "https://api.openai.com/v1", "m"))
    assert not ok and "Key" in msg
    ok, msg = await llm_service.check_connection(LlmConfig("openai", "", "https://api.openai.com/v1", "m"))
    assert not ok and "Key" in msg


def test_config_defaults_and_key_reuse() -> None:
    cfg = llm_service.get_config()
    assert cfg.provider == "anthropic" and cfg.model == "claude-opus-5-5" and not cfg.ready
    settings_service.set("ai_image_api_key", "sk-image")
    llm_service.save_config("openai", "", "", "")
    cfg = llm_service.get_config()
    assert cfg.api_key == "sk-image" and cfg.base_url == "https://api.openai.com/v1" and cfg.ready
    llm_service.save_config("ollama", "", "", "")
    assert llm_service.get_config().ready  # 本机模型不需要 Key
    llm_service.save_config("custom", "", "http://192.168.1.5:8000/v1", "")
    assert not llm_service.get_config().ready  # 没填模型


def test_fallbacks_only_on_official_endpoint() -> None:
    assert llm_service._uses_fallbacks(LlmConfig("anthropic", "k", "https://api.anthropic.com", "claude-opus-5-5"))
    assert not llm_service._uses_fallbacks(LlmConfig("anthropic", "k", "https://proxy.example.com", "claude-opus-5-5"))
    assert not llm_service._uses_fallbacks(LlmConfig("anthropic", "k", "https://api.anthropic.com", "claude-haiku-5-5"))


async def test_anthropic_complete_sends_fallbacks(monkeypatch) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["beta"] = request.headers.get("anthropic-beta")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "stop_reason": "tool_use", "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "content": [{"type": "text", "text": "好"},
                        {"type": "tool_use", "id": "t1", "name": "ocr", "input": {"inputs": ["f1"]}}],
        })

    import anthropic
    transport = httpx2_transport(handler)
    real = anthropic.AsyncAnthropic

    def patched(**kw):
        return real(http_client=anthropic.DefaultAsyncHttpxClient(transport=transport), **kw)
    monkeypatch.setattr(anthropic, "AsyncAnthropic", patched)
    cfg = LlmConfig("anthropic", "sk-ant", "https://api.anthropic.com", "claude-opus-5-5")
    turn = await llm_service.complete(cfg, "sys", [{"role": "user", "content": "hi"}],
                                      [{"name": "ocr", "description": "d", "parameters": {"type": "object"}}])
    assert seen["url"].endswith("/v1/messages?beta=true") or seen["url"].endswith("/v1/messages")
    assert "server-side-fallback-2026-07-01" in (seen["beta"] or "")
    assert seen["body"]["fallbacks"] == "default"
    assert seen["body"]["tools"][0]["input_schema"] == {"type": "object"}
    assert turn.text == "好" and turn.tool_calls[0].id == "t1"
    assert turn.raw[1]["type"] == "tool_use"


def httpx2_transport(handler):
    import httpx2
    return httpx2.MockTransport(lambda req: _to_httpx2(handler(_from_httpx2(req))))


def _from_httpx2(req):
    return httpx.Request(req.method, str(req.url), headers=dict(req.headers), content=req.read())


def _to_httpx2(resp: httpx.Response):
    import httpx2
    return httpx2.Response(resp.status_code, headers=dict(resp.headers), content=resp.content)


def _mock_httpx(monkeypatch, handler) -> None:
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)
    monkeypatch.setattr(llm_service.httpx, "AsyncClient", factory)
