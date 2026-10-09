"""提示词源解析 — 把 JSON / CSV / Markdown 格式的提示词集合转换为统一模板结构。

支持的格式：
- JSON：`{"name": ..., "license": ..., "homepage": ..., "templates": [...]}` 或直接是列表。
  每条至少包含 name/title 与 prompt/prompt_template，其余字段可选（见 templates.py）。
- CSV：表头含 prompt 列，标题列可为 title / name / act，可选 category、tags、author。
- Markdown：GitHub 上常见的 "awesome prompts" README —— 每个 ##/### 标题下的第一个
  代码块视为一条提示词，标题里的 "(by @作者)" 作为署名，所在的 ## 标题作为分类。

提示词里的占位符会转换为可填写的变量：
- `{变量}`（本应用 / 自定义模板写法）
- `{argument name="变量" default="默认值"}`（部分 GPT Image 提示词库写法）
- `[主体]`（中文提示词库常见写法）
"""
from __future__ import annotations

import csv
import io
import json
import re

# 推荐的开源提示词源（只引用地址，运行时由用户自行下载，内容版权归原作者）
RECOMMENDED_SOURCES: list[dict] = [
    {
        "name": "Awesome GPT-4o Images",
        "url": "https://raw.githubusercontent.com/jamez-bondos/awesome-gpt4o-images/main/README.md",
        "homepage": "https://github.com/jamez-bondos/awesome-gpt4o-images",
        "license": "CC BY 4.0",
        "description": "100+ 个中文 GPT-4o / gpt-image 精选案例，每条署名原作者",
    },
    {
        "name": "Awesome GPT Image 2 Prompts",
        "url": "https://raw.githubusercontent.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts/main/README_zh-CN.md",
        "homepage": "https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts",
        "license": "CC0-1.0",
        "description": "数百条 GPT Image 2 提示词：电商、广告、人像、海报等分类",
    },
]

MAX_VARIABLES = 8

