"""Windows 点击问题复现用的最小应用（临时，不合入）。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import flet as ft  # noqa: E402

from ui.components.image_viewer import ImageViewer, ViewerItem  # noqa: E402

LOG = Path(__file__).with_name("events.log")


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.monotonic():.2f} {msg}\n")


def main(page: ft.Page):
    page.title = "FTKREPRO"
    page.window.left, page.window.top = 0, 0
    page.window.width, page.window.height = 1000, 700
    img = Path(sys.argv[1])
    hits = {"pointer": 0, "content": 0}

    def opn(_):
        log("OPEN")
        v = ImageViewer(page, [ViewerItem(path=img, title="a"), ViewerItem(path=img, title="b")], 0,
                        on_save=lambda it: log("SAVE"), on_reveal=lambda it: log("REVEAL"))
        orig_close, orig_ptr, orig_hover = v.close, v._on_pointer, v._on_content_hover

        async def close():
            log(f"CLOSE pointer={hits['pointer']} content={hits['content']}")
            await orig_close()

        def ptr(e=None):
            hits["pointer"] += 1
            orig_ptr(e)

        def hov(e):
            hits["content"] += 1
            orig_hover(e)

        v.close, v._on_pointer = close, ptr
        v.host.on_hover = ptr
        v._viewer.content.on_hover = hov
        orig_go = v._go

        async def go(step):
            log(f"GO {step}")
            await orig_go(step)
        v._go = go
        v.open()

    def url(_):
        log("URL click")
        try:
            page.run_task(page.launch_url, "https://example.com")
            log("URL run_task ok")
        except Exception as e:
            log(f"URL run_task error {e!r}")

    page.add(ft.Button("open", on_click=opn), ft.Button("url", on_click=url))
    log("READY")


ft.run(main)
