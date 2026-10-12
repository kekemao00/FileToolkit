"""大模型服务 — 用户自带 Key（BYOK），支持 Claude 与 OpenAI 兼容接口的工具调用。

两种协议统一成同一套「会话消息」格式，上层（agent_service）不关心服务商：
    {"role": "user", "content": str}
    {"role": "assistant", "content": str, "tool_calls": [ToolCall...], "raw": 原生消息}
    {"role": "tool", "tool_call_id": str, "name": str, "content": str, "is_error": bool}

assistant 消息保留服务商原生内容（raw）原样回传：Claude 的 thinking 块必须原样带回，
DeepSeek 等 OpenAI 兼容服务也可能带有自己的字段。

- Claude：Anthropic 官方 SDK（AsyncAnthropic）。官方地址 + 支持的模型时开启服务端拒答回退。
- OpenAI 兼容：httpx 直连 /chat/completions（OpenAI、DeepSeek、通义千问、智谱、Kimi、
  OpenRouter、Ollama 及自定义服务）。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from services import settings_service

ANTHROPIC = "anthropic"
OPENAI = "openai"


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    protocol: str
    base_url: str
    model: str
    needs_key: bool = True
    key_hint: str = ""


PROVIDERS: list[Provider] = [
    Provider("anthropic", "Anthropic Claude", ANTHROPIC, "https://api.anthropic.com", "claude-opus-5-5",
             key_hint="sk-ant-..."),
    Provider("openai", "OpenAI", OPENAI, "https://api.openai.com/v1", "gpt-5", key_hint="sk-..."),
    Provider("deepseek", "DeepSeek", OPENAI, "https://api.deepseek.com/v1", "deepseek-chat"),
    Provider("qwen", "通义千问（阿里云百炼）", OPENAI, "https://dashscope.aliyuncs.com/compatible-mode/v1",
             "qwen-plus"),
    Provider("zhipu", "智谱 GLM", OPENAI, "https://open.bigmodel.cn/api/paas/v4", "glm-4.6"),
    Provider("moonshot", "Kimi（月之暗面）", OPENAI, "https://api.moonshot.cn/v1", "kimi-k2-turbo-preview"),
    Provider("openrouter", "OpenRouter", OPENAI, "https://openrouter.ai/api/v1", "anthropic/claude-opus-5-5"),
    Provider("ollama", "Ollama（本机）", OPENAI, "http://localhost:11434/v1", "qwen3", needs_key=False),
    Provider("custom", "自定义（OpenAI 兼容）", OPENAI, "", "", needs_key=False),
]
PROVIDERS_BY_KEY = {p.key: p for p in PROVIDERS}
DEFAULT_PROVIDER = "anthropic"

# Claude 官方 API 上支持服务端拒答回退（fallbacks: "default"）的模型前缀
_FALLBACK_MODELS = ("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5")
_OFFICIAL_ANTHROPIC = "https://api.anthropic.com"

_TIMEOUT = httpx.Timeout(connect=15.0, read=120.0, write=60.0, pool=15.0)
MAX_TOKENS = 16000


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    api_key: str
    base_url: str
    model: str

    @property
    def protocol(self) -> str:
        p = PROVIDERS_BY_KEY.get(self.provider)
        return p.protocol if p else OPENAI

    @property
    def label(self) -> str:
        p = PROVIDERS_BY_KEY.get(self.provider)
        return p.label if p else self.provider

    @property
    def local(self) -> bool:
        host = httpx.URL(self.base_url).host if self.base_url else ""
        return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local")

    @property
    def ready(self) -> bool:
        """可以发起请求：有地址和模型，且需要 Key 时已填 Key。"""
        if not self.base_url or not self.model:
            return False
        p = PROVIDERS_BY_KEY.get(self.provider)
        needs_key = p.needs_key if p else True
        return bool(self.api_key) or not needs_key or self.local


def get_config() -> LlmConfig:
    provider = settings_service.get("ai_chat_provider", "") or DEFAULT_PROVIDER
    preset = PROVIDERS_BY_KEY.get(provider, PROVIDERS_BY_KEY[DEFAULT_PROVIDER])
    key = settings_service.get("ai_chat_api_key", "")
    if not key and provider == "openai":
        # OpenAI 账号在「AI 生图」里填过 Key 时直接复用
        key = settings_service.get("ai_image_api_key", "") or settings_service.get("openai_api_key", "")
    return LlmConfig(
        provider=provider,
        api_key=key.strip(),
        base_url=(settings_service.get("ai_chat_base_url", "") or preset.base_url).strip(),
        model=(settings_service.get("ai_chat_model", "") or preset.model).strip(),
    )


def save_config(provider: str, api_key: str, base_url: str, model: str) -> None:
    settings_service.set("ai_chat_provider", provider)
    settings_service.set("ai_chat_api_key", api_key.strip())
    settings_service.set("ai_chat_base_url", base_url.strip())
    settings_service.set("ai_chat_model", model.strip())


def is_configured() -> bool:
    return get_config().ready


# ── 结果类型 ─────────────────────────────────────────────────────────────
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    parse_error: str = ""   # 参数不是合法 JSON 时的说明


@dataclass
class LlmTurn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None          # 原生 assistant 消息，原样回传
    stop_reason: str = ""

    def as_message(self) -> dict:
        return {"role": "assistant", "content": self.text, "tool_calls": self.tool_calls, "raw": self.raw}


class LlmError(Exception):
    """给用户看的错误。kind: auth / not_found / rate_limit / bad_request / no_tools / server /
    network / timeout / refusal / config / unknown。"""

    def __init__(self, message: str, kind: str = "unknown") -> None:
        super().__init__(message)
        self.kind = kind


# ── 入口 ─────────────────────────────────────────────────────────────────
async def complete(config: LlmConfig, system: str, messages: list[dict], tools: list[dict],
                   max_tokens: int = MAX_TOKENS) -> LlmTurn:
    """发起一轮带工具定义的对话。tools: [{"name", "description", "parameters"}]。"""
    if not config.ready:
        raise LlmError("还没有配置大模型，请在「设置 → AI 模型」中填写", "config")
    if config.protocol == ANTHROPIC:
        return await _anthropic_complete(config, system, messages, tools, max_tokens)
    return await _openai_complete(config, system, messages, tools, max_tokens)


_PING_TOOL = {
    "name": "ping",
    "description": "连接测试用的工具，不需要调用。",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}


async def check_connection(config: LlmConfig) -> tuple[bool, str]:
    """发一条极短的带工具定义的请求，确认 Key、地址、模型和工具调用都可用。"""
    if not config.base_url or not config.model:
        return False, "请填写 Base URL 和模型名称"
    if not config.ready:
        return False, "请先填写 API Key"
    try:
        await complete(config, "这是连接测试。", [{"role": "user", "content": "请只回复 ok"}],
                       [_PING_TOOL], max_tokens=1024)
    except LlmError as e:
        return False, str(e)
    return True, f"连接成功：{config.label} · {config.model}，支持工具调用"


# ── OpenAI 兼容 ──────────────────────────────────────────────────────────
def to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        role = m["role"]
        if role == "user":
            out.append({"role": "user", "content": m["content"]})
        elif role == "assistant":
            raw = m.get("raw")
            if isinstance(raw, dict) and raw.get("role") == "assistant":
                out.append(raw)
                continue
            msg: dict = {"role": "assistant", "content": m.get("content") or ""}
            if m.get("tool_calls"):
                msg["tool_calls"] = [
                    {"id": c.id, "type": "function",
                     "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)}}
                    for c in m["tool_calls"]
                ]
            out.append(msg)
        elif role == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
    return out


def openai_tools(tools: list[dict]) -> list[dict]:
    return [{"type": "function", "function": t} for t in tools]


def parse_openai_message(msg: dict) -> LlmTurn:
    calls: list[ToolCall] = []
    raw_calls = msg.get("tool_calls") or []
    for i, c in enumerate(raw_calls):
        fn = c.get("function") or {}
        args_text = fn.get("arguments") or "{}"
        if not c.get("id"):
            c["id"] = f"call_{uuid.uuid4().hex[:12]}"
        try:
            args = json.loads(args_text) if isinstance(args_text, str) else dict(args_text)
            err = "" if isinstance(args, dict) else "参数必须是 JSON 对象"
        except (ValueError, TypeError):
            args, err = {}, "参数不是合法的 JSON"
        calls.append(ToolCall(c["id"], fn.get("name", ""), args if isinstance(args, dict) else {}, err))
    raw = {k: v for k, v in msg.items() if v is not None}
    raw["role"] = "assistant"
    if "content" not in raw:
        raw["content"] = ""
    text = msg.get("content") or ""
    if isinstance(text, list):  # 少数服务返回分段内容
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    return LlmTurn(text.strip(), calls, raw)


async def _openai_complete(config: LlmConfig, system: str, messages: list[dict], tools: list[dict],
                           max_tokens: int) -> LlmTurn:
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    # 不传 temperature / max_tokens：推理模型不接受，各家默认值也足够
    payload = {
        "model": config.model,
        "messages": to_openai_messages(system, messages),
        "tools": openai_tools(tools),
        "tool_choice": "auto",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        raise LlmError("请求超时：模型长时间没有返回，请稍后重试", "timeout") from None
    except httpx.HTTPError as e:
        raise LlmError(f"无法连接到 {config.base_url}（{e.__class__.__name__}），请检查网络和 Base URL",
                       "network") from None
    if resp.status_code >= 400:
        raise _http_error(resp.status_code, _error_text(resp), config)
    try:
        data = resp.json()
        msg = data["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise LlmError("模型返回的数据格式无法识别，请确认 Base URL 是 OpenAI 兼容接口", "bad_request") from None
    turn = parse_openai_message(msg)
    turn.stop_reason = str(data["choices"][0].get("finish_reason") or "")
    return turn


def _error_text(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            return str(err.get("message") or err)
        if err:
            return str(err)
        return str(data.get("message") or data)[:300]
    except ValueError:
        return resp.text[:300]


def _http_error(status: int, detail: str, config: LlmConfig) -> LlmError:
    low = detail.lower()
    if status in (401, 403):
        return LlmError("API Key 无效或没有权限，请在设置中检查", "auth")
    if status == 404:
        if "model" in low:
            return LlmError(f"找不到模型「{config.model}」，请在设置中确认模型名称", "not_found")
        return LlmError("接口地址不存在，请检查 Base URL", "not_found")
    if status == 429:
        return LlmError("请求太频繁或额度不足，请稍后再试", "rate_limit")
    if status >= 500:
        return LlmError(f"模型服务暂时不可用（HTTP {status}），请稍后重试", "server")
    if "tool" in low or "function" in low:
        return LlmError(f"模型「{config.model}」不支持工具调用，请换一个模型。原始信息：{detail[:160]}", "no_tools")
    if "model" in low and ("not" in low or "exist" in low or "invalid" in low):
        return LlmError(f"模型「{config.model}」不可用，请在设置中确认模型名称。原始信息：{detail[:160]}", "not_found")
    return LlmError(f"请求被拒绝（HTTP {status}）：{detail[:200]}", "bad_request")


# ── Claude ──────────────────────────────────────────────────────────────
def to_anthropic_messages(messages: list[dict]) -> list[dict]:
    """转换为 Messages API 格式：工具结果放进 user 消息，相邻同角色消息合并。"""
    out: list[dict] = []

    def push(role: str, blocks: list[dict]) -> None:
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": list(blocks)})

    for m in messages:
        role = m["role"]
        if role == "user":
            push("user", [{"type": "text", "text": m["content"]}])
        elif role == "assistant":
            raw = m.get("raw")
            if isinstance(raw, list):
                push("assistant", [dict(b) for b in raw])
                continue
            blocks: list[dict] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for c in m.get("tool_calls") or []:
                blocks.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments})
            push("assistant", blocks or [{"type": "text", "text": "…"}])
        elif role == "tool":
            block: dict = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            if m.get("is_error"):
                block["is_error"] = True
            push("user", [block])
    return out


def anthropic_tools(tools: list[dict]) -> list[dict]:
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools]


def _block_dict(block: Any) -> dict:
    if isinstance(block, dict):
        return block
    if hasattr(block, "to_dict"):
        return block.to_dict()
    return block.model_dump(exclude_none=True)


def parse_anthropic_content(blocks: list[dict], stop_reason: str = "") -> LlmTurn:
    texts: list[str] = []
    calls: list[ToolCall] = []
    for b in blocks:
        if b.get("type") == "text":
            texts.append(b.get("text", ""))
        elif b.get("type") == "tool_use":
            args = b.get("input")
            calls.append(ToolCall(b.get("id", ""), b.get("name", ""), args if isinstance(args, dict) else {},
                                  "" if isinstance(args, dict) else "参数必须是 JSON 对象"))
    return LlmTurn("".join(texts).strip(), calls, blocks, stop_reason)


def _uses_fallbacks(config: LlmConfig) -> bool:
    return (config.base_url.rstrip("/") == _OFFICIAL_ANTHROPIC
            and config.model.startswith(_FALLBACK_MODELS))


async def _anthropic_complete(config: LlmConfig, system: str, messages: list[dict], tools: list[dict],
                              max_tokens: int) -> LlmTurn:
    import anthropic

    client = anthropic.AsyncAnthropic(
        api_key=config.api_key or "none",
        base_url=config.base_url.rstrip("/") or None,
        timeout=120.0,
        max_retries=2,
    )
    params: dict[str, Any] = {
        "model": config.model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": to_anthropic_messages(messages),
        "tools": anthropic_tools(tools),
        "cache_control": {"type": "ephemeral"},
    }
    try:
        async with client:
            if _uses_fallbacks(config):
                # 模型拒答时由服务端按类别换到推荐的回退模型重跑
                resp = await client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
            else:
                resp = await client.messages.create(**params)
    except anthropic.AuthenticationError:
        raise LlmError("API Key 无效，请在设置中检查", "auth") from None
    except anthropic.PermissionDeniedError:
        raise LlmError("API Key 没有权限使用这个模型", "auth") from None
    except anthropic.NotFoundError:
        raise LlmError(f"找不到模型「{config.model}」或接口地址不对，请在设置中确认", "not_found") from None
    except anthropic.RateLimitError:
        raise LlmError("请求太频繁或额度不足，请稍后再试", "rate_limit") from None
    except anthropic.BadRequestError as e:
        raise _http_error(400, str(e.message), config) from None
    except anthropic.APITimeoutError:
        raise LlmError("请求超时：模型长时间没有返回，请稍后重试", "timeout") from None
    except anthropic.APIConnectionError:
        raise LlmError(f"无法连接到 {config.base_url}，请检查网络和 Base URL", "network") from None
    except anthropic.APIStatusError as e:
        raise _http_error(e.status_code, str(e.message), config) from None

    if resp.stop_reason == "refusal":
        raise LlmError("模型拒绝处理这个请求，请换个说法再试", "refusal")
    blocks = [_block_dict(b) for b in resp.content]
    return parse_anthropic_content(blocks, str(resp.stop_reason or ""))
