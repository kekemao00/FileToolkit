"""OCR 文字识别

布局：左侧主内容区（标题 + 选择文件区 + 文件信息 / 进度 / 结果） + 右侧参数面板（白色卡片）
三视图互斥切换，外观与 ui/components/workbench.py 一致。
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import flet as ft

from core.ocr.client import INSTALL_HINT, find_tesseract, recognize
from services import history_service, settings_service
from services.task_service import run_task
from ui import style as s
from ui.components.top_bar import TopBar
from ui.palette import c
from ui.utils import show_toast

# 语言选项（并排按钮）
_LANGUAGES = [
    {"key": "chi_sim", "label": "简体中文"},
    {"key": "eng", "label": "English"},
    {"key": "chi_sim+eng", "label": "中英混合"},
    {"key": "jpn", "label": "日本語"},
]

_INPUT_EXTS = {"png", "jpg", "jpeg", "bmp", "tiff", "tif", "pdf"}


class OcrPage(ft.Column):
    """OCR 文字识别 — 工作台布局。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._input_file: Path | None = None
        self._task: asyncio.Task | None = None
        self._output_file: Path | None = None
        self._result_text_value: str = ""

        # 处理中视图组件
        self._progress_title = s.text(kind="title")
        self._progress_pct = s.text("0%", "mono", color="ink")
        self._progress_bar = ft.ProgressBar(
            value=0, color=c("ink"), bgcolor=c("surface-3"), bar_height=4, border_radius=2,
        )
        self._progress_desc = s.text(kind="small")
        self._progress_cancel_btn = s.button("取消识别", lambda _: self._cancel(), kind="secondary")

        # 结果视图组件
        self._result_title = s.text(kind="title", expand=True)
        self._result_icon = ft.Icon(ft.Icons.CHECK_ROUNDED, color="#FFFFFF", size=16)
        self._result_icon_box = ft.Container(
            content=self._result_icon, width=32, height=32, bgcolor=c("accent"),
            border_radius=16, alignment=ft.Alignment(0, 0),
        )
        self._result_text = s.text_field(
            multiline=True,
            min_lines=10,
            max_lines=18,
            read_only=False,
        )
        # 摘要字段
        self._sum_lang = s.text("--", "body-medium")
        self._sum_chars = s.text("--", "mono", color="ink")
        self._sum_paras = s.text("--", "mono", color="ink")
        self._sum_status = s.text("--", "body-medium")

        # 语言选择（分段标签页，墨黑指示条在选项间滑动）
        self._language_value = "chi_sim"
        self._lang_tabs = s.Segmented(
            [(lang["key"], lang["label"]) for lang in _LANGUAGES], self._language_value,
            on_change=self._select_lang, size=12.5, fill_width=278,
        )

        # 文件名显示
        self._file_name = s.text(kind="body-medium")
        self._file_info_container = ft.Container(visible=False)

        # 运行按钮（会变形：按钮 → 加载圆 → 对勾 / 错误）
        self._run_btn = s.MorphButton(self._start_task, label="开始识别",
                                      icon=ft.Icons.DOCUMENT_SCANNER_OUTLINED)
        self._run_btn.set_label("开始识别", enabled=False)

        self._main_content = self._build_main_content()
        self._build_param_panel()

        self._NARROW_BREAKPOINT = 800
        self._is_narrow = None
        self._body_container: ft.Control = ft.Container()
        self._topbar = self._build_topbar()

        self.controls = [self._topbar, self._body_container]
        self._apply_responsive_layout(update=False)

        self._prev_on_resize = None

    def did_mount(self) -> None:
        self._prev_on_resize = self._page.on_resize
        self._page.on_resize = self._on_page_resized

    def will_unmount(self) -> None:
        if self._page.on_resize == self._on_page_resized:
            self._page.on_resize = self._prev_on_resize

    def _build_topbar(self) -> ft.Control:
        return TopBar(self._page)

    def _build_main_content(self) -> ft.Control:
        self._workspace_view = self._build_workspace_view()
        self._processing_view = self._build_processing_view()
        self._complete_view = self._build_complete_view()
        self._processing_view.visible = False
        self._complete_view.visible = False

        return ft.Container(
            content=ft.Column(
                controls=[
                    self._workspace_view,
                    self._processing_view,
                    self._complete_view,
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )

    def _build_workspace_view(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    s.text("OCR 文字识别", "headline"),
                                    s.text("图片 / 扫描件 / PDF 文字识别", "small"),
                                ],
                                spacing=4,
                            ),
                            ft.Container(expand=True),
                            self._build_engine_badge(),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    self._build_drop_zone(),
                    self._build_file_info(),
                ],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=ft.padding.only(left=s.PAGE_X, right=16, top=4, bottom=20),
        )

    def _build_engine_badge(self) -> ft.Control:
        """本地引擎状态：检测到 Tesseract 才显示「就绪」，否则提示只能提取 PDF 文字。"""
        ready = find_tesseract() is not None
        return ft.Container(
            tooltip=None if ready else INSTALL_HINT,
            content=ft.Row(
                controls=[
                    ft.Container(width=6, height=6, border_radius=3,
                                 bgcolor=c("accent") if ready else c("ink-3")),
                    s.text("本地引擎就绪" if ready else "未安装 Tesseract，仅能提取 PDF 文字",
                           "caption", color="ink-2"),
                ],
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=22,
            bgcolor=c("surface"),
            border=ft.border.all(1, c("line-strong")),
            border_radius=11,
            padding=ft.padding.symmetric(horizontal=9),
        )

    def _build_drop_zone(self) -> ft.Control:
        self._drop_icon = ft.Container(
            content=ft.Icon(ft.Icons.DOCUMENT_SCANNER_OUTLINED, color=c("ink-2", "fg"), size=20),
            width=44, height=44, bgcolor=c("surface-2"), border_radius=22,
            alignment=ft.Alignment(0, 0), animate=s.snappy(),
        )
        self._drop_zone_body = ft.Container(
            content=ft.Column(
                controls=[
                    self._drop_icon,
                    s.text("点击选择图片或 PDF", "title", text_align=ft.TextAlign.CENTER),
                    s.text("支持 JPG / PNG / BMP / TIFF / PDF", "small", text_align=ft.TextAlign.CENTER),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=c("surface"),
            border=ft.border.all(1, c("line")),
            border_radius=s.R_PANEL,
            on_click=self._pick_file,
            on_hover=self._on_drop_zone_hover,
            expand=True,
            animate=s.snappy(),
        )
        self._drop_zone_wrapper = ft.Container(
            content=self._drop_zone_body,
            height=168,
            animate_size=s.default(),
        )
        return self._drop_zone_wrapper

    def _on_drop_zone_hover(self, e: ft.ControlEvent) -> None:
        on = e.data in (True, "true")
        self._drop_zone_body.bgcolor = c("surface-2" if on else "surface")
        self._drop_zone_body.border = ft.border.all(1, c("line-strong" if on else "line"))
        self._drop_icon.bgcolor = c("surface-3" if on else "surface-2")
        self._drop_zone_body.update()

    def _build_file_info(self) -> ft.Control:
        self._file_info_container = ft.Container(
            visible=False,
            content=s.card(
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, color=c("ink-2", "fg"), size=16),
                            width=32, height=32, bgcolor=c("surface-2"), border_radius=s.R_BUTTON,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(
                            controls=[self._file_name, s.text("准备识别", "caption")],
                            spacing=2, tight=True, expand=True,
                        ),
                        s.icon_button(ft.Icons.CLOSE_OUTLINED, self._remove_file, tooltip="移除", color="ink-3"),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.only(left=14, right=8, top=10, bottom=10),
            ),
        )
        return self._file_info_container

    def _build_param_panel(self) -> ft.Control:
        self._param_panel = s.card(
            ft.Column(
                controls=[
                    ft.Column(
                        controls=[
                            s.text("参数设置", "title"),
                            self._section("识别语言", self._lang_tabs),
                        ],
                        spacing=20,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    ft.Row(controls=[self._run_btn], alignment=ft.MainAxisAlignment.CENTER),
                    s.text("本地处理 · 隐私保护已开启", "caption", text_align=ft.TextAlign.CENTER),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            ),
            width=320,
            margin=ft.margin.only(right=s.PAGE_X, bottom=20, top=4),
        )
        return self._param_panel

    def _section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(controls=[s.text(label, "caption"), content], spacing=8)

    def _select_lang(self, key: str) -> None:
        self._language_value = key

    def _build_processing_view(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                self._progress_title,
                                ft.Container(expand=True),
                                self._progress_pct,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.only(bottom=8),
                    ),
                    self._progress_bar,
                    self._progress_desc,
                    ft.Row(controls=[ft.Container(expand=True),
                                     self._progress_cancel_btn]),
                ],
                spacing=12,
            ),
            bgcolor=c("surface"),
            border=ft.border.all(1, c("line")),
            border_radius=s.R_PANEL,
            padding=ft.padding.all(24),
            margin=ft.margin.only(left=s.PAGE_X, right=16, top=4),
        )

    def _build_complete_view(self) -> ft.Container:
        summary_panel = s.card(
            ft.Column(
                controls=[
                    s.text("文档摘要", "title"),
                    ft.Container(height=4),
                    self._build_summary_row("识别语言", self._sum_lang),
                    self._build_summary_row("字符数", self._sum_chars),
                    self._build_summary_row("段落数", self._sum_paras),
                    self._build_summary_row("状态", self._sum_status, last=True),
                    ft.Container(height=8),
                    ft.Row(
                        controls=[
                            s.button("复制文本", self._copy_result, kind="secondary", expand=True),
                            s.button("保存 TXT", self._save_result, expand=True),
                        ],
                        spacing=8,
                    ),
                    s.button("打开所在文件夹", self._open_output_folder, kind="secondary",
                             icon=ft.Icons.FOLDER_OPEN_OUTLINED),
                    s.button("继续识别", lambda _: self._reset(), kind="ghost"),
                ],
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=16,
            width=260,
        )

        result_panel = s.card(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[self._result_icon_box, self._result_title],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self._result_text,
                ],
                spacing=12,
            ),
            padding=16,
            expand=True,
        )

        return ft.Container(
            content=ft.Row(
                controls=[result_panel, summary_panel],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            margin=ft.margin.only(left=s.PAGE_X, right=16, top=4),
        )

    def _build_summary_row(self, label: str, value_text: ft.Text, last: bool = False) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[s.text(label, "small"), ft.Container(expand=True), value_text],
            ),
            padding=ft.padding.symmetric(vertical=8),
            border=None if last else ft.border.only(bottom=ft.BorderSide(1, c("line"))),
        )

    # ── 响应式 ──────────────────────────────────────────────
    def _apply_responsive_layout(self, update: bool = True) -> None:
        width = self._page.width or 1000
        narrow = width < self._NARROW_BREAKPOINT
        if narrow == self._is_narrow:
            return
        self._is_narrow = narrow
        if narrow:
            self._param_panel.width = None
            self._param_panel.margin = ft.margin.only(left=s.PAGE_X, right=s.PAGE_X, bottom=20)
            self._run_btn.full_width = 320
            new_body = ft.Column(
                controls=[self._main_content, self._param_panel],
                expand=True, spacing=0, scroll=ft.ScrollMode.AUTO,
            )
        else:
            self._param_panel.width = 320
            self._param_panel.margin = ft.margin.only(right=s.PAGE_X, bottom=20, top=4)
            self._run_btn.full_width = 278
            new_body = ft.Row(
                controls=[self._main_content, self._param_panel],
                expand=True, spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        self._body_container = new_body
        self.controls[1] = new_body
        if update:
            self.update()

    def _on_page_resized(self, e) -> None:
        self._apply_responsive_layout()

    # ── 事件处理 ────────────────────────────────────────────
    def _pick_file(self, _) -> None:
        self._page.run_task(self._pick_file_async)

    async def _pick_file_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        try:
            files = await picker.pick_files(
                dialog_title="选择图片或扫描件",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=list(_INPUT_EXTS),
                allow_multiple=False,
            )
        except RuntimeError:
            self._show_snack("无法打开文件选择器，请检查系统环境")
            return
        if not files:
            self._page.update()
            return
        paths = [Path(f.path) for f in files if f.path]
        if paths:
            self._input_file = paths[0]
            self._file_name.value = self._input_file.name
            self._file_info_container.visible = True
            self._run_btn.set_label("开始识别", enabled=True)
            self._drop_zone_wrapper.height = 120
        self._page.update()

    def _remove_file(self, _) -> None:
        self._input_file = None
        self._file_info_container.visible = False
        self._run_btn.set_label("开始识别", enabled=False)
        self._drop_zone_wrapper.height = 168
        self.update()

    def _start_task(self, _) -> None:
        if not self._input_file:
            self._show_snack("请先选择要识别的文件")
            return
        kwargs = {
            "input_file": self._input_file,
            "language": self._language_value,
            "output_dir": settings_service.resolve_output_dir(self._input_file),
        }
        self._show_processing(self._input_file.name)
        self._run_seq = getattr(self, "_run_seq", 0) + 1
        seq = self._run_seq

        async def _run():
            await run_task(recognize, kwargs,
                           lambda *a: seq == self._run_seq and self._on_progress(*a),
                           lambda r: seq == self._run_seq and self._on_complete(r))
        self._task = self._page.run_task(_run)

    def _on_progress(self, current, total, desc):
        if total > 0:
            self._progress_bar.value = current / total
            pct = int(current / total * 100)
            self._progress_pct.value = f"{pct}%"
        self._progress_desc.value = desc or "正在处理..."
        self._processing_view.update()

    def _on_complete(self, result):
        from core.models import TaskResult, TaskStatus

        if isinstance(result, TaskResult) and result.status == TaskStatus.CANCELLED:
            return
        if isinstance(result, TaskResult):
            if result.status == TaskStatus.FAILED:
                text = ""
                ok = False
                self._result_title.value = "识别失败"
                self._result_title.color = c("danger", "fg")
                self._sum_status.value = "失败"
                self._sum_status.color = c("danger", "fg")
            else:
                # 优先从保存的 txt 读取
                text = ""
                if result.output_files:
                    self._output_file = result.output_files[0]
                    try:
                        text = self._output_file.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        text = ""
                ok = True
                self._result_title.value = "识别完成"
                self._result_title.color = c("ink", "fg")
                self._sum_status.value = "成功"
                self._sum_status.color = c("accent-fg", "fg")
        elif isinstance(result, dict):
            ok = True
            text = result.get("text", "")
            self._result_title.value = "识别完成"
            self._result_title.color = c("ink", "fg")
        else:
            ok = True
            text = str(result) if result else ""
            self._result_title.value = "识别完成"
            self._result_title.color = c("ink", "fg")
        self._result_icon.icon = ft.Icons.CHECK_ROUNDED if ok else ft.Icons.PRIORITY_HIGH_ROUNDED
        self._result_icon_box.bgcolor = c("accent") if ok else c("danger")
        self._last_ok = ok

        self._result_text_value = text
        # 失败时把完整原因（含安装指引）放进结果框，方便阅读和复制链接
        self._result_text.value = text if ok else (result.error_message or "识别失败")

        # 摘要
        lang_label = next((lg["label"] for lg in _LANGUAGES
                           if lg["key"] == self._language_value), "--")
        self._sum_lang.value = lang_label
        self._sum_chars.value = str(len(text))
        self._sum_paras.value = str(len([p for p in text.split("\n") if p.strip()]))

        history_service.save_task(
            "ocr", "recognize", result,
            input_desc=self._input_file.name if self._input_file else "",
        )
        self._show_complete()

    def _cancel(self) -> None:
        self._run_seq = getattr(self, "_run_seq", 0) + 1
        if self._task and not self._task.done():
            self._task.cancel()
        self._reset_to_workspace()

    def _reset(self) -> None:
        self._input_file = None
        self._output_file = None
        self._result_text_value = ""
        self._result_text.value = ""
        self._file_info_container.visible = False
        self._drop_zone_wrapper.height = 168
        self._run_btn.set_label("开始识别", enabled=False)
        self._reset_to_workspace()

    def _reset_to_workspace(self) -> None:
        self._workspace_view.visible = True
        self._processing_view.visible = False
        self._complete_view.visible = False
        self.update()
        self._run_btn.morph_idle()

    def _show_processing(self, file_label: str) -> None:
        self._progress_title.value = f"正在识别 {file_label}…"
        self._progress_pct.value = "0%"
        self._progress_bar.value = 0
        self._progress_desc.value = "初始化引擎…"
        self._workspace_view.visible = False
        self._processing_view.visible = True
        self._complete_view.visible = False
        self.update()
        self._run_btn.morph_loading()

    def _show_complete(self) -> None:
        self._workspace_view.visible = False
        self._processing_view.visible = False
        self._complete_view.visible = True
        self.update()
        self._run_btn.morph_result(getattr(self, "_last_ok", True), "识别失败")

    def _copy_result(self, _) -> None:
        if self._result_text.value:
            self._page.run_task(self._copy_async, self._result_text.value)

    async def _copy_async(self, text: str) -> None:
        # Flet 0.84 已移除 page.set_clipboard，改用 Clipboard 服务
        try:
            await ft.Clipboard().set(text)
            self._show_snack("已复制到剪贴板", kind="success")
        except Exception as e:
            self._show_snack(f"复制失败：{e}")

    def _save_result(self, _) -> None:
        if not self._result_text.value or not self._input_file:
            self._show_snack("无可保存的识别结果")
            return
        out_dir = settings_service.resolve_output_dir(self._input_file)
        out_path = self._output_file or out_dir / f"{self._input_file.stem}_ocr.txt"
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(self._result_text.value, encoding="utf-8")
            self._output_file = out_path
            self._show_snack(f"已保存到 {out_path}", kind="success")
        except OSError as exc:
            self._show_snack(f"保存失败：{exc}", kind="error")

    def _open_output_folder(self, _) -> None:
        target = self._output_file
        if not target or not target.exists():
            self._show_snack("输出文件不存在或尚未保存")
            return
        folder = target.parent
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(target)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _show_snack(self, msg: str, color: str | None = None, kind: str | None = None) -> None:
        show_toast(self._page, msg, color=color, kind=kind)
