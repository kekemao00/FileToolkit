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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import flet as ft

from core.batch import run_batch
from core.models import TaskResult, TaskStatus
from core.paths import unique_path  # noqa: F401  页面从这里引用
from core.task_control import TaskCancelled
from services import history_service, settings_service
from services.task_service import run_task
from ui import style as s
from ui.components.top_bar import TopBar
from ui.handoff import pop_pending_files
from ui.palette import c
from ui.utils import is_mounted, notify_task_done, open_folder, show_toast


@dataclass(frozen=True)
class WorkbenchFunction:
    key: str
    label: str
    desc: str
    icon: str
    extensions: tuple[str, ...]
    min_files: int = 1
    orderable: bool = False      # 文件顺序有意义（如 PDF 合并），列表显示上下移动按钮
    uses_output_dir: bool = True  # 原地处理的功能（如重命名）隐藏输出位置
    accepts_folders: bool = False  # 可以添加整个文件夹（如压缩）
    show_size: bool = False       # 完成后显示体积变化（压缩类功能）

    @property
    def any_file(self) -> bool:
        return "*" in self.extensions

    def accepts(self, path: Path) -> bool:
        if path.is_dir():
            return self.accepts_folders
        return self.any_file or path.suffix.lower().lstrip(".") in self.extensions


def run_for_each(
    fn: Callable[..., TaskResult],
    input_files: list[Path],
    make_kwargs: Callable[[Path], dict],
    progress_callback=None,
) -> TaskResult:
    """把单文件 core 函数逐个应用到多个文件，汇总输出。

    单个文件失败不中断整批，失败原因记入 warnings；全部失败才算任务失败。
    """
    extra_warnings: list[str] = []
    total = len(input_files)

    def one(path: Path) -> list[Path]:
        kwargs = make_kwargs(path)
        if progress_callback and "progress_callback" not in kwargs:
            i = input_files.index(path)

            def sub(cur: int, tot: int, desc: str) -> None:
                frac = min(1.0, cur / tot) if tot else 0.0
                progress_callback(int((i + frac) * 1000), total * 1000, f"{path.name}：{desc}")
            kwargs["progress_callback"] = sub
        res = fn(**kwargs)
        if res.status == TaskStatus.CANCELLED:
            raise TaskCancelled()
        if res.status != TaskStatus.SUCCESS:
            raise RuntimeError(res.error_message or "处理失败")
        extra_warnings.extend(res.warnings)
        return list(res.output_files)

    result = run_batch(input_files, None, one, progress_callback, "已完成")
    result.warnings = extra_warnings + result.warnings
    return result


def _bytes_str(size: int) -> str:
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024 ** 3:.2f} GB"


def _total_size(path: Path) -> int:
    """文件大小；文件夹则累加其中所有文件。"""
    try:
        if path.is_dir():
            return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return path.stat().st_size
    except OSError:
        return 0


def _size_str(path: Path) -> str:
    if path.is_dir():
        return "文件夹"
    try:
        return _bytes_str(path.stat().st_size)
    except OSError:
        return "?"


def describe_inputs(files: list[Path], noun: str = "个文件") -> str:
    """历史记录里的输入描述：「a.pdf」或「a.pdf 等 3 个文件」。"""
    if not files:
        return ""
    if len(files) == 1:
        return files[0].name
    return f"{files[0].name} 等 {len(files)} {noun}"


