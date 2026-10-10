"""OCR 识别模块 — 本地 Tesseract（直接调用可执行文件，不依赖 pytesseract）

- 图片：转成临时 PNG（摆正 EXIF 方向、兼容 WebP / HEIC、避开中文路径）后交给 tesseract
- PDF：先提取内嵌文字；整份没有文字（扫描件）且装了 Tesseract 时，逐页渲染后识别
"""
import os
import sys
import tempfile
import time
from pathlib import Path

from core.models import ProgressCallback, TaskResult, TaskStatus
from core.paths import unique_path
from core.platform import _find_binary
from core.task_control import TaskCancelled, check_cancelled, run_process

INSTALL_HINT = (
    "未检测到 Tesseract OCR，图片文字识别需要先安装：\n"
    "Windows：https://github.com/UB-Mannheim/tesseract/wiki（安装时勾选 Chinese Simplified）\n"
    "macOS：brew install tesseract tesseract-lang\n"
    "Linux：sudo apt install tesseract-ocr tesseract-ocr-chi-sim"
)

_LANG_LABELS = {"chi_sim": "简体中文", "eng": "英文", "jpn": "日文"}


def find_tesseract() -> Path | None:
    """PATH / 内嵌 assets/bin / Homebrew / Windows 默认安装目录；找不到返回 None。"""
    found = _find_binary("tesseract")
    if found.is_absolute() and found.is_file():
        return found
    if sys.platform == "win32":
        roots = [os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")]
        for root in roots:
            p = Path(root) / "Tesseract-OCR" / "tesseract.exe"
            if root and p.is_file():
                return p
    return None


def installed_languages(tesseract: Path) -> set[str]:
    try:
        code, out, _ = run_process([str(tesseract), "--list-langs"], timeout=20)
    except (OSError, TimeoutError):
        return set()
    return {ln.strip() for ln in out.splitlines()[1:] if ln.strip()} if code == 0 else set()


def recognize(
    input_file: Path,
    language: str = "chi_sim",
    progress_callback: ProgressCallback | None = None,
    output_dir: Path | None = None,
) -> TaskResult:
    """
    OCR 识别图片或 PDF 中的文字，结果写入 <output_dir>/<文件名>_ocr.txt。

    Args:
        input_file: 输入图片或 PDF 路径
        language: 识别语言 (chi_sim/eng/chi_sim+eng/jpn)
        progress_callback: 可选进度回调
        output_dir: 结果目录，默认输入文件旁的 output/

    Returns:
        TaskResult，output_files[0] 为结果 txt
    """
    t0 = time.time()
    try:
        if progress_callback:
            progress_callback(0, 1, "正在初始化 OCR...")

        if input_file.suffix.lower() == ".pdf":
            text = _extract_pdf_text(input_file, progress_callback)
            if not text:
                tess = find_tesseract()
                if tess is None:
                    raise RuntimeError("这份 PDF 没有可提取的文字（可能是扫描件）。\n" + INSTALL_HINT)
                text = _ocr_pdf_pages(tess, input_file, language, progress_callback)
        else:
            tess = find_tesseract()
            if tess is None:
                raise RuntimeError(INSTALL_HINT)
            if progress_callback:
                progress_callback(0, 1, "正在识别文字...")
            from PIL import Image

            from core.image._common import open_image
            with tempfile.TemporaryDirectory(prefix="ftk-ocr-") as tmp:
                png = Path(tmp) / "page.png"
                img: Image.Image = open_image(input_file)
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                img.save(png)
                text = _tesseract(tess, png, language)

        out_dir = output_dir or input_file.parent / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = unique_path(out_dir / f"{input_file.stem}_ocr.txt")
        out_path.write_text(text, encoding="utf-8")

        if progress_callback:
            progress_callback(1, 1, "识别完成")
        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[out_path],
            output_dir=out_dir,
            duration_seconds=time.time() - t0,
        )

    except TaskCancelled:
        return TaskResult(status=TaskStatus.CANCELLED, error_message="已取消",
                          duration_seconds=time.time() - t0)
    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def _tesseract(tess: Path, image: Path, language: str) -> str:
    code, out, err = run_process([str(tess), str(image), "stdout", "-l", language], timeout=600)
    if code != 0:
        if "Failed loading language" in err or "Error opening data file" in err:
            missing = [_LANG_LABELS.get(lang, lang) for lang in language.split("+")]
            raise RuntimeError(f"Tesseract 缺少「{'、'.join(missing)}」语言包，请重新安装并勾选对应语言"
                               "（macOS：brew install tesseract-lang）")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        raise RuntimeError("Tesseract 识别失败：" + (lines[-1] if lines else f"退出码 {code}"))
    return out.strip()


def _ocr_pdf_pages(tess: Path, input_file: Path, language: str,
                   progress_callback: ProgressCallback | None) -> str:
    """扫描版 PDF：逐页按 200dpi 渲染后识别。"""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(input_file))
    try:
        total = len(pdf)
        texts: list[str] = []
        with tempfile.TemporaryDirectory(prefix="ftk-ocr-") as tmp:
            for i in range(total):
                check_cancelled()
                png = Path(tmp) / f"p{i}.png"
                pdf[i].render(scale=200 / 72).to_pil().save(png)
                texts.append(_tesseract(tess, png, language))
                if progress_callback:
                    progress_callback(i + 1, total, f"识别第 {i + 1}/{total} 页")
        return "\n\n".join(t for t in texts if t).strip()
    finally:
        pdf.close()


def _extract_pdf_text(
    input_file: Path,
    progress_callback: ProgressCallback | None,
) -> str:
    """从 PDF 文件逐页提取文本（使用 pypdf，不需要 Tesseract）。"""
    import pypdf

    reader = pypdf.PdfReader(str(input_file))
    total = len(reader.pages)
    all_text: list[str] = []

    for i, page in enumerate(reader.pages, start=1):
        check_cancelled()
        text = page.extract_text() or ""
        all_text.append(text)
        if progress_callback:
            progress_callback(i, total, f"处理第 {i}/{total} 页")

    return "\n".join(all_text).strip()
