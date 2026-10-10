"""
File Toolkit — 问题反馈

应用内的「问题反馈 / 功能建议」表单与仓库里的 GitHub Issue 表单
（.github/ISSUE_TEMPLATE/*.yml）一一对应：字段 id、选项文字都相同。
提交时不需要登录或令牌，只是拼出一个预填好的「新建 Issue」链接，用浏览器打开，
用户在 GitHub 页面上确认、拖入截图后提交。

修改 Issue 表单时要同步改这里，tests/services/test_feedback_service.py 会检查两边是否一致。
"""
from __future__ import annotations

import locale
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import urlencode

from core.version import app_version

REPO = "kekemao00/FileToolkit"
NEW_ISSUE_URL = f"https://github.com/{REPO}/issues/new"
ISSUES_URL = f"https://github.com/{REPO}/issues"

# GitHub 对过长的链接会直接报错，留出余量
MAX_URL_LENGTH = 7000
_TRUNCATED = "\n\n…（内容过长已截断，请在这里补充完整）"


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    kind: str                      # textarea / input / dropdown
    required: bool = True
    hint: str = ""                 # 说明文字
    placeholder: str = ""
    options: tuple[str, ...] = ()
    auto: bool = False             # 由应用自动检测（环境信息）


@dataclass(frozen=True)
class Form:
    key: str
    template: str                  # .github/ISSUE_TEMPLATE 下的文件名
    name: str
    heading: str                   # 表单卡片标题
    title_hint: str
    title_prefix: str
    intro: str
    fields: tuple[Field, ...]


OS_OPTIONS = (
    "Windows 11",
    "Windows 10",
    "macOS（Apple 芯片）",
    "macOS（Intel 芯片）",
    "Linux",
    "其他",
)

INSTALL_OPTIONS = (
    "Releases 下载的 windows-x64.zip",
    "Releases 下载的 macos-arm64.zip",
    "Releases 下载的 linux-x64.tar.gz",
    "从源码运行（python main.py）",
    "其他",
)

BUG_EXAMPLE = (
    "步骤：打开「PDF → 合并」，点「选择文件」按钮\n"
    "期望：弹出的选文件窗口跟随系统语言，显示中文\n"
    "实际：选文件窗口是英文的"
)

BUG = Form(
    key="bug",
    template="bug_report.yml",
    name="问题反馈",
    heading="描述问题",
    title_hint="一句话概括，例如：选文件窗口是英文的",
    title_prefix="[问题] ",
    intro="把问题按步骤描述清楚，让开发者能照着做一遍就看到同样的现象。",
    fields=(
        Field("steps", "复现步骤", "textarea",
              hint="在哪个页面、点了哪个按钮、选了什么文件（格式 / 大致大小）、改了哪些选项。一步一行。",
              placeholder="1. 打开「PDF」→「合并」\n2. 点「选择文件」按钮\n3. 弹出选文件窗口"),
        Field("expected", "期望结果", "textarea",
              hint="你认为应该发生什么？",
              placeholder="选文件窗口和我电脑的系统语言一致，显示中文"),
        Field("actual", "实际结果", "textarea",
              hint="实际发生了什么？有报错提示的话，把提示文字原样贴过来。",
              placeholder="选文件窗口显示的是英文"),
        Field("frequency", "出现频率", "dropdown",
              options=("每次都会出现", "偶尔出现", "只出现过一次")),
        Field("os", "操作系统", "dropdown", options=OS_OPTIONS, auto=True),
        Field("os_version", "系统版本与语言", "input",
              placeholder="例如 macOS 15.1，系统语言简体中文", auto=True),
        Field("app_version", "File Toolkit 版本", "input", placeholder="例如 1.6.0", auto=True),
        Field("install", "安装方式", "dropdown", options=INSTALL_OPTIONS, auto=True),
        Field("extra", "补充信息", "textarea", required=False,
              hint="例如是否装了 LibreOffice / Tesseract / unrar，升级前是否正常，其他你觉得有关的线索。"),
    ),
)

FEATURE = Form(
    key="feature",
    template="feature_request.yml",
    name="功能建议",
    heading="描述建议",
    title_hint="一句话概括，例如：图片转 PDF 时自动摆正方向",
    title_prefix="[建议] ",
    intro="比起「加一个 XX 功能」，更希望你讲讲想完成什么事、现在卡在哪。",
    fields=(
        Field("area", "相关模块", "dropdown", options=(
            "PDF", "图片", "音视频", "压缩解压", "文字识别", "AI / 提示词出图",
            "设置 / 更新 / 记录等应用整体", "新的模块",
        )),
        Field("problem", "你想解决什么问题？", "textarea",
              hint="描述使用场景，以及现在的做法哪里不方便。",
              placeholder="我经常要把手机拍的几十张发票合成 PDF，但现在每张都要手动旋转……"),
        Field("solution", "希望的做法", "textarea",
              hint="你期望在哪个页面、通过什么操作来完成，结果是什么样。",
              placeholder="在「图片 → 合成 PDF」里加一个「自动摆正方向」开关"),
        Field("alternatives", "其他参考", "textarea", required=False,
              hint="有没有别的软件做得好的例子，或者你考虑过的其他方案。"),
    ),
)

FORMS: dict[str, Form] = {BUG.key: BUG, FEATURE.key: FEATURE}


