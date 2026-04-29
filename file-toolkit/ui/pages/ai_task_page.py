"""AI 智能任务页 — 基于 Figma 设计稿 1:325 的 1:1 复刻"""
import flet as ft


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
    """AI 智能任务：Hero + 输入控制台 + 状态指示器"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self._page = page

        self._input_field = ft.TextField(
            hint_text="描述您想完成的任务...",
            hint_style=ft.TextStyle(color="#97aed5", size=16),
            border=ft.InputBorder.NONE,
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=4,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        )

        self.controls = [self._build_content()]

    # ── 整体内容（可滚动） ──────────────────────────────
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
                    # AI 头像
                    self._build_ai_avatar(),
                    # 标题
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
                    # 副标题
                    ft.Container(
                        width=512,
                        padding=ft.padding.symmetric(horizontal=4),
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
        # 外层旋转边框 1（12° 旋转）
        border_outer = ft.Container(
            width=192, height=192,
            alignment=ft.Alignment(0, 0),
            content=ft.Container(
                width=172, height=172,
                border_radius=32,
                border=ft.border.all(2, ft.Colors.with_opacity(0.2, "#005f98")),
                rotate=ft.Rotate(angle=0.21),  # ~12°
            ),
        )
        # 外层旋转边框 2（-6° 旋转）
        border_inner = ft.Container(
            width=192, height=192,
            alignment=ft.Alignment(0, 0),
            content=ft.Container(
                width=164, height=164,
                border_radius=32,
                border=ft.border.all(2, ft.Colors.with_opacity(0.2, "#6b1ef3")),
                rotate=ft.Rotate(angle=-0.105),  # ~-6°
            ),
        )
        # 渐变核心方块
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
        # 动态光晕
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
                    # 光晕层
                    ft.Container(
                        width=192, height=192,
                        alignment=ft.Alignment(0, 0),
                        content=aura,
                    ),
                    # 旋转边框
                    border_outer,
                    border_inner,
                    # 核心
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
            padding=ft.padding.symmetric(horizontal=64),
            content=ft.Container(
                width=896,
                padding=ft.padding.symmetric(horizontal=24),
                content=ft.Column(
                    spacing=24,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # Prompt 建议按钮
                        self._build_prompt_suggestions(),
                        # 主输入控制台
                        self._build_input_console(),
                        # 底部状态指示器
                        self._build_status_indicators(),
                    ],
                ),
            ),
        )

    def _build_prompt_suggestions(self) -> ft.Control:
        """3 个 Prompt 建议按钮"""
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
                            item["label"],
                            size=14,
                            color="#162f50",
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
        )

    def _build_input_console(self) -> ft.Control:
        """毛玻璃风格主输入控制台"""
        # 附件按钮
        attach_btn = ft.Container(
            padding=8,
            border_radius=8,
            ink=True,
            on_click=self._on_attach,
            content=ft.Icon(ft.Icons.ATTACH_FILE, color="#455c7f", size=20),
        )
        # 麦克风按钮
        mic_btn = ft.Container(
            padding=8,
            border_radius=8,
            ink=True,
            content=ft.Icon(ft.Icons.MIC_NONE, color="#455c7f", size=19),
        )
        # 发送按钮
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

        # 内部行
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

        # 外层毛玻璃容器
        return ft.Container(
            border_radius=16,
            border=ft.border.all(1, "#ffffff"),
            bgcolor=ft.Colors.with_opacity(0.7, "#ffffff"),
            blur=ft.Blur(8, 8),
            shadow=ft.BoxShadow(
                blur_radius=50,
                spread_radius=-12,
                color=ft.Colors.with_opacity(0.05, "#005f98"),
                offset=ft.Offset(0, 25),
            ),
            padding=9,
            content=inner_row,
        )

    def _build_status_indicators(self) -> ft.Control:
        """底部 3 个状态指示器"""
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
                        ind["label"],
                        size=11,
                        color="#61789c",
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
            return
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text("AI 任务解析功能即将上线，敬请期待"),
            bgcolor="#005f98",
        )
        self._page.snack_bar.open = True
        self._page.update()

    def _on_attach(self, _) -> None:
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text("文件附件功能即将上线"),
            bgcolor="#005f98",
        )
        self._page.snack_bar.open = True
        self._page.update()

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
