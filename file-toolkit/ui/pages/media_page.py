"""音视频工作台 — 视频转换 / 压缩 / 剪辑，音频提取 / 转换"""
import re
from pathlib import Path

import flet as ft

from core.media.audio import convert_audio, extract_audio
from core.media.video import compress_video, convert_video, cut_video
from ui.components.workbench import ChoiceGroup, Workbench, WorkbenchFunction
from ui.palette import c
from ui.utils import show_toast

_VIDEO = ("mp4", "avi", "mkv", "mov", "flv", "wmv", "webm", "m4v")
_AUDIO = ("mp3", "wav", "flac", "aac", "ogg", "wma", "m4a")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}(\.\d+)?$")


def _seconds(t: str) -> float:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _hint(text: str) -> ft.Text:
    return ft.Text(text, size=11, color=c("ink-3", "fg"))


class MediaPage(Workbench):
    TITLE = "音视频工作台"
    SUBTITLE = "视频转换、压缩与剪辑，音频提取与转换"
    MODULE = "media"
    PICK_LABEL = "点击选择音视频文件"
    PICK_ICON = ft.Icons.VIDEO_FILE_OUTLINED
    FILE_ICON = ft.Icons.MOVIE_OUTLINED
    FUNCTIONS = [
        WorkbenchFunction("video_convert", "视频转换", "MP4 / MKV / MOV / AVI / WebM", ft.Icons.SWAP_HORIZ_OUTLINED,
                          _VIDEO),
        WorkbenchFunction("video_compress", "视频压缩", "降低码率或分辨率", ft.Icons.COMPRESS_OUTLINED,
                          _VIDEO),
        WorkbenchFunction("video_cut", "视频剪辑", "截取一段时间", ft.Icons.CONTENT_CUT_OUTLINED,
                          _VIDEO),
        WorkbenchFunction("audio_extract", "音频提取", "从视频导出音轨", ft.Icons.MUSIC_NOTE_OUTLINED,
                          _VIDEO),
        WorkbenchFunction("audio_convert", "音频转换", "MP3 / WAV / FLAC / AAC / OGG", ft.Icons.GRAPHIC_EQ_OUTLINED,
                          _AUDIO),
    ]

    def __init__(self, page: ft.Page, initial_func: str | None = None) -> None:
        self._video_format = ChoiceGroup(
            [("mp4", "MP4"), ("mkv", "MKV"), ("mov", "MOV"), ("avi", "AVI"), ("webm", "WebM")], "mp4")
        self._quality = ChoiceGroup([("high", "画质优先"), ("medium", "均衡"), ("low", "体积优先")], "medium")
        self._resolution = ChoiceGroup(
            [("original", "原始"), ("1080p", "1080p"), ("720p", "720p"), ("480p", "480p")], "original")
        self._cut_start = self.text_field("00:00:00", "开始 HH:MM:SS", expand=True)
        self._cut_end = self.text_field("00:01:00", "结束 HH:MM:SS", expand=True)
        self._extract_format = ChoiceGroup(
            [("mp3", "MP3"), ("wav", "WAV"), ("flac", "FLAC"), ("aac", "AAC")], "mp3")
        self._audio_format = ChoiceGroup(
            [("mp3", "MP3"), ("wav", "WAV"), ("flac", "FLAC"), ("aac", "AAC"), ("ogg", "OGG")], "mp3")
        self._bitrate = ChoiceGroup([("128", "128k"), ("192", "192k"), ("256", "256k"), ("320", "320k")], "192")
        super().__init__(page, initial_func)

    def build_params(self, key: str) -> list[ft.Control]:
        if key == "video_convert":
            return [self.section("目标格式", self._video_format)]
        if key == "video_compress":
            return [
                self.section("压缩强度", self._quality),
                self.section("分辨率", ft.Column(controls=[
                    self._resolution, _hint("降低分辨率是减小体积最有效的方式"),
                ], spacing=8)),
            ]
        if key == "video_cut":
            return [self.section("时间范围", ft.Column(controls=[
                ft.Row(controls=[self._cut_start, ft.Text("至", color=c("ink-2", "fg")), self._cut_end], spacing=8),
                _hint("格式 时:分:秒，如 00:01:30；选多个视频时每个都截取同一段"),
            ], spacing=8))]
        if key == "audio_extract":
            return [self.section("输出格式", self._extract_format)]
        return [
            self.section("目标格式", self._audio_format),
            self.section("比特率", ft.Column(controls=[
                self._bitrate, _hint("WAV / FLAC 为无损格式，比特率设置不生效"),
            ], spacing=8)),
        ]

    def build_task(self, key: str, files: list[Path], out_dir: Path):
        if key == "video_convert":
            return convert_video, {"input_files": files, "output_dir": out_dir,
                                   "target_format": self._video_format.value}
        if key == "video_compress":
            return compress_video, {"input_files": files, "output_dir": out_dir,
                                    "quality": self._quality.value, "resolution": self._resolution.value}
        if key == "video_cut":
            start = (self._cut_start.value or "").strip()
            end = (self._cut_end.value or "").strip()
            if not _TIME_RE.match(start) or not _TIME_RE.match(end):
                show_toast(self._page, "时间格式应为 时:分:秒，如 00:01:30")
                return None
            if _seconds(end) <= _seconds(start):
                show_toast(self._page, "结束时间必须晚于开始时间")
                return None
            return self.each(cut_video, files, lambda p: {
                "input_file": p, "output_dir": out_dir, "start_time": start, "end_time": end})
        if key == "audio_extract":
            fmt = self._extract_format.value
            return self.each(extract_audio, files, lambda p: {
                "input_file": p, "output_dir": out_dir, "audio_format": fmt})
        return convert_audio, {"input_files": files, "output_dir": out_dir,
                               "target_format": self._audio_format.value, "bitrate": self._bitrate.value}
