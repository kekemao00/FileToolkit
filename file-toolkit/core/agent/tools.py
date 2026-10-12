"""大模型可调用的工具目录 — 把应用已有的本地处理能力包装成带 JSON Schema 的工具。

每个工具声明：
  - 接受的输入扩展名（"*" 表示任意文件），是否接受文件夹，至少几个输入
  - 参数 schema（发给模型；本地 validate_args() 也按它校验并补默认值）
  - 产物类型预测 outputs(args, input_exts)：规划阶段用它检查下一步能否接上
  - run(files, args, out_dir, progress_callback) -> TaskResult：执行阶段真正调用 core 函数

工具只读传入的文件、只往 out_dir 写，不修改源文件。
"""
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.models import ProgressCallback, TaskResult, TaskStatus
from core.paths import unique_path

PDF = ("pdf",)
OFFICE = ("doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "rtf")
IMAGES = ("jpg", "jpeg", "png", "webp", "bmp", "gif", "tif", "tiff", "heic", "heif")
VIDEO = ("mp4", "avi", "mkv", "mov", "flv", "wmv", "webm", "m4v")
AUDIO = ("mp3", "wav", "flac", "aac", "ogg", "wma", "m4a")
ARCHIVES = ("zip", "7z", "rar", "tar", "gz", "tgz", "bz2", "xz")
MARKDOWN = ("md", "markdown", "txt")
ANY = ("*",)
FOLDER = "<folder>"  # 产物是文件夹（如解压结果）

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}(\.\d+)?$")
_RANGE_RE = re.compile(r"^\s*\d+\s*(-\s*\d+\s*)?$")
_BAD_NAME = re.compile(r'[\\/:*?"<>|]')

Args = dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str          # 界面上的步骤名
    description: str    # 给模型看的说明
    route: str          # 对应工作台（取图标、可跳转）
    accepts: tuple[str, ...]
    params: dict[str, dict]
    run: Callable[[list[Path], Args, Path, ProgressCallback | None], TaskResult]
    outputs: Callable[[Args, set[str]], set[str]]
    summary: Callable[[Args], str]
    required: tuple[str, ...] = ()
    min_inputs: int = 1
    accepts_folders: bool = False
    check: Callable[[Args], str | None] | None = None

    def accepts_ext(self, ext: str) -> bool:
        if ext == FOLDER:
            return self.accepts_folders
        return "*" in self.accepts or ext in self.accepts

    def accepts_path(self, path: Path) -> bool:
        if path.is_dir():
            return self.accepts_folders
        return self.accepts_ext(path.suffix.lower().lstrip("."))

    def schema(self) -> dict:
        """发给模型的参数 schema（inputs + 工具参数）。"""
        props: dict[str, dict] = {
            "inputs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要处理的文件编号：附件或已生成文件用 f 编号（如 f1），"
                               "本次方案中前面步骤的产物用 s 编号（如 s1）",
            },
        }
        for key, spec in self.params.items():
            props[key] = {k: v for k, v in spec.items() if k != "default"}
        return {
            "type": "object",
            "properties": props,
            "required": ["inputs", *self.required],
            "additionalProperties": False,
        }


# ── 参数校验 ─────────────────────────────────────────────────────────────
def validate_args(tool: ToolSpec, raw: Args) -> tuple[Args, str | None]:
    """按 schema 校验工具参数并补默认值，返回 (参数, 错误)。inputs 不在这里处理。"""
    args: Args = {}
    unknown = [k for k in raw if k != "inputs" and k not in tool.params]
    if unknown:
        return {}, f"不支持的参数：{'、'.join(unknown)}"
    for key, spec in tool.params.items():
        value = raw.get(key)
        if value is None or value == "":
            if key in tool.required:
                return {}, f"缺少参数 {key}（{spec.get('description', '')}）"
            if "default" in spec:
                args[key] = spec["default"]
            continue
        value, err = _coerce(key, value, spec)
        if err:
            return {}, err
        args[key] = value
    if tool.check:
        err = tool.check(args)
        if err:
            return {}, err
    return args, None


