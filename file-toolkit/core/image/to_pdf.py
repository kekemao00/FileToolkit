"""图片合成 PDF（每张图一页，按列表顺序）"""
import time
from pathlib import Path

from PIL import Image

from core.image._common import open_image, to_rgb
from core.models import ProgressCallback, TaskResult, TaskStatus
from core.task_control import TaskCancelled, check_cancelled

_A4_PX = (1240, 1754)  # A4 @150dpi
_MARGIN = 60


def _on_a4(img: Image.Image) -> Image.Image:
    """等比缩放后居中放到 A4 白纸上；横图用横向 A4。"""
    w, h = _A4_PX if img.height >= img.width else _A4_PX[::-1]
    box = (w - 2 * _MARGIN, h - 2 * _MARGIN)
    scale = min(box[0] / img.width, box[1] / img.height, 1.0)
    if scale < 1.0:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.Resampling.LANCZOS)
    page = Image.new("RGB", (w, h), (255, 255, 255))
    page.paste(img, ((w - img.width) // 2, (h - img.height) // 2))
    return page


def images_to_pdf(
    input_files: list[Path],
    output_file: Path,
    page_size: str = "fit",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    多张图片按顺序合成一个 PDF。

    Args:
        input_files: 图片列表（顺序即页序）
        output_file: 输出 PDF 路径
        page_size: fit（页面与图片同尺寸）/ a4（放到 A4 纸上，留白边）
        progress_callback: 可选进度回调
    """
    t0 = time.time()
    if not input_files:
        return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")
    pages: list[Image.Image] = []
    warnings: list[str] = []
    try:
        total = len(input_files)
        for i, path in enumerate(input_files, start=1):
            check_cancelled()
            try:
                img = to_rgb(open_image(path))
                pages.append(_on_a4(img) if page_size == "a4" else img)
            except Exception as exc:
                warnings.append(f"{path.name}：{exc}")
            if progress_callback:
                progress_callback(i, total, f"已添加：{path.name} ({i}/{total})")
        if not pages:
            return TaskResult(status=TaskStatus.FAILED, error_message="没有可用的图片：\n" + "\n".join(warnings),
                              duration_seconds=time.time() - t0)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        pages[0].save(output_file, format="PDF", save_all=True, append_images=pages[1:],
                      resolution=150.0)
        return TaskResult(status=TaskStatus.SUCCESS, output_files=[output_file],
                          output_dir=output_file.parent, warnings=warnings,
                          duration_seconds=time.time() - t0)
    except TaskCancelled:
        return TaskResult(status=TaskStatus.CANCELLED, error_message="已取消",
                          duration_seconds=time.time() - t0)
    except Exception as exc:
        return TaskResult(status=TaskStatus.FAILED, error_message=str(exc),
                          duration_seconds=time.time() - t0)
