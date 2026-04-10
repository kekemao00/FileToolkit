"""PDF↔Office 转换模块"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult


def pdf_to_docx(
    input_file: Path,
    output_file: Path,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    PDF 转 Word（.docx）。使用 pdf2docx 还原排版。

    注意：复杂排版（多栏/特殊字体）还原度有限，UI 层应提示用户。
    """
    raise NotImplementedError


def pdf_to_xlsx(
    input_file: Path,
    output_file: Path,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """PDF 转 Excel（.xlsx），提取表格数据。"""
    raise NotImplementedError


def pdf_to_pptx(
    input_file: Path,
    output_file: Path,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """PDF 转 PowerPoint（.pptx）。"""
    raise NotImplementedError


def office_to_pdf(
    input_file: Path,
    output_dir: Path,
    source_format: Literal["docx", "xlsx", "pptx"],
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    Office 文件转 PDF（依赖 LibreOffice CLI）。

    若 LibreOffice 未安装，返回 TaskResult(FAILED, error_message=...) 而非抛异常。
    """
    raise NotImplementedError
