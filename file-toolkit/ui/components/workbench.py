"""
模块工作台基类 — PDF / 图片 / 音视频共用的页面骨架

布局：
    TopBar
    ├── 左侧：标题 + 选择文件区 + 文件列表（或处理中 / 完成视图）
    └── 右侧参数面板：功能卡片 → 当前功能的参数 → 输出位置 → 开始处理

子类只需声明：
    TITLE / SUBTITLE / MODULE / PICK_LABEL / FILE_ICON / FILE_NOUN
    FUNCTIONS: list[WorkbenchFunction]
    build_params(key) -> list[ft.Control]          当前功能的参数区
    build_task(key, files, out_dir) -> (fn, kwargs) | None   None 表示校验未通过

每个功能声明自己接受的扩展名；单文件的 core 函数用 run_for_each 包成批处理。
"""
import asyncio
import functools
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import flet as ft

from core.models import TaskResult, TaskStatus
from services import history_service, settings_service
from services.task_service import run_task
from ui.components.top_bar import TopBar
from ui.palette import c
from ui.utils import notify_task_done, open_folder, show_toast


@dataclass(frozen=True)
class WorkbenchFunction:
    key: str
    label: str
    desc: str
    icon: str
    color: str
    bg: str
    extensions: tuple[str, ...]
    min_files: int = 1
    orderable: bool = False      # 文件顺序有意义（如 PDF 合并），列表显示上下移动按钮
    uses_output_dir: bool = True  # 原地处理的功能（如重命名）隐藏输出位置


def run_for_each(
    fn: Callable[..., TaskResult],
    input_files: list[Path],
    make_kwargs: Callable[[Path], dict],
    progress_callback=None,
) -> TaskResult:
    """把单文件 core 函数逐个应用到多个文件，汇总输出；任一失败即停止并返回失败。"""
    t0 = time.time()
    outputs: list[Path] = []
    out_dir: Path | None = None
    total = len(input_files)
    for i, path in enumerate(input_files, start=1):
        if progress_callback:
            progress_callback(i - 1, total, f"正在处理：{path.name}")
        res = fn(**make_kwargs(path))
        if res.status != TaskStatus.SUCCESS:
            return TaskResult(
                status=TaskStatus.FAILED,
                output_files=outputs,
                output_dir=out_dir,
                error_message=f"{path.name}：{res.error_message or '处理失败'}",
                duration_seconds=time.time() - t0,
            )
        outputs.extend(res.output_files or [])
        out_dir = out_dir or res.output_dir or (res.output_files[0].parent if res.output_files else None)
        if progress_callback:
            progress_callback(i, total, f"已完成：{path.name}")
    return TaskResult(
        status=TaskStatus.SUCCESS,
        output_files=outputs,
        output_dir=out_dir,
        duration_seconds=time.time() - t0,
    )


def unique_path(path: Path) -> Path:
    """目标已存在时追加 _1、_2…，避免覆盖用户之前的结果。"""
    if not path.exists():
        return path
    i = 1
    while (candidate := path.with_name(f"{path.stem}_{i}{path.suffix}")).exists():
        i += 1
    return candidate


def is_mounted(control: ft.Control) -> bool:
    """Flet 0.84 未挂载时访问 .page 会抛 RuntimeError。"""
    try:
        return control.page is not None
    except RuntimeError:
        return False


