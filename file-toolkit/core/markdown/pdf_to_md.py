"""PDF 转 Markdown。

文字型 PDF：按字号识别标题，把折行拼回段落，识别表格和项目符号，去掉每页重复的页眉页脚和页码。
没有文字的页（扫描件）在装了 Tesseract 时自动 OCR。
"""
from __future__ import annotations

import io
import re
import statistics
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from core.markdown._common import ImageSink, MdDoc, join_lines, table_md
from core.models import ProgressCallback
from core.task_control import check_cancelled

_BULLETS = "•●▪■◦○·‣⁃–—-*►▶✓✔◆◇□"
_BULLET_RE = re.compile(rf"^[{re.escape(_BULLETS)}]\s*")
_NUMBERED_RE = re.compile(
    r"^(?:\(?\d{1,3}[.)、．]|\(\d{1,3}\)|（\d{1,3}）|[一二三四五六七八九十]{1,3}[、.．]|"
    r"[（(][一二三四五六七八九十]{1,3}[)）]|第[一二三四五六七八九十百\d]+[章节条部分篇])\s*"
)
_SENTENCE_END = tuple("。！？；：.!?;:」』”）)")
_PAGE_NUM_RE = re.compile(
    r"^(?:[-–—\s]*\d+[-–—\s]*|第\s*\d+\s*页(?:\s*[,，/]?\s*共\s*\d+\s*页)?|\d+\s*/\s*\d+|"
    r"page\s*\d+(?:\s*of\s*\d+)?)$", re.I)


@dataclass
class _Line:
    text: str
    top: float
    bottom: float
    x0: float
    x1: float
    size: float
    bold: bool


@dataclass
class _Page:
    number: int
    width: float
    height: float
    items: list[tuple[float, str, object]] = field(default_factory=list)  # (top, kind, data)
    ocr_text: str | None = None
    no_text: bool = False


_CID = re.compile(r"\(cid:\d+\)")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\ufffd]")


def _clean(text: str) -> str:
    """字体没有 Unicode 映射的字形：行首的当作项目符号，其余去掉；控制字符去掉。"""
    text = _CONTROL.sub("", text)
    text = re.sub(r"^\s*\(cid:\d+\)\s*", "• ", text)
    return re.sub(r"\s{2,}", " ", _CID.sub("", text)).strip()


def _line_from(raw: dict) -> _Line | None:
    chars = [c for c in raw.get("chars", [])
             if c.get("text", "").strip() and not _CID.fullmatch(c["text"]) and not _CONTROL.fullmatch(c["text"])]
    text = _clean(raw.get("text") or "")
    if not text or not chars:
        return None
    sizes = [round(float(c.get("size", 0)), 1) for c in chars]
    bold = sum(1 for c in chars if re.search(r"bold|black|heavy|semibold", str(c.get("fontname", "")), re.I))
    return _Line(text=text, top=float(raw["top"]), bottom=float(raw["bottom"]),
                 x0=float(raw["x0"]), x1=float(raw["x1"]),
                 size=statistics.median(sizes), bold=bold >= len(chars) * 0.8)


def _inside(line: _Line, boxes: list[tuple[float, float, float, float]]) -> bool:
    cy = (line.top + line.bottom) / 2
    cx = (line.x0 + line.x1) / 2
    return any(x0 - 1 <= cx <= x1 + 1 and top - 1 <= cy <= bottom + 1 for x0, top, x1, bottom in boxes)


def _read_page(page, number: int, images: ImageSink) -> _Page:
    out = _Page(number=number, width=float(page.width), height=float(page.height))
    boxes: list[tuple[float, float, float, float]] = []
    try:
        tables = page.find_tables()
    except Exception:
        tables = []
    for t in tables:
        try:
            rows = t.extract()
        except Exception:
            continue
        # 只有一行或一列的「表格」多半是带框线的文字段落，按普通文字处理
        if len(rows) < 2 or max((len(r) for r in rows), default=0) < 2:
            continue
        md = table_md([[_clean(c or "") for c in r] for r in rows])
        if md:
            boxes.append(tuple(t.bbox))
            out.items.append((float(t.bbox[1]), "table", md))

    for raw in page.extract_text_lines(return_chars=True, strip=True):
        line = _line_from(raw)
        if line and not _inside(line, boxes):
            out.items.append((line.top, "line", line))

    if not any(k == "line" for _, k, _ in out.items) and not boxes:
        out.no_text = True

    if images.enabled and not out.no_text:
        page_area = out.width * out.height
        for im in page.images:
            x0, top, x1, bottom = (max(0.0, float(im["x0"])), max(0.0, float(im["top"])),
                                   min(out.width, float(im["x1"])), min(out.height, float(im["bottom"])))
            w, h = x1 - x0, bottom - top
            if w < 40 or h < 40 or w * h > page_area * 0.9:
                continue  # 图标、装饰线条、整页背景图
            try:
                pil = page.crop((x0, top, x1, bottom)).to_image(resolution=150).original
                buf = io.BytesIO()
                pil.convert("RGB").save(buf, "PNG", optimize=True)
            except Exception:
                continue
            md = images.add(buf.getvalue(), "png")
            if md:
                out.items.append((top, "image", md))
    out.items.sort(key=lambda it: it[0])
    return out


