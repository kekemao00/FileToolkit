"""图片批量压缩模块"""
from pathlib import Path

from PIL import Image

from core.batch import run_batch
from core.image._common import open_image, to_rgb
from core.models import ProgressCallback, TaskResult
from core.paths import reserve

_LEVEL_QUALITY = {
    "low": 85,
    "medium": 65,
    "high": 40,
}


def compress_images(
    input_files: list[Path],
    output_dir: Path,
    level: str = "medium",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量图片压缩。JPG / WebP / PNG 保持原格式，其他格式转为 JPG。

    Args:
        input_files: 输入图片列表
        output_dir: 输出目录
        level: 压缩级别 low(轻度)/medium(标准)/high(极限)
        progress_callback: 可选进度回调
    """
    quality = _LEVEL_QUALITY.get(level, 65)
    claimed: set[Path] = set()

    def one(path: Path) -> Path:
        img = open_image(path)
        ext = path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            fmt, out_ext = "JPEG", ".jpg"
        elif ext == ".webp":
            fmt, out_ext = "WEBP", ".webp"
        elif ext == ".png":
            fmt, out_ext = "PNG", ".png"
        else:
            fmt, out_ext = "JPEG", ".jpg"

        save_kwargs: dict = {"optimize": True}
        if fmt == "JPEG":
            img = to_rgb(img)
            save_kwargs.update(quality=quality, progressive=True)
        elif fmt == "WEBP":
            save_kwargs["quality"] = quality
        elif level == "high" and img.mode in ("RGB", "RGBA"):
            # PNG 无损压缩空间有限，极限档量化到 256 色（体积通常减半以上）
            img = img.quantize(256, method=Image.Quantize.FASTOCTREE if img.mode == "RGBA"
                               else Image.Quantize.MEDIANCUT)

        out_path = reserve(output_dir / f"{path.stem}_compressed{out_ext}", claimed, input_files)
        img.save(out_path, format=fmt, **save_kwargs)
        return out_path

    return run_batch(input_files, output_dir, one, progress_callback, "已压缩")

