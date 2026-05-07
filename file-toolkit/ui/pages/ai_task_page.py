"""AI 智能任务页 — 基于 Figma 设计稿 1:1 还原

布局：Hero 区（渐变头像 + 标题 + 副标题）+ 交互区（Prompt 建议 + 输入控制台 + 附件列表 + 状态指示）
遵循核心模式的视觉风格；AI 服务未配置时给出明确提示，不使用"即将上线"。
"""
from pathlib import Path

import flet as ft

from services import settings_service
from ui.utils import show_toast

# Prompt 建议按钮数据
_PROMPT_SUGGESTIONS = [
    {"icon": ft.Icons.IMAGE, "label": "图片转PDF并加水印"},
    {"icon": ft.Icons.MOVIE, "label": "压缩视频并提取音频"},
    {"icon": ft.Icons.DRIVE_FILE_RENAME_OUTLINE, "label": "批量重命名图片"},
]

# 底部状态指示器
_STATUS_INDICATORS = [
    {"color": "#006571", "label": "支持 50+ 种格式"},
    {"color": "#6b1ef3", "label": "端到端加密处理"},
    {"color": "#2aa7ff", "label": "极速 AI 编排"},
]


class AiTaskPage(ft.Column):
    """AI 智能任务：Hero + 输入控制台 + 状态指示器。"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._attached_files: list[Path] = []

        self._input_field = ft.TextField(
            hint_text="描述您想完成的任务...",
            hint_style=ft.TextStyle(color="#455c7f", size=16),
            text_style=ft.TextStyle(color="#162f50", size=16),
            border=ft.InputBorder.NONE,
            cursor_color="#005f98",
            selection_color=ft.Colors.with_opacity(0.15, "#005f98"),
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=4,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        )

        self._attach_list = ft.Row(
            controls=[],
            wrap=True,
            spacing=8,
            run_spacing=8,
            visible=False,
        )

        self.controls = [self._build_content()]

    # ── 整体内容 ──────────────────────────────────────
    def _build_content(self) -> ft.Control:
        return ft.Container(
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack(
                expand=True,
                controls=[
                    # 装饰性模糊圆（右上）
                    ft.Container(
                        width=384, height=384,
                        border_radius=9999,
                        bgcolor=ft.Colors.with_opacity(0.05, "#005f98"),
                        blur=32,
                        right=-96, top=-96,
                    ),
                    # 装饰性模糊圆（左下）
                    ft.Container(
                        width=384, height=384,
                        border_radius=9999,
                        bgcolor=ft.Colors.with_opacity(0.05, "#6b1ef3"),
                        blur=32,
                        left=-96, bottom=-96,
                    ),
                    # 主内容列
                    ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            self._build_hero_section(),
                            self._build_interaction_area(),
                        ],
                    ),
                ],
            ),
        )

    # ── Hero 区域 ──────────────────────────────────────
    def _build_hero_section(self) -> ft.Control:
        return ft.Container(
            padding=ft.padding.only(top=80, bottom=40),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    self._build_ai_avatar(),
                    ft.Container(
                        padding=ft.padding.only(bottom=16, top=24),
                        content=ft.Text(
                            "你好，我是您的 文件全能王 AI 助手",
                            size=30,
                            weight=ft.FontWeight.W_500,
                            color="#162f50",
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=24),
                        content=ft.Text(
                            "一个软件，搞定所有文件。请告诉我您的需求，\n我将为您自动编排并执行最复杂的文件处理流程。",
                            size=18,
                            color="#455c7f",
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                ],
            ),
        )

    def _build_ai_avatar(self) -> ft.Control:
        """AI 头像：渐变方块 + 旋转边框装饰 + 动态光晕"""
        border_outer = ft.Container(
            width=192, height=192,
            alignment=ft.Alignment(0, 0),
            content=ft.Container(
                width=172, height=172,
                border_radius=32,
                border=ft.border.all(2, ft.Colors.with_opacity(0.2, "#005f98")),
                rotate=ft.Rotate(angle=0.21),
            ),
        )
        border_inner = ft.Container(
            width=192, height=192,
            alignment=ft.Alignment(0, 0),
            content=ft.Container(
                width=164, height=164,
                border_radius=32,
                border=ft.border.all(2, ft.Colors.with_opacity(0.2, "#6b1ef3")),
                rotate=ft.Rotate(angle=-0.105),
            ),
        )
        core = ft.Container(
            width=128, height=128,
            border_radius=24,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#005f98", "#6b1ef3"],
            ),
            shadow=ft.BoxShadow(
                blur_radius=50,
                spread_radius=-12,
                color=ft.Colors.with_opacity(0.2, "#005f98"),
                offset=ft.Offset(0, 25),
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Icon(ft.Icons.AUTO_AWESOME, color="#ffffff", size=55),
        )
        aura = ft.Container(
            width=192, height=192,
            border_radius=9999,
            bgcolor=ft.Colors.with_opacity(0.20, "#2aa7ff"),
            blur=32,
        )

        return ft.Container(
            width=192, height=192,
            content=ft.Stack(
                width=192, height=192,
                controls=[
                    ft.Container(
                        width=192, height=192,
                        alignment=ft.Alignment(0, 0),
                        content=aura,
                    ),
                    border_outer,
                    border_inner,
                    ft.Container(
                        width=192, height=192,
                        alignment=ft.Alignment(0, 0),
                        content=core,
                    ),
                ],
            ),
        )

    # ── 交互区域 ──────────────────────────────────────
    def _build_interaction_area(self) -> ft.Control:
        return ft.Container(
            expand=True,
            padding=ft.padding.symmetric(horizontal=24),
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                expand=True,
                spacing=24,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    self._build_prompt_suggestions(),
                    self._build_input_console(),
                    self._attach_list,
                    self._build_status_indicators(),
                ],
            ),
        )

    def _build_prompt_suggestions(self) -> ft.Control:
        buttons = []
        for item in _PROMPT_SUGGESTIONS:
            btn = ft.Container(
                bgcolor="#ffffff",
                border=ft.border.all(1, ft.Colors.with_opacity(0.1, "#97aed5")),
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=21, vertical=11),
                shadow=ft.BoxShadow(
                    blur_radius=1,
                    color=ft.Colors.with_opacity(0.05, "#000000"),
                    offset=ft.Offset(0, 1),
                ),
                ink=True,
                on_click=lambda _, lbl=item["label"]: self._use_suggestion(lbl),
                on_hover=self._on_btn_hover,
                animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(item["icon"], color="#455c7f", size=15),
                        ft.Text(
                            item["label"], size=14, color="#162f50",
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )
            buttons.append(btn)

        return ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
            controls=buttons,
            wrap=True,
            run_spacing=8,
        )

    def _build_input_console(self) -> ft.Control:
        """毛玻璃风格主输入控制台"""
        attach_btn = ft.Container(
            padding=8,
            border_radius=8,
            tooltip="附加文件",
            ink=True,
            on_click=self._on_attach,
            content=ft.Icon(ft.Icons.ATTACH_FILE, color="#455c7f", size=20),
        )
        # 麦克风（本地无语音识别后端，点击提示功能配置）
        mic_btn = ft.Container(
            padding=8,
            border_radius=8,
            tooltip="语音输入",
            ink=True,
            on_click=self._on_mic,
            content=ft.Icon(ft.Icons.MIC_NONE, color="#455c7f", size=19),
        )
        send_btn = ft.Container(
            padding=12,
            border_radius=12,
            bgcolor="#005f98",
            ink=True,
            on_click=self._on_submit,
            shadow=ft.BoxShadow(
                blur_radius=15,
                spread_radius=-3,
                color=ft.Colors.with_opacity(0.2, "#005f98"),
                offset=ft.Offset(0, 10),
            ),
            content=ft.Icon(ft.Icons.SEND_ROUNDED, color="#ffffff", size=16),
        )

        inner_row = ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.END,
                spacing=12,
                controls=[
                    attach_btn,
                    ft.Container(
                        expand=True,
                        padding=ft.padding.symmetric(vertical=3),
                        content=self._input_field,
                    ),
                    ft.Row(
                        spacing=4,
                        controls=[mic_btn, send_btn],
                    ),
                ],
            ),
        )

        return ft.Container(
            border_radius=16,
            border=ft.border.all(1, "#d5e3ff"),
            bgcolor="#f8fafc",
            shadow=ft.BoxShadow(
                blur_radius=50,
                spread_radius=-12,
                color=ft.Colors.with_opacity(0.08, "#005f98"),
                offset=ft.Offset(0, 25),
            ),
            padding=9,
            content=inner_row,
        )

    def _build_status_indicators(self) -> ft.Control:
        items = []
        for ind in _STATUS_INDICATORS:
            item = ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=6, height=6,
                        border_radius=9999,
                        bgcolor=ind["color"],
                    ),
                    ft.Text(
                        ind["label"], size=11, color="#61789c",
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            )
            items.append(item)

        return ft.Container(
            padding=ft.padding.only(top=16, bottom=48),
            opacity=0.6,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=24,
                controls=items,
            ),
        )

    # ── 事件处理 ──────────────────────────────────────
    def _use_suggestion(self, label: str) -> None:
        self._input_field.value = label
        self._input_field.update()

    def _on_submit(self, _) -> None:
        text = (self._input_field.value or "").strip()
        if not text:
            self._show_snack("请先输入任务描述", color="#455c7f")
            return

        # 检查 AI 服务配置
        api_key = settings_service.get_ai_api_key() if hasattr(
            settings_service, "get_ai_api_key") else None
        if not api_key:
            self._show_snack(
                "AI 服务配置中，请在「设置」中配置 API Key 后使用",
                color="#005f98",
                duration=3000,
            )
            return

        # 已配置时的处理入口（后端服务就绪后接入）
        self._show_snack("正在解析任务…", color="#005f98")

    def _on_attach(self, _) -> None:
        self._page.run_task(self._pick_attach_async)

    async def _pick_attach_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        try:
            files = await picker.pick_files(
                dialog_title="选择附件",
                allow_multiple=True,
            )
        except RuntimeError:
            self._show_snack("无法打开文件选择器，请检查系统环境")
            return
        if not files:
            self._page.update()
            return
        paths = [Path(f.path) for f in files if f.path]
        if paths:
            self._attached_files.extend(paths)
            self._rebuild_attach_list()
        self._page.update()

    def _rebuild_attach_list(self) -> None:
        self._attach_list.controls.clear()
        has_files = bool(self._attached_files)
        self._attach_list.visible = has_files
        for f in self._attached_files:
            chip = ft.Container(
                bgcolor="#ffffff",
                border=ft.border.all(1, "#d5e3ff"),
                border_radius=9999,
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ATTACHMENT, color="#005f98", size=14),
                        ft.Text(
                            f.name, size=12, color="#162f50",
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_color="#94a3b8",
                            icon_size=12,
                            tooltip="移除",
                            on_click=lambda _, path=f: self._remove_attach(path),
                            style=ft.ButtonStyle(
                                padding=ft.padding.all(2),
                                overlay_color=ft.Colors.with_opacity(0.08, "#dc2626"),
                            ),
                        ),
                    ],
                ),
            )
            self._attach_list.controls.append(chip)

    def _remove_attach(self, path: Path) -> None:
        if path in self._attached_files:
            self._attached_files.remove(path)
        self._rebuild_attach_list()
        self._page.update()

    def _on_mic(self, _) -> None:
        self._show_snack("语音输入需要系统麦克风权限，请在系统设置中授权后重试")

    def _show_snack(self, msg: str, color: str = "#005f98", duration: int = 2200) -> None:
        show_toast(self._page, msg, duration=duration, color=color)

    @staticmethod
    def _on_btn_hover(e: ft.ControlEvent) -> None:
        c = e.control
        if e.data == "true":
            c.bgcolor = "#f8fafc"
            c.border = ft.border.all(1, ft.Colors.with_opacity(0.3, "#005f98"))
        else:
            c.bgcolor = "#ffffff"
            c.border = ft.border.all(1, ft.Colors.with_opacity(0.1, "#97aed5"))
        c.update()
