"""视频处理模块 — 格式转换、压缩、剪切"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult

VideoCodec = Literal["libx264", "libx265", "libvpx-vp9", "av1"]
AudioCodec = Literal["aac", "mp3", "ac3", "flac", "copy"]
Resolution = Literal["3840x2160", "1920x1080", "1280x720", "854x480", "640x360"]


def convert_video(
    input_file: Path,
    output_file: Path,
    video_codec: VideoCodec = "libx264",
    audio_codec: AudioCodec = "aac",
    resolution: Resolution | None = None,
    bitrate: str | None = None,
    fps: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    视频格式转换。

    Args:
        input_file: 输入视频路径
        output_file: 输出视频路径（扩展名决定容器格式）
        video_codec: 视频编码，None 表示保持原始
        audio_codec: 音频编码
        resolution: 输出分辨率，None 表示保持原始
        bitrate: 视频码率，如 "2M"，None 表示自动
        fps: 帧率，None 表示保持原始
        progress_callback: 可选进度回调（通过解析 FFmpeg stderr time= 字段）
    """
    raise NotImplementedError


def compress_video(
    input_file: Path,
    output_file: Path,
    resolution: Resolution | None = None,
    crf: int = 23,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    视频压缩（使用 CRF 恒定质量模式）。

    Args:
        crf: H.264 质量因子，0-51，越小质量越高，23 为默认值
    """
    raise NotImplementedError


def cut_video(
    input_file: Path,
    output_file: Path,
    start_time: float | str,
    end_time: float | str,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    视频剪切（-ss 精确定位，-c copy 避免重编码，速度快）。

    Args:
        start_time: 开始时间，秒数（float）或 "HH:MM:SS" 格式
        end_time: 结束时间，同上
    """
    raise NotImplementedError
