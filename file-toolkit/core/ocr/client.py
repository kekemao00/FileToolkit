"""OCR 识别模块 — 调用百度/腾讯 OCR API"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult

OCRProvider = Literal["baidu", "tencent"]


async def recognize(
    input_file: Path,
    provider: OCRProvider = "baidu",
    api_key: str = "",
    secret_key: str = "",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    调用 OCR API 识别图片或 PDF 中的文字。

    Args:
        input_file: 输入图片或 PDF 路径
        provider: OCR 服务商
        api_key: API Key
        secret_key: Secret Key（百度 OCR 需要）
        progress_callback: 可选进度回调

    Returns:
        TaskResult，output_files 包含生成的文本文件路径
    """
    raise NotImplementedError
