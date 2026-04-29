"""压缩解压页 — 基于 Figma 设计稿 1:1155 的工作区布局"""
import asyncio
from pathlib import Path

import flet as ft

from core.archive.handler import compress, extract
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.drop_zone import DropZone
from ui.components.progress_card import ProgressCard
from ui.components.result_card import ResultCard


# 特性卡片数据
_FEATURES = [
    {
        "icon": ft.Icons.LOCK_OUTLINE,
        "icon_bg": ft.Colors.with_opacity(0.3, "#2aa7ff"),
        "title": "本地处理",
        "desc": "隐私安全，文件不上传",
    },
    {
        "icon": ft.Icons.SPEED,
        "icon_bg": ft.Colors.with_opacity(0.3, "#d9caff"),
        "title": "多线程加速",
        "desc": "最高提升 400% 效率",
    },
    {
        "icon": ft.Icons.HISTORY,
        "icon_bg": ft.Colors.with_opacity(0.3, "#00e3fd"),
        "title": "处理历史",
        "desc": "随时找回最近记录",
    },
]


class ArchivePage(ft.Column):
    """压缩解压：工作区布局（左侧拖拽 + 右侧配置面板）"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._task: asyncio.Task | None = None
        self._input_files: list[Path] = []
        self._extract_file: Path | None = None

        # 当前模式：compress / extract
        self._mode = "compress"

        # 格式选择状态
        self._selected_format = "zip"

        # 固实压缩开关
        self._solid_enabled = True

        # 密码输入
        self._password_field = ft.TextField(
            hint_text="输入访问密码",
            hint_style=ft.TextStyle(color="#6b7280", size=14),
            border=ft.InputBorder.NONE,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=16),
            password=True,
            can_reveal_password=True,
        )

        # 分卷大小
        self._volume_field = ft.TextField(
            hint_text="输入分卷大小",
            hint_style=ft.TextStyle(color="#6b7280", size=14),
            border=ft.InputBorder.NONE,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=16),
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        # 拖拽区
        self._drop_zone = DropZone(
            label="点击或将文件拖拽至此处",
            sublabel="支持 ZIP, 7Z, RAR, TAR.GZ 等主流压缩格式\n(单文件上限 2GB)",
            on_files_selected=self._on_files_selected,
            allow_multiple=True,
            icon=ft.Icons.FOLDER_ZIP,
        )
        self._drop_zone.set_page(page)

        # 进度 & 结果
        self._progress = ProgressCard(on_cancel=self._cancel)
        self._result = ResultCard(on_reset=self._reset)

        self.controls = [self._build_content()]

    # ── 整体内容 ──────────────────────────────────────
    def _build_content(self) -> ft.Control:
        return ft.Container(
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack(
                expand=True,
                controls=[
                    # 装饰性模糊圆
                    ft.Container(
                        width=512, height=409,
                        border_radius=9999,
                        bgcolor=ft.Colors.with_opacity(0.1, "#2aa7ff"),
                        blur=60,
                        right=-128, top=-102,
                    ),
                    ft.Container(
                        width=384, height=307,
                        border_radius=9999,
                        bgcolor=ft.Colors.with_opacity(0.1, "#6b1ef3"),
                        blur=50,
                        left=128, bottom=-102,
                    ),
                    # 主内容
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            self._build_workspace(),
                        ],
                    ),
                ],
            ),
        )

    # ── 工作区（左右分栏） ─────────────────────────────
    def _build_workspace(self) -> ft.Control:
        return ft.Container(
            expand=True,
            padding=ft.padding.all(40),
            content=ft.Row(
                expand=True,
                spacing=32,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    # 左侧主区域
                    ft.Container(
                        expand=2,
                        content=ft.Column(
                            spacing=24,
                            controls=[
                                self._build_left_header(),
                                self._build_drop_area(),
                                self._build_features(),
                                self._progress,
                                self._result,
                            ],
                        ),
                    ),
                    # 右侧配置面板
                    ft.Container(
                        expand=1,
                        content=self._build_config_panel(),
                    ),
                ],
            ),
        )

    # ── 左侧标题栏 ───────────────────────────────────
    def _build_left_header(self) -> ft.Control:
        # 标签
        tag_fast = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.2, "#00e3fd"),
            border_radius=9999,
            padding=ft.padding.symmetric(horizontal=12, vertical=4),
            content=ft.Text(
                "极速模式", size=10, color="#004d57",
                weight=ft.FontWeight.BOLD,
            ),
        )
        tag_encrypt = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.2, "#d9caff"),
            border_radius=9999,
            padding=ft.padding.symmetric(horizontal=12, vertical=4),
            content=ft.Text(
                "端到端加密", size=10, color="#5500cd",
                weight=ft.FontWeight.BOLD,
            ),
        )

        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.END,
            controls=[
                ft.Column(
                    spacing=4,
                    controls=[
                        ft.Text(
                            "压缩解压", size=24,
                            weight=ft.FontWeight.BOLD,
                            color="#162f50",
                        ),
                        ft.Text(
                            "极速无损压缩，主流格式一键互转",
                            size=14, color="#455c7f",
                        ),
                    ],
                ),
                ft.Row(spacing=8, controls=[tag_fast, tag_encrypt]),
            ],
        )

    # ── 拖拽区域 ──────────────────────────────────────
    def _build_drop_area(self) -> ft.Control:
        return self._drop_zone

    # ── 特性卡片 ──────────────────────────────────────
    def _build_features(self) -> ft.Control:
        cards = []
        for feat in _FEATURES:
            card = ft.Container(
                expand=True,
                height=74,
                bgcolor="#ffffff",
                border=ft.border.all(1, "#f1f5f9"),
                border_radius=16,
                padding=17,
                shadow=ft.BoxShadow(
                    blur_radius=1,
                    color=ft.Colors.with_opacity(0.05, "#000000"),
                    offset=ft.Offset(0, 1),
                ),
                content=ft.Row(
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=40, height=40,
                            border_radius=12,
                            bgcolor=feat["icon_bg"],
                            alignment=ft.Alignment(0, 0),
                            content=ft.Icon(feat["icon"], size=16, color="#162f50"),
                        ),
                        ft.Column(
                            spacing=0,
                            controls=[
                                ft.Text(
                                    feat["title"], size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color="#162f50",
                                ),
                                ft.Text(
                                    feat["desc"], size=10,
                                    color="#455c7f",
                                ),
                            ],
                        ),
                    ],
                ),
            )
            cards.append(card)

        return ft.Row(spacing=24, controls=cards)

    # ── 右侧配置面板 ─────────────────────────────────
    def _build_config_panel(self) -> ft.Control:
        return ft.Container(
            bgcolor="#ffffff",
            border=ft.border.all(1, "#f1f5f9"),
            border_radius=32,
            padding=33,
            shadow=ft.BoxShadow(
                blur_radius=1,
                color=ft.Colors.with_opacity(0.05, "#000000"),
                offset=ft.Offset(0, 1),
            ),
            content=ft.Column(
                spacing=32,
                controls=[
                    # 标题
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.SETTINGS, color="#162f50", size=20),
                            ft.Text(
                                "处理配置", size=18,
                                weight=ft.FontWeight.BOLD,
                                color="#162f50",
                            ),
                        ],
                    ),
                    # 压缩格式
                    self._build_format_selector(),
                    # 加密设置
                    self._build_password_section(),
                    # 分卷压缩
                    self._build_volume_section(),
                    # 固实压缩开关
                    self._build_solid_toggle(),
                    # 执行按钮
                    ft.Container(expand=True),
                    self._build_execute_button(),
                ],
            ),
        )

    def _build_format_selector(self) -> ft.Control:
        formats = ["ZIP", "7Z", "TAR.GZ"]
        buttons = []
        for fmt in formats:
            key = fmt.lower().replace(".", "")
            is_active = self._selected_format == key
            btn = ft.Container(
                expand=True,
                height=44,
                border_radius=12,
                bgcolor="#005f98" if is_active else "#f8fafc",
                alignment=ft.Alignment(0, 0),
                ink=True,
                on_click=lambda _, f=key: self._select_format(f),
                shadow=ft.BoxShadow(
                    blur_radius=6, spread_radius=-1,
                    color=ft.Colors.with_opacity(0.2, "#005f98"),
                    offset=ft.Offset(0, 4),
                ) if is_active else None,
                content=ft.Text(
                    fmt, size=14,
                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500,
                    color="#ffffff" if is_active else "#455c7f",
                    text_align=ft.TextAlign.CENTER,
                ),
            )
            buttons.append(btn)

        return ft.Column(
            spacing=0,
            controls=[
                ft.Text(
                    "压缩格式", size=11, color="#455c7f",
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=12),
                ft.Row(spacing=8, controls=buttons),
            ],
        )

    def _build_password_section(self) -> ft.Control:
        return ft.Column(
            spacing=0,
            controls=[
                ft.Text(
                    "加密设置 (可选)", size=11, color="#455c7f",
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=12),
                ft.Container(
                    bgcolor="#f8fafc",
                    border_radius=12,
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                padding=ft.padding.only(left=16),
                                content=ft.Icon(ft.Icons.LOCK_OUTLINE, size=16, color="#6b7280"),
                            ),
                            ft.Container(expand=True, content=self._password_field),
                        ],
                    ),
                ),
            ],
        )

    def _build_volume_section(self) -> ft.Control:
        return ft.Column(
            spacing=0,
            controls=[
                ft.Text(
                    "分卷压缩", size=11, color="#455c7f",
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=12),
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Container(
                            expand=True,
                            bgcolor="#f8fafc",
                            border_radius=12,
                            height=52,
                            content=self._volume_field,
                        ),
                        ft.Container(
                            bgcolor="#f1f5f9",
                            border_radius=12,
                            padding=ft.padding.symmetric(horizontal=20, vertical=16),
                            content=ft.Text(
                                "MB", size=14, color="#005f98",
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                    ],
                ),
                ft.Container(height=4),
                ft.Text(
                    "设置为 0 或留空则不分卷",
                    size=10,
                    color=ft.Colors.with_opacity(0.6, "#455c7f"),
                ),
            ],
        )

    def _build_solid_toggle(self) -> ft.Control:
        self._solid_switch = ft.Switch(
            value=self._solid_enabled,
            active_color="#005f98",
            on_change=self._on_solid_change,
        )

        return ft.Container(
            border=ft.border.only(top=ft.BorderSide(1, "#f8fafc")),
            padding=ft.padding.only(top=25),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Text(
                                "启用固实压缩", size=14, color="#162f50",
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=12, color="#455c7f"),
                        ],
                    ),
                    self._solid_switch,
                ],
            ),
        )

    def _build_execute_button(self) -> ft.Control:
        return ft.Column(
            spacing=20,
            controls=[
                ft.Container(
                    width=float("inf"),
                    border_radius=16,
                    bgcolor="#005f98",
                    padding=ft.padding.symmetric(vertical=20),
                    ink=True,
                    on_click=self._start_task,
                    shadow=ft.BoxShadow(
                        blur_radius=30, spread_radius=-5,
                        color=ft.Colors.with_opacity(0.4, "#005f98"),
                        offset=ft.Offset(0, 15),
                    ),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Text(
                                "执行压缩任务", size=18,
                                weight=ft.FontWeight.BOLD,
                                color="#ffffff",
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Icon(ft.Icons.ARROW_FORWARD, color="#ffffff", size=16),
                        ],
                    ),
                ),
                ft.Text(
                    '任务完成后文件将保存至"我的文件"或默认\n下载目录。',
                    size=10,
                    color=ft.Colors.with_opacity(0.7, "#455c7f"),
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
        )

    # ── 事件处理 ──────────────────────────────────────
    def _select_format(self, fmt: str) -> None:
        self._selected_format = fmt
        # 重建整个内容以刷新格式选择器状态
        self.controls = [self._build_content()]
        self.update()

    def _on_solid_change(self, e) -> None:
        self._solid_enabled = e.control.value

    def _on_files_selected(self, paths: list[Path]) -> None:
        if paths:
            # 判断是压缩包还是普通文件
            archive_exts = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz"}
            first_ext = paths[0].suffix.lower()
            if len(paths) == 1 and first_ext in archive_exts:
                self._mode = "extract"
                self._extract_file = paths[0]
            else:
                self._mode = "compress"
                self._input_files = paths

    def _start_task(self, _) -> None:
        if self._mode == "compress":
            self._start_compress()
        else:
            self._start_extract()

    def _start_compress(self) -> None:
        if not self._input_files:
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text("请先选择要压缩的文件"),
                bgcolor="#005f98",
            )
            self._page.snack_bar.open = True
            self._page.update()
            return

        out_dir = settings_service.resolve_output_dir(self._input_files[0])
        fmt_map = {"zip": "zip", "7z": "7z", "targz": "tar.gz"}
        kwargs = {
            "input_files": self._input_files,
            "output_dir": out_dir,
            "format": fmt_map.get(self._selected_format, "zip"),
        }
        self._result.hide()
        self._progress.show(f"{len(self._input_files)} 个文件", "正在压缩...")

        async def _run():
            await run_task(compress, kwargs, self._on_progress, self._on_complete_compress)
        self._task = self._page.run_task(_run)

    def _start_extract(self) -> None:
        if not self._extract_file:
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text("请先选择要解压的文件"),
                bgcolor="#005f98",
            )
            self._page.snack_bar.open = True
            self._page.update()
            return

        out_dir = settings_service.resolve_output_dir(self._extract_file)
        kwargs = {"input_file": self._extract_file, "output_dir": out_dir}
        self._result.hide()
        self._progress.show(self._extract_file.name, "正在解压...")

        async def _run():
            await run_task(extract, kwargs, self._on_progress, self._on_complete_extract)
        self._task = self._page.run_task(_run)

    def _on_progress(self, current, total, desc):
        self._progress.update_progress(current, total, desc)

    def _on_complete_compress(self, result):
        self._progress.hide()
        self._result.show(result, "压缩完成！")
        history_service.save_task("archive", "compress", result,
                                 input_desc=f"{len(self._input_files)} 个文件")

    def _on_complete_extract(self, result):
        self._progress.hide()
        self._result.show(result, "解压完成！")
        history_service.save_task("archive", "extract", result,
                                 input_desc=self._extract_file.name if self._extract_file else "")

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._progress.hide()

    def _reset(self) -> None:
        self._input_files.clear()
        self._extract_file = None
        self._drop_zone.clear()
        self._drop_zone.update()