# ── 环境检测 ──────────────────────────────────────────────────────────
def _windows_is_11() -> bool:
    try:
        return sys.getwindowsversion().build >= 22000  # type: ignore[attr-defined]
    except AttributeError:
        return False


def detect_os(system: str | None = None, machine: str | None = None) -> str:
    """返回与 OS_OPTIONS 一致的选项文字。"""
    system = system or sys.platform
    machine = (machine or platform.machine()).lower()
    if system == "win32":
        return "Windows 11" if _windows_is_11() else "Windows 10"
    if system == "darwin":
        return "macOS（Apple 芯片）" if machine in ("arm64", "aarch64") else "macOS（Intel 芯片）"
    if system.startswith("linux"):
        return "Linux"
    return "其他"


def _os_version() -> str:
    if sys.platform == "win32":
        return f"Windows {'11' if _windows_is_11() else '10'}（{platform.version()}）"
    if sys.platform == "darwin":
        ver = platform.mac_ver()[0]
        return f"macOS {ver}" if ver else "macOS"
    if sys.platform.startswith("linux"):
        try:
            return platform.freedesktop_os_release().get("PRETTY_NAME", "Linux")
        except OSError:
            return f"Linux {platform.release()}"
    return platform.platform()


_LANG_NAMES = {
    "zh_cn": "简体中文", "zh_hans": "简体中文", "zh_sg": "简体中文",
    "zh_tw": "繁体中文", "zh_hk": "繁体中文", "zh_hant": "繁体中文",
    "en": "英文", "ja": "日文", "ko": "韩文",
}


def language_name(code: str) -> str:
    """把 zh_CN / zh-Hans-CN / en_US.UTF-8 之类的区域代码转成中文名；不认识的原样返回。"""
    norm = code.split(".")[0].replace("-", "_").lower()
    parts = norm.split("_")
    for n in (2, 1):
        name = _LANG_NAMES.get("_".join(parts[:n]))
        if name:
            return name
    return code


def _system_locale() -> str:
    try:
        if sys.platform == "win32":
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
            return locale.windows_locale.get(lcid, "")
        if sys.platform == "darwin":
            # 从 Finder 打开的 .app 没有 LANG，直接问系统
            out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"],
                                 capture_output=True, text=True, timeout=3).stdout
            first = out.strip("()\n ").split(",")[0].strip().strip('"')
            if first:
                return first
    except (OSError, AttributeError, subprocess.SubprocessError):
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(var):
            return os.environ[var]
    return locale.getlocale()[0] or ""


def detect_install(packaged: bool | None = None, system: str | None = None) -> str:
    """返回与 INSTALL_OPTIONS 一致的选项文字。"""
    if packaged is None:
        from services.update_installer import current_executable, is_packaged
        packaged = is_packaged(current_executable())
    if not packaged:
        return "从源码运行（python main.py）"
    from services.update_service import platform_key
    key = platform_key(system)
    for opt in INSTALL_OPTIONS:
        if key and key in opt:
            return opt
    return "其他"


def detect_environment() -> dict[str, str]:
    """自动填写的环境信息，键为字段 id。"""
    lang = _system_locale()
    version = _os_version()
    if lang:
        version = f"{version}，系统语言{language_name(lang)}"
    return {
        "os": detect_os(),
        "os_version": version,
        "app_version": app_version(),
        "install": detect_install(),
    }


# ── 生成链接 / 文本 ──────────────────────────────────────────────────
def missing_fields(form: Form, values: dict[str, str]) -> list[str]:
    """未填写的必填项（返回标签）。"""
    return [f.label for f in form.fields if f.required and not values.get(f.id, "").strip()]


def build_issue_url(form: Form, title: str, values: dict[str, str]) -> str:
    """预填好的新建 Issue 链接。字段 id 与 Issue 表单一致，GitHub 会按 id 填进对应输入框。

    链接太长时从最长的一项开始截断，保证 GitHub 能打开。
    """
    params = {"template": form.template, "title": form.title_prefix + title.strip()}
    for f in form.fields:
        v = values.get(f.id, "").strip()
        if v:
            params[f.id] = v

    def _url() -> str:
        return f"{NEW_ISSUE_URL}?{urlencode(params)}"

    url = _url()
    while len(url) > MAX_URL_LENGTH:
        longest = max((k for k in params if k != "template"), key=lambda k: len(params[k]))
        text = params[longest].removesuffix(_TRUNCATED)
        overflow = len(url) - MAX_URL_LENGTH
        # 编码后中文约 9 倍长，按比例估算要砍掉的字数
        ratio = max(1.0, len(urlencode({"": text})) / max(1, len(text)))
        keep = max(0, len(text) - int(overflow / ratio) - 20)
        params[longest] = text[:keep] + _TRUNCATED
        url = _url()
    return url


def format_markdown(form: Form, title: str, values: dict[str, str]) -> str:
    """复制用的纯文本（Markdown），没有 GitHub 账号时可以发给开发者。"""
    lines = [f"# {form.title_prefix}{title.strip()}", ""]
    for f in form.fields:
        v = values.get(f.id, "").strip()
        if v:
            lines += [f"### {f.label}", "", v, ""]
    return "\n".join(lines).rstrip() + "\n"