def _in_margin(p: _Page, top: float, line, body: float | None = None) -> bool:
    """页面顶部 / 底部 7% 区域里、字号不比正文大的行（页眉页脚候选）。"""
    if body is not None and line.size > body * 1.15:
        return False
    return top < p.height * 0.07 or top > p.height * 0.93


def _repeated_margins(pages: list[_Page], body: float) -> set[str]:
    """页眉页脚：在一半以上页面的顶部 / 底部重复出现的文字（数字视为相同）。"""
    if len(pages) < 3:
        return set()
    counts: Counter[str] = Counter()
    for p in pages:
        seen = set()
        for top, kind, data in p.items:
            if kind == "line" and _in_margin(p, top, data, body):
                seen.add(re.sub(r"\d+", "#", data.text))  # type: ignore[attr-defined]
        counts.update(seen)
    need = max(2, len(pages) // 2)
    return {k for k, n in counts.items() if n >= need}


def _ocr_page(pdf_path: Path, index: int, tess: Path, language: str) -> str:
    import pypdfium2 as pdfium

    from core.ocr.client import _tesseract

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        with tempfile.TemporaryDirectory(prefix="ftk-md-ocr-") as tmp:
            png = Path(tmp) / "page.png"
            doc[index].render(scale=200 / 72).to_pil().save(png)
            return _tesseract(tess, png, language)
    finally:
        doc.close()


def _ocr_language(tess: Path) -> str:
    from core.ocr.client import installed_languages

    langs = installed_languages(tess)
    picked = [lang for lang in ("chi_sim", "eng") if lang in langs]
    return "+".join(picked) or "eng"


def _text_to_paragraphs(text: str) -> list[str]:
    paras = []
    for block in re.split(r"\n\s*\n", text):
        merged = ""
        for ln in block.splitlines():
            merged = join_lines(merged, ln.strip())
        if merged:
            paras.append(merged)
    return paras


class _Writer:
    def __init__(self, body_size: float, heading_sizes: list[float]) -> None:
        self.body = body_size
        self.levels = {size: i + 1 for i, size in enumerate(heading_sizes[:3])}
        self.blocks: list[str] = []
        self.para: str = ""
        self.prev: _Line | None = None
        self.left = 0.0
        self.right = 0.0
        self.page_break = False  # 新的一页开始：上一页没写完的段落可能接着写

    def flush(self) -> None:
        if self.para:
            self.blocks.append(self.para)
        self.para = ""
        self.prev = None

    def heading_level(self, line: _Line) -> int:
        if len(line.text) > 120:
            return 0
        for size, level in self.levels.items():
            if abs(line.size - size) < 0.6:
                return level
        if line.bold and line.size >= self.body - 0.5 and len(line.text) <= 40 \
                and not line.text.endswith(_SENTENCE_END) and not _BULLET_RE.match(line.text):
            return min(len(self.levels) + 1, 4)
        return 0

    def line(self, line: _Line) -> None:
        level = self.heading_level(line)
        if level:
            # 同一个标题被折成两行（字号相同、紧挨着）时拼回一行
            if self.blocks and self.para == "" and self.prev is not None and self.prev.size == line.size \
                    and line.top - self.prev.bottom < line.size * 0.8 and self.blocks[-1].startswith("#" * level + " "):
                self.blocks[-1] = join_lines(self.blocks[-1], line.text)
            else:
                self.flush()
                self.blocks.append("#" * level + " " + line.text)
            self.prev = line
            return
        text = line.text
        bullet = _BULLET_RE.match(text)
        indented = line.x0 - self.left >= line.size * 1.5
        prev = self.prev
        if prev is None or not self.para or bullet or _NUMBERED_RE.match(text) \
                or abs(line.size - prev.size) > 1.0:
            new_para = True
        elif self.page_break:
            new_para = indented
        else:
            new_para = (
                line.top - prev.bottom > max(line.size, prev.size) * 0.7
                or line.top < prev.top - 1  # 换栏
                or (indented and prev.x0 - self.left < line.size * 1.5)
                or (prev.text.endswith(_SENTENCE_END) and self.right - prev.x1 > line.size * 2)
                or prev.x1 - self.left < (self.right - self.left) * 0.5  # 上一行很短：多半是单独的一行
            )
        self.page_break = False
        if bullet:
            text = "- " + text[bullet.end():]
        if new_para:
            if self.para:
                self.blocks.append(self.para)
            self.para = text
        else:
            self.para = join_lines(self.para, text)
        self.prev = line

    def raw(self, md: str) -> None:
        self.flush()
        self.blocks.append(md)


def pdf_to_md(path: Path, images: ImageSink, page_markers: bool = False,
              progress_callback: ProgressCallback | None = None) -> MdDoc:
    import pdfplumber

    pages: list[_Page] = []
    warnings: list[str] = []
    meta: dict[str, str | int] = {}
    with pdfplumber.open(str(path)) as pdf:
        total = len(pdf.pages)
        meta["pages"] = total
        title = str((pdf.metadata or {}).get("Title") or "").strip()
        if title and not title.lower().startswith(("microsoft", "untitled")):
            meta["title"] = title
        for i, page in enumerate(pdf.pages):
            check_cancelled()
            pages.append(_read_page(page, i + 1, images))
            page.flush_cache()
            if progress_callback:
                progress_callback(i + 1, total, f"读取第 {i + 1}/{total} 页")

    # 没有文字的页：有 Tesseract 就 OCR
    blank = [p for p in pages if p.no_text]
    if blank:
        from core.ocr.client import find_tesseract

        tess = find_tesseract()
        if tess is not None:
            language = _ocr_language(tess)
            for n, p in enumerate(blank, start=1):
                check_cancelled()
                if progress_callback:
                    progress_callback(n - 1, len(blank), f"OCR 识别第 {p.number} 页（{n}/{len(blank)}）")
                try:
                    p.ocr_text = _ocr_page(path, p.number - 1, tess, language)
                except Exception as exc:  # 单页识别失败不影响其他页
                    warnings.append(f"{path.name} 第 {p.number} 页 OCR 失败：{exc}")
        elif len(blank) == len(pages):
            raise RuntimeError("这份 PDF 没有可提取的文字（可能是扫描件）。安装 Tesseract OCR 后可自动识别，"
                               "安装方法见「OCR 识别」页")

    lines = [d for p in pages for _, k, d in p.items if k == "line"]
    weights: Counter[float] = Counter()
    for ln in lines:
        weights[round(ln.size * 2) / 2] += len(ln.text)  # type: ignore[attr-defined]
    body = weights.most_common(1)[0][0] if weights else 10.0
    heading_sizes = sorted((s for s in weights if s > body * 1.15), reverse=True)
    margins = _repeated_margins(pages, body)

    w = _Writer(body, heading_sizes)
    for p in pages:
        if page_markers:
            w.raw(f"<!-- 第 {p.number} 页 -->")
        if p.no_text:
            if p.ocr_text:
                for para in _text_to_paragraphs(p.ocr_text):
                    w.raw(para)
            else:
                w.raw(f"<!-- 第 {p.number} 页没有可提取的文字 -->")
            continue
        page_lines = [d for _, k, d in p.items if k == "line"]
        w.left = min((ln.x0 for ln in page_lines), default=0.0)  # type: ignore[attr-defined]
        w.right = max((ln.x1 for ln in page_lines), default=p.width)  # type: ignore[attr-defined]
        for top, kind, data in p.items:
            if kind == "line":
                line: _Line = data  # type: ignore[assignment]
                if _in_margin(p, top, line, body) and (re.sub(r"\d+", "#", line.text) in margins
                                  or _PAGE_NUM_RE.match(line.text.strip())):
                    continue
                w.line(line)
            else:
                w.raw(str(data))
        # 段落没写完（末尾不是句号）时留给下一页接着拼；加页码标记时每页单独成段
        if page_markers or w.para.endswith(_SENTENCE_END):
            w.flush()
        w.page_break = True
    w.flush()
    return MdDoc("\n\n".join(w.blocks), meta, warnings)
