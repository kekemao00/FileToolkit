"""图片格式转换模块"""
from pathlib import Path

from core.batch import run_batch
from core.image._common import open_image, to_rgb
from core.models import ProgressCallback, TaskResult
from core.paths import reserve

_FORMAT_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
    "tif": "TIFF",
}


def convert_image(
    input_files: list[Path],
    output_dir: Path,
    target_format: str,
    quality: int = 85,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量图片格式转换。

    Args:
        input_files: 输入图片列表
        output_dir: 输出目录
        target_format: 目标格式（jpg/png/webp/bmp/tiff）
        quality: JPEG/WebP 质量 1-100
        progress_callback: 可选进度回调
    """
    pil_format = _FORMAT_MAP.get(target_format.lower(), "JPEG")
    ext = target_format.lower()
    if ext == "jpeg":
        ext = "jpg"
    claimed: set[Path] = set()

    def one(path: Path) -> Path:
        img = open_image(path)
        if pil_format in ("JPEG", "BMP"):
            img = to_rgb(img)
        elif img.mode == "P":
            img = img.convert("RGBA" if "transparency" in img.info else "RGB")

        save_kwargs: dict = {}
        if pil_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        if pil_format == "PNG":
            save_kwargs["optimize"] = True

        out_path = reserve(output_dir / f"{path.stem}.{ext}", claimed, input_files)
        img.save(out_path, format=pil_format, **save_kwargs)
        return out_path

    return run_batch(input_files, output_dir, one, progress_callback, "已转换")
