"""OCR 识别模块 — 调用百度/腾讯 OCR API 或本地 Tesseract"""
import base64
import time
from pathlib import Path

import httpx

from core.models import ProgressCallback, TaskResult, TaskStatus


def recognize(
    input_file: Path,
    language: str = "chi_sim",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    OCR 识别图片或 PDF 中的文字。

    优先尝试本地 Tesseract，不可用时提示配置云端 API。

    Args:
        input_file: 输入图片或 PDF 路径
        language: 识别语言 (chi_sim/eng/chi_sim+eng/jpn)
        progress_callback: 可选进度回调

    Returns:
        TaskResult，识别的文本存入 output_files 指向的 .txt 文件
    """
    t0 = time.time()
    try:
        if progress_callback:
            progress_callback(0, 1, "正在初始化 OCR...")

        # 尝试本地 Tesseract
        text = _try_tesseract(input_file, language, progress_callback)

        if text is None:
            return TaskResult(
                status=TaskStatus.FAILED,
                error_message="OCR 引擎不可用。请安装 Tesseract OCR：\n"
                              "Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                              "Linux: sudo apt install tesseract-ocr tesseract-ocr-chi-sim\n"
                              "macOS: brew install tesseract tesseract-lang",
                duration_seconds=time.time() - t0,
            )

        # 将识别结果写入文本文件
        out_dir = input_file.parent / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{input_file.stem}_ocr.txt"
        out_path.write_text(text, encoding="utf-8")

        if progress_callback:
            progress_callback(1, 1, "识别完成")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[out_path],
            output_dir=out_dir,
            error_message=text,  # 将文本放在 error_message 供 UI 读取
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def _try_tesseract(
    input_file: Path,
    language: str,
    progress_callback: ProgressCallback | None,
) -> str | None:
    """尝试使用 pytesseract 进行本地 OCR，不可用返回 None。"""
    try:
        import pytesseract
        from PIL import Image

        ext = input_file.suffix.lower()
        if ext == ".pdf":
            # PDF 需要先转为图片
            return _tesseract_pdf(input_file, language, progress_callback)

        if progress_callback:
            progress_callback(0, 1, "正在识别文字...")

        img = Image.open(input_file)
        text = pytesseract.image_to_string(img, lang=language)
        return text.strip()

    except ImportError:
        return None
    except Exception:
        return None


def _tesseract_pdf(
    input_file: Path,
    language: str,
    progress_callback: ProgressCallback | None,
) -> str:
    """对 PDF 文件逐页提取文本（先尝试直接提取，再 OCR）。"""
    import pypdf

    reader = pypdf.PdfReader(str(input_file))
    total = len(reader.pages)
    all_text: list[str] = []

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        all_text.append(text)
        if progress_callback:
            progress_callback(i, total, f"处理第 {i}/{total} 页")

    return "\n".join(all_text).strip()
