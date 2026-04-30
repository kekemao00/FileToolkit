"""音频处理模块 — 格式转换、从视频提取音频"""
import subprocess
import time
from pathlib import Path

from core.models import ProgressCallback, TaskResult, TaskStatus
from core.platform import get_ffmpeg_path


def extract_audio(
    input_file: Path,
    output_dir: Path,
    audio_format: str = "mp3",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    从视频文件提取音频轨道。

    Args:
        input_file: 输入视频路径
        output_dir: 输出目录
        audio_format: 输出音频格式 (mp3/wav/flac/aac)
        progress_callback: 可选进度回调
    """
    t0 = time.time()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg = str(get_ffmpeg_path())
        out_path = output_dir / f"{input_file.stem}.{audio_format}"

        if progress_callback:
            progress_callback(0, 1, "正在提取音频...")

        codec = _format_to_codec(audio_format)
        cmd = [
            ffmpeg, "-i", str(input_file),
            "-vn",
            "-acodec", codec,
        ]
        if audio_format == "mp3":
            cmd.extend(["-b:a", "192k"])

        cmd.extend(["-y", str(out_path)])
        _run_ffmpeg(cmd)

        if progress_callback:
            progress_callback(1, 1, "提取完成")

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


def convert_audio(
    input_files: list[Path],
    output_dir: Path,
    target_format: str = "mp3",
    bitrate: str = "192",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量音频格式转换。

    Args:
        input_files: 输入音频列表
        output_dir: 输出目录
        target_format: 目标格式 (mp3/wav/flac/aac/ogg)
        bitrate: 比特率字符串 "128"/"192"/"256"/"320"
        progress_callback: 可选进度回调
    """
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")

        output_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg = str(get_ffmpeg_path())
        codec = _format_to_codec(target_format)
        br = f"{bitrate}k"

        output_files: list[Path] = []
        total = len(input_files)

        for i, path in enumerate(input_files, start=1):
            out_path = output_dir / f"{path.stem}.{target_format}"
            cmd = [
                ffmpeg, "-i", str(path),
                "-acodec", codec,
            ]
            # FLAC/WAV 是无损格式，不设比特率
            if target_format not in ("flac", "wav"):
                cmd.extend(["-b:a", br])

            cmd.extend(["-y", str(out_path)])
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


def _format_to_codec(fmt: str) -> str:
    """音频格式 → FFmpeg 编码器名称。"""
    return {
        "mp3": "libmp3lame",
        "aac": "aac",
        "flac": "flac",
        "wav": "pcm_s16le",
        "ogg": "libvorbis",
        "m4a": "aac",
    }.get(fmt, "libmp3lame")


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
