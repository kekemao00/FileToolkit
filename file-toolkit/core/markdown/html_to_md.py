"""网页（.html）转 Markdown：去掉脚本、样式、导航等噪声，只留正文结构。"""
from __future__ import annotations

import base64
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from core.markdown._common import ImageSink, MdDoc, table_md

_DROP = {"script", "style", "noscript", "template", "iframe", "svg", "canvas", "form", "button",
         "input", "select", "textarea", "nav", "footer", "aside", "head", "meta", "link", "object"}
_BLOCK = {"p", "div", "section", "article", "main", "header", "figure", "figcaption", "address",
          "details", "summary", "dl", "dt", "dd", "center", "body", "html"}
_WS = re.compile(r"[ \t\r\n ]+")


class _Html:
    def __init__(self, base_dir: Path | None, images: ImageSink) -> None:
        self.base_dir = base_dir
        self.images = images

    # ── 行内 ────────────────────────────────────────────────────────────
    def inline(self, el) -> str:
        parts: list[str] = [_WS.sub(" ", el.text or "")]
        for child in el:
            parts.append(self.inline_el(child))
            parts.append(_WS.sub(" ", child.tail or ""))
        return "".join(parts)

    def inline_el(self, el) -> str:
        tag = el.tag if isinstance(el.tag, str) else ""
        tag = tag.lower()
        if not tag or tag in _DROP:
            return ""
        if tag == "br":
            return "\n"
        if tag == "img":
            return self.image(el)
        inner = self.inline(el)
        core = inner.strip()
        if not core:
            return inner
        lead = " " if inner[:1].isspace() else ""
        trail = " " if inner[-1:].isspace() else ""
        if tag in ("strong", "b"):
            core = f"**{core}**"
        elif tag in ("em", "i", "cite"):
            core = f"*{core}*"
        elif tag in ("del", "s", "strike"):
            core = f"~~{core}~~"
        elif tag in ("code", "kbd", "samp", "tt"):
            core = f"`{core}`" if "`" not in core else f"`` {core} ``"
        elif tag == "a":
            href = (el.get("href") or "").strip()
            if href and not href.lower().startswith("javascript:") and href != "#":
                core = f"[{core}]({href.replace(' ', '%20')})"
        elif tag == "sup":
            core = f"^{core}"
        return lead + core + trail

    def image(self, el) -> str:
        src = (el.get("src") or el.get("data-src") or "").strip()
        alt = el.get("alt") or ""
        if not src or not self.images.enabled:
            return ""
        if src.startswith("data:"):
            m = re.match(r"data:image/([\w+.-]+);base64,(.*)", src, re.S)
            if m:
                try:
                    return self.images.add(base64.b64decode(m.group(2)), m.group(1).replace("svg+xml", "svg"), alt)
                except ValueError:
                    return ""
            return ""
        parsed = urlparse(src)
        if parsed.scheme in ("http", "https") or src.startswith("//"):
            return f"![{alt}]({src})"  # 网络图片保留原链接
        if self.base_dir is not None:
            local = (self.base_dir / unquote(parsed.path)).resolve()
            if local.is_file():
                return self.images.add_file(local, alt)
        return ""

    # ── 块 ──────────────────────────────────────────────────────────────
    def blocks(self, el, out: list[str]) -> None:
        """el 的子内容按块输出；连续的行内内容合成一段。"""
        buf: list[str] = [_WS.sub(" ", el.text or "")]

        def flush() -> None:
            text = "".join(buf)
            text = "\n".join(_WS.sub(" ", ln).strip() for ln in text.split("\n"))
            text = text.strip()
            if text:
                out.append(text)
            buf.clear()

        for child in el:
            tag = child.tag.lower() if isinstance(child.tag, str) else ""
            if tag and tag not in _DROP and self.is_block(tag):
                flush()
                self.block(child, tag, out)
            elif tag:
                buf.append(self.inline_el(child))
            buf.append(_WS.sub(" ", child.tail or ""))
        flush()

    @staticmethod
    def is_block(tag: str) -> bool:
        return tag in _BLOCK or tag in ("ul", "ol", "table", "pre", "blockquote", "hr") or \
            bool(re.fullmatch(r"h[1-6]", tag))

    def block(self, el, tag: str, out: list[str]) -> None:
        if re.fullmatch(r"h[1-6]", tag):
            text = _WS.sub(" ", self.inline(el)).strip()
            if text:
                out.append("#" * int(tag[1]) + " " + text)
        elif tag in ("ul", "ol"):
            md = self.list(el, tag == "ol", 0)
            if md:
                out.append(md)
        elif tag == "table":
            md = self.table(el)
            if md:
                out.append(md)
        elif tag == "pre":
            code = el.text_content().strip("\n")
            lang = ""
            code_el = el.find(".//code")
            if code_el is not None:
                m = re.search(r"(?:language|lang)-([\w+-]+)", code_el.get("class") or "")
                lang = m.group(1) if m else ""
            out.append(f"```{lang}\n{code}\n```")
        elif tag == "blockquote":
            inner: list[str] = []
            self.blocks(el, inner)
            if inner:
                out.append("\n".join("> " + ln if ln else ">" for ln in "\n\n".join(inner).split("\n")))
        elif tag == "hr":
            out.append("---")
        else:
            self.blocks(el, out)

    def list(self, el, ordered: bool, depth: int) -> str:
        lines: list[str] = []
        n = 0
        for li in el:
            if not isinstance(li.tag, str) or li.tag.lower() != "li":
                continue
            n += 1
            marker = f"{n}." if ordered else "-"
            text_parts: list[str] = [_WS.sub(" ", li.text or "")]
            nested: list[str] = []
            for child in li:
                tag = child.tag.lower() if isinstance(child.tag, str) else ""
                if tag in ("ul", "ol"):
                    nested.append(self.list(child, tag == "ol", depth + 1))
                elif tag in ("p", "div"):
                    text_parts.append(" " + self.inline(child) + " ")
                elif tag:
                    text_parts.append(self.inline_el(child))
                text_parts.append(_WS.sub(" ", child.tail or ""))
            text = _WS.sub(" ", "".join(text_parts).replace("\n", " ")).strip()
            lines.append("    " * depth + f"{marker} {text}")
            lines.extend(x for x in nested if x)
        return "\n".join(lines)

    def table(self, el) -> str:
        rows: list[list[str]] = []
        for tr in el.iter("tr"):
            row: list[str] = []
            for cell in tr:
                if not isinstance(cell.tag, str) or cell.tag.lower() not in ("td", "th"):
                    continue
                text = _WS.sub(" ", self.inline(cell)).strip()
                row.append(text)
                try:
                    span = int(cell.get("colspan") or 1)
                except ValueError:
                    span = 1
                row.extend([""] * (min(span, 50) - 1))
            if row:
                rows.append(row)
        return table_md(rows)


