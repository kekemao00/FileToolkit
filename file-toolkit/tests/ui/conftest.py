import pytest


@pytest.fixture(autouse=True)
def _fresh_ai_conversation():
    """AI 页面的对话状态是模块级的（离开页面不丢），每个测试从空对话开始。"""
    from ui.pages import ai_task_page
    ai_task_page.reset_conversation()
    yield
    ai_task_page.reset_conversation()
