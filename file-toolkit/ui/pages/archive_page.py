"""压缩解压中心

布局：左侧主内容区（标题 + 选择文件区 + 文件卡片网格） + 右侧参数面板（白色卡片）
三视图互斥切换（工作区 / 处理中 / 完成），外观与 ui/components/workbench.py 一致。
"""
import asyncio
import subprocess
import sys
import time
from pathlib import Path

import flet as ft

from core.archive.handler import compress, extract
from core.models import TaskResult, TaskStatus
from services import history_service, settings_service
from services.task_service import run_task
from ui import style as s
from ui.components.top_bar import TopBar
from ui.palette import c
from ui.utils import notify_task_done, show_toast

_FUNCTIONS = [
    {"label": "ZIP 压缩", "desc": "通用兼容格式", "icon": ft.Icons.FOLDER_ZIP_OUTLINED,
     "key": "compress_zip"},
    {"label": "7Z 压缩", "desc": "高压缩比", "icon": ft.Icons.INVENTORY_2_OUTLINED,
     "key": "compress_7z"},
    {"label": "TAR.GZ", "desc": "Linux 常用", "icon": ft.Icons.ARCHIVE_OUTLINED,
     "key": "compress_targz"},
    {"label": "解压", "desc": "ZIP/7Z/RAR/TAR", "icon": ft.Icons.UNARCHIVE_OUTLINED,
     "key": "extract"},
]

_ARCHIVE_EXTS = {"zip", "7z", "rar", "tar", "gz", "bz2", "xz", "tgz"}


