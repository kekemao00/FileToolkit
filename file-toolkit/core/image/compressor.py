"""图片批量压缩模块"""
import time
from pathlib import Path

from PIL import Image

from core.models import ProgressCallback, TaskResult, TaskStatus

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
    批量图片压缩。

    Args:
        input_files: 输入图片列表
        output_dir: 输出目录
        level: 压缩级别 low(轻度)/medium(标准)/high(极限)
        progress_callback: 可选进度回调
    """
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")

        output_dir.mkdir(parents=True, exist_ok=True)
        quality = _LEVEL_QUALITY.get(level, 65)

        output_files: list[Path] = []
        total = len(input_files)

        for i, path in enumerate(input_files, start=1):
            img = Image.open(path)
            ext = path.suffix.lower()

            # 根据原格式选择输出格式和参数
            if ext in (".jpg", ".jpeg"):
                out_format = "JPEG"
                out_ext = ".jpg"
            elif ext == ".webp":
                out_format = "WEBP"
                out_ext = ".webp"
            elif ext == ".png":
                out_format = "PNG"
                out_ext = ".png"
            else:
                # 其他格式转为 JPEG 压缩
                out_format = "JPEG"
                out_ext = ".jpg"

            # RGBA/P → RGB（JPEG 不支持 alpha）
            if out_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = bg
            elif out_format == "JPEG" and img.mode != "RGB":
                img = img.convert("RGB")

            out_path = output_dir / f"{path.stem}_compressed{out_ext}"
            save_kwargs: dict = {"optimize": True}
            if out_format in ("JPEG", "WEBP"):
                save_kwargs["quality"] = quality

            img.save(out_path, format=out_format, **save_kwargs)
            output_files.append(out_path)

            if progress_callback:
                progress_callback(i, total, f"已压缩：{path.name} ({i}/{total})")

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
