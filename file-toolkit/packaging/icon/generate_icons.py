"""
从 source.png 生成各平台应用图标。

    cd file-toolkit && python packaging/icon/generate_icons.py

source.png 是原始设计稿（四周透明留白不均匀）。脚本先裁掉留白、修正
半透明，再按平台惯例重新留白：
- macOS 按 Apple 图标网格：1024 画布里主体 824（约 80%），带轻微投影
- Windows / Linux 主体占 92%，避免在任务栏、开始菜单里显得比别的应用小

输出（flet build 按文件名自动识别 assets/icon*.png）：
- assets/icon.png         默认图标（Windows、Linux 及其余平台）
- assets/icon_macos.png   macOS 图标
- assets/icons/app.ico    开发模式下 Windows 窗口图标（多尺寸）
- packaging/linux/file-toolkit.png  Linux 发布包里的菜单图标（256px）
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).parent
ASSETS = HERE.parent.parent / "assets"
CANVAS = 1024

TIGHT_RATIO = 0.92               # Windows / Linux 主体占比
MACOS_BODY = 824                 # Apple 图标网格主体尺寸
MACOS_SHADOW = (0, 12, 14, 0.28)  # dx, dy, 模糊半径, 不透明度


def load_artwork() -> Image.Image:
    """裁掉透明留白，清掉零星噪点，主体改为完全不透明，拉成正方形。"""
    rgba = np.array(Image.open(HERE / "source.png").convert("RGBA"))
    alpha = rgba[:, :, 3].astype(np.float32)
    # 设计稿主体 alpha 只有 254，留白里散落着 alpha<16 的噪点
    alpha = np.clip(alpha * 255 / 254, 0, 255)
    alpha[alpha < 16] = 0
    rgba[:, :, 3] = alpha.astype(np.uint8)

    ys, xs = np.where(alpha > 0)
    art = Image.fromarray(rgba).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    # 原图主体宽高只差约 0.6%，直接缩放成正方形，避免边缘出现细缝
    side = max(art.size)
    art = art.resize((side, side), Image.LANCZOS)
    # 设计稿是纯色块但带细微色彩噪点，量化掉后 PNG 体积从约 500KB 降到几十 KB，肉眼无差别
    return art.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).convert("RGBA")


def place(art: Image.Image, body: int, shadow=None) -> Image.Image:
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    body_img = art.resize((body, body), Image.LANCZOS)
    offset = (CANVAS - body) // 2
    if shadow:
        dx, dy, blur, opacity = shadow
        mask = body_img.getchannel("A").point(lambda v: int(v * opacity))
        shade = Image.new("RGBA", body_img.size, (0, 0, 0, 0))
        shade.putalpha(mask)
        layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        layer.paste(shade, (offset + dx, offset + dy))
        canvas = Image.alpha_composite(canvas, layer.filter(ImageFilter.GaussianBlur(blur)))
    canvas.alpha_composite(body_img, (offset, offset))
    return canvas


def main() -> None:
    art = load_artwork()
    tight = place(art, round(CANVAS * TIGHT_RATIO))
    tight.save(ASSETS / "icon.png", optimize=True)
    place(art, MACOS_BODY, MACOS_SHADOW).save(ASSETS / "icon_macos.png", optimize=True)
    (ASSETS / "icons").mkdir(exist_ok=True)
    tight.save(ASSETS / "icons" / "app.ico",
               sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    tight.resize((256, 256), Image.LANCZOS).save(
        HERE.parent / "linux" / "file-toolkit.png", optimize=True)


if __name__ == "__main__":
    main()
