"""
功能目录 — 全局搜索、首页入口、模块「更多工具」共用的单一数据源。

新增功能时只需在 FEATURES 里加一行，搜索即可自动覆盖。
route 可带 `?func=<key>`，由 router 解析后传给工作台页面作为默认选中的功能。
"""
from dataclasses import dataclass

import flet as ft


@dataclass(frozen=True)
class Feature:
    title: str
    route: str
    icon: str
    group: str
    keywords: tuple[str, ...] = ()

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        haystack = " ".join((self.title, self.group, *self.keywords)).lower()
        return all(part in haystack for part in q.split())


FEATURES: list[Feature] = [
    # AI
    Feature("AI 智能任务", "/ai", ft.Icons.AUTO_AWESOME, "AI", ("助手", "自动", "ai")),
    Feature("提示词出图", "/prompt-image", ft.Icons.AUTO_FIX_HIGH, "AI",
            ("生图", "海报", "图片生成", "prompt", "gpt-image")),
    # PDF
    Feature("PDF 合并", "/pdf?func=merge", ft.Icons.MERGE, "PDF", ("合并", "merge", "pdf")),
    Feature("PDF 拆分", "/pdf?func=split", ft.Icons.CONTENT_CUT, "PDF", ("拆分", "分割", "split", "页码")),
    Feature("PDF 压缩", "/pdf?func=compress", ft.Icons.COMPRESS, "PDF", ("压缩", "减小", "compress")),
    Feature("PDF 转 Word / Excel / PPT", "/pdf?func=to_office", ft.Icons.DESCRIPTION_OUTLINED, "PDF",
            ("转换", "word", "docx", "excel", "xlsx", "ppt", "pptx", "office")),
    Feature("Office 转 PDF", "/pdf?func=from_office", ft.Icons.PICTURE_AS_PDF_OUTLINED, "PDF",
            ("转换", "word", "excel", "ppt", "docx", "office", "libreoffice")),
    Feature("PDF 加密 / 水印", "/pdf?func=protect", ft.Icons.LOCK_OUTLINED, "PDF",
            ("加密", "密码", "水印", "保护", "watermark")),
    # 图片
    Feature("图片压缩", "/image?func=compress", ft.Icons.COMPRESS, "图片", ("压缩", "减小", "jpg", "png")),
    Feature("图片格式转换", "/image?func=convert", ft.Icons.TRANSFORM, "图片",
            ("转换", "格式", "png", "jpg", "webp", "heic")),
    Feature("图片尺寸调整", "/image?func=resize", ft.Icons.PHOTO_SIZE_SELECT_LARGE, "图片",
            ("尺寸", "缩放", "分辨率", "resize")),
    Feature("图片加水印", "/image?func=watermark", ft.Icons.WATER_DROP_OUTLINED, "图片", ("水印", "watermark")),
    Feature("图片批量重命名", "/image?func=rename", ft.Icons.DRIVE_FILE_RENAME_OUTLINE, "图片",
            ("重命名", "改名", "批量", "rename")),
    # 音视频
    Feature("视频格式转换", "/media?func=video_convert", ft.Icons.SWAP_HORIZ, "音视频",
            ("视频", "转换", "mp4", "avi", "mov", "mkv")),
    Feature("视频压缩", "/media?func=video_compress", ft.Icons.COMPRESS, "音视频", ("视频", "压缩", "码率")),
    Feature("视频剪辑", "/media?func=video_cut", ft.Icons.CONTENT_CUT, "音视频", ("视频", "剪辑", "裁剪", "截取")),
    Feature("提取音频", "/media?func=audio_extract", ft.Icons.MUSIC_NOTE, "音视频", ("音频", "提取", "mp3")),
    Feature("音频格式转换", "/media?func=audio_convert", ft.Icons.GRAPHIC_EQ, "音视频",
            ("音频", "转换", "mp3", "wav", "aac", "flac")),
    # 压缩解压
    Feature("ZIP 压缩", "/archive?func=compress_zip", ft.Icons.FOLDER_ZIP, "压缩解压", ("压缩", "打包", "zip")),
    Feature("7Z 压缩", "/archive?func=compress_7z", ft.Icons.ARCHIVE, "压缩解压", ("压缩", "打包", "7z")),
    Feature("TAR.GZ 压缩", "/archive?func=compress_targz", ft.Icons.INVENTORY_2_OUTLINED, "压缩解压",
            ("压缩", "打包", "tar", "gz", "linux")),
    Feature("解压文件", "/archive?func=extract", ft.Icons.UNARCHIVE_OUTLINED, "压缩解压",
            ("解压", "zip", "7z", "rar", "tar")),
    # OCR
    Feature("OCR 文字识别", "/ocr", ft.Icons.DOCUMENT_SCANNER, "OCR", ("识别", "文字", "提取文字", "扫描", "ocr")),
    # 其他
    Feature("最近操作", "/history", ft.Icons.HISTORY, "应用", ("历史", "记录")),
    Feature("设置", "/settings", ft.Icons.SETTINGS_OUTLINED, "应用", ("设置", "主题", "输出目录", "api key")),
]


# 历史记录里的 action 键 → 显示名（最近操作页、首页共用）
ACTION_LABELS: dict[str, str] = {
    "merge": "合并", "split": "拆分", "compress": "压缩", "protect": "加密水印",
    "to_word": "转 Word", "to_office": "转 Office", "from_office": "Office 转 PDF",
    "convert": "格式转换", "resize": "尺寸调整", "watermark": "加水印", "rename": "批量重命名",
    "video_convert": "视频转换", "video_compress": "视频压缩", "video_cut": "视频剪辑",
    "audio_extract": "音频提取", "audio_convert": "音频转换",
    "compress_zip": "ZIP 压缩", "compress_7z": "7Z 压缩", "compress_targz": "TAR.GZ 压缩", "extract": "解压",
    "recognize": "文字识别", "ocr": "OCR 识别", "ai_task": "AI 处理",
}


def search_features(query: str, limit: int = 8) -> list[Feature]:
    return [f for f in FEATURES if f.matches(query)][:limit]
