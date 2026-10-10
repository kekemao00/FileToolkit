"""图片尺寸调整模块"""
from pathlib import Path

from PIL import Image

from core.batch import run_batch
from core.image._common import open_image, to_rgb
from core.models import ProgressCallback, TaskResult, TaskStatus
from core.paths import reserve


def resize_images(
    input_files: list[Path],
    output_dir: Path,
    width: int | None = None,
    height: int | None = None,
    keep_ratio: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    批量图片尺寸调整。

    Args:
        input_files: 输入图片列表
        output_dir: 输出目录
        width: 目标宽度（px），None 表示按高度等比
        height: 目标高度（px），None 表示按宽度等比
        keep_ratio: 是否保持宽高比；True 时以宽度/高度任一边为基准等比缩放
        progress_callback: 可选进度回调
    """
    if not width and not height:
        return TaskResult(status=TaskStatus.FAILED, error_message="宽度或高度至少填写一项")
    if width is not None and width <= 0:
        return TaskResult(status=TaskStatus.FAILED, error_message="宽度必须为正整数")
    if height is not None and height <= 0:
        return TaskResult(status=TaskStatus.FAILED, error_message="高度必须为正整数")
    claimed: set[Path] = set()

    def one(path: Path) -> Path:
        img = open_image(path)
        ow, oh = img.size
        if keep_ratio:
            # 等比缩放：同时提供宽高时按目标框适配（取较小缩放比，避免超框）
            if width and height:
                ratio = min(width / ow, height / oh)
                new_w, new_h = max(1, round(ow * ratio)), max(1, round(oh * ratio))
            elif width:
                new_w, new_h = width, max(1, round(oh * width / ow))
            else:
                assert height
                new_w, new_h = max(1, round(ow * height / oh)), height
        else:
            new_w, new_h = width or ow, height or oh

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        ext = path.suffix.lower()
        out_path = reserve(output_dir / f"{path.stem}_resized{ext}", claimed, input_files)
        if ext in (".jpg", ".jpeg"):
            to_rgb(resized).save(out_path, format="JPEG", quality=95)
        elif ext == ".webp":
            resized.save(out_path, format="WEBP", quality=95)
        elif ext == ".png":
            resized.save(out_path, format="PNG", optimize=True)
        elif ext == ".heic":
            # 不写 HEIC，换成 JPG
            out_path = reserve(out_path.with_suffix(".jpg"), claimed, input_files)
            to_rgb(resized).save(out_path, format="JPEG", quality=95)
        else:
            resized.save(out_path)
        return out_path

    return run_batch(input_files, output_dir, one, progress_callback, "已调整")
