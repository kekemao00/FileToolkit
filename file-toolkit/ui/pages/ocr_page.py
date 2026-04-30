"""OCR 文字识别 — 基于 Figma 设计稿 1:1395 的 1:1 复刻

布局：顶部栏 + 标题区（GPU徽章） + 精致拖拽区 + Bento Grid 结果区
"""
import asyncio
from pathlib import Path

import flet as ft

from core.ocr.client import recognize
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.top_bar import TopBar


class OcrPage(ft.Column):
    """OCR 文字识别 — Figma 风格"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._input_file: Path | None = None
        self._task: asyncio.Task | None = None

        # 语言选择
        self._lang_dropdown = ft.Dropdown(
            value="chi_sim",
            options=[
                ft.dropdown.Option("chi_sim", "简体中文"),
                ft.dropdown.Option("eng", "English"),
                ft.dropdown.Option("chi_sim+eng", "中英混合"),
                ft.dropdown.Option("jpn", "日本語"),
            ],
            width=180,
            border_radius=12,
            bgcolor="#d5e3ff",
            border_color="transparent",
            text_size=14,
        )

        # 结果文本
        self._result_text = ft.TextField(
            multiline=True,
            min_lines=12,
            max_lines=20,
            read_only=False,
            border_radius=12,
            border_color="#e2e8f0",
            visible=False,
            text_size=14,
            color="#162f50",
        )

        # 进度条
        self._progress_container = ft.Container(visible=False)
        self._progress_text = ft.Text("", size=13, color="#455c7f")
        self._progress_bar = ft.ProgressBar(
            color="#005f98", bgcolor="#d5e3ff", width=500,
        )

        # 结果区
        self._result_section = ft.Container(visible=False)

        # 文件名显示
        self._file_name = ft.Text("", size=14, color="#162f50", font_family="Manrope")
        self._file_info = ft.Container(visible=False)

        self.controls = [
            TopBar(page),
            self._build_content(),
        ]

    # ── 整体内容 ──────────────────────────────────────────
    def _build_content(self) -> ft.Control:
        return ft.Container(
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack(
                expand=True,
                controls=[
                    # 装饰性模糊圆
                    ft.Container(
                        width=400, height=400,
                        border_radius=9999,
                        bgcolor=ft.Colors.with_opacity(0.06, "#0891b2"),
                        blur=50,
                        right=-100, top=-100,
                    ),
                    ft.Container(
                        width=300, height=300,
                        border_radius=9999,
                        bgcolor=ft.Colors.with_opacity(0.06, "#6b1ef3"),
                        blur=40,
                        left=-50, bottom=-80,
                    ),
                    # 主内容
                    ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        spacing=0,
                        controls=[
                            self._build_header_section(),
                            self._build_drop_zone(),
                            self._build_file_info(),
                            self._build_progress_section(),
                            self._build_result_area(),
                        ],
                    ),
                ],
            ),
        )

    # ── 标题区 ────────────────────────────────────────────
    def _build_header_section(self) -> ft.Control:
        gpu_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.MEMORY, color="#006571", size=12),
                    ft.Text(
                        "GPU 加速已就绪", size=10, color="#006571",
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.2, "#00e3fd"),
            border_radius=9999,
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
        )

        return ft.Container(
            padding=ft.padding.only(left=48, right=48, top=40, bottom=8),
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                "OCR 文字识别", size=28,
                                weight=ft.FontWeight.W_500,
                                color="#162f50", font_family="Manrope",
                            ),
                            ft.Text(
                                "高精度光学字符识别引擎",
                                size=16, color="#455c7f", font_family="Manrope",
                            ),
                        ],
                        spacing=4,
                    ),
                    ft.Container(expand=True),
                    gpu_badge,
                    ft.Container(width=16),
                    # 语言选择
                    ft.Column(
                        controls=[
                            ft.Text(
                                "识别语言", size=11, color="#455c7f",
                                weight=ft.FontWeight.BOLD,
                            ),
                            self._lang_dropdown,
                        ],
                        spacing=4,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
        )

    # ── 拖拽区 ────────────────────────────────────────────
    def _build_drop_zone(self) -> ft.Control:
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=48, vertical=24),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.DOCUMENT_SCANNER, color="#0891b2", size=32,
                            ),
                            width=64, height=64,
                            bgcolor=ft.Colors.with_opacity(0.15, "#0891b2"),
                            border_radius=9999,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(
                            "拖放文件或点击扫描", size=20,
                            color="#162f50", font_family="Manrope",
                            weight=ft.FontWeight.W_500,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "支持 JPG, PNG, PDF 格式 (最大 20MB)",
                            size=13, color="#455c7f", font_family="Manrope",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(
                            content=ft.Container(
                                content=ft.Text(
                                    "选择文件", size=15,
                                    color="#ffffff", font_family="Manrope",
                                ),
                                bgcolor="#005f98",
                                border_radius=12,
                                padding=ft.padding.symmetric(horizontal=28, vertical=10),
                                shadow=ft.BoxShadow(
                                    blur_radius=15, spread_radius=-3,
                                    color=ft.Colors.with_opacity(0.3, "#005f98"),
                                    offset=ft.Offset(0, 10),
                                ),
                            ),
                            on_click=self._pick_file,
                            padding=ft.padding.only(top=8),
                        ),
                    ],
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                bgcolor="#ffffff",
                border=ft.border.all(2, ft.Colors.with_opacity(0.3, "#0891b2")),
                border_radius=20,
                padding=ft.padding.symmetric(vertical=40),
                shadow=ft.BoxShadow(
                    blur_radius=1,
                    color=ft.Colors.with_opacity(0.05, "#000000"),
                    offset=ft.Offset(0, 1),
                ),
            ),
        )

    # ── 文件信息 ──────────────────────────────────────────
    def _build_file_info(self) -> ft.Control:
        self._file_info = ft.Container(
            visible=False,
            padding=ft.padding.symmetric(horizontal=48),
            content=ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.INSERT_DRIVE_FILE, color="#0891b2", size=18,
                            ),
                            width=36, height=36,
                            bgcolor=ft.Colors.with_opacity(0.15, "#0891b2"),
                            border_radius=10,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(
                            controls=[
                                self._file_name,
                                ft.Text(
                                    "准备识别", size=11, color="#455c7f",
                                ),
                            ],
                            spacing=2, tight=True, expand=True,
                        ),
                        ft.Container(
                            content=ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.DOCUMENT_SCANNER,
                                            color="#ffffff", size=14,
                                        ),
                                        ft.Text(
                                            "开始识别", size=14,
                                            color="#ffffff", font_family="Manrope",
                                        ),
                                    ],
                                    spacing=8,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                bgcolor="#005f98",
                                border_radius=12,
                                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                                shadow=ft.BoxShadow(
                                    blur_radius=10, spread_radius=-2,
                                    color=ft.Colors.with_opacity(0.2, "#005f98"),
                                    offset=ft.Offset(0, 4),
                                ),
                            ),
                            on_click=self._start_task,
                        ),
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#ffffff",
                border_radius=16,
                padding=ft.padding.all(16),
                shadow=ft.BoxShadow(
                    blur_radius=1,
                    color=ft.Colors.with_opacity(0.05, "#000000"),
                    offset=ft.Offset(0, 1),
                ),
            ),
        )
        return self._file_info

    # ── 进度区 ────────────────────────────────────────────
    def _build_progress_section(self) -> ft.Control:
        self._progress_container = ft.Container(
            visible=False,
            padding=ft.padding.symmetric(horizontal=48, vertical=16),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.HOURGLASS_TOP,
                                        color="#005f98", size=18,
                                    ),
                                    width=36, height=36,
                                    bgcolor=ft.Colors.with_opacity(0.15, "#005f98"),
                                    border_radius=10,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "正在识别...", size=16,
                                            weight=ft.FontWeight.W_500,
                                            color="#162f50", font_family="Manrope",
                                        ),
                                        self._progress_text,
                                    ],
                                    spacing=2, tight=True, expand=True,
                                ),
                            ],
                            spacing=16,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        self._progress_bar,
                    ],
                    spacing=16,
                ),
                bgcolor=ft.Colors.with_opacity(0.7, "#ffffff"),
                blur=ft.Blur(8, 8),
                border_radius=16,
                padding=ft.padding.all(20),
                border=ft.border.all(1, "#ffffff"),
                shadow=ft.BoxShadow(
                    blur_radius=20, spread_radius=-5,
                    color=ft.Colors.with_opacity(0.08, "#005f98"),
                    offset=ft.Offset(0, 10),
                ),
            ),
        )
        return self._progress_container

    # ── 结果区（Bento Grid） ─────────────────────────────
    def _build_result_area(self) -> ft.Control:
        self._result_section = ft.Container(
            visible=False,
            padding=ft.padding.only(left=48, right=48, top=16, bottom=40),
            content=ft.Row(
                controls=[
                    # 左侧：识别文本
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.TEXT_SNIPPET,
                                            color="#005f98", size=18,
                                        ),
                                        ft.Text(
                                            "识别结果", size=16,
                                            weight=ft.FontWeight.W_600,
                                            color="#162f50", font_family="Manrope",
                                        ),
                                        ft.Container(expand=True),
                                        ft.Container(
                                            content=ft.Row(
                                                controls=[
                                                    ft.Icon(
                                                        ft.Icons.COPY,
                                                        color="#005f98", size=14,
                                                    ),
                                                    ft.Text(
                                                        "复制", size=12,
                                                        color="#005f98",
                                                    ),
                                                ],
                                                spacing=4,
                                            ),
                                            on_click=self._copy_result,
                                            ink=True,
                                            border_radius=8,
                                            padding=ft.padding.symmetric(
                                                horizontal=12, vertical=6,
                                            ),
                                        ),
                                        ft.Container(
                                            content=ft.Row(
                                                controls=[
                                                    ft.Icon(
                                                        ft.Icons.SAVE_ALT,
                                                        color="#005f98", size=14,
                                                    ),
                                                    ft.Text(
                                                        "保存 TXT", size=12,
                                                        color="#005f98",
                                                    ),
                                                ],
                                                spacing=4,
                                            ),
                                            on_click=self._save_result,
                                            ink=True,
                                            border_radius=8,
                                            padding=ft.padding.symmetric(
                                                horizontal=12, vertical=6,
                                            ),
                                        ),
                                    ],
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Divider(height=1, color="#e2e8f0"),
                                self._result_text,
                            ],
                            spacing=12,
                        ),
                        bgcolor="#ffffff",
                        border_radius=20,
                        padding=ft.padding.all(24),
                        shadow=ft.BoxShadow(
                            blur_radius=1,
                            color=ft.Colors.with_opacity(0.05, "#000000"),
                            offset=ft.Offset(0, 1),
                        ),
                        expand=2,
                    ),
                    # 右侧：摘要面板
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "文档摘要", size=16,
                                    weight=ft.FontWeight.W_600,
                                    color="#162f50", font_family="Manrope",
                                ),
                                ft.Divider(height=1, color="#e2e8f0"),
                                self._build_summary_row(
                                    "识别语言", "简体中文",
                                ),
                                self._build_summary_row("字符数", "--"),
                                self._build_summary_row("段落数", "--"),
                                self._build_summary_row("置信度", "--"),
                                ft.Container(expand=True),
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.DOWNLOAD,
                                                color="#ffffff", size=16,
                                            ),
                                            ft.Text(
                                                "导出为 Word", size=14,
                                                color="#ffffff",
                                                font_family="Manrope",
                                            ),
                                        ],
                                        spacing=8,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                    ),
                                    bgcolor="#005f98",
                                    border_radius=12,
                                    padding=ft.padding.symmetric(vertical=12),
                                    shadow=ft.BoxShadow(
                                        blur_radius=10, spread_radius=-2,
                                        color=ft.Colors.with_opacity(0.2, "#005f98"),
                                        offset=ft.Offset(0, 4),
                                    ),
                                    ink=True,
                                ),
                            ],
                            spacing=12,
                        ),
                        bgcolor="#ffffff",
                        border_radius=20,
                        padding=ft.padding.all(24),
                        shadow=ft.BoxShadow(
                            blur_radius=1,
                            color=ft.Colors.with_opacity(0.05, "#000000"),
                            offset=ft.Offset(0, 1),
                        ),
                        expand=1,
                    ),
                ],
                spacing=24,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        )
        return self._result_section

    def _build_summary_row(self, label: str, value: str) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(label, size=13, color="#455c7f", font_family="Manrope"),
                    ft.Container(expand=True),
                    ft.Text(
                        value, size=13, color="#162f50",
                        weight=ft.FontWeight.W_500, font_family="Manrope",
                    ),
                ],
            ),
            padding=ft.padding.symmetric(vertical=8),
            border=ft.border.only(
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.3, "#e2e8f0")),
            ),
        )

    # ── 事件处理 ──────────────────────────────────────────
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
                allowed_extensions=["png", "jpg", "jpeg", "bmp", "tiff", "pdf"],
                allow_multiple=False,
            )
        except RuntimeError:
            files = None
        if not files:
            self._page.update()
            return
        paths = [Path(f.path) for f in files if f.path]
        if paths:
            self._input_file = paths[0]
            self._file_name.value = self._input_file.name
            self._file_info.visible = True
            self._result_section.visible = False
            self._result_text.visible = False
        self._page.update()

    def _start_task(self, _) -> None:
        if not self._input_file:
            return
        kwargs = {
            "input_file": self._input_file,
            "language": self._lang_dropdown.value,
        }
        self._progress_container.visible = True
        self._progress_text.value = f"正在处理 {self._input_file.name}..."
        self._result_section.visible = False
        self._result_text.visible = False
        self.update()

        async def _run():
            await run_task(recognize, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, current, total, desc):
        if total > 0:
            self._progress_bar.value = current / total
        self._progress_text.value = desc or "正在处理..."
        self._progress_container.update()

    def _on_complete(self, result):
        self._progress_container.visible = False

        # 从 TaskResult 读取识别文本（存储在输出的 .txt 文件中）
        from core.models import TaskResult
        if isinstance(result, TaskResult):
            if result.failed:
                text = result.error_message or "识别失败"
            elif result.output_files:
                try:
                    text = result.output_files[0].read_text(encoding="utf-8")
                except Exception:
                    text = ""
            else:
                text = ""
        elif isinstance(result, dict):
            text = result.get("text", "")
        else:
            text = str(result)

        self._result_text.value = text
        self._result_text.visible = True
        self._result_section.visible = True

        # 更新摘要
        char_count = len(text)
        para_count = len([p for p in text.split("\n") if p.strip()])
        summary_col = self._result_section.content.controls[1].content
        summary_col.controls[3].content.controls[1].value = str(char_count)
        summary_col.controls[4].content.controls[1].value = str(para_count)

        self.update()
        history_service.save_task(
            "ocr", "recognize", result,
            input_desc=self._input_file.name if self._input_file else "",
        )

    def _copy_result(self, _) -> None:
        if self._result_text.value:
            self._page.set_clipboard(self._result_text.value)
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text("已复制到剪贴板"), bgcolor="#005f98",
            )
            self._page.snack_bar.open = True
            self._page.update()

    def _save_result(self, _) -> None:
        if not self._result_text.value or not self._input_file:
            return
        out_dir = settings_service.resolve_output_dir(self._input_file)
        out_path = out_dir / f"{self._input_file.stem}_ocr.txt"
        out_path.write_text(self._result_text.value, encoding="utf-8")
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text(f"已保存到 {out_path}"), bgcolor="#005f98",
        )
        self._page.snack_bar.open = True
        self._page.update()
