"""压缩解压统一处理模块"""
import os
import tarfile
import time
import zipfile
from pathlib import Path

import py7zr

from core.models import ProgressCallback, TaskResult, TaskStatus


def compress(
    input_files: list[Path],
    output_dir: Path,
    format: str = "zip",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    压缩文件或文件夹。

    Args:
        input_files: 文件或文件夹的混合列表
        output_dir: 输出目录
        format: 压缩格式 zip / 7z / tar.gz
        progress_callback: 可选进度回调
    """
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")

        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成输出文件名
        base_name = input_files[0].stem if len(input_files) == 1 else "archive"
        ext_map = {"zip": ".zip", "7z": ".7z", "tar.gz": ".tar.gz"}
        ext = ext_map.get(format, ".zip")
        output_file = output_dir / f"{base_name}{ext}"

        # 收集所有待压缩文件（展开文件夹）
        file_entries: list[tuple[Path, str]] = []
        for p in input_files:
            if p.is_dir():
                for root, _, files in os.walk(p):
                    for f in files:
                        full = Path(root) / f
                        arcname = str(full.relative_to(p.parent))
                        file_entries.append((full, arcname))
            else:
                file_entries.append((p, p.name))

        total = len(file_entries)

        if format == "zip":
            _compress_zip(output_file, file_entries, total, progress_callback)
        elif format == "7z":
            _compress_7z(output_file, file_entries, total, progress_callback)
        elif format == "tar.gz":
            _compress_tar(output_file, file_entries, total, progress_callback)
        else:
            return TaskResult(status=TaskStatus.FAILED, error_message=f"不支持的格式: {format}")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[output_file],
            output_dir=output_dir,
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def _compress_zip(
    output_file: Path,
    entries: list[tuple[Path, str]],
    total: int,
    cb: ProgressCallback | None,
) -> None:
    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (full_path, arcname) in enumerate(entries, start=1):
            zf.write(full_path, arcname)
            if cb:
                cb(i, total, f"压缩中：{arcname} ({i}/{total})")


def _compress_7z(
    output_file: Path,
    entries: list[tuple[Path, str]],
    total: int,
    cb: ProgressCallback | None,
) -> None:
    with py7zr.SevenZipFile(str(output_file), "w") as sz:
        for i, (full_path, arcname) in enumerate(entries, start=1):
            sz.write(full_path, arcname)
            if cb:
                cb(i, total, f"压缩中：{arcname} ({i}/{total})")


def _compress_tar(
    output_file: Path,
    entries: list[tuple[Path, str]],
    total: int,
    cb: ProgressCallback | None,
) -> None:
    with tarfile.open(output_file, "w:gz") as tf:
        for i, (full_path, arcname) in enumerate(entries, start=1):
            tf.add(full_path, arcname)
            if cb:
                cb(i, total, f"压缩中：{arcname} ({i}/{total})")


def extract(
    input_file: Path,
    output_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    解压归档文件。

    支持格式：zip / 7z / rar / tar.gz / tar.bz2 / tar.xz
    自动根据后缀名路由到对应库。
    """
    t0 = time.time()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = input_file.name.lower()

        if suffix.endswith(".zip"):
            _extract_zip(input_file, output_dir, progress_callback)
        elif suffix.endswith(".7z"):
            _extract_7z(input_file, output_dir, progress_callback)
        elif suffix.endswith(".rar"):
            _extract_rar(input_file, output_dir, progress_callback)
        elif suffix.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")):
            _extract_tar(input_file, output_dir, progress_callback)
        elif suffix.endswith(".gz") and not suffix.endswith(".tar.gz"):
            _extract_tar(input_file, output_dir, progress_callback)
        else:
            return TaskResult(
                status=TaskStatus.FAILED,
                error_message=f"不支持的压缩格式: {input_file.suffix}",
            )

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[],
            output_dir=output_dir,
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def _extract_zip(src: Path, dst: Path, cb: ProgressCallback | None) -> None:
    with zipfile.ZipFile(src, "r") as zf:
        members = zf.namelist()
        total = len(members)
        for i, name in enumerate(members, start=1):
            zf.extract(name, dst)
            if cb:
                cb(i, total, f"解压中：{name} ({i}/{total})")


def _extract_7z(src: Path, dst: Path, cb: ProgressCallback | None) -> None:
    with py7zr.SevenZipFile(str(src), "r") as sz:
        if cb:
            cb(1, 1, "正在解压 7z 文件...")
        sz.extractall(path=str(dst))
        if cb:
            cb(1, 1, "解压完成")


def _extract_rar(src: Path, dst: Path, cb: ProgressCallback | None) -> None:
    import rarfile
    with rarfile.RarFile(str(src), "r") as rf:
        members = rf.namelist()
        total = len(members)
        for i, name in enumerate(members, start=1):
            rf.extract(name, dst)
            if cb:
                cb(i, total, f"解压中：{name} ({i}/{total})")


def _extract_tar(src: Path, dst: Path, cb: ProgressCallback | None) -> None:
    with tarfile.open(src, "r:*") as tf:
        members = tf.getmembers()
        total = len(members)
        for i, member in enumerate(members, start=1):
            tf.extract(member, dst, filter="data")
            if cb:
                cb(i, total, f"解压中：{member.name} ({i}/{total})")
