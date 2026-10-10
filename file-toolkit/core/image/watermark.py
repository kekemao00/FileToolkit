"""图片水印模块"""
from pathlib import Path

from PIL import Image, ImageDraw

from core.batch import run_batch
from core.fonts import pillow_font
from core.image._common import open_image, to_rgb
from core.models import ProgressCallback, TaskResult, TaskStatus
from core.paths import reserve


def _get_font(font_size: int):
    """能显示中文的系统字体（Windows 微软雅黑 / macOS 黑体 / Linux 文泉驿等）。"""
    return pillow_font(font_size)


def _calc_position(
    img_w: int, img_h: int, text_w: int, text_h: int, position: str,
) -> tuple[int, int]:
    """根据位置标识计算文字左上角坐标。"""
    margin = 20
    cx = (img_w - text_w) // 2
    cy = (img_h - text_h) // 2
    positions = {
        "top_left": (margin, margin),
        "top_center": (cx, margin),
        "top_right": (img_w - text_w - margin, margin),
        "center_left": (margin, cy),
        "center": (cx, cy),
        "center_right": (img_w - text_w - margin, cy),
        "bottom_left": (margin, img_h - text_h - margin),
        "bottom_center": (cx, img_h - text_h - margin),
        "bottom_right": (img_w - text_w - margin, img_h - text_h - margin),
        # 兼容旧格式（带连字符）
        "top-left": (margin, margin),
        "top-right": (img_w - text_w - margin, margin),
        "bottom-left": (margin, img_h - text_h - margin),
        "bottom-right": (img_w - text_w - margin, img_h - text_h - margin),
    }
    return positions.get(position, (cx, cy))


def add_text_watermark(
    input_files: list[Path],
    output_dir: Path,
    text: str,
    position: str = "bottom_right",
    opacity: int = 30,
    font_size: int = 24,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    在图片上添加文字水印。

    Args:
        input_files: 输入图片列表
        output_dir: 输出目录
        text: 水印文字
        position: 位置 (top_left/top_right/bottom_left/bottom_right/center/tile)
        opacity: 透明度 10-100（UI Slider 值）
        font_size: 字号
        progress_callback: 可选进度回调
    """
    if not text:
        return TaskResult(status=TaskStatus.FAILED, error_message="水印文字不能为空")
    alpha = int(255 * opacity / 100)
    font = _get_font(font_size)
    fill = (255, 255, 255, alpha)
    claimed: set[Path] = set()

    def one(path: Path) -> Path:
        img = open_image(path).convert("RGBA")
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        if position == "tile":
            spacing_x, spacing_y = text_w + 80, text_h + 80
            for y in range(0, img.height, spacing_y):
                for x in range(0, img.width, spacing_x):
                    draw.text((x, y), text, font=font, fill=fill)
        else:
            x, y = _calc_position(img.width, img.height, text_w, text_h, position)
            draw.text((x - bbox[0], y - bbox[1]), text, font=font, fill=fill)

        return _save_like(Image.alpha_composite(img, layer), path, output_dir, claimed, input_files)

    return run_batch(input_files, output_dir, one, progress_callback, "已添加水印")


def _save_like(img: Image.Image, src: Path, output_dir: Path, claimed: set[Path],
               inputs: list[Path]) -> Path:
    """按原格式保存（JPG / WebP 保持，其他存 PNG 以保留透明度）。"""
    ext = src.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        out = reserve(output_dir / f"{src.stem}_watermark{ext}", claimed, inputs)
        to_rgb(img).save(out, format="JPEG", quality=95)
    elif ext == ".webp":
        out = reserve(output_dir / f"{src.stem}_watermark.webp", claimed, inputs)
        img.save(out, format="WEBP", quality=95)
    else:
        out = reserve(output_dir / f"{src.stem}_watermark.png", claimed, inputs)
        img.save(out, format="PNG")
    return out


def add_image_watermark(
    input_files: list[Path],
    output_dir: Path,
    watermark_image: Path,
    position: str = "bottom_right",
    opacity: float = 0.5,
    scale: float = 0.2,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """在图片上叠加图片水印。"""
    try:
        wm = open_image(watermark_image).convert("RGBA")
    except Exception as exc:
        return TaskResult(status=TaskStatus.FAILED, error_message=f"水印图片无法打开：{exc}")
    claimed: set[Path] = set()

    def one(path: Path) -> Path:
        img = open_image(path).convert("RGBA")
        wm_w = max(1, int(img.width * scale))
        wm_h = max(1, int(wm.height * (wm_w / wm.width)))
        wm_resized = wm.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
        wm_resized.putalpha(wm_resized.getchannel("A").point(lambda p: int(p * opacity)))
        x, y = _calc_position(img.width, img.height, wm_w, wm_h, position)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        layer.paste(wm_resized, (x, y))
        return _save_like(Image.alpha_composite(img, layer), path, output_dir, claimed, input_files)

    return run_batch(input_files, output_dir, one, progress_callback, "已添加水印")
