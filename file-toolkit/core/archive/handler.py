"""压缩解压统一处理模块"""
import logging
import os
import re
import tarfile
import time
import zipfile
from pathlib import Path

import py7zr

from core.models import ProgressCallback, TaskResult, TaskStatus
from core.paths import unique_path
from core.task_control import TaskCancelled, check_cancelled

logger = logging.getLogger(__name__)


def _safe_extract_check(member_name: str, dst: Path) -> Path | None:
    """校验解压成员路径，防止 Zip Slip 路径穿越。

    Returns:
        合法时返回 resolve 后的目标 Path；非法时返回 None。
    """
    if not member_name:
        return None
    # 拒绝绝对路径
    if os.path.isabs(member_name):
        logger.warning("拒绝绝对路径成员: %s", member_name)
        return None
    # 拒绝显式 .. 穿越（即便未 resolve 也先过滤一次）
    if ".." in Path(member_name).parts:
        logger.warning("拒绝路径穿越成员: %s", member_name)
        return None
    try:
        target = (dst / member_name).resolve()
        dst_resolved = dst.resolve()
    except OSError as exc:
        logger.warning("路径 resolve 失败 %s: %s", member_name, exc)
        return None
    if not target.is_relative_to(dst_resolved):
        logger.warning("路径穿越被拒: %s", member_name)
        return None
    return target


