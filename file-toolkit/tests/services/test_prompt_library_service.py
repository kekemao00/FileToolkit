"""提示词库服务：我的模板、订阅源、收藏、生成历史。"""
from pathlib import Path

import pytest

from core.prompt_image import templates as tpl
from services import history_service, settings_service
from services import prompt_library_service as lib


@pytest.fixture(autouse=True)
def _settings(tmp_path: Path):
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)


def test_custom_template_crud():
    item = lib.save_custom("我的海报", "A poster about {主题} in {风格}")
    assert [v["name"] for v in item["variables"]] == ["主题", "风格"]
    assert lib.templates_for(lib.CUSTOM_SOURCE)[0]["id"] == item["id"]
    lib.save_custom("改名", "Only {主题}", template_id=item["id"])
    assert [t["name"] for t in lib.list_custom()] == ["改名"]
    lib.toggle_favorite(item["id"])
    lib.delete_custom(item["id"])
    assert lib.list_custom() == [] and lib.list_favorites() == []


def test_import_file_source_and_listing(tmp_path: Path):
    f = tmp_path / "lib.json"
    f.write_text('{"name": "本地库", "templates": [{"name": "A", "prompt": "A red fox"}]}',
                 encoding="utf-8")
    record = lib.import_file(f)
    assert record["name"] == "本地库" and record["count"] == 1
    assert any(k == record["id"] for k, _ in lib.source_options())
    everything = lib.templates_for(lib.ALL)
    assert len(everything) == len(tpl.TEMPLATES) + 1
    # 重复导入同一个文件只更新，不新增来源
    assert lib.import_file(f)["id"] == record["id"]
    assert len(lib.list_sources()) == 1
    lib.set_source_enabled(record["id"], False)
    assert len(lib.templates_for(lib.ALL)) == len(tpl.TEMPLATES)
    lib.remove_source(record["id"])
    assert lib.list_sources() == [] and lib.templates_for(record["id"]) == []


def test_favorites_follow_templates():
    tid = tpl.TEMPLATES[3]["id"]
    assert lib.toggle_favorite(tid) is True
    assert [t["id"] for t in lib.templates_for(lib.FAVORITES)] == [tid]
    assert lib.toggle_favorite(tid) is False


def test_history_skips_missing_files(tmp_path: Path):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    lib.add_history(img, "prompt", "模板", "1024x1024")
    lib.add_history(tmp_path / "gone.png", "p2", "模板", "1024x1024")
    assert [h["path"] for h in lib.list_history()] == [str(img)]


def test_normalize_github_blob_url():
    assert lib.normalize_url("https://github.com/o/r/blob/main/docs/p.json") == \
        "https://raw.githubusercontent.com/o/r/main/docs/p.json"
