"""工作台集成测试：用界面上的参数构建任务并真实执行 core 函数。"""
import shutil
import subprocess
from pathlib import Path

import pikepdf
import pypdf
import pytest
from PIL import Image

from core.models import TaskStatus
from services import history_service, settings_service
from ui.components.workbench import run_for_each
from ui.features import FEATURES
from ui.pages.image_page import ImagePage
from ui.pages.media_page import MediaPage
from ui.pages.pdf_page import PdfPage
from ui.router import _LEGACY_ROUTES, _parse_route, _resolve_page


class _FakePage:
    width = 1280
    on_resize = None

    def run_task(self, *args, **kwargs):
        pass


@pytest.fixture(autouse=True)
def _settings(tmp_path: Path):
    db = tmp_path / "app.db"
    history_service.init_db(db)
    settings_service.init_settings(db)


def _pdf(path: Path, pages: int = 3) -> Path:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as f:
        writer.write(f)
    return path


def _img(path: Path, size=(64, 48)) -> Path:
    Image.new("RGB", size, (200, 80, 40)).save(path)
    return path


def _run(page, key: str, files: list[Path], out_dir: Path):
    fn, kwargs = page.build_task(key, files, out_dir)
    return fn(**kwargs)


# ── PDF ──────────────────────────────────────────────────────────────────
def test_pdf_merge_keeps_order_and_name(tmp_path: Path) -> None:
    a, b = _pdf(tmp_path / "a.pdf", 1), _pdf(tmp_path / "b.pdf", 2)
    page = PdfPage(_FakePage(), "merge")
    page._merge_name.value = "合并结果"
    result = _run(page, "merge", [b, a], tmp_path / "out")
    assert result.status == TaskStatus.SUCCESS
    assert result.output_files == [tmp_path / "out" / "合并结果.pdf"]
    assert len(pypdf.PdfReader(result.output_files[0]).pages) == 3


def test_pdf_split_by_range_for_every_file(tmp_path: Path) -> None:
    files = [_pdf(tmp_path / "x.pdf", 6), _pdf(tmp_path / "y.pdf", 6)]
    page = PdfPage(_FakePage(), "split")
    page._split_mode.value = "range"
    page._split_ranges.value = "1-2, 3-6"
    result = _run(page, "split", files, tmp_path / "out")
    assert result.status == TaskStatus.SUCCESS
    assert len(result.output_files) == 4


