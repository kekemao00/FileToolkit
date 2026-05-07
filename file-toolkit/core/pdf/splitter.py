"""PDF 分割模块"""
import time
from pathlib import Path
from typing import Literal

import pypdf

from core.models import ProgressCallback, TaskResult, TaskStatus


def split_pdf(
    input_file: Path,
    output_dir: Path,
    mode: Literal["pages", "range", "each"] = "pages",
    pages_per_file: int = 5,
    page_ranges: list[str] | None = None,
    filename_template: str = "{stem}_第{n}部分",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    """
    PDF 分割。

    Args:
        input_file: 源 PDF 路径
        output_dir: 输出目录（不存在则自动创建）
        mode: pages（按固定页数）/ range（按页码范围）/ each（每页单独）
        pages_per_file: mode=pages 时每份页数
        page_ranges: mode=range 时页面范围列表，如 ["1-5", "8"]（1-based）
        filename_template: 支持 {stem} {n} {start} {end} 占位符
        progress_callback: 可选进度回调 (current, total, desc)
    """
    t0 = time.time()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        reader = pypdf.PdfReader(str(input_file))
        total_pages = len(reader.pages)
        stem = input_file.stem

        # 根据 mode 构建「切片列表」：[(start_0based, end_exclusive, n, start_1based, end_1based)]
        slices: list[tuple[int, int, int, int, int]] = []

        if mode == "pages":
            n = 1
            for start in range(0, total_pages, pages_per_file):
                end = min(start + pages_per_file, total_pages)
                slices.append((start, end, n, start + 1, end))
                n += 1

        elif mode == "range":
            if not page_ranges:
                return TaskResult(
                    status=TaskStatus.FAILED,
                    error_message="mode=range 时须提供 page_ranges",
                )
            for n, rng in enumerate(page_ranges, start=1):
                range_text = rng.strip()
                if "-" not in range_text:
                    # 单页码，如 "8" 表示只取第 8 页
                    try:
                        page_num = int(range_text)
                    except ValueError:
                        return TaskResult(
                            status=TaskStatus.FAILED,
                            error_message=(
                                f"范围格式错误：{rng}，应为 '起始-结束'（如 1-5）"
                                "或单页码（如 8）"
                            ),
                        )
                    s, e = page_num - 1, page_num
                else:
                    parts = range_text.split("-")
                    if len(parts) != 2:
                        return TaskResult(
                            status=TaskStatus.FAILED,
                            error_message=(
                                f"范围格式错误：{rng}，应为 '起始-结束'（如 1-5）"
                                "或单页码（如 8）"
                            ),
                        )
                    try:
                        s, e = int(parts[0]) - 1, int(parts[1])
                    except ValueError:
                        return TaskResult(
                            status=TaskStatus.FAILED,
                            error_message=(
                                f"范围格式错误：{rng}，应为 '起始-结束'（如 1-5）"
                                "或单页码（如 8）"
                            ),
                        )
                if s < 0 or e > total_pages or s >= e:
                    return TaskResult(
                        status=TaskStatus.FAILED,
                        error_message=f"页码范围越界：{rng}（文档共 {total_pages} 页）",
                    )
                slices.append((s, e, n, s + 1, e))

        elif mode == "each":
            for i in range(total_pages):
                slices.append((i, i + 1, i + 1, i + 1, i + 1))

        output_files: list[Path] = []
        total = len(slices)

        for start, end, n, s1, e1 in slices:
            name = filename_template.format(stem=stem, n=n, start=s1, end=e1)
            out_path = output_dir / f"{name}.pdf"

            writer = pypdf.PdfWriter()
            for page_idx in range(start, end):
                writer.add_page(reader.pages[page_idx])
            with open(out_path, "wb") as f:
                writer.write(f)

            output_files.append(out_path)
            if progress_callback:
                progress_callback(n, total, f"已生成第 {n}/{total} 份")

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
