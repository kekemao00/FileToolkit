"""智能入口 — 把一句话需求拆成步骤，并匹配到功能目录里的工具。

纯本地规则：按连接词切分句子，用功能的关键词打分；同分时参考上一步产出的
文件类型（如"图片转 PDF 再加水印"的水印落到 PDF 上）或附件的扩展名。
"""
import re
from pathlib import Path

from ui.features import FEATURES, Feature

_SPLIT = re.compile(r"然后|之后|接着|再|并且|并|，|,|、|；|;|。|和|及")
_TO = re.compile(r"转换?[成为]|变成|改成|换成")

_EXT_GROUP = {
    "pdf": "PDF",
    **dict.fromkeys(("jpg", "jpeg", "png", "webp", "bmp", "gif", "tif", "tiff", "heic", "heif"), "图片"),
    **dict.fromkeys(("mp4", "mov", "avi", "mkv", "flv", "wmv", "webm", "mp3", "wav", "aac",
                     "flac", "m4a", "ogg"), "音视频"),
    **dict.fromkeys(("zip", "7z", "rar", "tar", "gz", "tgz"), "压缩解压"),
}

# 这些功能的产物换了类型，后续步骤按新类型匹配
_OUTPUT_GROUP = {
    "/image?func=to_pdf": "PDF",
    "/pdf?func=from_office": "PDF",
    "/pdf?func=to_images": "图片",
    "/media?func=audio_extract": "音视频",
}

_CANDIDATES = [f for f in FEATURES if f.group not in ("AI", "应用")]


_PHOTO = re.compile(r"照片|相片|图像")


def _norm(text: str) -> str:
    return _PHOTO.sub("图片", _TO.sub("转", re.sub(r"\s+", "", text.lower())))


def _terms(feature: Feature) -> set[str]:
    words = {_norm(k) for k in feature.keywords}
    words.update(_norm(t) for t in re.split(r"[\s/]+", feature.title))
    return {w for w in words if len(w) >= 2}


_TERMS = {f.route: _terms(f) for f in _CANDIDATES}


def _file_group(files: list[Path]) -> str | None:
    groups = [_EXT_GROUP.get(p.suffix.lower().lstrip(".")) for p in files]
    groups = [g for g in groups if g]
    return max(set(groups), key=groups.count) if groups else None


def _best(segment: str, context: str | None) -> Feature | None:
    best, best_score = None, 0
    for feature in _CANDIDATES:
        score = sum(len(t) for t in _TERMS[feature.route] if t in segment)
        if not score:
            continue
        if _norm(feature.group) in segment:
            score += 3
        elif feature.group == context:
            score += 2
        if score > best_score:
            best, best_score = feature, score
    return best


def plan_steps(text: str, files: list[Path] | None = None) -> list[Feature]:
    """一句话 → 有序的功能步骤（去掉相邻重复，匹配不到的片段跳过）。"""
    context = _file_group(files or [])
    steps: list[Feature] = []
    for raw in _SPLIT.split(_norm(text)):
        if not raw:
            continue
        feature = _best(raw, context)
        if feature is None or (steps and steps[-1] == feature):
            continue
        steps.append(feature)
        context = _OUTPUT_GROUP.get(feature.route, feature.group)
    return steps