def html_string_to_md(html: str | bytes, images: ImageSink, base_dir: Path | None = None) -> MdDoc:
    import lxml.html

    if isinstance(html, str):
        html = re.sub(r"^\s*<\?xml[^>]*\?>", "", html)  # 带编码声明的 str 会被 lxml 拒绝
    root = lxml.html.document_fromstring(html)
    title_el = root.find(".//title")
    title = _WS.sub(" ", title_el.text_content()).strip() if title_el is not None else ""
    for bad in root.xpath("//comment()"):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)
    body = root
    for path in (".//main", ".//article", ".//body"):
        found = root.find(path)
        if found is not None:
            body = found
            break
    out: list[str] = []
    _Html(base_dir, images).blocks(body, out)
    meta: dict[str, str | int] = {"title": title} if title else {}
    return MdDoc("\n\n".join(out), meta)


def decode_html(data: bytes) -> str:
    """按 <meta charset> 解码；没有声明时依次尝试 UTF-8、GB18030。"""
    m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", data[:4096], re.I)
    encodings = [m.group(1).decode("ascii", "ignore")] if m else []
    for enc in encodings + ["utf-8-sig", "gb18030"]:
        try:
            return data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("latin-1")


def html_to_md(path: Path, images: ImageSink) -> MdDoc:
    return html_string_to_md(decode_html(path.read_bytes()), images, path.parent)
