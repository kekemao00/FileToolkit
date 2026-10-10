"""图片批处理：EXIF 方向、不覆盖、单个失败不影响整批"""
from pathlib import Path

from PIL import Image

from core.image.compressor import compress_images
from core.image.converter import convert_image
from core.image.resizer import resize_images
from core.image.watermark import add_text_watermark
from core.models import TaskStatus


def _rotated_jpeg(path: Path) -> Path:
    """像素 40x20（横），EXIF 标记要求顺时针转 90° 显示（竖拍照片）。"""
    img = Image.new("RGB", (40, 20), (200, 30, 30))
    exif = Image.Exif()
    exif[0x0112] = 6
    img.save(path, format="JPEG", exif=exif.tobytes())
    return path


def test_outputs_follow_exif_orientation(tmp_path: Path) -> None:
    src = _rotated_jpeg(tmp_path / "phone.jpg")
    for fn, kwargs in [
        (compress_images, {}),
        (convert_image, {"target_format": "png"}),
        (add_text_watermark, {"text": "水印"}),
    ]:
        res = fn(input_files=[src], output_dir=tmp_path / fn.__name__, **kwargs)
        assert res.status == TaskStatus.SUCCESS, res.error_message
        with Image.open(res.output_files[0]) as out:
            assert out.size == (20, 40), fn.__name__

    res = resize_images(input_files=[src], output_dir=tmp_path / "r", width=10)
    with Image.open(res.output_files[0]) as out:
        assert out.size == (10, 20)


def test_convert_never_overwrites_source_or_previous_output(tmp_path: Path) -> None:
    src = tmp_path / "a.png"
    Image.new("RGB", (8, 8), (0, 0, 255)).save(src)
    before = src.read_bytes()

    # 输出目录 = 源目录，格式相同
    res = convert_image(input_files=[src], output_dir=tmp_path, target_format="png")
    assert res.status == TaskStatus.SUCCESS
    assert res.output_files[0] != src
    assert src.read_bytes() == before

    # a.png 和 a.jpg 转成同一格式不互相覆盖
    jpg = tmp_path / "a.jpg"
    Image.new("RGB", (8, 8)).save(jpg)
    res = convert_image(input_files=[src, jpg], output_dir=tmp_path / "out", target_format="webp")
    assert len({p.name for p in res.output_files}) == 2


def test_one_bad_file_does_not_abort_batch(tmp_path: Path) -> None:
    good = tmp_path / "good.png"
    Image.new("RGB", (8, 8)).save(good)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")

    res = compress_images(input_files=[bad, good], output_dir=tmp_path / "out")
    assert res.status == TaskStatus.SUCCESS
    assert len(res.output_files) == 1
    assert len(res.warnings) == 1 and res.warnings[0].startswith("bad.png")

    res = compress_images(input_files=[bad], output_dir=tmp_path / "out")
    assert res.status == TaskStatus.FAILED