class ChoiceGroup(ft.Row):
    """一组互斥选项（如目标格式 PNG / JPG / WebP）。

    放得下一行时用分段标签页（墨黑指示条在选项间滑动），
    选项太多时换成可换行的标签 chip。
    """

    MAX_WIDTH = 270   # 参数面板内容宽 278 减去余量

    def __init__(self, options: list[tuple[str, str]], value: str,
                 on_change: Callable[[str], None] | None = None) -> None:
        super().__init__(wrap=True, spacing=6, run_spacing=6)
        self.value = value
        self._options = options
        self._on_change = on_change
        seg = s.Segmented(options, value, on_change=self._segment_changed)
        if seg.width <= self.MAX_WIDTH + 8:
            self._segmented: s.Segmented | None = s.Segmented(
                options, value, on_change=self._segment_changed, fill_width=self.MAX_WIDTH + 8)
            self.controls = [self._segmented]
        else:
            self._segmented = None
            self._render()

    def _segment_changed(self, value: str) -> None:
        self.value = value
        if self._on_change:
            self._on_change(value)

    def _render(self) -> None:
        self.controls = []
        for val, label in self._options:
            active = val == self.value
            self.controls.append(ft.Container(
                content=ft.Text(
                    label, size=12.5, weight=ft.FontWeight.W_500, font_family=s.FONT,
                    color=c("on-ink" if active else "ink-2", "fg"),
                ),
                bgcolor=c("ink") if active else c("surface"),
                border=ft.border.all(1, c("ink") if active else c("line-strong")),
                border_radius=14,
                height=28,
                alignment=ft.Alignment(0, 0),
                padding=ft.padding.symmetric(horizontal=11),
                on_click=lambda _, v=val: self._select(v),
                animate=s.snappy(),
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
    PICK_ICON = ft.Icons.UPLOAD_FILE_OUTLINED
    FILE_ICON = ft.Icons.INSERT_DRIVE_FILE_OUTLINED
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
        self._run_seq = 0
        self._custom_out_dir: Path | None = None
        self._result_dir: Path | None = None
        self._is_narrow: bool | None = None
        self._prev_on_resize = None

        self._file_count = s.text(kind="title")
        self._file_hint = s.text(kind="small", visible=False)
        self._file_list = ft.Column(spacing=0)

        self._func_grid = ft.Column(spacing=6)
        self._params = ft.Column(spacing=20)
        self._out_dir_text = s.text(kind="small", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True)
        self._run_btn = s.MorphButton(self._start_task)

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
        handed_over = pop_pending_files()
        if handed_over:
            self.add_files(handed_over, update=False)

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
        return ft.Column(controls=[s.text(label, "caption"), content], spacing=8)

    @staticmethod
    def each(fn: Callable[..., TaskResult], files: list[Path], make_kwargs: Callable[[Path], dict]):
        """单文件 core 函数 → build_task 返回值（逐个处理全部文件）。"""
        return functools.partial(run_for_each, fn, files, make_kwargs), {}

    @staticmethod
    def text_field(value: str = "", hint: str = "", **kwargs) -> ft.TextField:
        return s.text_field(value, hint, **kwargs)

    def _build_workspace_view(self) -> ft.Control:
        self._folder_btn = s.button("添加文件夹", self._pick_folder, kind="ghost", height=30,
                                    icon=ft.Icons.CREATE_NEW_FOLDER_OUTLINED,
                                    visible=self.func.accepts_folders)
        self._pick_icon = ft.Container(
            content=ft.Icon(self.PICK_ICON, color=c("ink-2", "fg"), size=20),
            width=44, height=44, border_radius=22, alignment=ft.Alignment(0, 0),
            bgcolor=c("surface-2"), animate=s.snappy(),
        )
        pick = ft.Container(
            content=ft.Column(
                controls=[
                    self._pick_icon,
                    s.text(self.PICK_LABEL, "title", text_align=ft.TextAlign.CENTER),
                    s.text(self._accept_hint(), "small", text_align=ft.TextAlign.CENTER),
                    self._folder_btn,
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            height=168,
            expand=True,
            bgcolor=c("surface"),
            border=ft.border.all(1, c("line")),
            border_radius=s.R_PANEL,
            on_click=self._pick_files,
            on_hover=self._on_pick_hover,
            animate=s.snappy(),
        )
        self._pick_area = pick
        self._pick_hint = pick.content.controls[2]
        self._file_card = s.card(
            ft.Column(controls=[
                ft.Container(
                    content=ft.Row(controls=[
                        self._file_count,
                        ft.Container(expand=True),
                        s.button("清空全部", lambda _: self._clear_files(), kind="ghost", height=30),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.only(left=16, right=8, top=10, bottom=6),
                ),
                ft.Container(content=self._file_hint, padding=ft.padding.only(left=16, right=16, bottom=6)),
                self._file_list,
            ], spacing=0),
            padding=ft.padding.only(bottom=6),
        )
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Column(controls=[
                        s.text(self.TITLE, "headline"),
                        s.text(self.SUBTITLE, "small"),
                    ], spacing=4),
                    ft.Row(controls=[pick]),
                    self._file_card,
                ],
                spacing=16,
            ),
            padding=ft.padding.only(left=s.PAGE_X, right=16, top=4, bottom=20),
        )

    def _accept_hint(self) -> str:
        if self.func.any_file:
            return "支持任意文件，也可以添加文件夹" if self.func.accepts_folders else "支持任意文件，可多选"
        exts = " / ".join(e.upper() for e in self.func.extensions[:8])
        more = " 等" if len(self.func.extensions) > 8 else ""
        return f"支持 {exts}{more}，可多选"

    def _on_pick_hover(self, e: ft.ControlEvent) -> None:
        on = e.data in (True, "true")
        self._pick_area.bgcolor = c("surface-2" if on else "surface")
        self._pick_area.border = ft.border.all(1, c("line-strong" if on else "line"))
        self._pick_icon.bgcolor = c("surface-3" if on else "surface-2")
        self._pick_area.update()

    def _build_param_panel(self) -> ft.Container:
        self._out_section = self.section("输出位置", ft.Container(
            content=ft.Row(controls=[
                ft.Icon(ft.Icons.FOLDER_OUTLINED, color=c("ink-3", "fg"), size=16),
                self._out_dir_text,
                s.icon_button(ft.Icons.EDIT_OUTLINED, self._pick_out_dir, tooltip="更改输出目录", size=28),
                s.icon_button(ft.Icons.RESTART_ALT_OUTLINED, lambda _: self._set_out_dir(None), tooltip="恢复默认",
                              size=28, color="ink-3"),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=c("surface-2"), border_radius=s.R_INPUT,
            padding=ft.padding.only(left=12, right=4, top=4, bottom=4),
        ))
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Column(
                        controls=[
                            s.text("参数设置", "title"),
                            self.section("选择功能", self._func_grid),
                            self._params,
                            self._out_section,
                        ],
                        spacing=20,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    # 开始按钮固定在面板底部，参数再多也不用滚动去找
                    ft.Row(controls=[self._run_btn], alignment=ft.MainAxisAlignment.CENTER),
                    s.text("本地处理 · 文件不会上传", "caption", text_align=ft.TextAlign.CENTER),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            ),
            width=320,
            bgcolor=c("surface"),
            border_radius=s.R_PANEL,
            border=ft.border.all(1, c("line")),
            padding=ft.padding.all(20),
            margin=ft.margin.only(right=s.PAGE_X, bottom=20, top=4),
        )

    # ── 功能卡片 ─────────────────────────────────────────────────────────
    def _func_card(self, f: WorkbenchFunction) -> ft.Control:
        active = f.key == self._func_key
        card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(f.icon, size=16, color=c("accent-fg" if active else "ink-2", "fg")),
                    ft.Text(f.label, size=13, weight=ft.FontWeight.W_500, font_family=s.FONT,
                            color=c("ink", "fg"), max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=c("accent-soft") if active else c("surface"),
            border=ft.border.all(1, c("accent") if active else c("line")),
            border_radius=s.R_BUTTON,
            padding=ft.padding.symmetric(horizontal=10),
            on_click=lambda _, k=f.key: self._select_func(k),
            tooltip=f.desc,
            expand=True,
            height=38,
            animate=s.snappy(),
        )
        if not active:
            s.hover_surface(card)
        return card

    def _func_desc(self) -> ft.Control:
        return s.text(self.func.desc, "small")

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
        self._folder_btn.visible = self.func.accepts_folders
        self._render_files()
        self.on_func_changed(key)
        self.update()

    # ── 文件 ─────────────────────────────────────────────────────────────
    def _applicable(self) -> list[Path]:
        return [p for p in self._files if self.func.accepts(p)]

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
                    ft.IconButton(ft.Icons.KEYBOARD_ARROW_UP_OUTLINED, icon_size=16, disabled=idx == 0,
                                  icon_color=c("ink-2", "fg"), tooltip="上移",
                                  style=ft.ButtonStyle(padding=ft.padding.all(0)),
                                  on_click=lambda _, i=idx: self._move_file(i, -1)),
                    ft.IconButton(ft.Icons.KEYBOARD_ARROW_DOWN_OUTLINED, icon_size=16, disabled=idx == len(self._files) - 1,
                                  icon_color=c("ink-2", "fg"), tooltip="下移",
                                  style=ft.ButtonStyle(padding=ft.padding.all(0)),
                                  on_click=lambda _, i=idx: self._move_file(i, 1)),
                ], spacing=0, width=28))
            controls += [
                ft.Container(
                    content=ft.Icon(ft.Icons.FOLDER_OUTLINED if path.is_dir() else self.FILE_ICON,
                                    color=c("ink-2", "fg"), size=14),
                    width=26, height=26, bgcolor=c("surface-3"), border_radius=13,
                    alignment=ft.Alignment(0, 0),
                ),
                s.text(path.name, "body", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                ft.Text("不适用" if not ok else _size_str(path), size=12, width=72,
                        font_family=s.FONT if not ok else s.MONO, text_align=ft.TextAlign.RIGHT,
                        color=c("ink-3", "fg") if not ok else c("ink-2", "fg")),
                s.icon_button(ft.Icons.CLOSE_OUTLINED, lambda _, p=path: self._remove_file(p), tooltip="移除",
                              size=28, color="ink-3"),
            ]
            row = ft.Container(
                content=ft.Row(controls=controls, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                opacity=1.0 if ok else 0.5,
                height=s.H_ROW,
                padding=ft.padding.only(left=16, right=8),
                animate=s.snappy(),
            )
            row.on_hover = lambda e, r=row: self._row_hover(r, e)
            if rows:
                rows.append(ft.Container(height=1, bgcolor=c("line"), margin=ft.margin.symmetric(horizontal=12)))
            rows.append(row)
        if not rows:
            rows.append(ft.Container(
                content=s.text("还没有选择文件", "small", color="ink-3"),
                padding=ft.padding.symmetric(vertical=18), alignment=ft.Alignment(0, 0),
            ))
        self._file_list.controls = rows

        n = len(applicable)
        self._run_btn.set_label(f"开始处理（{n} {self.FILE_NOUN}）", enabled=n >= self.func.min_files)
        self.on_files_changed()

    @staticmethod
    def _row_hover(row: ft.Container, e: ft.ControlEvent) -> None:
        row.bgcolor = c("surface-2") if e.data in (True, "true") else None
        row.update()

    def _pick_files(self, _) -> None:
        self._page.run_task(self._pick_files_async)

    async def _pick_files_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        any_file = self.func.any_file
        try:
            picked = await self._file_picker.pick_files(
                dialog_title=f"选择用于「{self.func.label}」的文件",
                file_type=ft.FilePickerFileType.ANY if any_file else ft.FilePickerFileType.CUSTOM,
                allowed_extensions=None if any_file else list(self.func.extensions),
                allow_multiple=True,
            )
        except RuntimeError:
            show_toast(self._page, "无法打开文件选择器，请检查系统环境", duration=3000)
            picked = None
        if picked:
            self.add_files([Path(f.path) for f in picked if f.path], update=False)
        self._page.update()

    def add_files(self, paths: list[Path], update: bool = True) -> None:
        """加入待处理列表（去重）。也供其他页面带着文件跳转过来时调用。"""
        existing = set(self._files)
        for path in paths:
            if path not in existing:
                self._files.append(path)
                existing.add(path)
        self._render_files()
        self._render_out_dir()
        if update and is_mounted(self):
            self.update()

    def _pick_folder(self, _) -> None:
        self._page.run_task(self._pick_folder_async)

    async def _pick_folder_async(self) -> None:
        if not hasattr(self, "_folder_picker"):
            self._folder_picker = ft.FilePicker()
        try:
            path = await self._folder_picker.get_directory_path(dialog_title="选择文件夹")
        except RuntimeError:
            path = None
        if path:
            self.add_files([Path(path)], update=False)
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
        self._run_seq += 1
        seq = self._run_seq
        self._running = (f.key, len(files))
        self._running_files = files
        self._show_processing(f"{f.label}：{len(files)} {self.FILE_NOUN}")

        async def _run():
            await run_task(fn, kwargs,
                           lambda *a: seq == self._run_seq and self._on_progress(*a),
                           lambda r: seq == self._run_seq and self._on_complete(r))
        self._task = self._page.run_task(_run)

    def _on_complete(self, result: TaskResult) -> None:
        if result.status == TaskStatus.CANCELLED:
            return
        key, _ = self._running
        history_service.save_task(self.MODULE, key, result,
                                  input_desc=describe_inputs(self._running_files, self.FILE_NOUN))
        self.after_task(key, self._running_files, result)
        self._result_dir = result.output_dir or (result.output_files[0].parent if result.output_files else None)
        self._show_complete(result)
        if result.status == TaskStatus.SUCCESS:
            notify_task_done(self._page, self._result_dir)

    def _cancel(self) -> None:
        self._run_seq += 1  # 之后到达的进度和结果都属于已取消的任务，忽略
        if self._task and not self._task.done():
            self._task.cancel()
        self._processing_view.visible = False
        self._workspace_view.visible = True
        self._run_btn.disabled = False
        self.update()
        self._run_btn.morph_idle()
        show_toast(self._page, "已取消，已经生成的文件会保留")

    # ── 处理中 / 完成视图 ────────────────────────────────────────────────
    def _card(self, content: ft.Control) -> ft.Container:
        return s.card(
            content, padding=24, visible=False,
            margin=ft.margin.only(left=s.PAGE_X, right=16, top=4, bottom=20),
            animate=s.smooth(),
        )

    def _build_processing_view(self) -> ft.Container:
        self._progress_title = s.text(kind="title", expand=True)
        self._progress_pct = s.text("0%", "mono", color="ink")
        self._progress_bar = ft.ProgressBar(value=None, color=c("ink"), bgcolor=c("surface-3"),
                                            bar_height=4, border_radius=2)
        self._progress_desc = s.text(kind="small")
        return self._card(ft.Column(controls=[
            ft.Row(controls=[self._progress_title, self._progress_pct]),
            self._progress_bar,
            self._progress_desc,
            ft.Row(controls=[
                ft.Container(expand=True),
                s.button("取消", lambda _: self._cancel(), kind="secondary"),
            ]),
        ], spacing=12))

    def _build_complete_view(self) -> ft.Container:
        self._result_icon = ft.Icon(ft.Icons.CHECK_ROUNDED, size=16)
        self._result_icon_box = ft.Container(content=self._result_icon, width=32, height=32,
                                             border_radius=16, alignment=ft.Alignment(0, 0))
        self._result_title = s.text(kind="title", expand=True)
        self._result_detail = s.text(kind="small", selectable=True)
        self._result_size = s.text(kind="body-medium", visible=False)
        self._result_warnings = ft.Column(spacing=4, visible=False)
        self._result_files = ft.Column(spacing=6)
        self._result_open_btn = s.button(
            "打开文件夹", lambda _: self._result_dir and open_folder(self._result_dir),
            icon=ft.Icons.FOLDER_OPEN_OUTLINED,
        )
        return self._card(ft.Column(controls=[
            ft.Row(controls=[self._result_icon_box, self._result_title], spacing=12),
            self._result_detail,
            self._result_size,
            self._result_warnings,
            self._result_files,
            ft.Row(controls=[
                s.button("返回继续处理", lambda _: self._back_to_workspace(clear=False), kind="secondary"),
                s.button("清空并开始新任务", lambda _: self._back_to_workspace(clear=True), kind="ghost"),
                ft.Container(expand=True),
                self._result_open_btn,
            ], spacing=8),
        ], spacing=14))

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
        self._run_btn.morph_loading()

    def _on_progress(self, current: int, total: int, desc: str) -> None:
        if total > 0:
            self._progress_bar.value = min(1.0, current / total)
            self._progress_pct.value = f"{int(current / total * 100)}%"
        self._progress_desc.value = desc
        self._processing_view.update()

    def _show_complete(self, result: TaskResult) -> None:
        ok = result.status == TaskStatus.SUCCESS
        self._result_icon.icon = ft.Icons.CHECK_ROUNDED if ok else ft.Icons.PRIORITY_HIGH_ROUNDED
        self._result_icon.color = "#FFFFFF"
        self._result_icon_box.bgcolor = c("accent") if ok else c("danger")
        self._result_title.value = "处理完成" if ok else "处理失败"
        self._result_title.color = c("ink", "fg") if ok else c("danger", "fg")
        if ok:
            n = len(result.output_files)
            self._result_detail.value = f"生成 {n} 个文件，用时 {result.duration_seconds:.1f} 秒"
            if result.warnings:
                self._result_title.value = f"处理完成，{len(result.warnings)} 个未成功"
        else:
            self._result_detail.value = result.error_message or "未知错误"
        self._render_size_change(result if ok else None)
        self._result_warnings.controls = [
            s.text(w, "small", color="danger", selectable=True) for w in result.warnings[:8]
        ] + ([s.text(f"…共 {len(result.warnings)} 条", "small")] if len(result.warnings) > 8 else [])
        self._result_warnings.visible = bool(result.warnings)
        self._result_files.controls = [
            ft.Row(controls=[
                ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, color=c("ink-3", "fg"), size=14),
                s.text(p.name, "body", expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=8)
            for p in result.output_files[:6]
        ]
        if len(result.output_files) > 6:
            self._result_files.controls.append(
                s.text(f"…共 {len(result.output_files)} 个文件", "small"))
        self._result_open_btn.visible = self._result_dir is not None
        self._processing_view.visible = False
        self._complete_view.visible = True
        self._run_btn.disabled = False
        self.update()
        self._run_btn.morph_result(ok, "处理失败" if not ok else "")

    def _render_size_change(self, result: TaskResult | None) -> None:
        """压缩类功能：原始总大小 → 结果总大小（节省比例）。"""
        show = bool(result and self.func.show_size and result.output_files)
        self._result_size.visible = show
        if not show:
            return
        assert result is not None
        before = sum(_total_size(p) for p in self._running_files)
        after = sum(_total_size(p) for p in result.output_files)
        if before <= 0:
            self._result_size.visible = False
            return
        saved = 1 - after / before
        change = f"减小 {saved:.0%}" if saved > 0.005 else ("增大 " + f"{-saved:.0%}" if saved < -0.005 else "几乎不变")
        self._result_size.value = f"{_bytes_str(before)} → {_bytes_str(after)}，{change}"
        self._result_size.color = c("accent-fg" if saved > 0.005 else "ink-2", "fg")

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
            panel.width = None
            panel.margin = ft.margin.only(left=s.PAGE_X, right=s.PAGE_X, bottom=20)
            self._run_btn.full_width = 320
            body = ft.Column(controls=[self._main_content, panel], expand=True, spacing=0,
                             scroll=ft.ScrollMode.AUTO)
        else:
            panel.width = 320
            panel.margin = ft.margin.only(right=s.PAGE_X, bottom=20, top=4)
            self._run_btn.full_width = 278
            body = ft.Row(controls=[self._main_content, panel], expand=True, spacing=0,
                          vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.controls[1] = body
        if update:
            self.update()

    def _on_page_resized(self, _) -> None:
        self._apply_responsive_layout()
