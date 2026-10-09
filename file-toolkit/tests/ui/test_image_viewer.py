"""全窗口看图器：尺寸换算、平移边界、看图列表顺序。"""
from pathlib import Path

from PIL import Image

from services import history_service, settings_service
from services import prompt_library_service as lib
from ui.components import image_viewer as iv
from ui.pages.prompt_image_page import PromptImagePage


class _FakePage:
    web = False
    width = 1280
    height = 800
    on_keyboard_event = None

    def __init__(self):
        self.overlay = []

    def run_task(self, *args, **kwargs):
        pass

    def update(self):
        pass


def _png(path: Path, size=(1024, 1536)) -> Path:
    Image.new("RGB", size, "#336699").save(path)
    return path


def test_fit_ratio_and_actual_scale(tmp_path: Path):
    assert iv.fit_ratio((1024, 1536), (1248, 768)) == 0.5
    assert iv.fit_ratio((200, 100), (1248, 768)) == 1.0      # 小图不放大
    viewer = iv.ImageViewer(_FakePage(), [iv.ViewerItem(path=_png(tmp_path / "a.png"))])
    assert viewer._actual_scale() == 2.0                     # 1:1 需要放大 2 倍
    assert viewer._max_scale() == 8.0


def test_pan_is_clamped_to_content(tmp_path: Path):
    viewer = iv.ImageViewer(_FakePage(), [iv.ViewerItem(path=_png(tmp_path / "a.png"))])
    assert viewer._clamp_t(1.0, -50, 30) == (0.0, 0.0)
    assert viewer._clamp_t(2.0, -5000, -100) == (-1280.0, -100.0)


def test_tap_outside_image_closes(tmp_path: Path):
    viewer = iv.ImageViewer(_FakePage(), [iv.ViewerItem(path=_png(tmp_path / "a.png"))])
    x, y, w, h = viewer._image_rect()
    assert (round(w), round(h)) == (512, 768)
    closed = []
    viewer._close_click = lambda _e=None: closed.append(True)

    class _Pos:
        def __init__(self, px, py):
            self.x, self.y = px, py

    class _Ev:
        def __init__(self, px, py):
            self.local_position = _Pos(px, py)

    viewer._on_stage_tap(_Ev(x + w / 2, y + h / 2))
    assert not closed
    viewer._on_stage_tap(_Ev(x - 20, y + 10))
    assert closed


def test_right_click_on_image_copies(tmp_path: Path):
    viewer = iv.ImageViewer(_FakePage(), [iv.ViewerItem(path=_png(tmp_path / "a.png"))])
    copied = []
    viewer._run = lambda fn, *a: copied.append(fn)
    x, y, w, h = viewer._image_rect()

    class _Ev:
        def __init__(self, px, py):
            self.local_position = type("P", (), {"x": px, "y": py})()

    viewer._on_secondary_tap(_Ev(x + 5, y + 5))
    viewer._on_secondary_tap(_Ev(x - 5, y + 5))
    assert copied == [viewer._copy]


def test_meta_shows_pixels_and_size(tmp_path: Path):
    item = iv.ViewerItem(path=_png(tmp_path / "a.png"), title="海报", meta="10-09")
    viewer = iv.ImageViewer(_FakePage(), [item])
    assert viewer._meta.value.startswith("1024 × 1536")
    assert viewer._title.value == "海报"


def test_lightbox_opens_at_current_history_item(tmp_path: Path, monkeypatch):
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)
    paths = [_png(tmp_path / f"{n}.png") for n in "abc"]
    for p in paths:
        lib.add_history(p, "prompt", "模板", "1024x1536")
    opened = []
    monkeypatch.setattr(iv.ImageViewer, "open", lambda self: opened.append(self))
    page = PromptImagePage(_FakePage())
    page._last_path = paths[1]
    page._open_lightbox()
    viewer = opened[0]
    assert [i.path for i in viewer._items] == list(reversed(paths))  # 最近作品新的在前
    assert viewer._item.path == paths[1]
    assert viewer._counter.value == "2 / 3"