def _size_str(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return "?"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


class ChoiceGroup(ft.Row):
    """一组互斥的胶囊按钮（如目标格式 PNG / JPG / WebP）。"""

    def __init__(self, options: list[tuple[str, str]], value: str,
                 on_change: Callable[[str], None] | None = None) -> None:
        super().__init__(wrap=True, spacing=8, run_spacing=8)
        self.value = value
        self._options = options
        self._on_change = on_change
        self._render()

    def _render(self) -> None:
        self.controls = []
        for val, label in self._options:
            active = val == self.value
            self.controls.append(ft.Container(
                content=ft.Text(
                    label, size=13, weight=ft.FontWeight.W_600,
                    color=c("#ffffff", "fg") if active else c("#162f50", "fg"),
                ),
                bgcolor=c("#005f98") if active else c("#ffffff"),
                border=ft.border.all(1, c("#005f98") if active else c("#e2e8f0")),
                border_radius=10,
                padding=ft.padding.symmetric(horizontal=14, vertical=8),
                on_click=lambda _, v=val: self._select(v),
                ink=True,
            ))

    def _select(self, value: str) -> None:
        self.value = value
        self._render()
        self.update()
        if self._on_change:
            self._on_change(value)


class Workbench(ft.Column):
    """模块工作台基类，见模块文档。"""

    TITLE = ""
    SUBTITLE = ""
    MODULE = ""                       # 写入历史记录的模块名
    PICK_LABEL = "点击选择文件"
    PICK_ICON = ft.Icons.UPLOAD_FILE
    FILE_ICON = ft.Icons.INSERT_DRIVE_FILE
    FILE_ICON_COLOR = "#005f98"
    FILE_ICON_BG = "#d5e3ff"
    FILE_NOUN = "个文件"
    FUNCTIONS: list[WorkbenchFunction] = []

    _NARROW_BREAKPOINT = 800

    # ── 子类实现 ─────────────────────────────────────────────────────────
    def build_params(self, key: str) -> list[ft.Control]:
        return []

    def build_task(self, key: str, files: list[Path], out_dir: Path) -> tuple[Callable, dict] | None:
        raise NotImplementedError

    def on_func_changed(self, key: str) -> None:
        """切换功能后的钩子（子类可选）。"""

    def on_files_changed(self) -> None:
        """文件列表变化后的钩子（子类可选），此时尚未 update。"""

    def after_task(self, key: str, files: list[Path], result: TaskResult) -> None:
        """任务结束后的钩子（子类可选），如原地重命名后刷新文件路径。"""

    # ── 构建 ─────────────────────────────────────────────────────────────
    def __init__(self, page: ft.Page, initial_func: str | None = None) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._files: list[Path] = []
        keys = [f.key for f in self.FUNCTIONS]
        self._func_key = initial_func if initial_func in keys else keys[0]
        self._task: asyncio.Task | None = None
        self._custom_out_dir: Path | None = None
        self._result_dir: Path | None = None
        self._is_narrow: bool | None = None
        self._prev_on_resize = None

        self._file_count = ft.Text(size=18, color=c("#162f50", "fg"), font_family="42dot Sans")
        self._file_hint = ft.Text(size=12, color=c("#b45309", "fg"), visible=False)
        self._file_list = ft.Column(spacing=0)

        self._func_grid = ft.Column(spacing=8)
        self._params = ft.Column(spacing=24)
        self._out_dir_text = ft.Text(
            size=12, color=c("#455c7f", "fg"), max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True,
        )
        self._run_label = ft.Text(size=18, color=c("#ffffff", "fg"), font_family="42dot Sans")
        self._run_btn = ft.Container(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.PLAY_ARROW, color=c("#ffffff", "fg"), size=20), self._run_label],
                spacing=8, alignment=ft.MainAxisAlignment.CENTER,
            ),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=[c("#005f98"), c("#00a3ff")],
            ),
            border_radius=16,
            padding=ft.padding.symmetric(vertical=16),
            shadow=ft.BoxShadow(
                blur_radius=25, spread_radius=-5,
                color=ft.Colors.with_opacity(0.2, c("#005f98", "fg")),
                offset=ft.Offset(0, 20),
            ),
            on_click=self._start_task,
            ink=True,
        )

        self._workspace_view = self._build_workspace_view()
        self._processing_view = self._build_processing_view()
        self._complete_view = self._build_complete_view()
        self._main_content = ft.Container(
            content=ft.Column(
                controls=[self._workspace_view, self._processing_view, self._complete_view],
                spacing=0, scroll=ft.ScrollMode.AUTO, expand=True,
            ),
            expand=True,
        )
        self._param_panel = self._build_param_panel()

        self._render_funcs()
        self._render_params()
        self._render_files()
        self._render_out_dir()

        self.controls = [TopBar(page), ft.Container()]
        self._apply_responsive_layout(update=False)

    def did_mount(self) -> None:
        self._prev_on_resize = self._page.on_resize
        self._page.on_resize = self._on_page_resized

    def will_unmount(self) -> None:
        if self._page.on_resize == self._on_page_resized:
            self._page.on_resize = self._prev_on_resize

    @property
    def func(self) -> WorkbenchFunction:
        return next(f for f in self.FUNCTIONS if f.key == self._func_key)

    def section(self, label: str, content: ft.Control) -> ft.Control:
        return ft.Column(controls=[
            ft.Text(label, size=12, color=c("#455c7f", "fg"), font_family="42dot Sans"),
            content,
        ], spacing=12)

    @staticmethod
    def each(fn: Callable[..., TaskResult], files: list[Path], make_kwargs: Callable[[Path], dict]):
        """单文件 core 函数 → build_task 返回值（逐个处理全部文件）。"""
        return functools.partial(run_for_each, fn, files, make_kwargs), {}

    @staticmethod
    def text_field(value: str = "", hint: str = "", **kwargs) -> ft.TextField:
        return ft.TextField(
            value=value, hint_text=hint, border_radius=12,
            bgcolor=c("#ffffff"), border_color=c("#d5e3ff"), text_size=14,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
            **kwargs,
        )

    def _build_workspace_view(self) -> ft.Control:
        pick = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(self.PICK_ICON, color=c("#005f98", "fg"), size=36),
                        width=68, height=68, border_radius=9999, alignment=ft.Alignment(0, 0),
                        bgcolor=ft.Colors.with_opacity(0.12, c("#005f98")),
                    ),
                    ft.Text(self.PICK_LABEL, size=18, color=c("#005f98", "fg"), font_family="42dot Sans",
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(self._accept_hint(), size=13, color=c("#455c7f", "fg"),
                            text_align=ft.TextAlign.CENTER),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            height=190,
            expand=True,
            bgcolor=c("#f4f6ff"),
            border=ft.border.all(2, ft.Colors.with_opacity(0.3, c("#005f98"))),
            border_radius=20,
            on_click=self._pick_files,
            on_hover=self._on_pick_hover,
            ink=True,
        )
        self._pick_area = pick
        self._pick_hint = pick.content.controls[2]
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Column(controls=[
                        ft.Text(self.TITLE, size=30, weight=ft.FontWeight.W_500,
                                color=c("#005f98", "fg"), font_family="42dot Sans"),
                        ft.Text(self.SUBTITLE, size=16, color=c("#455c7f", "fg"), font_family="42dot Sans"),
                    ], spacing=4),
                    ft.Row(controls=[pick]),
                    ft.Column(controls=[
                        ft.Row(controls=[
                            self._file_count,
                            ft.Container(expand=True),
                            ft.TextButton("清空全部", style=ft.ButtonStyle(color=c("#005f98", "fg")),
                                          on_click=lambda _: self._clear_files()),
                        ]),
                        self._file_hint,
                        self._file_list,
                    ], spacing=8),
                ],
                spacing=24,
            ),
            padding=ft.padding.all(32),
        )

    def _accept_hint(self) -> str:
        exts = " / ".join(e.upper() for e in self.func.extensions[:8])
        more = " 等" if len(self.func.extensions) > 8 else ""
        return f"支持 {exts}{more}，可多选"

    def _on_pick_hover(self, e: ft.ControlEvent) -> None:
        self._pick_area.bgcolor = (
            ft.Colors.with_opacity(0.06, c("#005f98")) if e.data == "true" else c("#f4f6ff")
        )
        self._pick_area.update()

    def _build_param_panel(self) -> ft.Container:
        self._out_section = self.section("输出位置", ft.Row(controls=[
            ft.Icon(ft.Icons.FOLDER_OUTLINED, color=c("#455c7f", "fg"), size=18),
            self._out_dir_text,
            ft.IconButton(icon=ft.Icons.FOLDER_OPEN, icon_color=c("#005f98", "fg"), icon_size=20,
                          tooltip="更改输出目录", on_click=self._pick_out_dir),
            ft.IconButton(icon=ft.Icons.RESTART_ALT, icon_color=c("#94a3b8", "fg"), icon_size=20,
                          tooltip="恢复默认", on_click=lambda _: self._set_out_dir(None)),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("参数设置", size=20, weight=ft.FontWeight.W_500,
                                    color=c("#005f98", "fg"), font_family="42dot Sans"),
                            self.section("选择功能", self._func_grid),
                            self._params,
                            self._out_section,
                        ],
                        spacing=24,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    # 开始按钮固定在面板底部，参数再多也不用滚动去找
                    self._run_btn,
                    ft.Text("本地处理 · 文件不会上传", size=10, color=c("#455c7f", "fg"),
                            font_family="42dot Sans", text_align=ft.TextAlign.CENTER),
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            ),
            width=320,
            bgcolor=c("#f4f6ff"),
            border_radius=16,
            border=ft.border.only(left=ft.BorderSide(1, c("#d5e3ff"))),
            padding=ft.padding.all(24),
        )

    # ── 功能卡片 ─────────────────────────────────────────────────────────
    def _func_card(self, f: WorkbenchFunction) -> ft.Control:
        active = f.key == self._func_key
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(f.icon, size=20,
                                        color=c("#ffffff", "fg") if active else c(f.color, "fg")),
                        width=36, height=36, border_radius=10, alignment=ft.Alignment(0, 0),
                        bgcolor=ft.Colors.with_opacity(0.2, c("#ffffff")) if active else c(f.bg),
                    ),
                    ft.Text(f.label, size=13, weight=ft.FontWeight.W_600, font_family="42dot Sans",
                            color=c("#ffffff", "fg") if active else c("#162f50", "fg"),
                            max_lines=2, expand=True),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=c("#005f98") if active else c("#ffffff"),
            border=ft.border.all(1, c("#005f98") if active else c("#e2e8f0")),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=10, vertical=10),
            on_click=lambda _, k=f.key: self._select_func(k),
            tooltip=f.desc,
            ink=True,
            expand=True,
            height=58,
        )

    def _func_desc(self) -> ft.Control:
        return ft.Text(self.func.desc, size=12, color=c("#455c7f", "fg"))

    def _render_funcs(self) -> None:
        cards = [self._func_card(f) for f in self.FUNCTIONS]
        rows = []
        for i in range(0, len(cards), 2):
            pair = cards[i:i + 2]
            if len(pair) == 1:
                pair.append(ft.Container(expand=True))
            rows.append(ft.Row(controls=pair, spacing=8))
        rows.append(self._func_desc())
        self._func_grid.controls = rows

    def _render_params(self) -> None:
        self._params.controls = self.build_params(self._func_key)
        self._out_section.visible = self.func.uses_output_dir

    def _select_func(self, key: str) -> None:
        if key == self._func_key:
            return
        self._func_key = key
        self._render_funcs()
        self._render_params()
        self._pick_hint.value = self._accept_hint()
        self._render_files()
        self.on_func_changed(key)
        self.update()

    # ── 文件 ─────────────────────────────────────────────────────────────
    def _applicable(self) -> list[Path]:
        exts = self.func.extensions
        return [p for p in self._files if p.suffix.lower().lstrip(".") in exts]

    def _render_files(self) -> None:
        applicable = set(self._applicable())
        orderable = self.func.orderable
        self._file_count.value = f"待处理文件 ({len(self._files)})"
        skipped = len(self._files) - len(applicable)
        self._file_hint.value = f"有 {skipped} 个文件不适用于「{self.func.label}」，处理时会跳过"
        self._file_hint.visible = skipped > 0

        rows = []
        for idx, path in enumerate(self._files):
            ok = path in applicable
            controls: list[ft.Control] = []
            if orderable:
                controls.append(ft.Column(controls=[
                    ft.IconButton(ft.Icons.KEYBOARD_ARROW_UP, icon_size=16, disabled=idx == 0,
                                  icon_color=c("#455c7f", "fg"), tooltip="上移",
                                  style=ft.ButtonStyle(padding=ft.padding.all(0)),
                                  on_click=lambda _, i=idx: self._move_file(i, -1)),
                    ft.IconButton(ft.Icons.KEYBOARD_ARROW_DOWN, icon_size=16, disabled=idx == len(self._files) - 1,
                                  icon_color=c("#455c7f", "fg"), tooltip="下移",
                                  style=ft.ButtonStyle(padding=ft.padding.all(0)),
                                  on_click=lambda _, i=idx: self._move_file(i, 1)),
                ], spacing=0, width=28))
            controls += [
                ft.Container(
                    content=ft.Icon(self.FILE_ICON, color=c(self.FILE_ICON_COLOR, "fg"), size=16),
                    width=32, height=32, bgcolor=c(self.FILE_ICON_BG), border_radius=6,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Text(path.name, size=14, color=c("#162f50", "fg"), font_family="42dot Sans",
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                ft.Text("不适用" if not ok else _size_str(path), size=12, width=72,
                        color=c("#b45309", "fg") if not ok else c("#455c7f", "fg")),
                ft.IconButton(icon=ft.Icons.CLOSE, icon_color=c("#94a3b8", "fg"), icon_size=16, tooltip="移除",
                              on_click=lambda _, p=path: self._remove_file(p)),
            ]
            rows.append(ft.Container(
                content=ft.Row(controls=controls, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=c("#ffffff"),
                opacity=1.0 if ok else 0.55,
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                border=ft.border.only(bottom=ft.BorderSide(1, c("#e2e8f0"))),
            ))
        if not rows:
            rows.append(ft.Container(
                content=ft.Text("还没有选择文件", size=13, color=c("#94a3b8", "fg")),
                padding=ft.padding.symmetric(vertical=16), alignment=ft.Alignment(0, 0),
            ))
        self._file_list.controls = rows

        n = len(applicable)
        self._run_label.value = f"开始处理（{n} {self.FILE_NOUN}）"
        self._run_btn.opacity = 1.0 if n >= self.func.min_files else 0.4
        self.on_files_changed()

    def _pick_files(self, _) -> None:
        self._page.run_task(self._pick_files_async)

    async def _pick_files_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        try:
            picked = await self._file_picker.pick_files(
                dialog_title=f"选择用于「{self.func.label}」的文件",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=list(self.func.extensions),
                allow_multiple=True,
            )
        except RuntimeError:
            show_toast(self._page, "无法打开文件选择器，请检查系统环境", duration=3000)
            picked = None
        if picked:
            existing = set(self._files)
            for f in picked:
                if f.path and Path(f.path) not in existing:
                    self._files.append(Path(f.path))
                    existing.add(Path(f.path))
            self._render_files()
            self._render_out_dir()
        self._page.update()

    def _move_file(self, idx: int, step: int) -> None:
        j = idx + step
        if 0 <= j < len(self._files):
            self._files[idx], self._files[j] = self._files[j], self._files[idx]
            self._render_files()
            self.update()

    def _remove_file(self, path: Path) -> None:
        self._files.remove(path)
        self._render_files()
        self._render_out_dir()
        self.update()

    def _clear_files(self) -> None:
        self._files.clear()
        self._render_files()
        self._render_out_dir()
        self.update()

    # ── 输出目录 ─────────────────────────────────────────────────────────
    def _out_dir(self, files: list[Path]) -> Path:
        return self._custom_out_dir or settings_service.resolve_output_dir(files[0])

    def _render_out_dir(self) -> None:
        if self._custom_out_dir:
            self._out_dir_text.value = str(self._custom_out_dir)
        elif self._files:
            self._out_dir_text.value = str(settings_service.resolve_output_dir(self._files[0]))
        elif settings_service.get("default_output_dir"):
            self._out_dir_text.value = settings_service.get("default_output_dir")
        else:
            self._out_dir_text.value = "输入文件旁的 output 文件夹"

    def _set_out_dir(self, path: Path | None) -> None:
        self._custom_out_dir = path
        self._render_out_dir()
        self._out_dir_text.update()

    def _pick_out_dir(self, _) -> None:
        self._page.run_task(self._pick_out_dir_async)

    async def _pick_out_dir_async(self) -> None:
        if not hasattr(self, "_dir_picker"):
            self._dir_picker = ft.FilePicker()
        try:
            path = await self._dir_picker.get_directory_path(dialog_title="选择输出目录")
        except RuntimeError:
            path = None
        if path:
            self._set_out_dir(Path(path))

    # ── 执行 ─────────────────────────────────────────────────────────────
    def _start_task(self, _) -> None:
        files = self._applicable()
        f = self.func
        if len(files) < f.min_files:
            if not self._files:
                show_toast(self._page, "请先选择文件")
            elif f.min_files > 1:
                show_toast(self._page, f"「{f.label}」至少需要 {f.min_files} {self.FILE_NOUN}")
            else:
                show_toast(self._page, f"所选文件都不适用于「{f.label}」")
            return
        task = self.build_task(f.key, files, self._out_dir(files))
        if task is None:
            return
        fn, kwargs = task
        self._running = (f.key, len(files))
        self._running_files = files
        self._show_processing(f"{f.label}：{len(files)} {self.FILE_NOUN}")

        async def _run():
            await run_task(fn, kwargs, self._on_progress, self._on_complete)
        self._task = self._page.run_task(_run)

    def _on_complete(self, result: TaskResult) -> None:
        if self._processing_view.visible is False:
            return  # 已取消
        key, count = self._running
        history_service.save_task(self.MODULE, key, result, input_desc=f"{count} {self.FILE_NOUN}")
        self.after_task(key, self._running_files, result)
        self._result_dir = result.output_dir or (result.output_files[0].parent if result.output_files else None)
        self._show_complete(result)
        if result.status == TaskStatus.SUCCESS:
            notify_task_done(self._page, self._result_dir)

    def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._processing_view.visible = False
        self._workspace_view.visible = True
        self.update()
        show_toast(self._page, "已停止等待；正在进行的单个文件可能仍会在后台完成")

    # ── 处理中 / 完成视图 ────────────────────────────────────────────────
    def _card(self, content: ft.Control) -> ft.Container:
        return ft.Container(
            content=content, bgcolor=c("#ffffff"), border=ft.border.all(1, c("#e2e8f0")),
            border_radius=16, padding=ft.padding.all(24), margin=ft.margin.all(32), visible=False,
        )

    def _build_processing_view(self) -> ft.Container:
        self._progress_title = ft.Text(size=24, weight=ft.FontWeight.W_600, color=c("#162f50", "fg"),
                                       font_family="42dot Sans", expand=True)
        self._progress_pct = ft.Text("0%", size=16, weight=ft.FontWeight.BOLD, color=c("#005f98", "fg"))
        self._progress_bar = ft.ProgressBar(value=None, color=c("#005f98", "fg"), bgcolor=c("#d5e3ff"),
                                            bar_height=8, border_radius=4)
        self._progress_desc = ft.Text(size=13, color=c("#455c7f", "fg"))
        return self._card(ft.Column(controls=[
            ft.Row(controls=[self._progress_title, self._progress_pct]),
            self._progress_bar,
            self._progress_desc,
            ft.Row(controls=[
                ft.Container(expand=True),
                ft.FilledButton("取消", style=ft.ButtonStyle(bgcolor=c("#be123c"), color=c("#ffffff", "fg")),
                                on_click=lambda _: self._cancel()),
            ]),
        ], spacing=12))

    def _build_complete_view(self) -> ft.Container:
        self._result_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=28)
        self._result_icon_box = ft.Container(content=self._result_icon, width=44, height=44,
                                             border_radius=9999, alignment=ft.Alignment(0, 0))
        self._result_title = ft.Text(size=22, weight=ft.FontWeight.W_600, font_family="42dot Sans", expand=True)
        self._result_detail = ft.Text(size=13, color=c("#455c7f", "fg"), selectable=True)
        self._result_files = ft.Column(spacing=8)
        self._result_open_btn = ft.FilledButton(
            "打开文件夹", icon=ft.Icons.FOLDER_OPEN,
            style=ft.ButtonStyle(bgcolor=c("#005f98"), color=c("#ffffff", "fg")),
            on_click=lambda _: self._result_dir and open_folder(self._result_dir),
        )
        return self._card(ft.Column(controls=[
            ft.Row(controls=[self._result_icon_box, self._result_title], spacing=12),
            self._result_detail,
            self._result_files,
            ft.Row(controls=[
                ft.TextButton("返回继续处理", style=ft.ButtonStyle(color=c("#455c7f", "fg")),
                              on_click=lambda _: self._back_to_workspace(clear=False)),
                ft.TextButton("清空并开始新任务", style=ft.ButtonStyle(color=c("#455c7f", "fg")),
                              on_click=lambda _: self._back_to_workspace(clear=True)),
                ft.Container(expand=True),
                self._result_open_btn,
            ]),
        ], spacing=16))

    def _show_processing(self, title: str) -> None:
        self._progress_title.value = title
        self._progress_pct.value = ""
        self._progress_bar.value = None
        self._progress_desc.value = "准备中…"
        self._workspace_view.visible = False
        self._complete_view.visible = False
        self._processing_view.visible = True
        self._run_btn.disabled = True
        self.update()

    def _on_progress(self, current: int, total: int, desc: str) -> None:
        if total > 0:
            self._progress_bar.value = min(1.0, current / total)
            self._progress_pct.value = f"{int(current / total * 100)}%"
        self._progress_desc.value = desc
        self._processing_view.update()

    def _show_complete(self, result: TaskResult) -> None:
        ok = result.status == TaskStatus.SUCCESS
        self._result_icon.icon = ft.Icons.CHECK_CIRCLE if ok else ft.Icons.ERROR_OUTLINE
        self._result_icon.color = c("#16a34a", "fg") if ok else c("#dc2626", "fg")
        self._result_icon_box.bgcolor = c("#d1fae5") if ok else c("#fee2e2")
        self._complete_view.border = ft.border.all(1, c("#bbf7d0") if ok else c("#fecaca"))
        self._result_title.value = "处理完成" if ok else "处理失败"
        self._result_title.color = c("#16a34a", "fg") if ok else c("#dc2626", "fg")
        if ok:
            n = len(result.output_files)
            self._result_detail.value = f"生成 {n} 个文件，用时 {result.duration_seconds:.1f} 秒"
        else:
            self._result_detail.value = result.error_message or "未知错误"
        self._result_files.controls = [
            ft.Row(controls=[
                ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, color=c("#455c7f", "fg"), size=14),
                ft.Text(p.name, size=13, color=c("#162f50", "fg"), expand=True,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=8)
            for p in result.output_files[:6]
        ]
        if len(result.output_files) > 6:
            self._result_files.controls.append(
                ft.Text(f"…共 {len(result.output_files)} 个文件", size=12, color=c("#455c7f", "fg")))
        self._result_open_btn.visible = self._result_dir is not None
        self._processing_view.visible = False
        self._complete_view.visible = True
        self._run_btn.disabled = False
        self.update()

    def _back_to_workspace(self, clear: bool) -> None:
        if clear:
            self._files.clear()
            self._render_files()
            self._render_out_dir()
        self._complete_view.visible = False
        self._workspace_view.visible = True
        self.update()

    # ── 响应式 ───────────────────────────────────────────────────────────
    def _apply_responsive_layout(self, update: bool = True) -> None:
        narrow = (self._page.width or 1000) < self._NARROW_BREAKPOINT
        if narrow == self._is_narrow:
            return
        self._is_narrow = narrow
        panel = self._param_panel
        if narrow:
            panel.width, panel.border_radius = None, 0
            panel.border = ft.border.only(top=ft.BorderSide(1, c("#d5e3ff")))
            body = ft.Column(controls=[self._main_content, panel], expand=True, spacing=0,
                             scroll=ft.ScrollMode.AUTO)
        else:
            panel.width, panel.border_radius = 320, 16
            panel.border = ft.border.only(left=ft.BorderSide(1, c("#d5e3ff")))
            body = ft.Row(controls=[self._main_content, panel], expand=True, spacing=0,
                          vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.controls[1] = body
        if update:
            self.update()

    def _on_page_resized(self, _) -> None:
        self._apply_responsive_layout()