_ARG_RE = re.compile(r'\{argument\s+name="([^"]{1,40})"(?:\s+default="([^"]*)")?\s*\}')
_CURLY_RE = re.compile(r"\{([^{}\"\n:=]{1,20})\}")
_BRACKET_RE = re.compile(r"\[([一-鿿A-Za-z][一-鿿A-Za-z /／、]{0,11})\](?!\()")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_WEB_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\((https?://[^)\s]*)\)")
_AUTHOR_RE = re.compile(r"\(\s*by\s+\[?\s*(@?[\w.\-]+)", re.IGNORECASE)
_TITLE_PREFIX_RE = re.compile(r"^(case|example|案例|示例)\s*\d+\s*[:：.\-]?\s*", re.IGNORECASE)
_HEADING_RE = re.compile(r"^(#{2,4})\s+(.*\S)\s*$")
# 代码块语言标记为这些时不是提示词（安装命令、API 示例等）
_CODE_LANGS = {"bash", "sh", "shell", "zsh", "python", "py", "js", "javascript", "ts",
               "typescript", "json", "yaml", "yml", "toml", "html", "css", "curl",
               "powershell", "ps1", "console", "go", "java", "c", "cpp", "rust", "sql"}
# 常见英文提示词库分类 → 中文
_CATEGORY_ZH = {
    "E-commerce": "电商", "Ad Creative": "广告创意", "Portrait & Photography": "人像摄影",
    "Poster & Illustration": "海报插画", "Character Design": "角色设计",
    "UI & Social Media Mockup": "UI 与社媒", "Comparison & Community Examples": "对比与社区",
    "Poster": "海报", "Illustration": "插画", "Portrait": "人像", "Photography": "摄影",
    "Logo": "Logo", "Product": "产品", "Architecture": "建筑", "Interior": "室内",
}
_GENERIC_CATEGORIES = {"", "案例", "cases", "case", "目录", "examples", "prompts", "提示词"}


class SourceParseError(ValueError):
    """提示词源内容无法解析。"""


# ── 变量识别 ─────────────────────────────────────────────────────────────
def detect_variables(prompt: str, *, include_brackets: bool = False) -> tuple[str, list[dict]]:
    """识别提示词里的占位符，返回 (规范化后的提示词, 变量列表)。

    规范化：`{argument name="x" default="y"}` 与 `[x]` 统一改写为 `{x}`。
    """
    variables: list[dict] = []
    seen: set[str] = set()

    def add(label: str, default: str = "", required: bool = True) -> bool:
        label = label.strip()
        if not label or label in seen:
            return label in seen
        if len(variables) >= MAX_VARIABLES or label.isdigit():
            return False
        seen.add(label)
        variables.append({
            "name": label, "label": label, "type": "text",
            "placeholder": default or f"填写{label}", "required": required and not default,
            "default": default,
        })
        return True

    def repl_arg(m: re.Match) -> str:
        label, default = m.group(1), m.group(2) or ""
        return f"{{{label.strip()}}}" if add(label, default) else (default or label)

    prompt = _ARG_RE.sub(repl_arg, prompt)

    for m in _CURLY_RE.finditer(prompt):
        if not _is_section_marker(prompt, m.start(), m.end(), m.group(1)):
            add(m.group(1))

    if include_brackets:
        def repl_bracket(m: re.Match) -> str:
            return f"{{{m.group(1).strip()}}}" if add(m.group(1)) else m.group(0)
        prompt = _BRACKET_RE.sub(repl_bracket, prompt)

    # 只保留真正被识别为变量的花括号，其余保持原样（assemble 时不会替换）
    return prompt, variables


def _is_section_marker(prompt: str, start: int, end: int, label: str) -> bool:
    """独占一行的全大写 `{PROJECT CARD}` 是长提示词里的分段标题，不是待填写的变量。"""
    label = label.strip()
    if " " not in label or label != label.upper() or not any(ch.isalpha() for ch in label):
        return False
    line_start = prompt.rfind("\n", 0, start) + 1
    line_end = prompt.find("\n", end)
    line = prompt[line_start:line_end if line_end != -1 else len(prompt)]
    return line.strip() == prompt[start:end]


def drop_section_markers(template: dict) -> dict:
    """旧版本导入的缓存里，分段标题被误识别成了必填变量，读取时去掉。"""
    prompt = template.get("prompt_template") or ""
    variables = template.get("variables") or []

    def is_marker(var: dict) -> bool:
        token = "{" + var["name"] + "}"
        pos = prompt.find(token)
        return pos != -1 and _is_section_marker(prompt, pos, pos + len(token), var["name"])

    kept = [v for v in variables if not is_marker(v)]
    if len(kept) != len(variables):
        template = {**template, "variables": kept}
    return template


def guess_size(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("9:16", "3:4", "2:3", "vertical", "portrait format", "竖版", "竖屏")):
        return "1024x1536"
    if any(k in t for k in ("16:9", "4:3", "3:2", "horizontal", "landscape format", "横版", "横屏")):
        return "1536x1024"
    return "1024x1024"


def make_template(*, source_id: str, index: int, name: str, prompt: str,
                  category: str = "", description: str = "", tags: list[str] | None = None,
                  author: str = "", link: str = "", license_: str = "",
                  variables: list[dict] | None = None, default_size: str = "",
                  icon: str = "AUTO_AWESOME", include_brackets: bool = True) -> dict:
    """组装一条标准模板。未提供 variables 时从提示词里自动识别。"""
    prompt = prompt.strip()
    if variables is None:
        prompt, variables = detect_variables(prompt, include_brackets=include_brackets)
    one_line = " ".join(prompt.split())
    return {
        "id": f"{source_id}:{index}",
        "name": (name or one_line[:24] or f"提示词 {index + 1}").strip()[:60],
        "description": (description or one_line[:80]).strip(),
        "category": _CATEGORY_ZH.get((category or "").strip(), (category or "未分类").strip()[:30]),
        "icon": icon,
        "tags": [t for t in (tags or []) if t][:4],
        "prompt_template": prompt,
        "variables": variables,
        "default_size": default_size or guess_size(prompt),
        "source": source_id,
        "author": author,
        "link": link,
        "license": license_,
    }


# ── 解析入口 ─────────────────────────────────────────────────────────────
def parse_source(text: str, source_id: str, *, hint: str = "",
                 default_license: str = "") -> tuple[dict, list[dict]]:
    """解析提示词源文本，返回 (元信息, 模板列表)。

    hint 是 URL 或文件名，用扩展名辅助判断格式。
    元信息：{"name", "license", "homepage", "format"}，缺失项为空字符串。
    """
    text = text.lstrip("﻿")
    stripped = text.lstrip()
    lower_hint = hint.lower().split("?")[0]
    if lower_hint.endswith(".json") or stripped.startswith(("{", "[")):
        meta, items = _parse_json(text, source_id)
    elif lower_hint.endswith((".csv", ".tsv")):
        meta, items = _parse_csv(text, source_id, delimiter="\t" if lower_hint.endswith(".tsv") else ",")
    else:
        meta, items = {"format": "markdown"}, _parse_markdown(text, source_id)
    meta.setdefault("name", "")
    meta.setdefault("homepage", "")
    meta["license"] = meta.get("license") or default_license
    if default_license or meta["license"]:
        for t in items:
            t["license"] = t.get("license") or meta["license"]
    if not items:
        raise SourceParseError("没有找到可用的提示词，请确认链接内容是 JSON / CSV / Markdown 提示词集合")
    return meta, items


def _parse_json(text: str, source_id: str) -> tuple[dict, list[dict]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SourceParseError(f"JSON 格式错误：{e}") from e
    meta: dict = {"format": "json"}
    if isinstance(data, dict):
        meta.update({k: str(data.get(k) or "") for k in ("name", "license", "homepage")})
        raw = data.get("templates") or data.get("prompts") or data.get("items") or data.get("data") or []
    elif isinstance(data, list):
        raw = data
    else:
        raw = []
    items: list[dict] = []
    for i, entry in enumerate(raw):
        if isinstance(entry, str):
            entry = {"prompt": entry}
        if not isinstance(entry, dict):
            continue
        prompt = entry.get("prompt_template") or entry.get("prompt") or entry.get("content") or ""
        if not isinstance(prompt, str) or not prompt.strip():
            continue
        tags = entry.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in re.split(r"[,，|]", tags)]
        variables = entry.get("variables")
        if not (isinstance(variables, list) and all(isinstance(v, dict) and v.get("name") for v in variables)):
            variables = None
        items.append(make_template(
            source_id=source_id, index=i,
            name=str(entry.get("name") or entry.get("title") or entry.get("act") or ""),
            prompt=prompt, category=str(entry.get("category") or ""),
            description=str(entry.get("description") or ""), tags=[str(t) for t in tags],
            author=str(entry.get("author") or ""), link=str(entry.get("link") or entry.get("url") or ""),
            license_=str(entry.get("license") or ""), variables=variables,
            default_size=str(entry.get("default_size") or ""),
            icon=str(entry.get("icon") or "AUTO_AWESOME"),
            include_brackets=False,
        ))
    return meta, items


def _parse_csv(text: str, source_id: str, delimiter: str = ",") -> tuple[dict, list[dict]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise SourceParseError("CSV 没有表头")
    fields = {f.strip().lower(): f for f in reader.fieldnames if f}
    prompt_col = fields.get("prompt") or fields.get("prompt_template") or fields.get("content")
    if not prompt_col:
        raise SourceParseError("CSV 缺少 prompt 列")
    title_col = fields.get("title") or fields.get("name") or fields.get("act")
    items: list[dict] = []
    for i, row in enumerate(reader):
        prompt = (row.get(prompt_col) or "").strip()
        if not prompt:
            continue
        tags_raw = row.get(fields.get("tags", ""), "") or ""
        items.append(make_template(
            source_id=source_id, index=i,
            name=(row.get(title_col) or "") if title_col else "",
            prompt=prompt,
            category=row.get(fields.get("category", ""), "") or "",
            tags=[t.strip() for t in re.split(r"[,，|]", tags_raw)],
            author=row.get(fields.get("author", ""), "") or "",
            include_brackets=False,
        ))
    return {"format": "csv"}, items


def _clean_category(title: str) -> str:
    title = _LINK_RE.sub(r"\1", title)
    title = re.sub(r"^[^\w一-鿿]+", "", title).strip()
    title = re.sub(r"\s*(cases|case|案例)$", "", title, flags=re.IGNORECASE).strip()
    return "" if title.lower() in _GENERIC_CATEGORIES else title


def _parse_heading(title: str) -> tuple[str, str, str]:
    """标题 → (名称, 作者, 链接)。"""
    author = ""
    m = _AUTHOR_RE.search(title)
    if m:
        author = m.group(1)
        title = title[:m.start()]
    link = ""
    lm = _LINK_RE.search(title)
    if lm:
        link = lm.group(2)
    title = _LINK_RE.sub(r"\1", title)
    title = re.sub(r"[*_`]", "", title)
    title = _TITLE_PREFIX_RE.sub("", title.strip())
    return title.strip(" -—:："), author, link


def _parse_markdown(text: str, source_id: str) -> list[dict]:
    items: list[dict] = []
    category = ""
    current: dict | None = None
    in_code = False
    fence = ""
    code_lang = ""
    code: list[str] = []

    def flush_entry() -> None:
        if current and current.get("prompt"):
            items.append(make_template(
                source_id=source_id, index=len(items), name=current["name"],
                prompt=current["prompt"], category=current["category"],
                author=current["author"], link=current["link"],
                tags=[current["category"]] if current["category"] else [],
            ))

    for line in text.splitlines():
        stripped = line.strip()
        if in_code:
            if stripped.startswith(fence) and stripped.strip("`~") == "":
                in_code = False
                body = "\n".join(code).strip()
                if (current is not None and not current.get("prompt") and body
                        and code_lang not in _CODE_LANGS and len(body) >= 15):
                    current["prompt"] = body
                code = []
            else:
                code.append(line)
            continue
        if stripped.startswith(("```", "~~~")):
            in_code = True
            fence = stripped[:3]
            code_lang = stripped[3:].strip().lower()
            continue
        m = _HEADING_RE.match(line)
        if m:
            flush_entry()
            level, title = len(m.group(1)), m.group(2)
            if level == 2:
                category = _clean_category(title)
            name, author, link = _parse_heading(title)
            current = {"name": name, "author": author, "link": link,
                       "category": category or "精选", "prompt": ""}
            continue
        # 标题后紧跟的 "[原文链接](...)" 补充为来源链接
        if current is not None and not current["link"]:
            lm = _WEB_LINK_RE.search(stripped)
            if lm:
                current["link"] = lm.group(2)
    flush_entry()
    return items


def to_export_json(name: str, templates: list[dict]) -> str:
    """导出为本应用的 JSON 提示词源格式（可分享给他人订阅 / 导入）。"""
    keep = ("name", "description", "category", "tags", "prompt_template", "variables",
            "default_size", "author", "link", "license")
    data = {
        "name": name,
        "templates": [{k: t.get(k) for k in keep if t.get(k)} for t in templates],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
