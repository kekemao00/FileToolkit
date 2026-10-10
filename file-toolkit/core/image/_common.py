"""图片模块共用：打开（含 HEIC、EXIF 方向）与去透明。"""
from pathlib import Path

from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - 依赖缺失时 HEIC 不可用，其余格式照常
    pass


def open_image(path: Path) -> Image.Image:
    """读入内存并按 EXIF 方向摆正，随即关闭文件句柄。

    手机竖拍的照片像素是横的，靠 EXIF Orientation 标记旋转；
    重新保存时标记会丢，不先摆正就会得到横倒的图。
    """
    with Image.open(path) as im:
        im.load()
        fixed = ImageOps.exif_transpose(im)
        return fixed if fixed is not im else im.copy()


def to_rgb(img: Image.Image, background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """JPEG / BMP 不支持透明：带透明通道的图铺到白底上，其余模式直接转 RGB。"""
    if img.mode == "P" and "transparency" in img.info:
        img = img.convert("RGBA")
    if img.mode in ("RGBA", "LA", "PA"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", img.size, background)
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return img if img.mode == "RGB" else img.convert("RGB")
