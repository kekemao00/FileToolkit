"""图片格式转换模块单元测试"""
from pathlib import Path

from PIL import Image

from core.image.converter import convert_image
from core.models import TaskStatus


def _make_png(path: Path, size: tuple[int, int] = (16, 16)) -> Path:
    Image.new("RGBA", size, (255, 0, 0, 255)).save(path, format="PNG")
    return path


class TestConvertImage:
    def test_convert_png_to_jpg(self, tmp_path: Path) -> None:
        src = _make_png(tmp_path / "a.png")
        out_dir = tmp_path / "out"

        result = convert_image(
            input_files=[src],
            output_dir=out_dir,
            target_format="jpg",
        )

        assert result.status == TaskStatus.SUCCESS
        assert len(result.output_files) == 1
        out = result.output_files[0]
        assert out.exists()
        assert out.suffix == ".jpg"
        with Image.open(out) as img:
            assert img.format == "JPEG"

    def test_batch_convert_to_webp(self, tmp_path: Path) -> None:
        srcs = [_make_png(tmp_path / f"{n}.png") for n in ("a", "b", "c")]
        out_dir = tmp_path / "out"
        seen: list[int] = []

        result = convert_image(
            input_files=srcs,
            output_dir=out_dir,
            target_format="webp",
            progress_callback=lambda cur, total, _desc: seen.append(cur),
        )

        assert result.status == TaskStatus.SUCCESS
        assert len(result.output_files) == 3
        assert all(p.exists() and p.suffix == ".webp" for p in result.output_files)
        assert seen == [1, 2, 3]

    def test_empty_input_fails(self, tmp_path: Path) -> None:
        result = convert_image(
            input_files=[],
            output_dir=tmp_path / "out",
            target_format="png",
        )
        assert result.status == TaskStatus.FAILED
