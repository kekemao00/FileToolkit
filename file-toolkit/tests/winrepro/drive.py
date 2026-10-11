"""在 Windows 上启动 app.py，用真实鼠标事件点击并截图（临时，不合入）。"""
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageGrab

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

img = OUT / "big.png"
Image.new("RGB", (1536, 1024), (40, 120, 200)).save(img)

proc = subprocess.Popen([sys.executable, str(HERE / "app.py"), str(img)])
hwnd = 0
for _ in range(180):
    hwnd = user32.FindWindowW(None, "FTKREPRO")
    if hwnd and (HERE / "events.log").exists():
        break
    time.sleep(1)
print("hwnd", hwnd, flush=True)
time.sleep(5)
user32.SetForegroundWindow(hwnd)
pt = wintypes.POINT(0, 0)
user32.ClientToScreen(hwnd, ctypes.byref(pt))
rc = wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(rc))
W, H = rc.right, rc.bottom
print("client origin", pt.x, pt.y, "size", W, H, flush=True)


def move(x, y):
    user32.SetCursorPos(pt.x + int(x), pt.y + int(y))


def click(x, y, button="left"):
    move(x, y)
    time.sleep(0.15)
    down, up = (0x0002, 0x0004) if button == "left" else (0x0008, 0x0010)
    user32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(up, 0, 0, 0, 0)


def wiggle(x, y):
    for i in range(6):
        move(x + i * 7, y + i * 3)
        time.sleep(0.05)


def shot(name):
    ImageGrab.grab().save(OUT / f"{name}.png")


def key(vk):
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 2, 0)


shot("00-start")
click(43, 68)            # url
time.sleep(2)
click(50, 26)            # open viewer
time.sleep(3)
wiggle(W / 2 - 60, H / 2)
shot("01-viewer")
wiggle(W / 2 + 60, H - 80)
click(W / 2 + 118, H - 51)   # reveal
time.sleep(1)
wiggle(W - 120, H / 2)
click(W - 47, H / 2)         # next
time.sleep(1)
shot("02-after-clicks")
wiggle(W - 120, 80)
click(W - 46, 46)            # close button
time.sleep(1.5)
shot("03-after-close")
click(50, 26)                # reopen
time.sleep(3)
key(0x1B)                    # Esc
time.sleep(1.5)
shot("04-after-esc")
click(50, 26)                # reopen
time.sleep(3)
click(60, H - 40)            # blank area closes
time.sleep(1.5)
shot("05-after-blank")
proc.kill()
print((HERE / "events.log").read_text(encoding="utf-8"), flush=True)
