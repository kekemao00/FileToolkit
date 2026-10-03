"""风格增强 — 可叠加到任何模板上的风格 / 光影 / 镜头 / 画质修饰词。

UI 以分组标签（chip）展示，用户点选后由 apply_modifiers() 追加到提示词末尾。
"""
from __future__ import annotations

# (分组名, [(id, 中文标签, 英文修饰词), ...])
MODIFIER_GROUPS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("画面风格", [
        ("photo", "写实摄影", "photorealistic photography"),
        ("cinematic", "电影感", "cinematic film still"),
        ("render3d", "3D 渲染", "high-end 3D render, octane render"),
        ("anime", "日系动漫", "anime illustration, cel shading"),
        ("watercolor", "水彩", "delicate watercolor painting"),
        ("oil", "油画", "textured oil painting"),
        ("flat", "扁平插画", "flat vector illustration"),
        ("cyberpunk", "赛博朋克", "cyberpunk aesthetic"),
        ("ink", "国风水墨", "traditional Chinese ink painting"),
        ("pixel", "像素风", "pixel art"),
        ("clay", "黏土", "claymation style"),
    ]),
    ("光影", [
        ("natural", "自然光", "soft natural light"),
        ("golden", "黄金时刻", "golden hour lighting"),
        ("studio", "影棚光", "professional studio lighting"),
        ("neon", "霓虹", "neon glow lighting"),
        ("rim", "轮廓光", "rim lighting"),
        ("volumetric", "体积光", "volumetric light rays"),
        ("dramatic", "戏剧明暗", "dramatic chiaroscuro lighting"),
    ]),
    ("镜头构图", [
        ("wide", "广角", "wide-angle shot"),
        ("closeup", "特写", "close-up shot"),
        ("macro", "微距", "macro photography"),
        ("topdown", "俯拍", "top-down view"),
        ("bokeh", "浅景深", "shallow depth of field, bokeh"),
        ("symmetric", "对称构图", "symmetrical composition"),
        ("thirds", "三分法", "rule of thirds composition"),
        ("tiltshift", "移轴", "tilt-shift effect"),
    ]),
    ("画质", [
        ("detailed", "高细节", "highly detailed"),
        ("8k", "8K 超清", "8K ultra high resolution"),
        ("sharp", "锐利对焦", "sharp focus"),
        ("grading", "专业调色", "professional color grading"),
        ("grain", "胶片颗粒", "subtle film grain"),
    ]),
]

_BY_ID: dict[str, str] = {mid: text for _, items in MODIFIER_GROUPS for mid, _, text in items}


def apply_modifiers(prompt: str, modifier_ids: list[str] | tuple[str, ...] = (),
                    negative: str = "") -> str:
    """把选中的修饰词和"避免出现"的内容追加到提示词末尾。"""
    prompt = (prompt or "").rstrip()
    extras = [_BY_ID[m] for m in modifier_ids if m in _BY_ID]
    if extras:
        sep = "" if not prompt or prompt.endswith((".", "。", ",", "，")) else "."
        prompt = f"{prompt}{sep} {', '.join(extras)}.".strip()
    negative = (negative or "").strip()
    if negative:
        prompt = f"{prompt}\nAvoid: {negative}."
    return prompt