def _coerce(key: str, value: Any, spec: dict) -> tuple[Any, str | None]:
    kind = spec.get("type")
    if kind == "integer":
        if isinstance(value, bool):
            return None, f"参数 {key} 应为整数"
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            value = int(value.strip())
        elif isinstance(value, float) and value.is_integer():
            value = int(value)
        if not isinstance(value, int):
            return None, f"参数 {key} 应为整数"
    elif kind == "number":
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                return None, f"参数 {key} 应为数字"
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None, f"参数 {key} 应为数字"
    elif kind == "boolean":
        if isinstance(value, str) and value.lower() in ("true", "false"):
            value = value.lower() == "true"
        if not isinstance(value, bool):
            return None, f"参数 {key} 应为 true / false"
    elif kind == "string":
        if isinstance(value, int | float) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            return None, f"参数 {key} 应为字符串"
        value = value.strip()
    if "enum" in spec and value not in spec["enum"]:
        return None, f"参数 {key} 只能是 {' / '.join(map(str, spec['enum']))}"
    if "minimum" in spec and value < spec["minimum"]:
        return None, f"参数 {key} 不能小于 {spec['minimum']}"
    if "maximum" in spec and value > spec["maximum"]:
        return None, f"参数 {key} 不能大于 {spec['maximum']}"
    return value, None


# ── 公共参数 / 小工具 ─────────────────────────────────────────────────────
def _enum(values: list, desc: str, default: Any = None) -> dict:
    kind = "integer" if all(isinstance(v, int) for v in values) else "string"
    spec: dict = {"type": kind, "enum": values, "description": desc}
    if default is not None:
        spec["default"] = default
    return spec


def _str(desc: str, default: str | None = None) -> dict:
    spec: dict = {"type": "string", "description": desc}
    if default is not None:
        spec["default"] = default
    return spec


def _int(desc: str, default: int | None = None, minimum: int | None = None,
         maximum: int | None = None) -> dict:
    spec: dict = {"type": "integer", "description": desc}
    for k, v in (("default", default), ("minimum", minimum), ("maximum", maximum)):
        if v is not None:
            spec[k] = v
    return spec


def _same(_: Args, exts: set[str]) -> set[str]:
    return set(exts)


def _const(*exts: str) -> Callable[[Args, set[str]], set[str]]:
    return lambda _a, _e: set(exts)


def _arg(key: str) -> Callable[[Args, set[str]], set[str]]:
    return lambda a, _e: {str(a[key]).lower()}


def _output_name(name: str, default: str, ext: str) -> str:
    name = _BAD_NAME.sub("_", (name or "").strip()) or default
    if not name.lower().endswith(f".{ext}"):
        name += f".{ext}"
    return name


def _check_name(key: str) -> Callable[[Args], str | None]:
    def check(a: Args) -> str | None:
        if _BAD_NAME.search(a.get(key) or ""):
            return f"{key} 不能包含 \\ / : * ? \" < > |"
        return None
    return check


def _each(fn: Callable[..., TaskResult], make: Callable[[Path], dict]):
    """单文件 core 函数逐个处理。"""
    from core.batch import run_for_each

    def runner(files: list[Path], progress: ProgressCallback | None) -> TaskResult:
        return run_for_each(fn, files, make, progress)
    return runner


