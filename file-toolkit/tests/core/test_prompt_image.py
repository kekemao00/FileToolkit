"""提示词模板、风格增强与提示词源解析。"""
import flet as ft
import pytest

from core.prompt_image import modifiers as mods
from core.prompt_image import sources as src
from core.prompt_image import templates as tpl


def test_builtin_templates_are_well_formed():
    ids = [t["id"] for t in tpl.TEMPLATES]
    assert len(ids) == len(set(ids)) >= 30
    for t in tpl.TEMPLATES:
        assert hasattr(ft.Icons, t["icon"]), t["icon"]
        names = {v["name"] for v in t["variables"]}
        for name in names:
            assert f"{{{name}}}" in t["prompt_template"], (t["id"], name)
        for v in t["variables"]:
            if v["type"] == "select":
                assert v["default"] in v["options"]
        # 填满所有变量后不应残留占位符
        values = {v["name"]: "x" for v in t["variables"]}
        assert "{" not in tpl.assemble_prompt(t, values)


def test_assemble_marks_missing_required_and_drops_empty_optional():
    t = tpl.get_template_by_id("poster_minimal")
    prompt = tpl.assemble_prompt(t, {"theme": "音乐节"})
    assert "[主标题]" in prompt
    assert '""' not in prompt  # 副标题留空后不留空引号
    assert "音乐节" in prompt


def test_get_templates_filters_by_category_and_keyword():
    assert all(t["category"] == "海报设计" for t in tpl.get_templates("海报设计"))
    assert [t["id"] for t in tpl.get_templates(keyword="小红书")] == ["xiaohongshu_cover"]


def test_apply_modifiers_appends_selected_and_negative():
    out = mods.apply_modifiers("A cat", ["cinematic", "8k", "unknown"], "text, watermark")
    assert out == "A cat. cinematic film still, 8K ultra high resolution.\nAvoid: text, watermark."
    assert mods.apply_modifiers("A cat.", []) == "A cat."


def test_detect_variables_handles_all_placeholder_styles():
    prompt, variables = src.detect_variables(
        'A {argument name="product" default="mug"} on {背景}, style [风格]',
        include_brackets=True,
    )
    assert prompt == "A {product} on {背景}, style {风格}"
    assert [(v["name"], v["default"], v["required"]) for v in variables] == [
        ("product", "mug", False), ("背景", "", True), ("风格", "", True)]


def test_parse_json_source():
    text = '{"name": "库", "license": "MIT", "templates": [' \
           '{"title": "猫", "prompt": "A {颜色} cat", "category": "动物", "tags": "a,b"},' \
           '{"prompt": ""}]}'
    meta, items = src.parse_source(text, "s1")
    assert meta["name"] == "库" and meta["license"] == "MIT"
    assert len(items) == 1
    t = items[0]
    assert t["id"] == "s1:0" and t["name"] == "猫" and t["category"] == "动物"
    assert t["tags"] == ["a", "b"] and t["license"] == "MIT"
    assert [v["name"] for v in t["variables"]] == ["颜色"]


def test_parse_csv_source():
    text = "act,prompt\nCat,A fluffy cat sitting\nDog,A happy dog running\n"
    _meta, items = src.parse_source(text, "s2", hint="prompts.csv")
    assert [t["name"] for t in items] == ["Cat", "Dog"]


def test_parse_markdown_source():
    text = """# Awesome
## 🛒 E-commerce Cases
### Case 1: [Skincare Ad](https://x.com/a/status/1) (by [@alice](https://x.com/alice))
```
A miniature diorama of a lotion bottle, vertical 9:16 poster
```
### Case 2: No prompt here
Just text.
## Install
```bash
pip install something-long-enough
```
### 案例 3：磨砂玻璃 (by [@bob](https://x.com/bob))
[原文链接](https://x.com/bob/status/2)
```
一张黑白照片，展示了一个[主体]在磨砂表面后的模糊剪影
```
"""
    _meta, items = src.parse_source(text, "md", hint="README.md")
    assert len(items) == 2
    a, b = items
    assert (a["name"], a["author"], a["link"], a["category"]) == (
        "Skincare Ad", "@alice", "https://x.com/a/status/1", "电商")
    assert a["default_size"] == "1024x1536"
    assert (b["name"], b["author"], b["link"]) == ("磨砂玻璃", "@bob", "https://x.com/bob/status/2")
    assert [v["name"] for v in b["variables"]] == ["主体"]


def test_parse_source_rejects_empty():
    with pytest.raises(src.SourceParseError):
        src.parse_source("# nothing", "x")


def test_export_round_trip():
    t = tpl.get_template_by_id("logo_modern")
    _meta, items = src.parse_source(src.to_export_json("导出", [t]), "rt")
    assert items[0]["prompt_template"] == t["prompt_template"]
    assert items[0]["variables"] == t["variables"]


def test_select_options_have_chinese_labels():
    from core.prompt_image.option_labels import OPTION_LABELS
    missing = [o for t in tpl.TEMPLATES for v in t["variables"] if v["type"] == "select"
               for o in v["options"] if o not in OPTION_LABELS
               and not o.isdigit() and not o.startswith(("Kodak", "Fujifilm", "CineStill"))]
    assert missing == []


def test_reference_templates_declare_photo_requirements():
    from core.prompt_image.templates import TEMPLATES, reference_spec
    refs = {t["id"]: reference_spec(t) for t in TEMPLATES if t.get("reference")}
    assert {"ref_couple_photo", "ref_wedding_photo", "ref_group_photo"} <= set(refs)
    assert refs["ref_couple_photo"]["min"] == 2 and not refs["ref_couple_photo"]["inferred"]
    assert reference_spec(tpl.get_template_by_id("poster_minimal")) is None


def test_reference_spec_is_inferred_from_imported_prompt():
    from core.prompt_image.templates import reference_spec
    spec = reference_spec({"prompt_template": "将这张照片变成一个摇头娃娃"})
    assert spec["inferred"] and spec["min"] == 0
    assert reference_spec({"prompt_template": "A red apple on a table"}) is None


def test_section_headers_are_not_variables():
    from core.prompt_image import sources
    prompt = "Make a poster.\n\n{PROJECT CARD}\nTITLE: X\nA {main color} cup in {CITY}"
    _, variables = sources.detect_variables(prompt)
    assert [v["name"] for v in variables] == ["main color", "CITY"]
    stale = {"prompt_template": prompt, "variables": [{"name": "PROJECT CARD"},
                                                      {"name": "main color"}]}
    assert [v["name"] for v in sources.drop_section_markers(stale)["variables"]] == ["main color"]
