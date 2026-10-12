"""输入框高频事件：防抖合并、不整页自动刷新。"""
import asyncio

from tests.ui._flet_fake import check_run_task
from ui import style as s


class _FakePage:
    def __init__(self):
        self.tasks = []

    def run_task(self, handler, *args, **kwargs):
        check_run_task(handler)
        self.tasks.append(asyncio.ensure_future(handler(*args, **kwargs)))


class _FakeEvent:
    def __init__(self, page, value):
        self.page = page
        self.value = value


async def test_debounced_runs_once_after_typing_stops():
    page = _FakePage()
    seen = []
    handler = s.debounced(lambda e: seen.append(e.value), delay=0.05)
    for v in ("n", "ni", "nih", "你好"):          # 输入法组字时一个字会触发好几次 on_change
        handler(_FakeEvent(page, v))
        await asyncio.sleep(0.01)
    await asyncio.gather(*page.tasks)
    assert seen == ["你好"]

    handler(_FakeEvent(page, "你好a"))           # 停顿后再输入，照常执行
    await asyncio.gather(*page.tasks)
    assert seen == ["你好", "你好a"]


def test_quiet_passes_event_through():
    seen = []
    assert s.quiet(lambda e: seen.append(e) or "ok")("evt") == "ok"
    assert seen == ["evt"]
