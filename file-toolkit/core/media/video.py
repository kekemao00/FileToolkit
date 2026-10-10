"""视频处理模块 — 格式转换、压缩、剪切"""
from pathlib import Path

from core.batch import run_batch
from core.media._ffmpeg import FileProgress, run_ffmpeg
from core.models import ProgressCallback, TaskResult, TaskStatus
from core.paths import reserve, unique_path

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
    批量视频格式转换（编码器由 FFmpeg 按目标格式选默认值）。

    Args:
        input_files: 输入视频列表
        output_dir: 输出目录
        target_format: 目标格式 (mp4/avi/mkv/mov/webm)
        progress_callback: 可选进度回调
    """
    claimed: set[Path] = set()
    progress = FileProgress(input_files, progress_callback)

    def one(path: Path) -> Path:
        out = reserve(output_dir / f"{path.stem}.{target_format}", claimed, input_files)
        run_ffmpeg(["-i", str(path), "-y", str(out)], progress.start(path))
        return out

    return run_batch(input_files, output_dir, one, progress_callback, "已转换")


def compress_video(
    input_files: list[Path],
    output_dir: Path,
    quality: str = "medium",
    resolution: str = "original",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量视频压缩（H.264 CRF 恒定质量）。

    Args:
        input_files: 输入视频列表
        output_dir: 输出目录
        quality: high(画质优先, CRF 18) / medium(均衡, 23) / low(体积优先, 28)
        resolution: original/1080p/720p/480p
        progress_callback: 可选进度回调
    """
    crf = _CRF_MAP.get(quality, 23)
    claimed: set[Path] = set()
    progress = FileProgress(input_files, progress_callback)

    def one(path: Path) -> Path:
        out = reserve(output_dir / f"{path.stem}_compressed.mp4", claimed, input_files)
        args = ["-i", str(path), "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
        if resolution in _RESOLUTION_MAP:
            # 只缩小不放大；宽高取偶数（libx264 要求）
            args += ["-vf", f"scale={_RESOLUTION_MAP[resolution]}:force_original_aspect_ratio=decrease"
                            ":force_divisible_by=2"]
        run_ffmpeg([*args, "-y", str(out)], progress.start(path))
        return out

    return run_batch(input_files, output_dir, one, progress_callback, "已压缩")


def _seconds(t: str) -> float:
    parts = [float(p) for p in t.strip().split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def cut_video(
    input_file: Path,
    output_dir: Path,
    start_time: str = "00:00:00",
    end_time: str = "00:01:00",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    视频剪切（流复制，不重新编码；起点会对齐到最近的关键帧）。

    Args:
        input_file: 输入视频路径
        output_dir: 输出目录
        start_time: 开始时间 "HH:MM:SS"
        end_time: 结束时间 "HH:MM:SS"
        progress_callback: 可选进度回调
    """
    length = _seconds(end_time) - _seconds(start_time)
    if length <= 0:
        return TaskResult(status=TaskStatus.FAILED, error_message="结束时间必须晚于开始时间")

    def one(path: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out = unique_path(output_dir / f"{path.stem}_cut{path.suffix}", [path])

        def frac(f: float) -> None:
            if progress_callback:
                progress_callback(int(f * 1000), 1000, f"正在剪辑  {int(f * 100)}%")

        run_ffmpeg(["-ss", start_time, "-i", str(path), "-t", f"{length:.3f}",
                    "-c", "copy", "-avoid_negative_ts", "make_zero", "-y", str(out)],
                   frac, duration=length)
        return out

    return run_batch([input_file], output_dir, one, progress_callback, "剪辑完成")
