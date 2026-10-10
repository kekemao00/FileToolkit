"""智能入口：一句话 → 功能步骤，以及带着附件跳到工作台。"""
from pathlib import Path

import pytest

from services import history_service, settings_service
from ui.handoff import pop_pending_files, set_pending_files
from ui.intent import plan_steps
from ui.pages.ai_task_page import AiTaskPage
from ui.router import _resolve_page


def _titles(text: str, files: list[Path] | None = None) -> list[str]:
    return [f.title for f in plan_steps(text, files)]


@pytest.mark.parametrize(("text", "expected"), [
    ("图片转PDF并加水印", ["图片转 PDF", "PDF 加密 / 水印"]),
    ("压缩视频并提取音频", ["视频压缩", "提取音频"]),
    ("批量重命名图片", ["图片批量重命名"]),
    ("把 Word 转成 PDF", ["Office 转 PDF"]),
    ("pdf转word", ["PDF 转 Word / Excel / PPT"]),
    ("PDF 转图片", ["PDF 转图片"]),
    ("合并PDF，然后压缩", ["PDF 合并", "PDF 压缩"]),
    ("把照片打包成zip", ["ZIP 压缩"]),
    ("识别图片里的文字", ["OCR 文字识别"]),
    ("今天天气怎么样", []),
])
def test_plan_steps(text: str, expected: list[str]) -> None:
    assert _titles(text) == expected


def test_attachments_pick_the_group() -> None:
    assert _titles("压缩", [Path("a.jpg"), Path("b.png")]) == ["图片压缩"]
    assert _titles("压缩", [Path("clip.mp4")]) == ["视频压缩"]
    assert _titles("加水印", [Path("a.pdf")]) == ["PDF 加密 / 水印"]


class _FakePage:
    width = 1280
    on_resize = None

    def __init__(self) -> None:
        self.routes: list[str] = []

    def run_task(self, *args, **kwargs):
        pass

    def go(self, route: str) -> None:
        self.routes.append(route)

    def update(self) -> None:
        pass


def test_open_step_hands_files_to_workbench(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)
    page = _FakePage()
    ai = AiTaskPage(page)
    images = [tmp_path / "a.jpg", tmp_path / "b.png"]
    ai._attached_files = list(images)
    ai._input_field.value = "图片转PDF并加水印"
    ai._on_submit(None)
    assert ai._plan.visible

    steps = plan_steps("图片转PDF并加水印")
    ai._open_step(steps[0], carry_files=True)
    assert page.routes == ["/image?func=to_pdf"]
    view = _resolve_page(page.routes[0], page)
    assert view.func.key == "to_pdf"
    assert view._files == images
    assert pop_pending_files() == []


def test_later_steps_do_not_carry_files() -> None:
    set_pending_files([Path("x.jpg")])
    page = _FakePage()
    ai = AiTaskPage(page)
    ai._attached_files = [Path("x.jpg")]
    ai._open_step(plan_steps("PDF 压缩")[0], carry_files=False)
    assert pop_pending_files() == []


def test_ocr_page_takes_handed_over_image(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)
    set_pending_files([tmp_path / "notes.txt", tmp_path / "scan.png"])
    view = _resolve_page("/ocr", _FakePage())
    assert view._input_file == tmp_path / "scan.png"


def test_history_search_matches_chinese_labels() -> None:
    from ui.pages.history_page import HistoryPage
    task = {"module": "image", "action": "compress", "input_desc": "a.jpg 等 3 个文件"}
    text = HistoryPage._search_text(task)
    assert "压缩" in text and "图片" in text and "a.jpg" in text
