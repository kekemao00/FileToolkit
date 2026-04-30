"""图片格式转换模块"""
import time
from pathlib import Path

from PIL import Image

from core.models import ProgressCallback, TaskResult, TaskStatus

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

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
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")

        output_dir.mkdir(parents=True, exist_ok=True)
        pil_format = _FORMAT_MAP.get(target_format.lower(), "JPEG")
        ext = target_format.lower()
        if ext == "jpeg":
            ext = "jpg"

        output_files: list[Path] = []
        total = len(input_files)

        for i, path in enumerate(input_files, start=1):
            img = Image.open(path)

            # RGBA → RGB（JPEG/BMP 不支持 alpha）
            if pil_format in ("JPEG", "BMP") and img.mode in ("RGBA", "P", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = bg
            elif img.mode == "P":
                img = img.convert("RGB")

            out_path = output_dir / f"{path.stem}.{ext}"
            save_kwargs: dict = {}
            if pil_format in ("JPEG", "WEBP"):
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True
            if pil_format == "PNG":
                save_kwargs["optimize"] = True

            img.save(out_path, format=pil_format, **save_kwargs)
            output_files.append(out_path)

            if progress_callback:
                progress_callback(i, total, f"已转换：{path.name} ({i}/{total})")

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
