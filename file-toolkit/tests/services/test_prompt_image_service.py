"""AI 生图服务：文生图与参考图（/images/edits）请求格式、错误提示。"""
import asyncio
import base64
from pathlib import Path

import httpx
import pytest
from PIL import Image

from services import history_service, prompt_image_service, settings_service

_PNG = base64.b64encode(b"fake-png").decode()


@pytest.fixture(autouse=True)
def _settings(tmp_path: Path):
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)
    settings_service.set("ai_image_api_key", "sk-test")
    settings_service.set("ai_image_base_url", "https://img.example.com/v1")


@pytest.fixture
def server(monkeypatch):
    """把 httpx.AsyncClient 换成本地 MockTransport，记录收到的请求。"""
    calls: list[httpx.Request] = []
    state = {"status": 200, "body": {"data": [{"b64_json": _PNG}]}}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(state["status"], json=state["body"])

    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(prompt_image_service.httpx, "AsyncClient", factory)
    return calls, state


def _photo(tmp_path: Path, name: str, fmt: str = "PNG") -> Path:
    path = tmp_path / name
    Image.new("RGB", (32, 32), (200, 120, 80)).save(path, fmt)
    return path


def test_generate_posts_json(server):
    calls, _ = server
    result = asyncio.run(prompt_image_service.generate_image("a cat"))
    assert result["success"] and result["image_bytes"] == b"fake-png"
    assert calls[0].url.path == "/v1/images/generations"
    assert b'"prompt":"a cat"' in calls[0].content


def test_edit_sends_every_reference_image(server, tmp_path):
    calls, _ = server
    refs = [_photo(tmp_path, "a.png"), _photo(tmp_path, "b.jpg", "JPEG")]
    result = asyncio.run(prompt_image_service.edit_image("two friends together", refs))
    assert result["success"]
    req = calls[0]
    assert req.url.path == "/v1/images/edits"
    assert req.headers["content-type"].startswith("multipart/form-data")
    body = req.content
    assert body.count(b'name="image[]"') == 2
    assert b'filename="a.png"' in body and b'filename="b.jpg"' in body
    assert b"two friends together" in body


def test_edit_single_image_uses_plain_field_and_converts_bmp(server, tmp_path):
    calls, _ = server
    ref = _photo(tmp_path, "me.bmp", "BMP")
    assert asyncio.run(prompt_image_service.edit_image("headshot", [ref]))["success"]
    body = calls[0].content
    assert b'name="image"' in body and b'name="image[]"' not in body
    assert b'filename="me.jpg"' in body


def test_edit_reports_unsupported_provider(server, tmp_path):
    _, state = server
    state["status"], state["body"] = 404, {"error": {"message": "Not Found"}}
    result = asyncio.run(prompt_image_service.edit_image("x", [_photo(tmp_path, "a.png")]))
    assert not result["success"]
    assert "不支持参考图" in result["error"]


def test_edit_reports_unreadable_image(server, tmp_path):
    bad = tmp_path / "broken.bmp"
    bad.write_bytes(b"not an image")
    result = asyncio.run(prompt_image_service.edit_image("x", [bad]))
    assert not result["success"] and "参考图读取失败" in result["error"]
    assert server[0] == []
