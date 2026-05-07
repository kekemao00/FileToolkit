"""图片水印模块"""
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.models import ProgressCallback, TaskResult, TaskStatus


def _get_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """尝试加载系统字体，失败则用默认字体。"""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, font_size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


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
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")
        if not text:
            return TaskResult(status=TaskStatus.FAILED, error_message="水印文字不能为空")

        output_dir.mkdir(parents=True, exist_ok=True)
        alpha = int(255 * opacity / 100)
        font = _get_font(font_size)

        output_files: list[Path] = []
        total = len(input_files)

        for i, path in enumerate(input_files, start=1):
            img = Image.open(path).convert("RGBA")

            # 创建水印层
            watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark_layer)

            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            fill = (255, 255, 255, alpha)

            if position == "tile":
                # 平铺模式：间隔绘制
                spacing_x = text_w + 80
                spacing_y = text_h + 80
                y = 0
                while y < img.height:
                    x = 0
                    while x < img.width:
                        draw.text((x, y), text, font=font, fill=fill)
                        x += spacing_x
                    y += spacing_y
            else:
                x, y = _calc_position(img.width, img.height, text_w, text_h, position)
                draw.text((x, y), text, font=font, fill=fill)

            result_img = Image.alpha_composite(img, watermark_layer)

            # 保存（保持原格式）
            ext = path.suffix.lower()
            out_path = output_dir / f"{path.stem}_watermark{ext}"
            if ext in (".jpg", ".jpeg"):
                result_img = result_img.convert("RGB")
                result_img.save(out_path, format="JPEG", quality=95)
            elif ext == ".webp":
                result_img.save(out_path, format="WEBP", quality=95)
            else:
                result_img.save(out_path, format="PNG")

            output_files.append(out_path)
            if progress_callback:
                progress_callback(i, total, f"已添加水印：{path.name} ({i}/{total})")

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
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")

        output_dir.mkdir(parents=True, exist_ok=True)
        wm = Image.open(watermark_image).convert("RGBA")

        output_files: list[Path] = []
        total = len(input_files)

        for i, path in enumerate(input_files, start=1):
            img = Image.open(path).convert("RGBA")

            # 缩放水印
            wm_w = int(img.width * scale)
            wm_h = int(wm.height * (wm_w / wm.width))
            wm_resized = wm.resize((wm_w, wm_h), Image.LANCZOS)

            # 调整透明度
            alpha_channel = wm_resized.split()[3]
            alpha_channel = alpha_channel.point(lambda p: int(p * opacity))
            wm_resized.putalpha(alpha_channel)

            # 计算位置
            x, y = _calc_position(img.width, img.height, wm_w, wm_h, position)

            # 合成
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            layer.paste(wm_resized, (x, y))
            result_img = Image.alpha_composite(img, layer)

            ext = path.suffix.lower()
            out_path = output_dir / f"{path.stem}_watermark{ext}"
            if ext in (".jpg", ".jpeg"):
                result_img = result_img.convert("RGB")
                result_img.save(out_path, format="JPEG", quality=95)
            else:
                result_img.save(out_path, format="PNG")

            output_files.append(out_path)
            if progress_callback:
                progress_callback(i, total, f"已添加水印：{path.name} ({i}/{total})")

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
