"""PDF 加密/解密模块（V2 功能）"""
from pathlib import Path

from core.models import ProgressCallback, TaskResult


def encrypt_pdf(
    input_file: Path,
    output_file: Path,
    user_password: str,
    owner_password: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """加密 PDF，设置用户密码（打开密码）和可选的所有者密码（权限密码）。"""
    raise NotImplementedError


def decrypt_pdf(
    input_file: Path,
    output_file: Path,
    password: str,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    解密 PDF（移除密码保护）。

    若密码错误，返回 TaskResult(FAILED) 并附带 PasswordIncorrectError 信息。
    """
    raise NotImplementedError
