"""PDF 加密/解密模块"""
import time
from pathlib import Path

import pikepdf

from core.models import ProgressCallback, TaskResult, TaskStatus


def encrypt_pdf(
    input_file: Path,
    output_file: Path,
    user_password: str,
    owner_password: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    PDF 加密（设置打开密码）。

    Args:
        input_file: 输入 PDF 路径
        output_file: 输出 PDF 路径
        user_password: 用户密码（打开文件需要）
        owner_password: 所有者密码（修改权限需要），默认与 user_password 相同
    """
    t0 = time.time()
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(0, 1, "正在加密...")

        with pikepdf.open(str(input_file)) as pdf:
            pdf.save(
                str(output_file),
                encryption=pikepdf.Encryption(
                    owner=owner_password or user_password,
                    user=user_password,
                    R=6,
                ),
            )

        if progress_callback:
            progress_callback(1, 1, "加密完成")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[output_file],
            output_dir=output_file.parent,
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def decrypt_pdf(
    input_file: Path,
    output_file: Path,
    password: str,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    PDF 解密。

    Args:
        input_file: 加密的 PDF 路径
        output_file: 解密后输出路径
        password: 密码
    """
    t0 = time.time()
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(0, 1, "正在解密...")

        with pikepdf.open(str(input_file), password=password) as pdf:
            pdf.save(str(output_file))

        if progress_callback:
            progress_callback(1, 1, "解密完成")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[output_file],
            output_dir=output_file.parent,
            duration_seconds=time.time() - t0,
        )

    except pikepdf.PasswordError:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message="密码错误，无法解密该 PDF 文件",
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )
