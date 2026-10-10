"""问题反馈页：路由、环境自动填写、必填校验与草稿保留。"""
from urllib.parse import parse_qs, urlparse

import pytest

from services import feedback_service as fb
from ui.pages import feedback_page
from ui.pages.feedback_page import FeedbackPage
from ui.router import _resolve_page


class _FakePage:
    width = 1280
    on_resize = None

    def __init__(self) -> None:
        self.tasks: list[tuple] = []

    def run_task(self, *args, **kwargs):
        self.tasks.append(args)

    async def launch_url(self, url: str) -> None:
        pass


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(feedback_page, "_drafts", {})
    monkeypatch.setattr(fb, "detect_environment", lambda: {
        "os": "Linux", "os_version": "Ubuntu 22.04，系统语言简体中文",
        "app_version": "1.6.0", "install": "从源码运行（python main.py）",
    })
    monkeypatch.setattr(feedback_page, "show_toast", lambda *a, **k: None)


def test_routes_pick_form():
    assert _resolve_page("/feedback", _FakePage())._kind == "bug"
    assert _resolve_page("/feedback?kind=feature", _FakePage())._kind == "feature"
    assert _resolve_page("/feedback?kind=nope", _FakePage())._kind == "bug"


def test_environment_prefilled_and_submit_opens_github():
    page = _FakePage()
    view = FeedbackPage(page)
    assert view._inputs["os"].value == "Linux"
    assert view._inputs["app_version"].value == "1.6.0"

    view._submit(None)
    assert page.tasks == []          # 必填项没填，不打开浏览器

    view._title.value = "选文件窗口是英文的"
    for key in ("steps", "expected", "actual"):
        view._inputs[key].value = key
    view._inputs["frequency"].value = "每次都会出现"
    view._submit(None)
    (fn, url), = page.tasks
    assert fn == page.launch_url
    q = parse_qs(urlparse(url).query)
    assert q["template"] == ["bug_report.yml"]
    assert q["install"] == ["从源码运行（python main.py）"]


def test_draft_kept_when_switching_forms():
    view = FeedbackPage(_FakePage())
    view._title.value = "草稿"
    view._inputs["steps"].value = "第一步"
    view._save_draft()
    view._kind = "feature"
    view._render()
    assert "steps" not in view._inputs
    view._kind = "bug"
    view._render()
    assert view._title.value == "草稿"
    assert view._inputs["steps"].value == "第一步"
