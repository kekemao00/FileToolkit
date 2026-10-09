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


class _Picked:
    def __init__(self, path: Path):
        self.path, self.name, self.bytes = str(path), path.name, None


def _photos(tmp_path: Path, n: int) -> list[Path]:
    paths = []
    for i in range(n):
        p = tmp_path / f"p{i}.png"
        p.write_bytes(b"x")
        paths.append(p)
    return paths


def test_reference_template_blocks_generation_until_enough_photos(tmp_path, monkeypatch):
    from services import prompt_image_service
    from ui.pages import prompt_image_page as mod
    toasts, tasks = [], []
    monkeypatch.setattr(mod, "show_toast", lambda _p, msg, **kw: toasts.append(msg))
    monkeypatch.setattr(prompt_image_service, "is_configured", lambda: True)
    page = PromptImagePage(_FakePage())
    page._page.run_task = lambda fn, *args: tasks.append((fn.__name__, args))
    page._select_template(tpl.get_template_by_id("ref_couple_photo"))
    page._var_controls["scene"].value = "海边"
    assert page._ref_title.value == "参考图"

    page._add_refs([_Picked(p) for p in _photos(tmp_path, 1)])
    page._on_generate()
    assert "至少 2 张" in toasts[-1]
    assert not any(name == "_generate_task" for name, _ in tasks)

    page._add_refs([_Picked(p) for p in _photos(tmp_path, 3)])  # 第 1 张重复，第 3 张超上限
    assert len(page._ref_images) == 2
    assert "最多 2 张" in toasts[-1]
    page._on_generate()
    name, args = tasks[-1]
    assert name == "_generate_task" and args[3] == page._ref_images


def test_photos_are_optional_for_normal_templates(tmp_path):
    page = PromptImagePage(_FakePage())
    assert page._ref_title.value == "参考图（可选）"
    page._add_refs([_Picked(p) for p in _photos(tmp_path, 2)])
    page._on_remove_ref(0)
    assert [p.name for p in page._ref_images] == ["p1.png"]
    page._select_template(tpl.TEMPLATES[1])
    assert len(page._ref_images) == 1  # 切换模板保留已上传的照片


def test_typing_refresh_is_debounced_when_mounted():
    page = PromptImagePage(_FakePage())
    scheduled = []
    page._page.run_task = lambda fn, *args: scheduled.append(args)
    page._mounted = True
    before = page._prompt_field.value
    page._var_controls["theme"].value = "音乐节"
    page._schedule_refresh()
    page._schedule_refresh()
    assert page._prompt_field.value == before  # 还没刷新
    assert [a[0] for a in scheduled] == [1, 2]
    import asyncio
    asyncio.run(page._debounced_refresh(1))  # 过期的那次直接丢弃
    assert page._prompt_field.value == before
    asyncio.run(page._debounced_refresh(2))
    assert "音乐节" in page._prompt_field.value
