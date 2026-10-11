"""启动真实应用并直接进入提示词出图页（临时，不合入）。"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("FLET_APP_STORAGE_DATA", tempfile.mkdtemp())
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import flet as ft  # noqa: E402

import main as app  # noqa: E402
from services import prompt_library_service as lib  # noqa: E402

LOG = Path(__file__).with_name("events.log")


def log(msg):
    import time
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.time():.2f} APP {msg}\n")


def wrapped(page: ft.Page):
    app._init_services()
    lib.add_history(Path(sys.argv[1]), "a cat", "测试模板", "1536x1024")
    app.main(page)
    page.window.left, page.window.top = 0, 0
    page.window.min_width, page.window.min_height = 600, 500
    page.window.width, page.window.height = int(os.environ.get("REPRO_W", 1280)), int(os.environ.get("REPRO_H", 800))
    from ui.pages.prompt_image_page import PromptImagePage
    orig_mount = PromptImagePage.did_mount

    def did_mount(self):
        orig_mount(self)
        self._show_history_item(lib.list_history()[0])
    PromptImagePage.did_mount = did_mount
    page.title = "FTKREPRO"
    page.go("/prompt-image")
    page.update()
    from ui.components import image_viewer as iv
    orig_close = iv.ImageViewer.close

    async def close(self):
        log("CLOSE")
        await orig_close(self)
    iv.ImageViewer.close = close
    orig_open = iv.ImageViewer.open

    def opn(self):
        log("OPEN")
        orig_open(self)
    iv.ImageViewer.open = opn
    from ui.pages import prompt_image_page as pip
    pip.open_folder = lambda p: log(f"REVEAL {p}")
    for name in ("_zoom_by", "_fit", "_actual", "_copy", "_go"):
        orig = getattr(iv.ImageViewer, name)

        def make(orig=orig, name=name):
            async def f(self, *a):
                log(f"VIEWER {name} {a}")
                return await orig(self, *a)
            return f
        setattr(iv.ImageViewer, name, make())
    log("READY")


ft.run(wrapped, assets_dir="assets")