def test_pdf_split_rejects_empty_range(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("ui.pages.pdf_page.show_toast", lambda *a, **k: None)
    page = PdfPage(_FakePage(), "split")
    page._split_mode.value = "range"
    page._split_ranges.value = " "
    assert page.build_task("split", [_pdf(tmp_path / "x.pdf")], tmp_path) is None


def test_pdf_compress_batches_all_files(tmp_path: Path) -> None:
    files = [_pdf(tmp_path / "x.pdf"), _pdf(tmp_path / "y.pdf")]
    result = _run(PdfPage(_FakePage(), "compress"), "compress", files, tmp_path / "out")
    assert result.status == TaskStatus.SUCCESS
    assert sorted(p.name for p in result.output_files) == ["x_compressed.pdf", "y_compressed.pdf"]


def test_pdf_protect_watermarks_then_encrypts(tmp_path: Path) -> None:
    page = PdfPage(_FakePage(), "protect")
    page._wm_text.value = "内部资料"
    page._password.value = "secret"
    result = _run(page, "protect", [_pdf(tmp_path / "doc.pdf")], tmp_path / "out")
    assert result.status == TaskStatus.SUCCESS
    out = result.output_files[0]
    assert out.name == "doc_protected.pdf"
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(out)
    with pikepdf.open(out, password="secret") as pdf:
        assert len(pdf.pages) == 3


def test_pdf_protect_requires_something(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("ui.pages.pdf_page.show_toast", lambda *a, **k: None)
    page = PdfPage(_FakePage(), "protect")
    assert page.build_task("protect", [_pdf(tmp_path / "doc.pdf")], tmp_path) is None


def test_legacy_to_word_deep_link_selects_to_office() -> None:
    assert PdfPage(_FakePage(), "to_word").func.key == "to_office"


# ── 图片 ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("key", ["compress", "convert", "resize", "watermark"])
def test_image_functions_write_outputs(tmp_path: Path, key: str) -> None:
    files = [_img(tmp_path / "a.png"), _img(tmp_path / "b.jpg")]
    page = ImagePage(_FakePage(), key)
    page._width.value = "32"
    page._wm_text.value = "© 2026"
    result = _run(page, key, files, tmp_path / "out")
    assert result.status == TaskStatus.SUCCESS, result.error_message
    assert len(result.output_files) == 2
    assert all(p.exists() for p in result.output_files)
    if key == "resize":
        assert Image.open(result.output_files[0]).size == (32, 24)


def test_image_rename_updates_file_list(tmp_path: Path) -> None:
    files = [_img(tmp_path / "a.png"), _img(tmp_path / "b.png")]
    page = ImagePage(_FakePage(), "rename")
    page._files = list(files)
    page._template.value = "照片_{n:02d}"
    page._refresh_preview(update=False)
    assert page._preview.controls[0].value == "a.png → 照片_01.png"
    result = _run(page, "rename", files, tmp_path)
    page.after_task("rename", files, result)
    assert [p.name for p in page._files] == ["照片_01.png", "照片_02.png"]
    assert all(p.exists() for p in page._files)


def test_inapplicable_files_are_skipped(tmp_path: Path) -> None:
    page = MediaPage(_FakePage(), "audio_convert")
    page._files = [tmp_path / "a.mp4", tmp_path / "b.mp3"]
    assert page._applicable() == [tmp_path / "b.mp3"]


# ── 音视频（需要 ffmpeg）────────────────────────────────────────────────
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="需要 ffmpeg")
def test_media_cut_and_extract(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=64x48:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440", "-t", "3", "-shortest", str(video)],
        check=True,
    )
    page = MediaPage(_FakePage(), "video_cut")
    page._cut_start.value = "00:00:01"
    page._cut_end.value = "00:00:02"
    cut = _run(page, "video_cut", [video], tmp_path / "out")
    assert cut.status == TaskStatus.SUCCESS, cut.error_message
    audio = _run(page, "audio_extract", [video], tmp_path / "out")
    assert audio.status == TaskStatus.SUCCESS, audio.error_message
    assert audio.output_files[0].suffix == ".mp3"


def test_video_cut_validates_time(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("ui.pages.media_page.show_toast", lambda *a, **k: None)
    page = MediaPage(_FakePage(), "video_cut")
    page._cut_start.value, page._cut_end.value = "00:01:00", "00:00:30"
    assert page.build_task("video_cut", [tmp_path / "v.mp4"], tmp_path) is None
    page._cut_start.value = "1:2"
    assert page.build_task("video_cut", [tmp_path / "v.mp4"], tmp_path) is None


# ── 批处理与路由 ─────────────────────────────────────────────────────────
def test_run_for_each_continues_after_failure(tmp_path: Path) -> None:
    from core.models import TaskResult

    calls = []

    def fn(input_file: Path) -> TaskResult:
        calls.append(input_file)
        ok = input_file.name != "bad"
        return TaskResult(status=TaskStatus.SUCCESS if ok else TaskStatus.FAILED,
                          output_files=[input_file] if ok else [], error_message=None if ok else "坏文件")

    result = run_for_each(fn, [Path("a"), Path("bad"), Path("c")], lambda p: {"input_file": p})
    assert result.status == TaskStatus.SUCCESS
    assert result.output_files == [Path("a"), Path("c")]
    assert result.warnings == ["bad：坏文件"]
    assert calls == [Path("a"), Path("bad"), Path("c")]

    result = run_for_each(fn, [Path("bad")], lambda p: {"input_file": p})
    assert result.status == TaskStatus.FAILED
    assert result.error_message == "bad：坏文件"


def test_every_feature_and_legacy_route_resolves() -> None:
    page = _FakePage()
    for route in [f.route for f in FEATURES if not f.route.startswith(("/ai", "/prompt", "/history",
                                                                          "/settings", "/ocr"))]:
        view = _resolve_page(route, page)
        _, params = _parse_route(route)
        assert view.func.key == params["func"], route
    for old, new in _LEGACY_ROUTES.items():
        if new == "/ocr":
            continue
        assert _resolve_page(old, page).func.key == _parse_route(new)[1]["func"], old


def test_merge_does_not_overwrite_previous_result(tmp_path: Path) -> None:
    a, b = _pdf(tmp_path / "a.pdf", 1), _pdf(tmp_path / "b.pdf", 1)
    page = PdfPage(_FakePage(), "merge")
    first = _run(page, "merge", [a, b], tmp_path / "out")
    second = _run(page, "merge", [a, b], tmp_path / "out")
    assert first.output_files[0].name == "merged.pdf"
    assert second.output_files[0].name == "merged_1.pdf"


# ── 压缩解压 ─────────────────────────────────────────────────────────────
def test_archive_compress_folder_with_7z_password_then_extract(tmp_path: Path) -> None:
    from ui.pages.archive_page import ArchivePage

    folder = tmp_path / "资料"
    folder.mkdir()
    (folder / "a.txt").write_text("A", encoding="utf-8")
    page = ArchivePage(_FakePage(), "compress_7z")
    page.add_files([folder], update=False)
    assert page._applicable() == [folder]
    page._password.value = "pw"
    page._name.value = "备份/2026"
    result = _run(page, "compress_7z", [folder], tmp_path / "out")
    assert result.status == TaskStatus.SUCCESS, result.error_message
    archive = result.output_files[0]
    assert archive.name == "备份_2026.7z"

    page = ArchivePage(_FakePage(), "extract")
    page._extract_password.value = "pw"
    result = _run(page, "extract", [archive], tmp_path / "x")
    assert result.status == TaskStatus.SUCCESS, result.error_message
    assert (tmp_path / "x" / "备份_2026" / "资料" / "a.txt").read_text(encoding="utf-8") == "A"


def test_archive_extract_only_accepts_archives(tmp_path: Path) -> None:
    from ui.pages.archive_page import ArchivePage

    page = ArchivePage(_FakePage(), "extract")
    page.add_files([tmp_path / "a.zip", tmp_path / "b.txt"], update=False)
    assert page._applicable() == [tmp_path / "a.zip"]


# ── 新增转换 ─────────────────────────────────────────────────────────────
def test_images_to_pdf_keeps_order_and_a4(tmp_path: Path) -> None:
    a, b = _img(tmp_path / "a.png", (300, 200)), _img(tmp_path / "b.jpg", (100, 400))
    page = ImagePage(_FakePage(), "to_pdf")
    page._pdf_page.value = "a4"
    result = _run(page, "to_pdf", [b, a], tmp_path / "out")
    assert result.status == TaskStatus.SUCCESS, result.error_message
    assert result.output_files == [tmp_path / "out" / "b.pdf"]
    pages = pypdf.PdfReader(result.output_files[0]).pages
    assert len(pages) == 2
    # 竖图放竖向 A4，横图放横向 A4
    assert float(pages[0].mediabox.height) > float(pages[0].mediabox.width)
    assert float(pages[1].mediabox.width) > float(pages[1].mediabox.height)


def test_pdf_to_images_and_pptx(tmp_path: Path) -> None:
    from pptx import Presentation

    src = _pdf(tmp_path / "doc.pdf", 3)
    page = PdfPage(_FakePage(), "to_images")
    page._image_format.value = "jpg"
    result = _run(page, "to_images", [src], tmp_path / "out")
    assert result.status == TaskStatus.SUCCESS, result.error_message
    assert [p.name for p in result.output_files] == ["第001页.jpg", "第002页.jpg", "第003页.jpg"]

    page = PdfPage(_FakePage(), "to_office")
    page._office_format.value = "pptx"
    result = _run(page, "to_office", [src], tmp_path / "out")
    assert result.status == TaskStatus.SUCCESS, result.error_message
    prs = Presentation(result.output_files[0])
    assert len(prs.slides) == 3
    assert abs(prs.slide_width / prs.slide_height - 595 / 842) < 0.01
