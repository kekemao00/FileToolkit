"""转 Markdown 的公共工具：图片输出、表格、文本整理、token 估算。"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

# 图片处理方式
IMAGE_EXTRACT = "extract"  # 单独保存到 <名称>_assets/，MD 用相对路径引用
IMAGE_SKIP = "skip"        # 不要图片（最省 token）
IMAGE_EMBED = "embed"      # base64 内嵌进 MD

_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
         "bmp": "image/bmp", "webp": "image/webp", "svg": "image/svg+xml", "tif": "image/tiff",
         "tiff": "image/tiff", "emf": "image/emf", "wmf": "image/wmf"}


@dataclass
class MdDoc:
    """一个文件转出的 Markdown 正文和附带信息。"""
    text: str
    meta: dict[str, str | int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class ImageSink:
    """收集文档里的图片，按处理方式返回 MD 引用。

    assets_dir 在第一次真正写图片时才创建；同一张图（内容相同）只保存一次。
    """

    def __init__(self, mode: str, assets_dir: Path | None = None, md_dir: Path | None = None,
                 prefix: str = "image") -> None:
        self.mode = mode
        self.assets_dir = assets_dir
        self.md_dir = md_dir
        self.prefix = prefix
        self.files: list[Path] = []
        self._seen: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return self.mode != IMAGE_SKIP

    def add(self, data: bytes, ext: str, alt: str = "") -> str:
        """返回图片的 MD 写法（不要图片时返回空串）。"""
        if not self.enabled or not data:
            return ""
        ext = (ext or "png").lower().lstrip(".")
        ext = "jpg" if ext == "jpeg" else ext
        digest = hashlib.sha1(data).hexdigest()
        if digest in self._seen:
            return image_md(alt, self._seen[digest])
        if self.mode == IMAGE_EMBED:
            target = f"data:{_MIME.get(ext, 'application/octet-stream')};base64," + \
                base64.b64encode(data).decode("ascii")
        else:
            assert self.assets_dir is not None
            self.assets_dir.mkdir(parents=True, exist_ok=True)
            path = self.assets_dir / f"{self.prefix}_{len(self.files) + 1:03d}.{ext}"
            path.write_bytes(data)
            self.files.append(path)
            base = self.md_dir or self.assets_dir.parent
            target = path.relative_to(base).as_posix()
        self._seen[digest] = target
        return image_md(alt, target)

    def add_file(self, path: Path, alt: str = "") -> str:
        try:
            data = path.read_bytes()
        except OSError:
            return ""
        return self.add(data, path.suffix, alt)


def image_md(alt: str, target: str) -> str:
    alt = re.sub(r"[\[\]\n]", " ", alt or "").strip()
    if " " in target or "(" in target or ")" in target:
        target = f"<{target}>"
    return f"![{alt}]({target})"


def cell_text(value: str) -> str:
    """表格单元格：竖线转义，换行改为 <br>。"""
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\n{2,}", "\n", text)
    return text.replace("|", "\\|").replace("\n", "<br>")


def table_md(rows: list[list[str]]) -> str:
    """二维文本 → GFM 表格，首行作表头。全空的行和列会被去掉。"""
    rows = [[cell_text(c if c is not None else "") for c in r] for r in rows]
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    keep = [j for j in range(width) if any(r[j] for r in rows)]
    rows = [[r[j] for j in keep] for r in rows]
    if not keep:
        return ""
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "|".join(" --- " for _ in keep) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def normalize_md(text: str) -> str:
    """统一换行、去掉行尾空白、最多保留一个空行，结尾一个换行。代码块内容不动。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    out: list[str] = []
    in_fence = False
    blank = 0
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence:
            line = line.rstrip()
            if not line:
                blank += 1
                if blank > 1:
                    continue
            else:
                blank = 0
        out.append(line)
    return "\n".join(out).strip("\n") + "\n"


def front_matter(meta: dict[str, str | int]) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, int):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f'{k}: "{str(v).replace(chr(34), chr(39))}"')
    lines.append("---")
    return "\n".join(lines) + "\n\n"


_CJK = re.compile(r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]")
_DATA_URI = re.compile(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+")


def estimate_tokens(text: str) -> int:
    """粗估 token：中日韩字符约 1 字 1 token，其余按词约 1.3 token。base64 图片按长度/4 计。"""
    uri_tokens = sum(len(m) // 4 for m in _DATA_URI.findall(text))
    text = _DATA_URI.sub("", text)
    cjk = len(_CJK.findall(text))
    words = len(re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", _CJK.sub(" ", text)))
    return cjk + round(words * 1.3) + uri_tokens


def is_cjk(ch: str) -> bool:
    return bool(ch) and bool(_CJK.match(ch))


def join_lines(a: str, b: str) -> str:
    """把 PDF / 文本里被折行的两行拼回一句：中文之间不加空格，英文连字符断词去掉连字符。"""
    if not a:
        return b
    if not b:
        return a
    if a.endswith("-") and len(a) > 1 and a[-2].isalpha() and b[:1].islower():
        return a[:-1] + b
    if is_cjk(a[-1]) or is_cjk(b[0]):
        return a + b
    return a + " " + b


def read_text_file(path: Path) -> str:
    """按 UTF-8 → GB18030 → Latin-1 顺序尝试解码文本文件。"""
    data = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")
