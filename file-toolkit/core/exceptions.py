"""
File Toolkit — 自定义异常类型

Core 层内部错误通过这些异常类型表达语义，
Service 层捕获后转换为 TaskResult(status=FAILED)。
"""


class FileToolkitError(Exception):
    """基础异常类型，所有自定义异常继承自此。"""


class UnsupportedFormatError(FileToolkitError):
    """文件格式不受支持。"""


class FileTooLargeError(FileToolkitError):
    """文件超出处理限制。"""


class BinaryNotFoundError(FileToolkitError):
    """外部二进制（FFmpeg/LibreOffice）未找到。"""


class PasswordRequiredError(FileToolkitError):
    """加密文件需要密码但未提供。"""


class PasswordIncorrectError(FileToolkitError):
    """提供的密码错误。"""


class OCRAPIError(FileToolkitError):
    """OCR API 调用失败。"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
