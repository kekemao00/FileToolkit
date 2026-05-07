"""图片尺寸调整模块"""
import time
from pathlib import Path

from PIL import Image

from core.models import ProgressCallback, TaskResult, TaskStatus


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
    t0 = time.time()
    try:
        if not input_files:
            return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")
        if not width and not height:
            return TaskResult(status=TaskStatus.FAILED, error_message="宽度或高度至少填写一项")
        # 宽高必须为正数
        if width is not None and width <= 0:
            return TaskResult(status=TaskStatus.FAILED, error_message="宽度必须为正整数")
        if height is not None and height <= 0:
            return TaskResult(status=TaskStatus.FAILED, error_message="高度必须为正整数")

        output_dir.mkdir(parents=True, exist_ok=True)
        output_files: list[Path] = []
        total = len(input_files)

        for i, path in enumerate(input_files, start=1):
            with Image.open(path) as img:
                ow, oh = img.size

                if keep_ratio:
                    # 等比缩放：同时提供宽高时按目标框适配（取较小缩放比，避免超框）
                    if width and height:
                        ratio = min(width / ow, height / oh)
                        new_w, new_h = max(1, int(ow * ratio)), max(1, int(oh * ratio))
                    elif width:
                        ratio = width / ow
                        new_w, new_h = width, max(1, int(oh * ratio))
                    else:
                        ratio = height / oh
                        new_w, new_h = max(1, int(ow * ratio)), height
                else:
                    new_w = width or ow
                    new_h = height or oh

                resized = img.resize((new_w, new_h), Image.LANCZOS)

                ext = path.suffix.lower()
                out_path = output_dir / f"{path.stem}_resized{ext}"

                save_kwargs: dict = {}
                if ext in (".jpg", ".jpeg"):
                    if resized.mode in ("RGBA", "P", "LA"):
                        bg = Image.new("RGB", resized.size, (255, 255, 255))
                        if resized.mode == "P":
                            resized = resized.convert("RGBA")
                        bg.paste(resized, mask=resized.split()[-1] if "A" in resized.mode else None)
                        resized = bg
                    save_kwargs["quality"] = 95
                    resized.save(out_path, format="JPEG", **save_kwargs)
                elif ext == ".webp":
                    save_kwargs["quality"] = 95
                    resized.save(out_path, format="WEBP", **save_kwargs)
                elif ext == ".png":
                    resized.save(out_path, format="PNG", optimize=True)
                else:
                    resized.save(out_path)

                output_files.append(out_path)

            if progress_callback:
                progress_callback(i, total, f"已调整：{path.name} ({i}/{total})")

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
