"""图片处理中心 — 基于 Figma 设计稿 17:4715 的 1:1 复刻

布局：TopAppBar + 左侧主内容区（标题+拖拽区+图片网格） + 右侧参数面板
"""
import asyncio
from pathlib import Path

import flet as ft

from core.image.converter import convert_image
from core.image.compressor import compress_images
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


_FUNCTIONS = [
    {"label": "格式转换", "icon": ft.Icons.TRANSFORM, "key": "convert"},
    {"label": "批量压缩", "icon": ft.Icons.COMPRESS, "key": "compress"},
    {"label": "添加水印", "icon": ft.Icons.WATER_DROP_OUTLINED, "key": "watermark"},
    {"label": "批量重命名", "icon": ft.Icons.DRIVE_FILE_RENAME_OUTLINE, "key": "rename"},
]


class ImagePage(ft.Column):
    """图片处理中心 — 工作台布局"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._files: list[Path] = []
        self._selected_func = "convert"
        self._task: asyncio.Task | None = None

        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)

        # 格式选择
        self._format_dropdown = ft.Dropdown(
            value="webp",
            options=[
                ft.dropdown.Option("png", "PNG"),
                ft.dropdown.Option("jpg", "JPG"),
                ft.dropdown.Option("webp", "WebP"),
                ft.dropdown.Option("bmp", "BMP"),
            ],
            width=270,
            border_radius=12,
            bgcolor="#d5e3ff",
            border_color="transparent",
            text_size=14,
        )

        # 质量滑块
        self._quality_value = ft.Text(
            "85%", size=12, weight=ft.FontWeight.BOLD, color="#005f98",
        )
        self._quality_slider = ft.Slider(
            min=0, max=100, value=85, divisions=20,
            active_color="#005f98", inactive_color="#d5e3ff",
            on_change=self._on_quality_change,
            width=270,
        )

        # 文件列表
        self._file_grid = ft.Column(spacing=12)
        self._file_count = ft.Text(
            "已添加图片 (0)", size=18, color="#162f50", font_family="Manrope",
        )

        # 功能按钮
        self._func_btns = []
        for f in _FUNCTIONS:
            active = f["key"] == self._selected_func
            btn = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            f["icon"],
                            color="#ffffff" if active else "#455c7f",
                            size=16,
                        ),
                        ft.Text(
                            f["label"], size=12,
                            color="#ffffff" if active else "#455c7f",
                            font_family="Manrope",
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#005f98" if active else "#d5e3ff",
                border_radius=12,
                padding=ft.padding.symmetric(vertical=12, horizontal=20),
                on_click=lambda _, k=f["key"]: self._select_func(k),
                ink=True,
                data=f["key"],
                width=130,
                height=68,
                alignment=ft.Alignment(0, 0),
            )
            self._func_btns.append(btn)

        # 运行按钮
        self._run_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PLAY_ARROW, color="#ffffff", size=20),
                    ft.Text(
                        "开始处理 (0张图片)", size=18,
                        color="#ffffff", font_family="Manrope",
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#005f98",
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=["#005f98", "#2aa7ff"],
            ),
            border_radius=16,
            padding=ft.padding.symmetric(vertical=16),
            shadow=ft.BoxShadow(
                blur_radius=25, spread_radius=-5,
                color=ft.Colors.with_opacity(0.2, "#005f98"),
                offset=ft.Offset(0, 20),
            ),
            on_click=self._start_task,
            ink=True,
        )

        self.controls = [
            self._build_topbar(),
            ft.Row(
                controls=[
                    self._build_main_content(),
                    self._build_param_panel(),
                ],
                expand=True,
                spacing=0,
            ),
        ]

    # ── 顶部栏 ──────────────────────────────────────────
    def _build_topbar(self) -> ft.Control:
        tag_batch = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.2, "#00e3fd"),
            border_radius=9999,
            padding=ft.padding.symmetric(horizontal=12, vertical=4),
            content=ft.Text(
                "批量处理", size=10, color="#004d57",
                weight=ft.FontWeight.BOLD,
            ),
        )
        tag_compress = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.2, "#d9caff"),
            border_radius=9999,
            padding=ft.padding.symmetric(horizontal=12, vertical=4),
            content=ft.Text(
                "高效压缩", size=10, color="#5500cd",
                weight=ft.FontWeight.BOLD,
            ),
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "图片处理工具", size=20,
                        weight=ft.FontWeight.W_600,
                        color="#162f50", font_family="Manrope",
                    ),
                    ft.VerticalDivider(width=1, color="#e2e8f0"),
                    tag_batch,
                    tag_compress,
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.SEARCH, color="#94a3b8", size=15),
                                            ft.Container(
                                                content=ft.Text(
                                                    "搜索功能或指令...", size=13,
                                                    color="#94a3b8",
                                                ),
                                                padding=ft.padding.only(left=8),
                                                expand=True,
                                            ),
                                        ],
                                        spacing=0,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    width=288, height=36,
                                    bgcolor=ft.Colors.with_opacity(0.5, "#f8fafc"),
                                    border=ft.border.all(
                                        1, ft.Colors.with_opacity(0.6, "#e2e8f0"),
                                    ),
                                    border_radius=9999,
                                    padding=ft.padding.symmetric(horizontal=15),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                                    icon_color="#475569", icon_size=20,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SETTINGS_OUTLINED,
                                    icon_color="#475569", icon_size=20,
                                    on_click=lambda _: self._page.go("/settings"),
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=80,
            bgcolor=ft.Colors.with_opacity(0.8, "#ffffff"),
            blur=ft.Blur(12, 12),
            border=ft.border.only(
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.5, "#e2e8f0")),
            ),
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
            padding=ft.padding.only(left=40, right=24),
        )

    # ── 左侧主内容 ──────────────────────────────────────
    def _build_main_content(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    # 标题区
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "图片处理中心", size=30,
                                    weight=ft.FontWeight.W_500,
                                    color="#005f98", font_family="Manrope",
                                ),
                                ft.Text(
                                    "支持批量转换、压缩及水印处理，享受极致效率",
                                    size=16, color="#455c7f", font_family="Manrope",
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=ft.padding.only(left=32, right=32, top=32),
                    ),
                    # 拖拽区
                    self._build_drop_zone(),
                    # 图片网格
                    self._build_file_grid(),
                    # 进度/结果
                    ft.Container(
                        content=ft.Column(
                            controls=[self._progress, self._result],
                            spacing=8,
                        ),
                        padding=ft.padding.symmetric(horizontal=32),
                    ),
                ],
                spacing=24,
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
        )

    def _build_drop_zone(self) -> ft.Control:
        return ft.Container(
            content=ft.Stack(
                controls=[
                    # 渐变发光边框
                    ft.Container(
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment(-1, 0),
                            end=ft.Alignment(1, 0),
                            colors=["#005f98", "#6b1ef3"],
                        ),
                        border_radius=16,
                        opacity=0.1,
                        blur=ft.Blur(4, 4),
                        expand=True,
                    ),
                    # 主体
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.IMAGE, color="#2aa7ff", size=30,
                                    ),
                                    width=64, height=64,
                                    bgcolor=ft.Colors.with_opacity(0.2, "#2aa7ff"),
                                    border_radius=9999,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Text(
                                    "拖拽图片至此，或点击上传",
                                    size=20, color="#005f98",
                                    font_family="Manrope",
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    "支持 JPG, PNG, WEBP, HEIC 等多种主流格式",
                                    size=14, color="#455c7f",
                                    font_family="Manrope",
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Container(
                                    content=ft.Container(
                                        content=ft.Text(
                                            "选择本地文件", size=16,
                                            color="#ffffff", font_family="Manrope",
                                            text_align=ft.TextAlign.CENTER,
                                        ),
                                        bgcolor="#005f98",
                                        border_radius=9999,
                                        padding=ft.padding.symmetric(
                                            horizontal=24, vertical=8,
                                        ),
                                        shadow=ft.BoxShadow(
                                            blur_radius=15, spread_radius=-3,
                                            color=ft.Colors.with_opacity(0.3, "#005f98"),
                                            offset=ft.Offset(0, 10),
                                        ),
                                    ),
                                    padding=ft.padding.only(top=8),
                                    on_click=self._pick_files,
                                ),
                            ],
                            spacing=16,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor="#ffffff",
                        border=ft.border.all(2, "#2aa7ff"),
                        border_radius=16,
                        padding=ft.padding.symmetric(vertical=40, horizontal=2),
                        expand=True,
                    ),
                ],
            ),
            padding=ft.padding.symmetric(horizontal=32),
            height=220,
        )

    def _build_file_grid(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self._file_count,
                            ft.Container(expand=True),
                            ft.TextButton(
                                "清空列表",
                                style=ft.ButtonStyle(color="#005f98"),
                                on_click=self._clear_files,
                            ),
                        ],
                    ),
                    self._file_grid,
                ],
                spacing=16,
            ),
            padding=ft.padding.symmetric(horizontal=32),
        )

    # ── 右侧参数面板 ────────────────────────────────────
    def _build_param_panel(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    # 标题
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SETTINGS, color="#005f98", size=18),
                            ft.Text(
                                "参数设置", size=20,
                                color="#005f98", font_family="Manrope",
                            ),
                        ],
                        spacing=8,
                    ),
                    # 功能选择
                    self._section(
                        "选择功能",
                        ft.Row(
                            controls=self._func_btns,
                            wrap=True, spacing=8, run_spacing=8,
                        ),
                    ),
                    # 目标格式
                    self._section("目标格式", self._format_dropdown),
                    # 输出质量
                    self._section(
                        "输出质量",
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Container(expand=True),
                                        self._quality_value,
                                    ],
                                ),
                                self._quality_slider,
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            "体积优先", size=10, color="#455c7f",
                                        ),
                                        ft.Container(expand=True),
                                        ft.Text("均衡", size=10, color="#455c7f"),
                                        ft.Container(expand=True),
                                        ft.Text(
                                            "画质优先", size=10, color="#455c7f",
                                        ),
                                    ],
                                ),
                            ],
                            spacing=8,
                        ),
                    ),
                    # 弹性空间
                    ft.Container(expand=True),
                    # 处理按钮
                    self._run_btn,
                    ft.Text(
                        "预计耗时: 8秒 • 隐私保护已开启",
                        size=10, color="#455c7f", font_family="Manrope",
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=24,
                expand=True,
            ),
            width=320,
            bgcolor=ft.Colors.with_opacity(0.7, "#f4f6ff"),
            blur=ft.Blur(6, 6),
            border=ft.border.only(left=ft.BorderSide(1, "#d5e3ff")),
            padding=ft.padding.all(24),
        )

    def _section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(
            controls=[
                ft.Text(
                    label.upper(), size=12, color="#455c7f", font_family="Manrope",
                ),
                content,
            ],
            spacing=12,
        )

    # ── 事件处理 ──────────────────────────────────────────
    def _select_func(self, key: str) -> None:
        self._selected_func = key
        for btn in self._func_btns:
            active = btn.data == key
            btn.bgcolor = "#005f98" if active else "#d5e3ff"
            col = btn.content
            col.controls[0].color = "#ffffff" if active else "#455c7f"
            col.controls[1].color = "#ffffff" if active else "#455c7f"
        self.update()

    def _on_quality_change(self, e) -> None:
        self._quality_value.value = f"{int(e.control.value)}%"
        self._quality_value.update()

    def _pick_files(self, _) -> None:
        self._page.run_task(self._pick_files_async)

    async def _pick_files_async(self) -> None:
        picker = ft.FilePicker()
        self._page.overlay.append(picker)
        self._page.update()
        try:
            files = await picker.pick_files(
                dialog_title="选择图片文件",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=[
                    "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "heic",
                ],
                allow_multiple=True,
            )
        except RuntimeError:
            files = None
        finally:
            self._page.overlay.remove(picker)
        if not files:
            self._page.update()
            return
        paths = [Path(f.path) for f in files if f.path]
        if paths:
            self._files.extend(paths)
            self._rebuild_file_grid()
        self._page.update()

    def _rebuild_file_grid(self) -> None:
        self._file_grid.controls.clear()
        self._file_count.value = f"已添加图片 ({len(self._files)})"

        # 每行 4 张卡片
        row_items = []
        for f in self._files:
            try:
                size = f.stat().st_size
                size_str = (
                    f"{size / 1024:.1f} KB"
                    if size < 1024 * 1024
                    else f"{size / 1024 / 1024:.1f} MB"
                )
            except OSError:
                size_str = "?"

            # 根据扩展名选择占位色
            ext = f.suffix.lower().lstrip(".")
            color_map = {
                "png": "#dcfce7", "jpg": "#fef2f2", "jpeg": "#fef2f2",
                "webp": "#eff6ff", "bmp": "#faf5ff", "heic": "#fff7ed",
            }
            thumb_bg = color_map.get(ext, "#f1f5f9")

            card = ft.Container(
                content=ft.Column(
                    controls=[
                        # 缩略图占位
                        ft.Container(
                            content=ft.Icon(ft.Icons.IMAGE, color="#94a3b8", size=32),
                            height=100,
                            bgcolor=thumb_bg,
                            border_radius=ft.border_radius.only(
                                top_left=12, top_right=12,
                            ),
                            alignment=ft.Alignment(0, 0),
                        ),
                        # 文件信息
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text(
                                        f.name, size=12,
                                        weight=ft.FontWeight.W_500,
                                        color="#162f50", font_family="Manrope",
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        size_str, size=10, color="#455c7f",
                                    ),
                                ],
                                spacing=2,
                            ),
                            padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        ),
                    ],
                    spacing=0,
                ),
                bgcolor="#ffffff",
                border=ft.border.all(1, "#f1f5f9"),
                border_radius=12,
                shadow=ft.BoxShadow(
                    blur_radius=1,
                    color=ft.Colors.with_opacity(0.05, "#000000"),
                    offset=ft.Offset(0, 1),
                ),
                expand=True,
            )
            row_items.append(card)

        # 分行排列，每行 4 个
        for i in range(0, len(row_items), 4):
            chunk = row_items[i:i + 4]
            # 补齐空位
            while len(chunk) < 4:
                chunk.append(ft.Container(expand=True))
            self._file_grid.controls.append(ft.Row(spacing=12, controls=chunk))

        # 更新按钮文字
        row = self._run_btn.content
        row.controls[1].value = f"开始处理 ({len(self._files)}张图片)"
        self.update()

    def _clear_files(self, _) -> None:
        self._files.clear()
        self._rebuild_file_grid()

    def _start_task(self, _) -> None:
        if not self._files:
            return
        out_dir = settings_service.resolve_output_dir(self._files[0])
        func = self._selected_func
        quality = int(self._quality_slider.value)

        if func == "convert":
            kwargs = {
                "input_files": self._files,
                "output_dir": out_dir,
                "target_format": self._format_dropdown.value,
                "quality": quality,
            }
            fn = convert_image
            desc = "正在转换..."
        elif func == "compress":
            level_map = {range(0, 34): "high", range(34, 67): "medium", range(67, 101): "low"}
            level = "medium"
            for r, l in level_map.items():
                if quality in r:
                    level = l
                    break
            kwargs = {
                "input_files": self._files,
                "output_dir": out_dir,
                "level": level,
            }
            fn = compress_images
            desc = "正在压缩..."
        else:
            # 水印和重命名跳转到子页面
            route = f"/image/{func}"
            self._page.go(route)
            return

        self._progress.show(f"{len(self._files)} 张图片", desc)
        self._result.hide()

        async def _run():
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, c, t, d):
        self._progress.update_progress(c, t, d)

    def _on_complete(self, result):
        self._progress.hide()
        self._result.show(result, "处理完成！")
        history_service.save_task(
            "image", self._selected_func, result,
            input_desc=f"{len(self._files)} 张图片",
        )

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress.hide()

    def _reset(self) -> None:
        self._files.clear()
        self._rebuild_file_grid()
