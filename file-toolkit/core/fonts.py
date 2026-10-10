"""查找可显示中文的系统字体（水印用）。

只用系统自带字体，不随应用打包。顺序：能显示中文的 TrueType 字体在前
（reportlab 只能嵌入 TrueType 轮廓，Noto CJK 这类 CFF 字体只给 Pillow 用）。
"""
import os
import sys
from functools import cache
from pathlib import Path


def _windows_fonts() -> Path:
    return Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


def cjk_font_candidates() -> list[tuple[Path, int]]:
    """(字体文件, ttc 子字体序号)，按优先级排列，只返回存在的文件。"""
    if sys.platform == "win32":
        d = _windows_fonts()
        items = [(d / "msyh.ttc", 0), (d / "msyh.ttf", 0), (d / "simhei.ttf", 0),
                 (d / "simsun.ttc", 0), (d / "arial.ttf", 0)]
    elif sys.platform == "darwin":
        items = [
            (Path("/System/Library/Fonts/STHeiti Light.ttc"), 0),
            (Path("/System/Library/Fonts/STHeiti Medium.ttc"), 0),
            (Path("/System/Library/Fonts/Hiragino Sans GB.ttc"), 0),
            (Path("/System/Library/Fonts/PingFang.ttc"), 0),
            (Path("/Library/Fonts/Arial Unicode.ttf"), 0),
            (Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"), 0),
            (Path("/System/Library/Fonts/Helvetica.ttc"), 0),
        ]
    else:
        items = [
            (Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"), 0),
            (Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"), 0),
            (Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"), 0),
            (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), 2),
            (Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"), 2),
            (Path("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc"), 2),
            (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), 0),
        ]
    return [(p, i) for p, i in items if p.is_file()]


@cache
def reportlab_font(text: str) -> str:
    """给 reportlab 注册一个能显示 text 的字体，返回字体名。

    纯 ASCII 直接用内置 Helvetica；含中文时依次尝试系统 TrueType 字体，
    都不行再退回 reportlab 内置的 STSong-Light（阅读器用自带字体显示，不嵌入）。
    """
    if text.isascii():
        return "Helvetica"
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for i, (path, index) in enumerate(cjk_font_candidates()):
        name = f"FTKCJK{i}"
        try:
            font = TTFont(name, str(path), subfontIndex=index)
            # 字体里缺字（如 DejaVu 没有汉字）就换下一个
            if all(ord(ch) in font.face.charToGlyph for ch in text if not ch.isspace()):
                pdfmetrics.registerFont(font)
                return name
        except Exception:
            continue
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


def pillow_font(size: int):
    """Pillow 用的字体；找不到系统字体时用 Pillow 自带的（只有拉丁字母）。"""
    from PIL import ImageFont

    for path, index in cjk_font_candidates():
        try:
            return ImageFont.truetype(str(path), size, index=index)
        except OSError:
            continue
    return ImageFont.load_default(size)
