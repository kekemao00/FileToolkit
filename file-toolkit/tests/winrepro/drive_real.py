"""Windows 上驱动真实应用的大图预览（临时，不合入）。"""
import base64
import ctypes
import io
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageGrab

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
LOG = HERE / "events.log"
user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
print("screen", user32.GetSystemMetrics(0), user32.GetSystemMetrics(1), flush=True)

img = OUT / "noise.png"
Image.frombytes("RGB", (1536, 1024), os.urandom(1536 * 1024 * 3)).save(img)

env = dict(os.environ, REPRO_W="1000", REPRO_H="740")
proc = subprocess.Popen([sys.executable, str(HERE / "realapp.py"), str(img)], env=env)
hwnd = 0
for _ in range(180):
    hwnd = user32.FindWindowW(None, "FTKREPRO")
    if hwnd and LOG.exists():
        break
    time.sleep(1)
time.sleep(6)
user32.SetForegroundWindow(hwnd)
pt = wintypes.POINT(0, 0)
user32.ClientToScreen(hwnd, ctypes.byref(pt))
rc = wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(rc))
W, H = rc.right, rc.bottom
print("client origin", pt.x, pt.y, "size", W, H, flush=True)


def grab():
    return ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + W, pt.y + H))


def dump(name):
    im = grab()
    im.save(OUT / f"{name}.png")
    small = im.convert("RGB")
    small.thumbnail((560, 560))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=45)
    b = base64.b64encode(buf.getvalue()).decode()
    print(f"IMG {name} {len(b)}", flush=True)
    for i in range(0, len(b), 4000):
        print(f"B64 {name} {b[i:i + 4000]}", flush=True)


def noisy_box():
    """找出噪点图（预览图）在客户区的位置。"""
    im = grab().convert("L").resize((W // 4, H // 4))
    px = im.load()
    xs, ys = [], []
    for y in range(1, im.height - 1):
        for x in range(1, im.width - 1):
            if abs(px[x, y] - px[x - 1, y]) > 25 and abs(px[x, y] - px[x, y - 1]) > 25:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    xs.sort()
    ys.sort()
    n = len(xs)
    return xs[n // 10] * 4, ys[n // 10] * 4, xs[n * 9 // 10] * 4, ys[n * 9 // 10] * 4


def mark(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"DRIVER {msg}\n")


def move(x, y):
    user32.SetCursorPos(pt.x + int(x), pt.y + int(y))


def click(x, y):
    mark(f"click {int(x)},{int(y)}")
    move(x, y)
    time.sleep(0.2)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def wiggle(x, y):
    for i in range(6):
        move(x + i * 7, y + i * 3)
        time.sleep(0.05)


def key(vk):
    mark(f"key {vk}")
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 2, 0)


dump("10-page")
box = noisy_box()
print("preview box", box, flush=True)
if box:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    wiggle(cx - 40, cy)
    click(cx, cy)
    time.sleep(3)
    wiggle(W / 2, H / 2)
    dump("11-viewer")
    wiggle(W / 2 + 40, H - 90)
    click(W / 2 + 118, H - 51)   # 打开所在文件夹
    time.sleep(1)
    wiggle(W / 2 - 40, H - 90)
    click(W / 2 - 118, H - 51)   # 缩小 or 第一个按钮
    time.sleep(1)
    wiggle(W - 120, 80)
    click(W - 46, 46)            # 关闭按钮
    time.sleep(2)
    dump("12-after-close")
    if box:
        wiggle(cx - 40, cy)
        click(cx, cy)
        time.sleep(3)
        key(0x1B)
        time.sleep(2)
        dump("13-after-esc")
proc.kill()
print(LOG.read_text(encoding="utf-8"), flush=True)
