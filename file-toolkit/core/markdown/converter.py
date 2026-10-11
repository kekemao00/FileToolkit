"""各类文档转 Markdown 的入口：按扩展名分发，单个输出或合并为一份。"""
from __future__ import annotations

import datetime as dt
import shutil
import tempfile
import time
from pathlib import Path

from core.markdown._common import (
    IMAGE_EXTRACT,
    ImageSink,
    MdDoc,
    estimate_tokens,
    front_matter,
    normalize_md,
    read_text_file,
)
from core.models import ProgressCallback, TaskResult, TaskStatus
from core.paths import unique_path
from core.platform import get_libreoffice_path
from core.task_control import TaskCancelled, check_cancelled, run_process

# 直接解析的格式
NATIVE_EXTENSIONS = ("docx", "pdf", "pptx", "xlsx", "xlsm", "csv", "html", "htm", "txt", "md", "markdown")
# 先用 LibreOffice 转成可解析的格式：扩展名 → 中间格式
LIBREOFFICE_EXTENSIONS = {"doc": "docx", "rtf": "docx", "odt": "docx", "wps": "docx",
                          "xls": "xlsx", "ods": "xlsx", "ppt": "pptx", "odp": "pptx"}
SUPPORTED_EXTENSIONS = NATIVE_EXTENSIONS + tuple(LIBREOFFICE_EXTENSIONS)

_KIND = {"docx": "Word", "doc": "Word", "rtf": "RTF", "odt": "Word", "wps": "Word", "pdf": "PDF",
         "pptx": "PowerPoint", "ppt": "PowerPoint", "odp": "PowerPoint", "xlsx": "Excel", "xlsm": "Excel",
         "xls": "Excel", "ods": "Excel", "csv": "CSV", "html": "HTML", "htm": "HTML", "txt": "文本",
         "md": "Markdown", "markdown": "Markdown"}

_LO_HINT = "需要先安装 LibreOffice（https://www.libreoffice.org/download/），或在 Office 里另存为 {fmt} 后再转换"


def _libreoffice_convert(src: Path, fmt: str, tmp_dir: Path) -> Path:
    soffice = get_libreoffice_path()
    if soffice is None:
        raise RuntimeError(f"「.{src.suffix.lstrip('.').lower()}」格式" + _LO_HINT.format(fmt=f".{fmt}"))
    out_dir = tmp_dir / "lo-out"
    cmd = [str(soffice), f"-env:UserInstallation={(tmp_dir / 'lo-profile').as_uri()}",
           "--headless", "--norestore", "--convert-to", fmt, "--outdir", str(out_dir), str(src)]
    code, out, err = run_process(cmd, timeout=600)
    produced = out_dir / f"{src.stem}.{fmt}"
    if not produced.is_file():
        detail = (err or out).strip().splitlines()[-2:]
        raise RuntimeError("LibreOffice 转换失败" + (f"：{' '.join(detail)}" if detail else "，文件可能已损坏或受密码保护"))
    return produced


def convert_file(path: Path, images: ImageSink, page_markers: bool = False,
                 progress_callback: ProgressCallback | None = None) -> MdDoc:
    """把一个文件转成 Markdown 正文（不写盘，图片按 images 的方式处理）。"""
    ext = path.suffix.lower().lstrip(".")
    if ext in LIBREOFFICE_EXTENSIONS:
        with tempfile.TemporaryDirectory(prefix="ftk-md-") as tmp:
            if progress_callback:
                progress_callback(0, 1, "正在用 LibreOffice 转换格式…")
            mid = _libreoffice_convert(path, LIBREOFFICE_EXTENSIONS[ext], Path(tmp))
            doc = convert_file(mid, images, page_markers, progress_callback)
    elif ext == "docx":
        from core.markdown.docx_to_md import docx_to_md
        doc = docx_to_md(path, images)
    elif ext == "pdf":
        from core.markdown.pdf_to_md import pdf_to_md
        doc = pdf_to_md(path, images, page_markers, progress_callback)
    elif ext == "pptx":
        from core.markdown.pptx_to_md import pptx_to_md
        doc = pptx_to_md(path, images)
    elif ext in ("xlsx", "xlsm"):
        from core.markdown.sheet_to_md import xlsx_to_md
        doc = xlsx_to_md(path)
    elif ext == "csv":
        from core.markdown.sheet_to_md import csv_to_md
        doc = csv_to_md(path)
    elif ext in ("html", "htm"):
        from core.markdown.html_to_md import html_to_md
        doc = html_to_md(path, images)
    elif ext in ("txt", "md", "markdown"):
        doc = MdDoc(read_text_file(path))
    else:
        raise RuntimeError(f"不支持的格式：.{ext}")
    if not doc.text.strip():
        raise RuntimeError("没有提取到任何文字内容")
    doc.meta = {"source": path.name, "format": _KIND.get(ext, ext.upper()), **doc.meta}
    return doc