# ── PDF ─────────────────────────────────────────────────────────────────
def _pdf_merge(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.pdf.merger import merge_pdf
    name = _output_name(a.get("output_name", ""), files[0].stem + "_合并", "pdf")
    return merge_pdf(input_files=files, output_file=unique_path(out / name), progress_callback=cb)


def _pdf_split(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.pdf.splitter import split_pdf
    extra: dict = {"mode": a["mode"]}
    if a["mode"] == "pages":
        extra["pages_per_file"] = a["pages_per_file"]
    elif a["mode"] == "range":
        extra["page_ranges"] = _ranges(a["page_ranges"])
    return _each(split_pdf, lambda p: {"input_file": p, "output_dir": out, **extra})(files, cb)


def _ranges(text: str) -> list[str]:
    return [r.strip().replace(" ", "") for r in re.split(r"[,，]", text or "") if r.strip()]


def _check_split(a: Args) -> str | None:
    if a["mode"] == "range":
        ranges = _ranges(a.get("page_ranges", ""))
        if not ranges:
            return "mode 为 range 时必须提供 page_ranges，如 \"1-3, 5, 8-10\""
        if not all(_RANGE_RE.match(r) for r in ranges):
            return "page_ranges 格式应为 \"1-3, 5, 8-10\""
    return None


def _pdf_compress(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.pdf.compressor import compress_pdf
    return _each(compress_pdf, lambda p: {
        "input_file": p, "output_file": unique_path(out / f"{p.stem}_compressed.pdf"),
        "quality": a["quality"]})(files, cb)


def _pdf_to_office(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.pdf.converter import pdf_to_docx, pdf_to_pptx, pdf_to_xlsx
    fn = {"docx": pdf_to_docx, "xlsx": pdf_to_xlsx, "pptx": pdf_to_pptx}[a["format"]]
    return _each(fn, lambda p: {"input_file": p, "output_dir": out})(files, cb)


def _pdf_to_images(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.pdf.converter import pdf_to_images
    return _each(pdf_to_images, lambda p: {
        "input_file": p, "output_dir": out, "image_format": a["image_format"], "dpi": a["dpi"]})(files, cb)


def _office_to_pdf(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.pdf.converter import office_to_pdf
    return _each(office_to_pdf, lambda p: {"input_file": p, "output_dir": out})(files, cb)


def _pdf_watermark(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.pdf.watermark import add_text_watermark
    return _each(add_text_watermark, lambda p: {
        "input_file": p, "output_file": unique_path(out / f"{p.stem}_watermarked.pdf"),
        "text": a["text"], "opacity": a["opacity"] / 100})(files, cb)


def _pdf_encrypt(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.pdf.encryptor import encrypt_pdf
    return _each(encrypt_pdf, lambda p: {
        "input_file": p, "output_file": unique_path(out / f"{p.stem}_protected.pdf"),
        "user_password": a["password"]})(files, cb)


# ── 图片 ────────────────────────────────────────────────────────────────
def _image_compress(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.image.compressor import compress_images
    return compress_images(input_files=files, output_dir=out, level=a["level"], progress_callback=cb)


def _image_convert(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.image.converter import convert_image
    return convert_image(input_files=files, output_dir=out, target_format=a["target_format"],
                         quality=a["quality"], progress_callback=cb)


def _image_resize(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.image.resizer import resize_images
    return resize_images(input_files=files, output_dir=out, width=a.get("width"), height=a.get("height"),
                         keep_ratio=a["keep_ratio"], progress_callback=cb)


def _check_resize(a: Args) -> str | None:
    if not a.get("width") and not a.get("height"):
        return "width 和 height 至少填一个"
    return None


def _image_watermark(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.image.watermark import add_text_watermark
    return add_text_watermark(input_files=files, output_dir=out, text=a["text"], position=a["position"],
                              opacity=a["opacity"], font_size=a["font_size"], progress_callback=cb)


def _images_to_pdf(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.image.to_pdf import images_to_pdf
    name = _output_name(a.get("output_name", ""), files[0].stem, "pdf")
    return images_to_pdf(input_files=files, output_file=unique_path(out / name), page_size=a["page_size"],
                         progress_callback=cb)


def _rename_copies(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    """先复制到输出目录再重命名副本，原文件保持不动。"""
    from core.image.renamer import batch_rename
    out.mkdir(parents=True, exist_ok=True)
    claimed: set[Path] = set()
    copies: list[Path] = []
    for f in files:
        target = unique_path(out / f.name, claimed)
        claimed.add(target)
        shutil.copy2(f, target)
        copies.append(target)
    return batch_rename(input_files=copies, template=a["template"], start_number=a["start_number"],
                        progress_callback=cb)


# ── 音视频 ──────────────────────────────────────────────────────────────
def _video_convert(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.media.video import convert_video
    return convert_video(input_files=files, output_dir=out, target_format=a["target_format"],
                         progress_callback=cb)


def _video_compress(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.media.video import compress_video
    return compress_video(input_files=files, output_dir=out, quality=a["quality"],
                          resolution=a["resolution"], progress_callback=cb)


def _seconds(t: str) -> float:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _check_cut(a: Args) -> str | None:
    if not _TIME_RE.match(a["start_time"]) or not _TIME_RE.match(a["end_time"]):
        return "时间格式应为 HH:MM:SS，如 00:01:30"
    if _seconds(a["end_time"]) <= _seconds(a["start_time"]):
        return "end_time 必须晚于 start_time"
    return None


def _video_cut(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.media.video import cut_video
    return _each(cut_video, lambda p: {
        "input_file": p, "output_dir": out, "start_time": a["start_time"], "end_time": a["end_time"]})(files, cb)


def _audio_extract(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.media.audio import extract_audio
    return _each(extract_audio, lambda p: {
        "input_file": p, "output_dir": out, "audio_format": a["audio_format"]})(files, cb)


def _audio_convert(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.media.audio import convert_audio
    return convert_audio(input_files=files, output_dir=out, target_format=a["target_format"],
                         bitrate=a["bitrate"], progress_callback=cb)


# ── 压缩包 ──────────────────────────────────────────────────────────────
def _archive(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.archive.handler import compress
    kwargs: dict = {"input_files": files, "output_dir": out, "format": a["format"], "progress_callback": cb}
    if a.get("password"):
        kwargs["password"] = a["password"]
    if a.get("archive_name"):
        kwargs["archive_name"] = a["archive_name"]
    return compress(**kwargs)


def _check_archive(a: Args) -> str | None:
    if a.get("password") and a["format"] != "7z":
        return "只有 7z 格式支持密码，请把 format 设为 7z 或去掉 password"
    return _check_name("archive_name")(a)


def _extract(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.archive.handler import extract_many
    return extract_many(input_files=files, output_dir=out, password=a.get("password", ""),
                        progress_callback=cb)


# ── OCR / Markdown ──────────────────────────────────────────────────────
def _ocr(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.ocr.client import recognize
    return _each(recognize, lambda p: {"input_file": p, "language": a["language"], "output_dir": out})(files, cb)


def _to_markdown(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.markdown.converter import merge_to_markdown, to_markdown
    opts = {"image_mode": a["image_mode"]}
    if a["merge"] and len(files) > 1:
        name = _output_name(a.get("merge_name", ""), "合并资料", "md")
        return merge_to_markdown(input_files=files, output_file=unique_path(out / name),
                                 progress_callback=cb, **opts)
    return _each(to_markdown, lambda p: {"input_file": p, "output_dir": out, **opts})(files, cb)


def _markdown_export(files: list[Path], a: Args, out: Path, cb) -> TaskResult:
    from core.markdown.from_md import from_markdown
    return _each(from_markdown, lambda p: {"input_file": p, "output_dir": out, "target": a["target"]})(files, cb)


def _md_inputs() -> tuple[str, ...]:
    from core.markdown.converter import SUPPORTED_EXTENSIONS
    return tuple(e for e in SUPPORTED_EXTENSIONS if e not in ("md", "markdown"))


# ── 摘要文字 ────────────────────────────────────────────────────────────
_LABELS = {
    "high": "高", "medium": "推荐", "low": "低", "pages": "按页数", "range": "按页码范围", "each": "每页一份",
    "fit": "与图片同尺寸", "a4": "A4", "original": "原始分辨率", "extract": "图片单独保存",
    "skip": "不要图片", "embed": "图片内嵌", "chi_sim": "简体中文", "eng": "英文",
    "chi_sim+eng": "中英文", "jpn": "日文",
}


def _l(v: Any) -> str:
    return _LABELS.get(str(v), str(v).upper() if isinstance(v, str) and len(v) <= 5 else str(v))


TOOLS: list[ToolSpec] = [
    ToolSpec(
        "pdf_merge", "PDF 合并", "把多个 PDF 按 inputs 的顺序合并成一个 PDF。", "/pdf?func=merge", PDF,
        {"output_name": _str("输出文件名（可选，不含路径）", "")},
        _pdf_merge, _const("pdf"), lambda a: f"输出：{a['output_name'] or '自动命名'}",
        min_inputs=2, check=_check_name("output_name"),
    ),
    ToolSpec(
        "pdf_split", "PDF 拆分", "拆分 PDF：按固定页数、按页码范围或每页一份。", "/pdf?func=split", PDF,
        {"mode": _enum(["pages", "range", "each"], "pages=每 N 页一份；range=按页码范围；each=每页一份", "pages"),
         "pages_per_file": _int("mode=pages 时每份页数", 5, minimum=1),
         "page_ranges": _str("mode=range 时的页码范围，如 \"1-3, 5, 8-10\"，每段一份", "")},
        _pdf_split, _const("pdf"),
        lambda a: _l(a["mode"]) + (f" · 每 {a['pages_per_file']} 页" if a["mode"] == "pages" else "")
        + (f" · {a['page_ranges']}" if a["mode"] == "range" else ""),
        check=_check_split,
    ),
    ToolSpec(
        "pdf_compress", "PDF 压缩", "减小 PDF 体积。quality：high=轻度（无损），medium=推荐，low=强力（体积最小）。",
        "/pdf?func=compress", PDF,
        {"quality": _enum(["high", "medium", "low"], "压缩强度", "medium")},
        _pdf_compress, _const("pdf"),
        lambda a: "强度：" + {"high": "轻度", "medium": "推荐", "low": "强力"}[a["quality"]],
    ),
    ToolSpec(
        "pdf_to_office", "PDF 转 Office", "PDF 转 Word（docx）、Excel（xlsx）或 PPT（pptx）。",
        "/pdf?func=to_office", PDF,
        {"format": _enum(["docx", "xlsx", "pptx"], "目标格式", "docx")},
        _pdf_to_office, _arg("format"), lambda a: f"转为 {_l(a['format'])}",
    ),
    ToolSpec(
        "pdf_to_images", "PDF 转图片", "把 PDF 每页导出为一张图片。", "/pdf?func=to_images", PDF,
        {"image_format": _enum(["png", "jpg"], "图片格式", "png"),
         "dpi": _enum([96, 150, 300], "清晰度，150 适合屏幕，300 适合打印", 150)},
        _pdf_to_images, _arg("image_format"), lambda a: f"{_l(a['image_format'])} · {a['dpi']} dpi",
    ),
    ToolSpec(
        "office_to_pdf", "Office 转 PDF", "Word / Excel / PPT / OpenDocument 转 PDF（需要本机安装 LibreOffice）。",
        "/pdf?func=from_office", OFFICE, {}, _office_to_pdf, _const("pdf"), lambda a: "转为 PDF",
    ),
    ToolSpec(
        "pdf_watermark", "PDF 加水印", "给 PDF 每页加斜向文字水印。", "/pdf?func=protect", PDF,
        {"text": _str("水印文字"), "opacity": _int("不透明度百分比 10-80", 30, minimum=10, maximum=80)},
        _pdf_watermark, _const("pdf"), lambda a: f"水印「{a['text']}」· 不透明度 {a['opacity']}%",
        required=("text",),
    ),
    ToolSpec(
        "pdf_encrypt", "PDF 加密", "给 PDF 设置打开密码。如需同时加水印，先加水印再加密。", "/pdf?func=protect", PDF,
        {"password": _str("打开密码")},
        _pdf_encrypt, _const("pdf"), lambda a: f"密码：{a['password']}", required=("password",),
    ),
    ToolSpec(
        "image_compress", "图片压缩", "压缩图片体积。level：low=轻度，medium=标准，high=极限。",
        "/image?func=compress", IMAGES,
        {"level": _enum(["low", "medium", "high"], "压缩强度", "medium")},
        _image_compress, _same, lambda a: "强度：" + {"low": "轻度", "medium": "标准", "high": "极限"}[a["level"]],
    ),
    ToolSpec(
        "image_convert", "图片格式转换", "图片转换为 jpg / png / webp / bmp / tiff。", "/image?func=convert", IMAGES,
        {"target_format": _enum(["jpg", "png", "webp", "bmp", "tiff"], "目标格式"),
         "quality": _int("jpg / webp 质量 1-100", 85, minimum=1, maximum=100)},
        _image_convert, _arg("target_format"), lambda a: f"转为 {_l(a['target_format'])}",
        required=("target_format",),
    ),
    ToolSpec(
        "image_resize", "图片尺寸调整", "调整图片宽高（像素）。只给宽或高时按比例缩放。", "/image?func=resize", IMAGES,
        {"width": _int("目标宽度（像素）", minimum=1, maximum=20000),
         "height": _int("目标高度（像素）", minimum=1, maximum=20000),
         "keep_ratio": {"type": "boolean", "description": "保持宽高比", "default": True}},
        _image_resize, _same,
        lambda a: f"{a.get('width') or '自动'} × {a.get('height') or '自动'}" + (" · 保持比例" if a["keep_ratio"] else ""),
        check=_check_resize,
    ),
    ToolSpec(
        "image_watermark", "图片加水印", "给图片加文字水印。", "/image?func=watermark", IMAGES,
        {"text": _str("水印文字"),
         "position": _enum(["top_left", "top_center", "top_right", "center_left", "center", "center_right",
                            "bottom_left", "bottom_center", "bottom_right"], "位置", "bottom_right"),
         "opacity": _int("不透明度百分比 0-100", 30, minimum=0, maximum=100),
         "font_size": _int("字号（像素）", 24, minimum=8, maximum=400)},
        _image_watermark, _same, lambda a: f"水印「{a['text']}」· {a['position']} · 不透明度 {a['opacity']}%",
        required=("text",),
    ),
    ToolSpec(
        "images_to_pdf", "图片转 PDF", "把多张图片按 inputs 顺序合成一个 PDF，每张一页。", "/image?func=to_pdf", IMAGES,
        {"page_size": _enum(["fit", "a4"], "fit=页面与图片同尺寸；a4=放到 A4 纸上", "fit"),
         "output_name": _str("输出文件名（可选）", "")},
        _images_to_pdf, _const("pdf"), lambda a: f"页面：{_l(a['page_size'])}", check=_check_name("output_name"),
    ),
    ToolSpec(
        "rename_files", "批量重命名", "复制文件并按模板重命名副本（原文件不动）。模板占位符：{name} 原文件名、"
        "{n} 序号（可写 {n:03d} 补零）、{date} 今天日期、{ext} 扩展名。", "/image?func=rename", ANY,
        {"template": _str("命名模板，不含扩展名，如 \"发票_{n:03d}\"", "{name}_{n:03d}"),
         "start_number": _int("起始序号", 1, minimum=0)},
        _rename_copies, _same, lambda a: f"模板：{a['template']}",
    ),
    ToolSpec(
        "video_convert", "视频格式转换", "视频转换为 mp4 / mkv / mov / avi / webm。", "/media?func=video_convert", VIDEO,
        {"target_format": _enum(["mp4", "mkv", "mov", "avi", "webm"], "目标格式", "mp4")},
        _video_convert, _arg("target_format"), lambda a: f"转为 {_l(a['target_format'])}",
    ),
    ToolSpec(
        "video_compress", "视频压缩", "压缩视频。降低分辨率是减小体积最有效的方式。", "/media?func=video_compress", VIDEO,
        {"quality": _enum(["high", "medium", "low"], "high=画质优先，medium=均衡，low=体积优先", "medium"),
         "resolution": _enum(["original", "1080p", "720p", "480p"], "输出分辨率", "original")},
        _video_compress, _same,
        lambda a: {"high": "画质优先", "medium": "均衡", "low": "体积优先"}[a["quality"]] + f" · {_l(a['resolution'])}",
    ),
    ToolSpec(
        "video_cut", "视频剪辑", "截取视频中的一段（多个视频都截同一段）。", "/media?func=video_cut", VIDEO,
        {"start_time": _str("开始时间 HH:MM:SS"), "end_time": _str("结束时间 HH:MM:SS")},
        _video_cut, _same, lambda a: f"{a['start_time']} 至 {a['end_time']}",
        required=("start_time", "end_time"), check=_check_cut,
    ),
    ToolSpec(
        "audio_extract", "提取音频", "从视频导出音轨。", "/media?func=audio_extract", VIDEO,
        {"audio_format": _enum(["mp3", "wav", "flac", "aac"], "音频格式", "mp3")},
        _audio_extract, _arg("audio_format"), lambda a: f"导出 {_l(a['audio_format'])}",
    ),
    ToolSpec(
        "audio_convert", "音频格式转换", "音频转换为 mp3 / wav / flac / aac / ogg。", "/media?func=audio_convert", AUDIO,
        {"target_format": _enum(["mp3", "wav", "flac", "aac", "ogg"], "目标格式", "mp3"),
         "bitrate": _enum(["128", "192", "256", "320"], "比特率 kbps（wav / flac 无效）", "192")},
        _audio_convert, _arg("target_format"), lambda a: f"转为 {_l(a['target_format'])} · {a['bitrate']}k",
    ),
    ToolSpec(
        "archive_compress", "打包压缩", "把所有输入文件（可含文件夹）打成一个压缩包。只有 7z 支持密码。",
        "/archive?func=compress_zip", ANY,
        {"format": _enum(["zip", "7z", "tar.gz"], "压缩格式", "zip"),
         "password": _str("打开密码（可选，仅 7z）", ""),
         "archive_name": _str("压缩包名称（可选，不含扩展名）", "")},
        _archive, lambda a, _e: {"gz" if a["format"] == "tar.gz" else a["format"]},
        lambda a: f"{_l(a['format'])}" + (" · 已加密" if a.get("password") else ""),
        accepts_folders=True, check=_check_archive,
    ),
    ToolSpec(
        "archive_extract", "解压", "解压 zip / 7z / rar / tar 压缩包，每个包解到单独文件夹。", "/archive?func=extract",
        ARCHIVES, {"password": _str("解压密码（可选）", "")},
        _extract, _const(FOLDER), lambda a: "解压" + (" · 带密码" if a.get("password") else ""),
    ),
    ToolSpec(
        "ocr", "OCR 文字识别", "识别图片或扫描版 PDF 中的文字，输出 txt（需要本机安装 Tesseract）。", "/ocr",
        IMAGES + PDF,
        {"language": _enum(["chi_sim", "eng", "chi_sim+eng", "jpn"], "识别语言", "chi_sim+eng")},
        _ocr, _const("txt"), lambda a: f"语言：{_l(a['language'])}",
    ),
    ToolSpec(
        "to_markdown", "转 Markdown", "Word / PDF / PPT / Excel / CSV / 网页 / txt 转为 Markdown，适合交给 AI。",
        "/markdown?func=to_md", _md_inputs(),
        {"image_mode": _enum(["extract", "skip", "embed"],
                             "图片处理：extract=单独保存；skip=不要图片（最省 token）；embed=内嵌", "extract"),
         "merge": {"type": "boolean", "description": "多个文件合并为一份 .md", "default": False},
         "merge_name": _str("合并后的文件名（可选）", "")},
        _to_markdown, _const("md"),
        lambda a: _l(a["image_mode"]) + (" · 合并为一份" if a["merge"] else ""), check=_check_name("merge_name"),
    ),
    ToolSpec(
        "markdown_export", "Markdown 转出", "Markdown 转为 Word（docx）、PDF 或单文件网页（html）。",
        "/markdown?func=from_md", MARKDOWN,
        {"target": _enum(["docx", "pdf", "html"], "目标格式", "docx")},
        _markdown_export, _arg("target"), lambda a: f"转为 {_l(a['target'])}",
    ),
]

TOOLS_BY_NAME: dict[str, ToolSpec] = {t.name: t for t in TOOLS}


def run_tool(tool: ToolSpec, files: list[Path], args: Args, out_dir: Path,
             progress_callback: ProgressCallback | None = None) -> TaskResult:
    """执行一个工具（在 task_service 的工作线程里调用）。"""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        return tool.run(files, args, out_dir, progress_callback)
    except Exception as exc:  # core 函数大多自己兜底，这里防止个别异常直接冒到界面
        from core.task_control import TaskCancelled
        if isinstance(exc, TaskCancelled):
            return TaskResult(status=TaskStatus.CANCELLED, error_message="已取消")
        return TaskResult(status=TaskStatus.FAILED, error_message=str(exc) or exc.__class__.__name__)
