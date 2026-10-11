"""Word（.docx）转 Markdown：标题、列表、表格、行内格式、超链接、图片。"""
from __future__ import annotations

import re
from pathlib import Path

from core.markdown._common import ImageSink, MdDoc, table_md
from core.task_control import check_cancelled

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_V = "urn:schemas-microsoft-com:vml"
_NS = {"w": _W, "r": _R, "a": _A, "v": _V}

_MONO_FONTS = ("consolas", "courier", "menlo", "monaco", "mono", "source code", "fira code")
_HEADING_STYLE = re.compile(r"^(?:heading|标题)\s*(\d)$", re.I)


def _w(tag: str) -> str:
    return f"{{{_W}}}{tag}"


def _on(rpr, tag: str) -> bool:
    """rPr 里的开关属性（<w:b/>、<w:b w:val="0"/>）。"""
    if rpr is None:
        return False
    el = rpr.find(_w(tag))
    if el is None:
        return False
    return el.get(_w("val"), "true").lower() not in ("0", "false", "off", "none")


class _Converter:
    def __init__(self, doc, images: ImageSink) -> None:
        self.doc = doc
        self.part = doc.part
        self.images = images
        self.blocks: list[tuple[str, str]] = []   # (kind, markdown)；kind=list 的相邻块不空行
        self._num_fmt: dict[tuple[str, int], str] = {}
        self._counters: dict[tuple[str, int], int] = {}
        self._code: list[str] = []
        self._styles = {s.style_id: s for s in doc.styles} if doc.styles is not None else {}

    # ── 样式 / 编号 ──────────────────────────────────────────────────────
    def _style_name(self, p) -> str:
        ppr = p.find(_w("pPr"))
        if ppr is None:
            return ""
        ps = ppr.find(_w("pStyle"))
        if ps is None:
            return ""
        sid = ps.get(_w("val"), "")
        style = self._styles.get(sid)
        return (style.name if style is not None and style.name else sid) or ""

    def _heading_level(self, p, style: str) -> int:
        m = _HEADING_STYLE.match(style.strip())
        if m:
            return max(1, min(6, int(m.group(1))))
        if style.lower() == "title" or style == "标题":
            return 1
        ppr = p.find(_w("pPr"))
        if ppr is not None:
            ol = ppr.find(_w("outlineLvl"))
            if ol is not None:
                try:
                    lvl = int(ol.get(_w("val"), "9"))
                except ValueError:
                    lvl = 9
                if lvl < 6:
                    return lvl + 1
        return 0

    def _list_info(self, p, style: str) -> tuple[str, int, bool] | None:
        """(numId, 层级, 是否有序)；不是列表返回 None。"""
        ppr = p.find(_w("pPr"))
        numpr = ppr.find(_w("numPr")) if ppr is not None else None
        if numpr is not None:
            num_el = numpr.find(_w("numId"))
            lvl_el = numpr.find(_w("ilvl"))
            num_id = num_el.get(_w("val"), "0") if num_el is not None else "0"
            if num_id == "0":
                return None
            ilvl = int(lvl_el.get(_w("val"), "0")) if lvl_el is not None else 0
            m = re.match(r"list (bullet|number)\s*(\d)", style.lower())
            if m and int(m.group(2)) - 1 > ilvl:
                # 「List Bullet 2」这类样式自带层级（LibreOffice 转出的 doc 只留样式）
                return num_id, int(m.group(2)) - 1, m.group(1) == "number"
            return num_id, ilvl, self._ordered(num_id, ilvl)
        low = style.lower()
        if low.startswith("list bullet") or low.startswith("list number"):
            m = re.search(r"(\d)$", low)
            ilvl = int(m.group(1)) - 1 if m else 0
            return f"style:{low.rstrip('0123456789 ')}", ilvl, low.startswith("list number")
        return None

    def _ordered(self, num_id: str, ilvl: int) -> bool:
        key = (num_id, ilvl)
        if key not in self._num_fmt:
            fmt = "bullet"
            try:
                numbering = self.part.numbering_part.element
                num = numbering.find(f"w:num[@w:numId='{num_id}']", _NS)
                abs_id = num.find("w:abstractNumId", _NS).get(_w("val")) if num is not None else None
                if abs_id is not None:
                    lvl = numbering.find(
                        f"w:abstractNum[@w:abstractNumId='{abs_id}']/w:lvl[@w:ilvl='{ilvl}']/w:numFmt", _NS)
                    if lvl is not None:
                        fmt = lvl.get(_w("val"), "bullet")
            except (KeyError, NotImplementedError, AttributeError):
                pass
            self._num_fmt[key] = fmt
        return self._num_fmt[key] not in ("bullet", "none")

    # ── 行内 ────────────────────────────────────────────────────────────
    def _image(self, r_id: str | None, alt: str = "") -> str:
        if not r_id or not self.images.enabled:
            return ""
        try:
            part = self.part.related_parts[r_id]
        except KeyError:
            return ""
        ext = Path(str(part.partname)).suffix
        return self.images.add(part.blob, ext, alt)

    def _run_segments(self, r, link: str | None) -> list[tuple[str, tuple]]:
        rpr = r.find(_w("rPr"))
        fonts = rpr.find(_w("rFonts")) if rpr is not None else None
        font = " ".join(v for v in (fonts.attrib.values() if fonts is not None else [])).lower()
        fmt = (
            _on(rpr, "b"), _on(rpr, "i"), _on(rpr, "strike") or _on(rpr, "dstrike"),
            any(m in font for m in _MONO_FONTS), link,
        )
        segs: list[tuple[str, tuple]] = []
        for child in r:
            tag = child.tag
            if tag == _w("t"):
                segs.append((child.text or "", fmt))
            elif tag == _w("tab"):
                segs.append(("\t", fmt))
            elif tag in (_w("br"), _w("cr")):
                if child.get(_w("type")) != "page":
                    segs.append(("\n", fmt))
            elif tag == _w("drawing"):
                for blip in child.iter(f"{{{_A}}}blip"):
                    alt = ""
                    for dp in child.iter("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"):
                        alt = dp.get("descr") or ""
                    md = self._image(blip.get(f"{{{_R}}}embed"), alt)
                    if md:
                        segs.append((md, ("img",)))
            elif tag == _w("pict") or tag == _w("object"):
                for im in child.iter(f"{{{_V}}}imagedata"):
                    md = self._image(im.get(f"{{{_R}}}id"))
                    if md:
                        segs.append((md, ("img",)))
        return segs

    def _inline(self, p) -> str:
        return _render_segments(self._segments(p))

    def _segments(self, p) -> list[tuple[str, tuple]]:
        segs: list[tuple[str, tuple]] = []

        def walk(el, link: str | None) -> None:
            for child in el:
                tag = child.tag
                if tag == _w("r"):
                    segs.extend(self._run_segments(child, link))
                elif tag == _w("hyperlink"):
                    target = None
                    rid = child.get(f"{{{_R}}}id")
                    if rid and rid in self.part.rels:
                        target = self.part.rels[rid].target_ref
                    elif child.get(_w("anchor")):
                        target = "#" + child.get(_w("anchor"))
                    walk(child, target)
                elif tag in (_w("ins"), _w("smartTag"), _w("sdt"), _w("sdtContent"), _w("fldSimple")):
                    walk(child, link)
        walk(p, None)
        return segs

    # ── 块 ──────────────────────────────────────────────────────────────
    def _flush_code(self) -> None:
        if self._code:
            self.blocks.append(("code", "```\n" + "\n".join(self._code) + "\n```"))
            self._code = []

    def paragraph(self, p) -> None:
        style = self._style_name(p)
        low = style.lower()
        if "code" in low or "preformatted" in low or low in ("source", "代码"):
            self._code.append("".join(t for t, f in self._segments(p) if len(f) > 1).replace("\t", "    "))
            return
        segs = self._segments(p)
        texts = [(t, f) for t, f in segs if t.strip()]
        if texts and all(len(f) > 1 and f[3] for _, f in texts) and "\n" in "".join(t for t, _ in segs):
            # 整段等宽字体且有换行：代码块
            self._flush_code()
            self.blocks.append(("code", "```\n" + "".join(t for t, _ in segs).strip("\n") + "\n```"))
            return
        self._flush_code()
        text = _render_segments(segs).strip()
        if not text:
            return
        level = self._heading_level(p, style)
        if level:
            self.blocks.append(("h", "#" * level + " " + text.replace("\n", " ")))
            self._counters.clear()
            return
        info = self._list_info(p, style)
        if info:
            num_id, ilvl, ordered = info
            for key in [k for k in self._counters if k[0] == num_id and k[1] > ilvl]:
                del self._counters[key]
            n = self._counters.get((num_id, ilvl), 0) + 1
            self._counters[(num_id, ilvl)] = n
            marker = f"{n}." if ordered else "-"
            body = text.replace("\n", "\n" + "    " * (ilvl + 1))
            self.blocks.append(("list", "    " * ilvl + f"{marker} {body}"))
            return
        if "quote" in low or "引用" in style:
            self.blocks.append(("p", "> " + text.replace("\n", "\n> ")))
            return
        self.blocks.append(("p", text))

    def table(self, tbl) -> None:
        self._flush_code()
        rows: list[list[str]] = []
        for tr in tbl.findall(_w("tr")):
            row: list[str] = []
            for tc in tr.findall(_w("tc")):
                parts = [self._inline(p).strip() for p in tc.iter(_w("p"))]
                text = "\n".join(x for x in parts if x)
                span = 1
                tcpr = tc.find(_w("tcPr"))
                if tcpr is not None and tcpr.find(_w("gridSpan")) is not None:
                    try:
                        span = int(tcpr.find(_w("gridSpan")).get(_w("val"), "1"))
                    except ValueError:
                        span = 1
                row.append(text)
                row.extend([""] * (span - 1))
            rows.append(row)
        if rows:  # 表头本来就加粗，不需要再写 **
            rows[0] = [re.sub(r"^\*\*(.+)\*\*$", r"\1", c, flags=re.S) for c in rows[0]]
        md = table_md(rows)
        if md:
            self.blocks.append(("table", md))

    def body(self, el) -> None:
        for child in el:
            check_cancelled()
            if child.tag == _w("p"):
                self.paragraph(child)
            elif child.tag == _w("tbl"):
                self.table(child)
            elif child.tag in (_w("sdt"), _w("sdtContent"), _w("customXml")):
                self.body(child)
        self._flush_code()

    def markdown(self) -> str:
        out: list[str] = []
        prev = ""
        for kind, md in self.blocks:
            if out:
                out.append("\n" if kind == "list" and prev == "list" else "\n\n")
            out.append(md)
            prev = kind
        return "".join(out)


def _wrap(text: str, fmt: tuple) -> str:
    if len(fmt) == 1:  # 图片
        return text
    bold, italic, strike, code, link = fmt
    core = text.strip()
    if not core:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    if code and "\n" not in core:
        tick = "``" if "`" in core else "`"
        core = f"{tick}{core}{tick}"
    else:
        if strike:
            core = f"~~{core}~~"
        if italic:
            core = f"*{core}*"
        if bold:
            core = f"**{core}**"
    if link:
        core = f"[{core}]({link})"
    return lead + core + trail


def _render_segments(segs: list[tuple[str, tuple]]) -> str:
    merged: list[list] = []
    for text, fmt in segs:
        if merged and merged[-1][1] == fmt and len(fmt) > 1:
            merged[-1][0] += text
        else:
            merged.append([text, fmt])
    return "".join(_wrap(t.replace("\t", " "), f) for t, f in merged)


def docx_to_md(path: Path, images: ImageSink) -> MdDoc:
    import docx

    doc = docx.Document(str(path))
    conv = _Converter(doc, images)
    conv.body(doc.element.body)
    meta: dict[str, str | int] = {}
    title = (doc.core_properties.title or "").strip()
    if title:
        meta["title"] = title
    return MdDoc(conv.markdown(), meta)