class ArchivePage(ft.Column):
    """压缩解压中心 — 工作台布局"""

    def __init__(self, page: ft.Page, initial_func: str | None = None) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._files: list[Path] = []
        self._selected_func = initial_func if initial_func in ("compress_zip", "compress_7z", "compress_targz", "extract") else "compress_zip"
        self._task: asyncio.Task | None = None
        self._output_dir: Path | None = None

        # 处理中状态组件
        self._progress_title = s.text(kind="title")
        self._progress_pct = s.text("0%", "mono", color="ink")
        self._progress_bar = ft.ProgressBar(
            value=0, color=c("ink"), bgcolor=c("surface-3"), bar_height=4, border_radius=2,
        )
        self._progress_file_rows = ft.Column(spacing=6)
        self._progress_cancel_btn = s.button("全部取消", lambda _: self._cancel(), kind="secondary")

        # 完成状态组件
        self._result_title = s.text(kind="title", expand=True)
        self._result_file_rows = ft.Column(spacing=6)
        self._result_open_btn = s.button("打开文件夹", self._open_output_folder,
                                         icon=ft.Icons.FOLDER_OPEN_OUTLINED)
        self._result_reset_btn = s.button("继续处理", lambda _: self._reset(), kind="secondary")

        # 密码输入（加密可选）
        self._password_field = s.text_field(
            hint="访问密码（可选）", expand=True, password=True, can_reveal_password=True,
        )

        # 分卷大小（MB，可选）
        self._volume_field = s.text_field(
            hint="分卷大小 MB（留空不分卷）", expand=True, keyboard_type=ft.KeyboardType.NUMBER,
        )

        # 固实压缩开关（仅视觉占位，当前后端未实现）
        self._solid_enabled = ft.Switch(value=False, tooltip="固实压缩暂未开启")

        # 文件列表（卡片网格）
        self._file_list = ft.Row(
            controls=[],
            wrap=True,
            spacing=10,
            run_spacing=10,
        )
        self._file_count = s.text("待处理文件 (0)", "title")

        # 运行按钮（会变形：按钮 → 加载圆 → 对勾 / 错误）
        self._run_btn = s.MorphButton(self._start_task, label="立即处理 (0个文件)")
        self._run_btn.set_label("立即处理 (0个文件)", enabled=False)

        # 功能卡片（2×2 网格）：选中态是强调色描边 + 浅底
        self._func_btns = []
        for f in _FUNCTIONS:
            btn = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(f["icon"], size=16),
                        s.text(f["label"], "label"),
                        s.text(f["desc"], "caption", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                ),
                border_radius=s.R_BUTTON + 1,
                padding=ft.padding.all(12),
                on_click=lambda _, k=f["key"]: self._select_func(k),
                data=f["key"],
                expand=True,
                animate=s.snappy(),
            )
            btn.on_hover = lambda e, b=btn: self._func_hover(b, e)
            self._func_btns.append(btn)
        self._style_func_btns()

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
                    ft.Column(
                        controls=[
                            s.text("压缩解压中心", "headline"),
                            s.text("极速无损压缩，主流格式一键互转", "small"),
                        ],
                        spacing=4,
                    ),
                    self._build_drop_zone(),
                    self._build_file_list(),
                ],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=ft.padding.only(left=s.PAGE_X, right=16, top=4, bottom=20),
        )

    def _build_drop_zone(self) -> ft.Control:
        self._drop_icon = ft.Container(
            content=ft.Icon(ft.Icons.FOLDER_ZIP_OUTLINED, color=c("ink-2", "fg"), size=20),
            width=44, height=44, bgcolor=c("surface-2"), border_radius=22,
            alignment=ft.Alignment(0, 0), animate=s.snappy(),
        )
        self._drop_zone_body = ft.Container(
            content=ft.Column(
                controls=[
                    self._drop_icon,
                    s.text("点击选择文件", "title", text_align=ft.TextAlign.CENTER),
                    s.text("可多选，压缩时打包为一个文件", "small", text_align=ft.TextAlign.CENTER),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=c("surface"),
            border=ft.border.all(1, c("line")),
            border_radius=s.R_PANEL,
            on_click=self._pick_files,
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

    def _build_file_list(self) -> ft.Control:
        self._file_list_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self._file_count,
                            ft.Container(expand=True),
                            s.button("清空全部", self._clear_files, kind="ghost", height=30),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self._file_list,
                ],
                spacing=10,
            ),
            visible=False,
        )
        return self._file_list_container

    def _build_param_panel(self) -> ft.Control:
        self._password_section = self._section("访问密码 (可选)", self._password_field)
        self._volume_section = self._section("分卷大小", self._volume_field)
        self._solid_section = self._section("固实压缩", ft.Row(
            controls=[
                ft.Icon(ft.Icons.LAYERS_OUTLINED, color=c("ink-2", "fg"), size=16),
                s.text("启用固实", "body", expand=True),
                self._solid_enabled,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ))

        self._param_panel = s.card(
            ft.Column(
                controls=[
                    ft.Column(
                        controls=[
                            s.text("参数设置", "title"),
                            self._section("选择功能", ft.Column(
                                controls=[
                                    ft.Row(controls=[self._func_btns[0], self._func_btns[1]], spacing=6),
                                    ft.Row(controls=[self._func_btns[2], self._func_btns[3]], spacing=6),
                                ],
                                spacing=6,
                            )),
                            self._password_section,
                            self._volume_section,
                            self._solid_section,
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
        self._update_param_sections()
        return self._param_panel

    def _section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(controls=[s.text(label, "caption"), content], spacing=8)

    def _style_func_btns(self) -> None:
        for btn in self._func_btns:
            active = btn.data == self._selected_func
            btn.bgcolor = c("accent-soft") if active else c("surface")
            btn.border = ft.border.all(1, c("accent") if active else c("line"))
            btn.content.controls[0].color = c("accent-fg" if active else "ink-2", "fg")

    def _func_hover(self, btn: ft.Container, e: ft.ControlEvent) -> None:
        if btn.data == self._selected_func:
            return
        on = e.data in (True, "true")
        btn.bgcolor = c("surface-2" if on else "surface")
        btn.border = ft.border.all(1, c("line-strong" if on else "line"))
        btn.update()

    def _update_param_sections(self) -> None:
        """按功能控制参数子区显示：解压时隐藏密码/分卷/固实。"""
        is_compress = self._selected_func != "extract"
        self._password_section.visible = is_compress
        self._volume_section.visible = is_compress
        self._solid_section.visible = is_compress

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
                    self._progress_file_rows,
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
        self._result_icon = ft.Icon(ft.Icons.CHECK_ROUNDED, color="#FFFFFF", size=16)
        self._result_icon_box = ft.Container(
            content=self._result_icon, width=32, height=32,
            bgcolor=c("accent"), border_radius=16, alignment=ft.Alignment(0, 0),
        )
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self._result_icon_box,
                            self._result_title,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self._result_file_rows,
                    ft.Row(
                        controls=[
                            self._result_reset_btn,
                            ft.Container(expand=True),
                            self._result_open_btn,
                        ],
                    ),
                ],
                spacing=14,
            ),
            bgcolor=c("surface"),
            border=ft.border.all(1, c("line")),
            border_radius=s.R_PANEL,
            padding=ft.padding.all(24),
            margin=ft.margin.only(left=s.PAGE_X, right=16, top=4),
        )

    def _select_func(self, key: str) -> None:
        self._selected_func = key
        self._style_func_btns()
        self._update_param_sections()
        if self._files:
            self._run_btn.set_label(f"立即处理 ({len(self._files)}个文件)")
        self.update()

    def _pick_files(self, _) -> None:
        self._page.run_task(self._pick_files_async)

    async def _pick_files_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        is_extract = self._selected_func == "extract"
        try:
            if is_extract:
                files = await picker.pick_files(
                    dialog_title="选择压缩包",
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=list(_ARCHIVE_EXTS),
                    allow_multiple=False,
                )
            else:
                files = await picker.pick_files(
                    dialog_title="选择要压缩的文件",
                    file_type=ft.FilePickerFileType.ANY,
                    allow_multiple=True,
                )
        except RuntimeError:
            show_toast(self._page, "无法打开文件选择器，请检查系统环境", duration=3000)
            files = None
        if not files:
            self._page.update()
            return
        paths = [Path(f.path) for f in files if f.path]
        if paths:
            if is_extract:
                # 解压模式只保留第一个压缩包
                self._files = [paths[0]]
            else:
                self._files.extend(paths)
            self._rebuild_file_list()
        self._page.update()

    def _rebuild_file_list(self) -> None:
        self._file_list.controls.clear()
        self._file_count.value = f"待处理文件 ({len(self._files)})"
        has_files = bool(self._files)
        self._file_list_container.visible = has_files
        self._drop_zone_wrapper.height = 120 if has_files else 168
        for f in self._files:
            try:
                if f.is_dir():
                    size_str = "文件夹"
                else:
                    size = f.stat().st_size
                    size_str = (
                        f"{size / 1024:.1f} KB" if size < 1024 * 1024
                        else f"{size / 1024 / 1024:.1f} MB"
                    )
            except OSError:
                size_str = "?"
            ext = f.suffix.lower().lstrip(".")
            is_archive = ext in _ARCHIVE_EXTS
            is_dir = f.is_dir() if f.exists() else False
            if is_dir:
                thumb_icon = ft.Icons.FOLDER_OUTLINED
                tag_text = "文件夹"
            elif is_archive:
                thumb_icon = ft.Icons.FOLDER_ZIP_OUTLINED
                tag_text = ext.upper()
            else:
                thumb_icon = ft.Icons.INSERT_DRIVE_FILE_OUTLINED
                tag_text = ext.upper() or "FILE"
            card = s.card(
                ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Icon(thumb_icon, color=c("ink-2", "fg"), size=16),
                                    width=32, height=32, bgcolor=c("surface-2"), border_radius=s.R_BUTTON,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Container(
                                    content=s.text(tag_text, "caption", color="ink-2"),
                                    height=22,
                                    alignment=ft.Alignment(0, 0),
                                    border=ft.border.all(1, c("line-strong")),
                                    border_radius=11,
                                    padding=ft.padding.symmetric(horizontal=8),
                                ),
                                ft.Container(expand=True),
                                s.icon_button(ft.Icons.CLOSE_OUTLINED, lambda _, path=f: self._remove_file(path),
                                              tooltip="移除", size=26, color="ink-3"),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        s.text(f.name, "body-medium", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        s.text(size_str, "mono"),
                    ],
                    spacing=6,
                ),
                padding=12,
                border_radius=12,
                width=210,
            )
            self._file_list.controls.append(card)
        self._run_btn.set_label(f"立即处理 ({len(self._files)}个文件)", enabled=has_files)
        self.update()

    def _clear_files(self, _) -> None:
        self._files.clear()
        self._rebuild_file_list()

    def _remove_file(self, path: Path) -> None:
        if path in self._files:
            self._files.remove(path)
        self._rebuild_file_list()
        self._page.update()

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

    def _start_task(self, _) -> None:
        if not self._files:
            show_toast(self._page, "请先选择文件")
            return

        out_dir = settings_service.resolve_output_dir(self._files[0])
        func = self._selected_func

        if func == "extract":
            # 解压：取第一个压缩包
            archive_files = [p for p in self._files
                             if p.suffix.lower().lstrip(".") in _ARCHIVE_EXTS]
            if not archive_files:
                show_toast(self._page, "解压需要选择压缩包文件")
                return
            kwargs = {"input_file": archive_files[0], "output_dir": out_dir}
            fn = extract
        elif func == "compress_zip":
            kwargs = {"input_files": self._files, "output_dir": out_dir,
                      "format": "zip"}
            fn = compress
        elif func == "compress_7z":
            kwargs = {"input_files": self._files, "output_dir": out_dir,
                      "format": "7z"}
            fn = compress
        elif func == "compress_targz":
            kwargs = {"input_files": self._files, "output_dir": out_dir,
                      "format": "tar.gz"}
            fn = compress
        else:
            show_toast(self._page, f"未知功能：{func}")
            return

        self._show_processing(f"{len(self._files)} 个文件")

        async def _run():
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_progress(self, current, total, desc) -> None:
        self._update_processing_progress(current, total, desc)

    def _on_complete(self, result: TaskResult) -> None:
        history_service.save_task(
            "archive", self._selected_func, result,
            input_desc=f"{len(self._files)} 个文件",
        )
        self._output_dir = result.output_dir if result.output_dir else (
            result.output_files[0].parent if result.output_files else None
        )
        self._show_complete(result)
        if result.status == TaskStatus.SUCCESS:
            notify_task_done(self._page, self._output_dir)

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._reset_to_workspace()

    def _reset(self) -> None:
        self._files.clear()
        self._rebuild_file_list()
        self._reset_to_workspace()

    def _reset_to_workspace(self) -> None:
        self._workspace_view.visible = True
        self._processing_view.visible = False
        self._complete_view.visible = False
        self.update()
        self._run_btn.morph_idle()

    def _show_processing(self, file_count_label: str) -> None:
        self._progress_title.value = "正在处理…"
        self._progress_pct.value = "0%"
        self._progress_bar.value = 0
        self._progress_file_rows.controls.clear()
        self._workspace_view.visible = False
        self._processing_view.visible = True
        self._complete_view.visible = False
        self.update()
        self._run_btn.morph_loading()

    def _update_processing_progress(self, current: int, total: int,
                                    desc: str) -> None:
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_pct.value = f"{pct}%"
        self._progress_bar.value = current / total if total > 0 else 0
        row_idx = current - 1
        row = ft.Row(
            controls=[
                ft.Icon(ft.Icons.FOLDER_ZIP_OUTLINED, color=c("ink-3", "fg"), size=16),
                s.text(desc, "body", expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.ProgressBar(
                    value=1.0, color=c("ink"), bgcolor=c("surface-3"),
                    height=4, border_radius=2, width=80,
                ),
                s.text(f"{current}/{total}", "mono", width=40),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        if row_idx < len(self._progress_file_rows.controls):
            self._progress_file_rows.controls[row_idx] = row
        else:
            self._progress_file_rows.controls.append(row)
        self._processing_view.update()

    def _show_complete(self, result: TaskResult) -> None:
        ok = result.status == TaskStatus.SUCCESS
        if ok:
            self._result_title.value = "处理完成"
            self._result_title.color = c("ink", "fg")
        else:
            self._result_title.value = f"处理失败：{result.error_message or '未知错误'}"
            self._result_title.color = c("danger", "fg")
        self._result_icon.icon = ft.Icons.CHECK_ROUNDED if ok else ft.Icons.PRIORITY_HIGH_ROUNDED
        self._result_icon_box.bgcolor = c("accent") if ok else c("danger")

        self._result_file_rows.controls.clear()
        # 对于压缩：output_files 是生成的归档；对于解压：output_dir 是解压目标
        display_files = result.output_files or []
        if not display_files and result.output_dir:
            display_files = []
            try:
                # 解压后无列表文件，展示目标目录本身
                self._result_file_rows.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, color=c("ink-3", "fg"),
                                        size=16),
                                s.text(str(result.output_dir), "body", expand=True, max_lines=1,
                                       overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Container(
                                    content=s.text("已解压", "caption", color="accent-fg"),
                                    height=22, alignment=ft.Alignment(0, 0),
                                    bgcolor=c("accent-soft"),
                                    border_radius=11,
                                    padding=ft.padding.symmetric(horizontal=8),
                                ),
                                s.icon_button(ft.Icons.FOLDER_OPEN_OUTLINED,
                                              lambda _, p=result.output_dir: self._open_dir(p),
                                              tooltip="打开目录", size=28),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor=c("surface-2"),
                        border_radius=s.R_INPUT,
                        padding=ft.padding.only(left=12, right=4, top=4, bottom=4),
                    )
                )
            except (OSError, AttributeError):
                pass
        else:
            for fp in display_files[:8]:
                self._result_file_rows.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_ZIP_OUTLINED, color=c("ink-3", "fg"),
                                        size=16),
                                s.text(fp.name, "body", expand=True, max_lines=1,
                                       overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Container(
                                    content=s.text("已完成", "caption", color="accent-fg"),
                                    height=22, alignment=ft.Alignment(0, 0),
                                    bgcolor=c("accent-soft"),
                                    border_radius=11,
                                    padding=ft.padding.symmetric(horizontal=8),
                                ),
                                s.icon_button(ft.Icons.FOLDER_OPEN_OUTLINED,
                                              lambda _, p=fp: self._open_file_location(p),
                                              tooltip="打开所在文件夹", size=28),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor=c("surface-2"),
                        border_radius=s.R_INPUT,
                        padding=ft.padding.only(left=12, right=4, top=4, bottom=4),
                    )
                )
            if len(display_files) > 8:
                self._result_file_rows.controls.append(
                    s.text(f"…共 {len(display_files)} 个文件", "small")
                )

        self._workspace_view.visible = False
        self._processing_view.visible = False
        self._complete_view.visible = True
        self.update()
        self._run_btn.morph_result(ok)

    def _open_output_folder(self, _) -> None:
        if self._output_dir and self._output_dir.exists():
            self._open_dir(self._output_dir)

    def _open_dir(self, path: Path) -> None:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _open_file_location(self, path: Path) -> None:
        folder = path.parent
        if not folder.exists():
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])


# 解压输入参数适配包装（预留：若将来需要批量解压多个压缩包）
def _batch_extract(
    input_files: list[Path],
    output_dir: Path,
    progress_callback=None,
):
    t0 = time.time()
    if not input_files:
        return TaskResult(status=TaskStatus.FAILED, error_message="未选择任何文件")
    output_dirs: list[Path] = []
    total = len(input_files)
    for i, path in enumerate(input_files, start=1):
        res = extract(path, output_dir, progress_callback=None)
        if res.status == TaskStatus.FAILED:
            return TaskResult(
                status=TaskStatus.FAILED,
                error_message=res.error_message,
                output_dir=output_dir,
                duration_seconds=time.time() - t0,
            )
        if res.output_dir:
            output_dirs.append(res.output_dir)
        if progress_callback:
            progress_callback(i, total, f"已解压：{path.name} ({i}/{total})")
    return TaskResult(
        status=TaskStatus.SUCCESS,
        output_files=[],
        output_dir=output_dir,
        duration_seconds=time.time() - t0,
    )
