"""音频处理模块 — 格式转换、从视频提取音频"""
from pathlib import Path
from typing import Literal

from core.models import ProgressCallback, TaskResult

AudioFormat = Literal["mp3", "aac", "flac", "wav", "m4a", "ogg"]


def extract_audio(
    input_file: Path,
    output_file: Path,
    output_format: AudioFormat = "mp3",
    bitrate: str = "192k",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    从视频文件提取音频轨道。

    Args:
        input_file: 输入视频路径
        output_file: 输出音频路径
        output_format: 输出音频格式
        bitrate: 音频比特率，如 "192k"、"320k"
    """
    raise NotImplementedError


def convert_audio(
    input_file: Path,
    output_file: Path,
    output_format: AudioFormat,
    bitrate: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    音频格式转换（MP3/AAC/FLAC/WAV/M4A/OGG 互转）。
    """
    raise NotImplementedError