def _with_meta(doc: MdDoc, include: bool) -> str:
    body = normalize_md(doc.text)
    if not include:
        return body
    meta = dict(doc.meta)
    meta["converted"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return front_matter(meta) + body


def _sub_progress(cb: ProgressCallback | None, name: str) -> ProgressCallback | None:
    if cb is None:
        return None
    return lambda cur, tot, desc: cb(cur, tot, f"{name}：{desc}")


def to_markdown(
    input_file: Path,
    output_dir: Path,
    image_mode: str = IMAGE_EXTRACT,
    include_meta: bool = False,
    page_markers: bool = False,
    progress_callback: ProgressCallback | None = None,
    **_,
) -> TaskResult:
    """一个文件转成一份 .md，图片（单独保存时）放在同名 _assets 文件夹。"""
    t0 = time.time()
    assets: Path | None = None
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = unique_path(output_dir / f"{input_file.stem}.md", [input_file])
        assets = unique_path(output_dir / f"{out_path.stem}_assets")
        images = ImageSink(image_mode, assets, output_dir)
        doc = convert_file(input_file, images, page_markers, progress_callback)
        out_path.write_text(_with_meta(doc, include_meta), encoding="utf-8", newline="\n")
        return TaskResult(status=TaskStatus.SUCCESS, output_files=[out_path], output_dir=output_dir,
                          warnings=doc.warnings, duration_seconds=time.time() - t0)
    except TaskCancelled:
        return TaskResult(status=TaskStatus.CANCELLED, error_message="已取消", duration_seconds=time.time() - t0)
    except Exception as exc:
        if assets is not None and assets.is_dir():
            shutil.rmtree(assets, ignore_errors=True)
        return TaskResult(status=TaskStatus.FAILED, error_message=str(exc), duration_seconds=time.time() - t0)


def merge_to_markdown(
    input_files: list[Path],
    output_file: Path,
    image_mode: str = IMAGE_EXTRACT,
    include_meta: bool = False,
    page_markers: bool = False,
    progress_callback: ProgressCallback | None = None,
    **_,
) -> TaskResult:
    """多个文件合并成一份 .md：每个文件一个一级标题，原有标题整体降一级。"""
    t0 = time.time()
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file = unique_path(output_file, input_files)
        assets = unique_path(output_file.with_name(f"{output_file.stem}_assets"))
        sections: list[str] = []
        warnings: list[str] = []
        total = len(input_files)
        for i, path in enumerate(input_files):
            check_cancelled()
            if progress_callback:
                progress_callback(i * 1000, total * 1000, f"正在转换 {path.name}（{i + 1}/{total}）")
            sub = None
            if progress_callback:
                def sub(cur: int, tot: int, desc: str, i: int = i, name: str = path.name) -> None:
                    frac = min(1.0, cur / tot) if tot else 0.0
                    progress_callback(int((i + frac) * 1000), total * 1000, f"{name}：{desc}")
            images = ImageSink(image_mode, assets, output_file.parent, prefix=f"{i + 1:02d}_{path.stem}")
            try:
                doc = convert_file(path, images, page_markers, sub)
            except TaskCancelled:
                raise
            except Exception as exc:
                warnings.append(f"{path.name}：{exc}")
                continue
            warnings.extend(doc.warnings)
            body = normalize_md(_demote(doc.text)).strip()
            head = f"# {path.name}\n\n"
            if include_meta:
                info = "，".join(f"{k}: {v}" for k, v in doc.meta.items() if k not in ("source",))
                head += f"> {info}\n\n" if info else ""
            sections.append(head + body)
        if not sections:
            raise RuntimeError("全部文件转换失败：\n" + "\n".join(warnings))
        text = "\n\n---\n\n".join(sections)
        if include_meta:
            text = front_matter({"files": len(sections),
                                 "converted": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}) + text
        output_file.write_text(normalize_md(text), encoding="utf-8", newline="\n")
        if progress_callback:
            progress_callback(total * 1000, total * 1000, "合并完成")
        return TaskResult(status=TaskStatus.SUCCESS, output_files=[output_file], output_dir=output_file.parent,
                          warnings=warnings, duration_seconds=time.time() - t0)
    except TaskCancelled:
        return TaskResult(status=TaskStatus.CANCELLED, error_message="已取消", duration_seconds=time.time() - t0)
    except Exception as exc:
        return TaskResult(status=TaskStatus.FAILED, error_message=str(exc), duration_seconds=time.time() - t0)


def _demote(text: str) -> str:
    """标题整体降一级（# → ##），代码块里的 # 不动。"""
    out: list[str] = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("#"):
            hashes = len(line) - len(line.lstrip("#"))
            if hashes < 6 and line[hashes:hashes + 1] == " ":
                line = "#" + line
        out.append(line)
    return "\n".join(out)


def markdown_stats(paths: list[Path]) -> tuple[int, int]:
    """(字符数, 预估 token 数)，用于结果页展示。"""
    chars = tokens = 0
    for p in paths:
        if p.suffix.lower() != ".md":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        chars += len(text)
        tokens += estimate_tokens(text)
    return chars, tokens
