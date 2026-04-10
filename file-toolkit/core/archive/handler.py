"""压缩解压统一处理模块"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult

ArchiveFormat = Literal["zip", "7z", "tar.gz"]
CompressionLevel = Literal["fast", "standard", "maximum"]


def compress(
    input_paths: list[Path],
    output_file: Path,
    format: ArchiveFormat = "zip",
    level: CompressionLevel = "standard",
    password: str | None = None,
    volume_size_mb: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    压缩文件或文件夹。

    Args:
        input_paths: 可以是文件或文件夹的混合列表
        output_file: 输出压缩包路径
        format: 压缩格式（rar 格式仅支持解压，不支持压缩）
        level: 压缩等级
        password: 加密密码，None 表示不加密
        volume_size_mb: 分卷大小（MB），None 表示不分卷

    格式路由：
        zip    → zipfile（内置）
        7z     → py7zr
        tar.gz → tarfile（内置）
    """
    raise NotImplementedError


def extract(
    input_file: Path,
    output_dir: Path,
    password: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    解压归档文件。

    支持格式：zip / 7z / tar.gz / tar.bz2 / rar
    rar 解压需要 rarfile 库（仅解压，不压缩）。

    若文件加密但未提供密码，返回 TaskResult(FAILED)，
    error_message 提示 PasswordRequiredError。
    """
    raise NotImplementedError
