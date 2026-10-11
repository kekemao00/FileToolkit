"""Windows 上驱动打包好的发布版（临时，不合入）。用法：drive_pkg.py <FileToolkit 目录>"""
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
pkg = Path(sys.argv[1])
exe = next(p for p in pkg.rglob("*.exe") if "ffmpeg" not in p.name.lower())
print("exe", exe, flush=True)


def find_hwnd():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        if user32.IsWindowVisible(h) and ("文件全能王" in buf.value or "File Toolkit" in buf.value):
            found.append(h)
        return True
    user32.EnumWindows(cb, 0)
    return found[0] if found else 0


def launch():
    p = subprocess.Popen([str(exe)], cwd=str(exe.parent))
    for _ in range(120):
        h = find_hwnd()
        if h:
            return p, h
        time.sleep(1)
    raise SystemExit("window not found")


def find_db():
    for base in (os.environ["APPDATA"], os.environ["LOCALAPPDATA"], os.environ["USERPROFILE"]):
        for p in Path(base).rglob("file_toolkit.db"):
            return p
    return None


p, h = launch()
time.sleep(12)
db = find_db()
print("db", db, flush=True)
p.kill()
subprocess.run(["taskkill", "/F", "/IM", exe.name], capture_output=True)
time.sleep(2)

from services import settings_service  # noqa: E402
from services import prompt_library_service as lib  # noqa: E402

settings_service.init_settings(db)
img = OUT / "noise.png"
Image.frombytes("RGB", (1536, 1024), os.urandom(1536 * 1024 * 3)).save(img)
lib.add_history(img, "a cat", "测试模板", "1536x1024")
print("history", len(lib.list_history()), flush=True)

p, hwnd = launch()
time.sleep(10)
user32.MoveWindow(hwnd, 0, 0, 1024, 740, True)
time.sleep(2)
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
    small = im.convert("RGB")
    small.thumbnail((560, 560))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=45)
    b = base64.b64encode(buf.getvalue()).decode()
    print(f"IMG {name} {len(b)}", flush=True)
    for i in range(0, len(b), 4000):
        print(f"B64 {name} {b[i:i + 4000]}", flush=True)


def move(x, y):
    user32.SetCursorPos(pt.x + int(x), pt.y + int(y))


def click(x, y):
    print(f"click {int(x)},{int(y)}", flush=True)
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
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 2, 0)


dump("20-home")
click(117, 173)                 # 侧栏「提示词出图」
time.sleep(3)
click(W * 0.812, H * 0.893)     # 最近作品缩略图
time.sleep(2)
dump("21-page")
wiggle(W * 0.87 - 40, H * 0.333)
click(W * 0.87, H * 0.333)      # 预览图
time.sleep(3)
wiggle(W / 2, H / 2)
dump("22-viewer")
wiggle(W / 2 - 40, H - 90)
click(W / 2 - 118, H - 51)      # 第一个按钮（缩小/放大）
time.sleep(1)
wiggle(W - 120, 80)
click(W - 46, 46)               # 关闭
time.sleep(2)
dump("23-after-close")
key(0x1B)
time.sleep(1)
dump("24-after-esc")
p.kill()
