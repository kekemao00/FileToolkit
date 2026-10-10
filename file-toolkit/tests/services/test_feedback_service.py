"""services.feedback_service：应用内问题反馈"""
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml

from services import feedback_service as fb

_TEMPLATES = Path(__file__).resolve().parents[3] / ".github" / "ISSUE_TEMPLATE"


def _query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


@pytest.mark.skipif(not _TEMPLATES.is_dir(), reason="需要仓库里的 Issue 模板")
@pytest.mark.parametrize("form", list(fb.FORMS.values()), ids=lambda f: f.key)
def test_form_matches_github_template(form):
    """字段 id、必填、下拉选项都要和 .github/ISSUE_TEMPLATE 里的表单一致，预填才能对上。"""
    tpl = yaml.safe_load((_TEMPLATES / form.template).read_text(encoding="utf-8"))
    assert tpl["title"] == form.title_prefix
    gh = {b["id"]: b for b in tpl["body"] if "id" in b}
    for f in form.fields:
        block = gh[f.id]
        assert block["type"] == f.kind
        assert block["attributes"]["label"].removesuffix("（可选）") == f.label
        assert block.get("validations", {}).get("required", False) == f.required
        if f.kind == "dropdown":
            assert tuple(block["attributes"]["options"]) == f.options
    # 应用里没有的只能是截图这类必须在 GitHub 页面上传的可选项
    extra = set(gh) - {f.id for f in form.fields}
    assert all(not gh[i].get("validations", {}).get("required") for i in extra)


def test_build_issue_url_prefills_fields():
    url = fb.build_issue_url(fb.BUG, "选文件窗口是英文的", {
        "steps": "1. 打开 PDF 合并\n2. 点选择文件", "expected": "中文", "actual": "英文",
        "os": "macOS（Apple 芯片）", "extra": "  ",
    })
    assert url.startswith(fb.NEW_ISSUE_URL + "?")
    q = _query(url)
    assert q["template"] == "bug_report.yml"
    assert q["title"] == "[问题] 选文件窗口是英文的"
    assert q["steps"] == "1. 打开 PDF 合并\n2. 点选择文件"
    assert q["os"] == "macOS（Apple 芯片）"
    assert "extra" not in q


def test_build_issue_url_truncates_long_content():
    url = fb.build_issue_url(fb.BUG, "日志", {"steps": "步骤", "actual": "报错" * 5000})
    assert len(url) <= fb.MAX_URL_LENGTH
    q = _query(url)
    assert q["steps"] == "步骤"
    assert q["actual"].startswith("报错报错")
    assert q["actual"].endswith("请在这里补充完整）")


def test_missing_fields_lists_required_labels():
    missing = fb.missing_fields(fb.FEATURE, {"area": "PDF", "problem": " "})
    assert missing == ["你想解决什么问题？", "希望的做法"]


def test_format_markdown_skips_empty():
    text = fb.format_markdown(fb.FEATURE, "批量旋转", {"area": "图片", "problem": "要一张张转"})
    assert text.startswith("# [建议] 批量旋转\n")
    assert "### 相关模块\n\n图片" in text
    assert "希望的做法" not in text


@pytest.mark.parametrize(("system", "machine", "expected"), [
    ("darwin", "arm64", "macOS（Apple 芯片）"),
    ("darwin", "x86_64", "macOS（Intel 芯片）"),
    ("linux", "x86_64", "Linux"),
    ("freebsd14", "amd64", "其他"),
])
def test_detect_os(system, machine, expected):
    assert fb.detect_os(system, machine) == expected
    assert expected in fb.OS_OPTIONS


def test_detect_install():
    assert fb.detect_install(packaged=False) == "从源码运行（python main.py）"
    assert fb.detect_install(packaged=True, system="win32") == "Releases 下载的 windows-x64.zip"
    assert fb.detect_install(packaged=True, system="freebsd") == "其他"


@pytest.mark.parametrize(("code", "name"), [
    ("zh_CN.UTF-8", "简体中文"), ("zh-Hans-CN", "简体中文"), ("zh_TW", "繁体中文"),
    ("en_US", "英文"), ("ja-JP", "日文"), ("fr_FR", "fr_FR"),
])
def test_language_name(code, name):
    assert fb.language_name(code) == name


def test_detect_environment_fills_auto_fields():
    env = fb.detect_environment()
    auto = {f.id for f in fb.BUG.fields if f.auto}
    assert set(env) == auto
    assert env["os"] in fb.OS_OPTIONS
    assert env["install"] in fb.INSTALL_OPTIONS
    assert all(env.values())
