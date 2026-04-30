"""视频处理模块 — 格式转换、压缩、剪切"""
import subprocess
import time
from pathlib import Path

from core.models import ProgressCallback, TaskResult, TaskStatus
from core.platform import get_ffmpeg_path

_CRF_MAP = {
    "low": 28,
    "medium": 23,
    "high": 18,
}

_RESOLUTION_MAP = {
    "1080p": "1920:1080",
    "720p": "1280:720",
    "480p": "854:480",
}


def convert_video(
    input_files: list[Path],
    output_dir: Path,
    target_format: str = "mp4",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量视频格式转换。

    Args:
        input_files: 输入视频列表
        output_dir: 输出目录
        target_format: 目标格式 (mp4/avi/mkv/mov/webm)
        progress_callback: 可选进度回调
    """
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")

        output_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg = str(get_ffmpeg_path())
        output_files: list[Path] = []
        total = len(input_files)

        for i, path in enumerate(input_files, start=1):
            out_path = output_dir / f"{path.stem}.{target_format}"
            cmd = [
                ffmpeg, "-i", str(path),
                "-y",
                str(out_path),
            ]
            _run_ffmpeg(cmd)
            output_files.append(out_path)

            if progress_callback:
                progress_callback(i, total, f"已转换：{path.name} ({i}/{total})")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=output_files,
            output_dir=output_dir,
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def compress_video(
    input_files: list[Path],
    output_dir: Path,
    quality: str = "medium",
    resolution: str = "original",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量视频压缩（CRF 恒定质量模式）。

    Args:
        input_files: 输入视频列表
        output_dir: 输出目录
        quality: low(轻度/质量优先)/medium(标准)/high(极限/体积优先)
        resolution: original/1080p/720p/480p
        progress_callback: 可选进度回调
    """
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")

        output_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg = str(get_ffmpeg_path())
        crf = _CRF_MAP.get(quality, 23)
        output_files: list[Path] = []
        total = len(input_files)

        for i, path in enumerate(input_files, start=1):
            out_path = output_dir / f"{path.stem}_compressed.mp4"
            cmd = [
                ffmpeg, "-i", str(path),
                "-c:v", "libx264",
                "-crf", str(crf),
                "-preset", "medium",
                "-c:a", "aac",
                "-b:a", "128k",
            ]

            if resolution != "original" and resolution in _RESOLUTION_MAP:
                scale = _RESOLUTION_MAP[resolution]
                cmd.extend(["-vf", f"scale={scale}:force_original_aspect_ratio=decrease"])

            cmd.extend(["-y", str(out_path)])
            _run_ffmpeg(cmd)
            output_files.append(out_path)

            if progress_callback:
                progress_callback(i, total, f"已压缩：{path.name} ({i}/{total})")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=output_files,
            output_dir=output_dir,
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def cut_video(
    input_file: Path,
    output_dir: Path,
    start_time: str = "00:00:00",
    end_time: str = "00:01:00",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    视频剪切。

    Args:
        input_file: 输入视频路径
        output_dir: 输出目录
        start_time: 开始时间 "HH:MM:SS"
        end_time: 结束时间 "HH:MM:SS"
        progress_callback: 可选进度回调
    """
    t0 = time.time()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg = str(get_ffmpeg_path())
        out_path = output_dir / f"{input_file.stem}_cut{input_file.suffix}"

        if progress_callback:
            progress_callback(0, 1, "正在剪辑...")

        cmd = [
            ffmpeg,
            "-ss", start_time,
            "-to", end_time,
            "-i", str(input_file),
            "-c", "copy",
            "-y",
            str(out_path),
        ]
        _run_ffmpeg(cmd)

        if progress_callback:
            progress_callback(1, 1, "剪辑完成")

        return TaskResult(
            status=TaskStatus.SUCCESS,
            output_files=[out_path],
            output_dir=output_dir,
            duration_seconds=time.time() - t0,
        )

    except Exception as exc:
        return TaskResult(
            status=TaskStatus.FAILED,
            error_message=str(exc),
            duration_seconds=time.time() - t0,
        )


def _run_ffmpeg(cmd: list[str]) -> None:
    """执行 ffmpeg 命令，失败时抛出异常。"""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if result.returncode != 0:
        stderr = result.stderr[-500:] if result.stderr else "未知错误"
        raise RuntimeError(f"FFmpeg 执行失败: {stderr}")
