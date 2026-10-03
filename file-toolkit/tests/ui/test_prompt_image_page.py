"""提示词出图页：构建、选模板、组装提示词、结果区状态。"""
from pathlib import Path

import pytest

from core.prompt_image import templates as tpl
from services import history_service, settings_service
from services import prompt_library_service as lib
from ui.pages.prompt_image_page import PromptImagePage


class _FakePage:
    web = False
    width = 1280
    height = 800

    def run_task(self, *args, **kwargs):
        pass

    def go(self, route):
        pass


@pytest.fixture(autouse=True)
def _settings(tmp_path: Path):
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)


def test_page_builds_and_assembles_prompt():
    page = PromptImagePage(_FakePage())
    assert page._current["id"] == tpl.TEMPLATES[0]["id"]
    page._var_controls["theme"].value = "音乐节"
    page._on_toggle_modifier("cinematic")
    page._refresh_prompt()
    assert "音乐节" in page._prompt_field.value
    assert "cinematic film still" in page._prompt_field.value


def test_manual_edit_is_not_overwritten_until_restored():
    page = PromptImagePage(_FakePage())
    page._prompt_field.value = "my own prompt"
    page._on_prompt_edited(None)
    page._var_controls["theme"].value = "x"
    page._refresh_prompt()
    assert page._prompt_field.value == "my own prompt"
    page._on_restore_prompt(None)
    assert page._prompt_field.value != "my own prompt"


def test_last_template_and_source_are_remembered():
    item = lib.save_custom("我的", "A {物体}")
    settings_service.set("prompt_image_last_source", lib.CUSTOM_SOURCE)
    settings_service.set("prompt_image_last_template", item["id"])
    page = PromptImagePage(_FakePage())
    assert page._source == lib.CUSTOM_SOURCE
    assert page._current["id"] == item["id"]
    assert list(page._var_controls) == ["物体"]


def test_desktop_preview_loads_from_saved_file(tmp_path: Path):
    img = tmp_path / "out.png"
    img.write_bytes(b"\x89PNG")
    page = PromptImagePage(_FakePage())
    assert page._image_control(b"bytes", img).src == str(img)
    web = _FakePage()
    web.web = True
    assert PromptImagePage(web)._image_control(b"bytes", img).src == b"bytes"
