"""提示词库服务 — 汇总内置模板、我的模板、订阅源，并持久化收藏与生成历史。

数据都存在 settings 表（JSON 字符串），不新增表结构：
- prompt_lib_custom      我的模板（list[template]）
- prompt_lib_sources     订阅源元信息（list[{id, name, url, homepage, license, count, updated_at, enabled}]）
- prompt_lib_cache:<id>  订阅源下载解析后的模板（list[template]）
- prompt_lib_favorites   收藏的模板 id（list[str]）
- prompt_image_history   最近生成记录（list[{path, prompt, template, size, created_at}]）
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import httpx

from core.prompt_image import sources as src
from core.prompt_image import templates as tpl
from services import settings_service

CUSTOM_SOURCE = "custom"
FAVORITES = "favorites"
ALL = "all"

_KEY_CUSTOM = "prompt_lib_custom"
_KEY_SOURCES = "prompt_lib_sources"
_KEY_CACHE = "prompt_lib_cache:"
_KEY_FAVORITES = "prompt_lib_favorites"
_KEY_HISTORY = "prompt_image_history"

HISTORY_LIMIT = 40
MAX_SOURCE_BYTES = 8 * 1024 * 1024


# ── JSON 读写 ────────────────────────────────────────────────────────────
def _load(key: str, default):
    raw = settings_service.get(key, "")
    if not raw:
        return default
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default
    return value if isinstance(value, type(default)) else default


def _save(key: str, value) -> None:
    settings_service.set(key, json.dumps(value, ensure_ascii=False))


# ── 来源列表 ─────────────────────────────────────────────────────────────
def list_sources() -> list[dict]:
    """用户添加的订阅源（不含内置 / 我的模板）。"""
    return _load(_KEY_SOURCES, [])


def get_source(source_id: str) -> dict | None:
    return next((s for s in list_sources() if s.get("id") == source_id), None)


def source_label(source_id: str) -> str:
    if source_id == tpl.BUILTIN_SOURCE:
        return "内置模板"
    if source_id == CUSTOM_SOURCE:
        return "我的模板"
    s = get_source(source_id)
    return s["name"] if s else source_id


def source_options() -> list[tuple[str, str]]:
    """来源下拉框选项：[(key, 显示名)]。"""
    opts = [
        (ALL, "全部来源"),
        (tpl.BUILTIN_SOURCE, f"内置模板 · {len(tpl.TEMPLATES)}"),
        (CUSTOM_SOURCE, f"我的模板 · {len(list_custom())}"),
        (FAVORITES, f"我的收藏 · {len(list_favorites())}"),
    ]
    for s in list_sources():
        if s.get("enabled", True):
            opts.append((s["id"], f"{s['name']} · {s.get('count', 0)}"))
    return opts


def templates_for(source_key: str) -> list[dict]:
    """按来源取模板列表。"""
    if source_key == tpl.BUILTIN_SOURCE:
        return list(tpl.TEMPLATES)
    if source_key == CUSTOM_SOURCE:
        return list_custom()
    if source_key == FAVORITES:
        favs = list_favorites()
        everything = {t["id"]: t for t in templates_for(ALL)}
        return [everything[i] for i in favs if i in everything]
    if source_key == ALL:
        result = list_custom() + list(tpl.TEMPLATES)
        for s in list_sources():
            if s.get("enabled", True):
                result.extend(_cached(s["id"]))
        return result
    return _cached(source_key)


def _cached(source_id: str) -> list[dict]:
    return [src.drop_section_markers(t) for t in _load(_KEY_CACHE + source_id, [])]


def categories_for(templates: list[dict]) -> list[str]:
    cats = list(dict.fromkeys(t.get("category") or "未分类" for t in templates))
    return ["全部"] + cats


def find_template(template_id: str) -> dict | None:
    return next((t for t in templates_for(ALL) if t["id"] == template_id), None)


# ── 订阅源：下载 / 导入 / 刷新 / 删除 ─────────────────────────────────────
async def fetch_text(url: str) -> str:
    """下载提示词源文本（GitHub 页面地址自动换成 raw 地址）。"""
    url = normalize_url(url)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "FileToolkit"})
        resp.raise_for_status()
        if len(resp.content) > MAX_SOURCE_BYTES:
            raise src.SourceParseError("文件过大（超过 8 MB）")
        return resp.text


def normalize_url(url: str) -> str:
    """github.com/<owner>/<repo>/blob/<ref>/<path> → raw.githubusercontent.com 地址。"""
    url = url.strip()
    prefix = "https://github.com/"
    if url.startswith(prefix) and "/blob/" in url:
        owner_repo, rest = url[len(prefix):].split("/blob/", 1)
        return f"https://raw.githubusercontent.com/{owner_repo}/{rest}"
    return url


def _store_source(meta: dict, items: list[dict], *, source_id: str, url: str,
                  fallback_name: str, homepage: str = "", license_: str = "",
                  local_path: str = "") -> dict:
    record = {
        "id": source_id,
        "name": meta.get("name") or fallback_name,
        "url": url,
        "homepage": meta.get("homepage") or homepage,
        "license": meta.get("license") or license_,
        "count": len(items),
        "updated_at": int(time.time()),
        "enabled": True,
    }
    if local_path:
        record["path"] = local_path
    _save(_KEY_CACHE + source_id, items)
    all_sources = [s for s in list_sources() if s.get("id") != source_id]
    old = get_source(source_id)
    if old:
        # 刷新时保留用户改过的名称与启用状态
        record["name"] = old.get("name") or record["name"]
        record["enabled"] = old.get("enabled", True)
        all_sources = [record if s.get("id") == source_id else s for s in list_sources()]
    else:
        all_sources.append(record)
    _save(_KEY_SOURCES, all_sources)
    return record


async def add_source(url: str, name: str = "", homepage: str = "", license_: str = "") -> dict:
    """下载并解析一个 URL 提示词源，返回保存后的来源记录。"""
    url = normalize_url(url)
    existing = next((s for s in list_sources() if s.get("url") == url), None)
    source_id = existing["id"] if existing else f"src-{uuid.uuid4().hex[:8]}"
    text = await fetch_text(url)
    meta, items = src.parse_source(text, source_id, hint=url, default_license=license_)
    fallback = name or url.rstrip("/").split("/")[-1] or "提示词源"
    return _store_source(meta, items, source_id=source_id, url=url, fallback_name=fallback,
                         homepage=homepage, license_=license_)


def import_file(path: Path) -> dict:
    """从本地 JSON / CSV / Markdown 文件导入为一个来源。"""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    url = path.resolve().as_uri()
    existing = next((s for s in list_sources() if s.get("url") == url), None)
    source_id = existing["id"] if existing else f"src-{uuid.uuid4().hex[:8]}"
    meta, items = src.parse_source(text, source_id, hint=path.name)
    return _store_source(meta, items, source_id=source_id, url=url, fallback_name=path.stem,
                         local_path=str(path.resolve()))


async def refresh_source(source_id: str) -> dict:
    s = get_source(source_id)
    if not s:
        raise KeyError(source_id)
    if s.get("path"):
        return import_file(Path(s["path"]))
    return await add_source(s["url"], s.get("name", ""), s.get("homepage", ""), s.get("license", ""))


def remove_source(source_id: str) -> None:
    _save(_KEY_SOURCES, [s for s in list_sources() if s.get("id") != source_id])
    settings_service.set(_KEY_CACHE + source_id, "")
    prefix = f"{source_id}:"
    _save(_KEY_FAVORITES, [f for f in list_favorites() if not f.startswith(prefix)])


def set_source_enabled(source_id: str, enabled: bool) -> None:
    sources = list_sources()
    for s in sources:
        if s.get("id") == source_id:
            s["enabled"] = enabled
    _save(_KEY_SOURCES, sources)


# ── 我的模板 ─────────────────────────────────────────────────────────────
def list_custom() -> list[dict]:
    return _load(_KEY_CUSTOM, [])


def save_custom(name: str, prompt: str, *, category: str = "我的模板", description: str = "",
                default_size: str = "1024x1024", template_id: str = "") -> dict:
    """保存（新建或覆盖）一个自定义模板。提示词里的 {变量} 自动变为可填写项。"""
    prompt, variables = src.detect_variables(prompt.strip())
    template_id = template_id or f"{CUSTOM_SOURCE}:{uuid.uuid4().hex[:8]}"
    one_line = " ".join(prompt.split())
    item = {
        "id": template_id,
        "name": name.strip() or one_line[:20] or "未命名模板",
        "description": description.strip() or one_line[:80],
        "category": category.strip() or "我的模板",
        "icon": "BOOKMARK",
        "tags": ["自定义"],
        "prompt_template": prompt,
        "variables": variables,
        "default_size": default_size,
        "source": CUSTOM_SOURCE,
        "author": "", "link": "", "license": "",
    }
    items = list_custom()
    for i, t in enumerate(items):
        if t["id"] == template_id:
            items[i] = item
            break
    else:
        items.insert(0, item)
    _save(_KEY_CUSTOM, items)
    return item


def delete_custom(template_id: str) -> None:
    _save(_KEY_CUSTOM, [t for t in list_custom() if t["id"] != template_id])
    _save(_KEY_FAVORITES, [f for f in list_favorites() if f != template_id])


def export_custom_json() -> str:
    return src.to_export_json("我的提示词模板", list_custom())


# ── 收藏 ─────────────────────────────────────────────────────────────────
def list_favorites() -> list[str]:
    return _load(_KEY_FAVORITES, [])


def is_favorite(template_id: str) -> bool:
    return template_id in list_favorites()


def toggle_favorite(template_id: str) -> bool:
    favs = list_favorites()
    if template_id in favs:
        favs.remove(template_id)
        on = False
    else:
        favs.insert(0, template_id)
        on = True
    _save(_KEY_FAVORITES, favs)
    return on


# ── 生成历史 ─────────────────────────────────────────────────────────────
def list_history() -> list[dict]:
    """最近生成记录（新的在前），自动剔除已被删除的文件。"""
    return [h for h in _load(_KEY_HISTORY, []) if h.get("path") and Path(h["path"]).exists()]


def add_history(path: Path, prompt: str, template_name: str, size: str) -> dict:
    entry = {"path": str(path), "prompt": prompt, "template": template_name, "size": size,
             "created_at": int(time.time())}
    items = [h for h in _load(_KEY_HISTORY, []) if h.get("path") != str(path)]
    items.insert(0, entry)
    _save(_KEY_HISTORY, items[:HISTORY_LIMIT])
    return entry