def compress(
    input_files: list[Path],
    output_dir: Path,
    format: str = "zip",
    progress_callback: ProgressCallback | None = None,
    password: str = "",
    archive_name: str = "",
) -> TaskResult:
    """
    压缩文件或文件夹。

    Args:
        input_files: 文件或文件夹的混合列表
        output_dir: 输出目录
        format: 压缩格式 zip / 7z / tar.gz
        progress_callback: 可选进度回调
        password: 7z 的打开密码（同时加密文件名）；ZIP / TAR.GZ 不支持，传了会报错
        archive_name: 压缩包名（不含扩展名）；默认单个文件用其名字，多个文件用第一个的名字
    """
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")

        if password and format != "7z":
            return TaskResult(status=TaskStatus.FAILED, error_message="只有 7Z 格式支持设置密码")
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成输出文件名（同名压缩包已存在时追加 _1，不覆盖）
        first = input_files[0]
        base_name = _clean_name(archive_name) or (first.name if first.is_dir() else first.stem)
        ext_map = {"zip": ".zip", "7z": ".7z", "tar.gz": ".tar.gz"}
        ext = ext_map.get(format, ".zip")
        output_file = unique_path(output_dir / f"{base_name}{ext}")

        # 收集所有待压缩文件（展开文件夹）
        file_entries: list[tuple[Path, str]] = []
        for p in input_files:
            if p.is_dir():
                for root, _, files in os.walk(p):
                    for f in files:
                        full = Path(root) / f
                        if full == output_file:
                            continue  # 输出目录在所选文件夹里时，别把正在写的压缩包也打进去
                        # 压缩包里统一用 / 分隔（Windows 上 relative_to 得到的是 \）
                        arcname = full.relative_to(p.parent).as_posix()
                        file_entries.append((full, arcname))
            else:
                file_entries.append((p, p.name))

        total = len(file_entries)

        if format == "zip":
            _compress_zip(output_file, file_entries, total, progress_callback)
        elif format == "7z":
            _compress_7z(output_file, file_entries, total, progress_callback, password)
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

    except TaskCancelled:
        output_file.unlink(missing_ok=True)
        return TaskResult(status=TaskStatus.CANCELLED, error_message="已取消",
                          duration_seconds=time.time() - t0)
    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def _clean_name(name: str) -> str:
    """去掉用户输入名里的路径分隔符、非法字符和压缩扩展名。"""
    name = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    for ext in (".tar.gz", ".zip", ".7z"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
    return name.strip(" .")


def _compress_zip(
    output_file: Path,
    entries: list[tuple[Path, str]],
    total: int,
    cb: ProgressCallback | None,
) -> None:
    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (full_path, arcname) in enumerate(entries, start=1):
            check_cancelled()
            zf.write(full_path, arcname)
            if cb:
                cb(i, total, f"压缩中：{arcname} ({i}/{total})")


def _compress_7z(
    output_file: Path,
    entries: list[tuple[Path, str]],
    total: int,
    cb: ProgressCallback | None,
    password: str = "",
) -> None:
    kwargs = {"password": password, "header_encryption": True} if password else {}
    with py7zr.SevenZipFile(str(output_file), "w", **kwargs) as sz:
        for i, (full_path, arcname) in enumerate(entries, start=1):
            check_cancelled()
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
            check_cancelled()
            tf.add(full_path, arcname)
            if cb:
                cb(i, total, f"压缩中：{arcname} ({i}/{total})")


def extract(
    input_file: Path,
    output_dir: Path,
    progress_callback: ProgressCallback | None = None,
    password: str = "",
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
            _extract_zip(input_file, output_dir, progress_callback, password)
        elif suffix.endswith(".7z"):
            _extract_7z(input_file, output_dir, progress_callback, password)
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
            output_files=[output_dir],
            output_dir=output_dir,
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


def zip_member_name(info: zipfile.ZipInfo) -> str:
    """还原 ZIP 成员的真实文件名。

    没有 UTF-8 标志（0x800）的成员名，Python 一律按 cp437 解码；Windows 资源管理器 / 老版
    WinRAR 打的中文包实际是 GBK，macOS 打的包常常是 UTF-8 却不设标志，直接解会是乱码。
    """
    name = info.filename
    if info.flag_bits & 0x800 or name.isascii():
        return name
    try:
        raw = name.encode("cp437")
    except UnicodeEncodeError:
        return name
    for encoding in ("utf-8", "gbk", "big5", "shift_jis"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return name


def _extract_zip(src: Path, dst: Path, cb: ProgressCallback | None, password: str = "") -> None:
    import shutil

    with zipfile.ZipFile(src, "r") as zf:
        infos = zf.infolist()
        encrypted = any(i.flag_bits & 0x1 for i in infos)
        if encrypted and not password:
            raise RuntimeError("压缩包有密码，请填写解压密码")
        if encrypted:
            zf.setpassword(password.encode("utf-8"))
        total = len(infos)
        for i, info in enumerate(infos, start=1):
            check_cancelled()
            name = zip_member_name(info)
            target = _safe_extract_check(name, dst)
            if target is None:
                if cb:
                    cb(i, total, f"跳过可疑路径：{name} ({i}/{total})")
                continue
            if info.is_dir() or name.endswith(("/", "\\")):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with zf.open(info) as fsrc, open(target, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst, 1024 * 1024)
                except RuntimeError as exc:
                    target.unlink(missing_ok=True)
                    if "password" in str(exc).lower():
                        raise RuntimeError("解压密码不正确") from exc
                    raise
                except NotImplementedError as exc:
                    target.unlink(missing_ok=True)
                    raise RuntimeError("这个 ZIP 用了 AES 加密，暂不支持，可用 7-Zip 解压") from exc
            if cb:
                cb(i, total, f"解压中：{name} ({i}/{total})")


def _extract_7z(src: Path, dst: Path, cb: ProgressCallback | None, password: str = "") -> None:
    # py7zr 的 extractall 一次性处理，先过滤非法成员再解压
    try:
        sz_ctx = py7zr.SevenZipFile(str(src), "r", password=password or None)
    except py7zr.exceptions.PasswordRequired as exc:
        raise RuntimeError("压缩包有密码，请填写解压密码") from exc
    with sz_ctx as sz:
        if sz.needs_password() and not password:
            raise RuntimeError("压缩包有密码，请填写解压密码")
        names = sz.getnames()
        safe_names: list[str] = []
        for n in names:
            if _safe_extract_check(n, dst) is not None:
                safe_names.append(n)
        if cb:
            cb(1, 1, "正在解压 7z 文件...")
        try:
            if len(safe_names) == len(names):
                sz.extractall(path=str(dst))
            elif safe_names:
                # 有成员被拒绝时逐个取出过滤后的部分
                sz.reset()
                sz.extract(path=str(dst), targets=safe_names)
        except Exception as exc:
            if password:
                raise RuntimeError("解压密码不正确，或压缩包已损坏") from exc
            raise
        if cb:
            cb(1, 1, "解压完成")


def _extract_rar(src: Path, dst: Path, cb: ProgressCallback | None) -> None:
    import rarfile
    try:
        rf_ctx = rarfile.RarFile(str(src), "r")
    except rarfile.RarCannotExec as exc:
        raise RuntimeError("解压 RAR 需要 unrar 或 7-Zip：Windows 请安装 WinRAR / 7-Zip 并加入 PATH，"
                           "macOS：brew install rar，Linux：sudo apt install unrar") from exc
    with rf_ctx as rf:
        members = rf.namelist()
        total = len(members)
        for i, name in enumerate(members, start=1):
            check_cancelled()
            safe_target = _safe_extract_check(name, dst)
            if safe_target is None:
                if cb:
                    cb(i, total, f"跳过可疑路径：{name} ({i}/{total})")
                continue
            rf.extract(name, dst)
            if cb:
                cb(i, total, f"解压中：{name} ({i}/{total})")


def _extract_tar(src: Path, dst: Path, cb: ProgressCallback | None) -> None:
    with tarfile.open(src, "r:*") as tf:
        members = tf.getmembers()
        total = len(members)
        for i, member in enumerate(members, start=1):
            check_cancelled()
            tf.extract(member, dst, filter="data")
            if cb:
                cb(i, total, f"解压中：{member.name} ({i}/{total})")


def archive_stem(path: Path) -> str:
    """去掉压缩包的（多段）扩展名：a.tar.gz → a。"""
    name = path.name
    for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".zip", ".7z", ".rar", ".tar", ".gz"):
        if name.lower().endswith(ext):
            return name[: -len(ext)] or name
    return path.stem


def extract_many(
    input_files: list[Path],
    output_dir: Path,
    progress_callback: ProgressCallback | None = None,
    password: str = "",
) -> TaskResult:
    """批量解压：每个压缩包解到输出目录下以包名命名的子文件夹（重名追加 _1），互不混在一起。"""
    from core.batch import run_batch

    def one(path: Path) -> Path:
        dest = unique_path(output_dir / archive_stem(path))
        res = extract(path, dest, password=password)
        if res.status != TaskStatus.SUCCESS:
            if res.status == TaskStatus.CANCELLED:
                raise TaskCancelled()
            raise RuntimeError(res.error_message or "解压失败")
        return dest

    return run_batch(input_files, output_dir, one, progress_callback, "已解压")
