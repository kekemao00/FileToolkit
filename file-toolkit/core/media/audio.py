"""音频处理模块 — 格式转换、从视频提取音频"""
from pathlib import Path

from core.batch import run_batch
from core.media._ffmpeg import FileProgress, run_ffmpeg
from core.models import ProgressCallback, TaskResult
from core.paths import reserve


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
    files = [input_file]
    progress = FileProgress(files, progress_callback)

    def one(path: Path) -> Path:
        out = reserve(output_dir / f"{path.stem}.{audio_format}", set(), files)
        args = ["-i", str(path), "-vn", "-acodec", _format_to_codec(audio_format)]
        if audio_format == "mp3":
            args += ["-b:a", "192k"]
        run_ffmpeg([*args, "-y", str(out)], progress.start(path))
        return out

    return run_batch(files, output_dir, one, progress_callback, "提取完成")


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
    codec = _format_to_codec(target_format)
    claimed: set[Path] = set()
    progress = FileProgress(input_files, progress_callback)

    def one(path: Path) -> Path:
        out = reserve(output_dir / f"{path.stem}.{target_format}", claimed, input_files)
        args = ["-i", str(path), "-vn", "-acodec", codec]
        # FLAC/WAV 是无损格式，不设比特率
        if target_format not in ("flac", "wav"):
            args += ["-b:a", f"{bitrate}k"]
        run_ffmpeg([*args, "-y", str(out)], progress.start(path))
        return out

    return run_batch(input_files, output_dir, one, progress_callback, "已转换")


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

