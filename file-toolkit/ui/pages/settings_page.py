"""设置页 — 外观 / 文件 / 网络(OCR) / AI 生图 / 关于，每组一张白卡片。"""
import flet as ft

from core.ocr.client import INSTALL_HINT, find_tesseract, installed_languages
from core.version import app_license
from services import settings_service
from services.prompt_image_service import DEFAULT_BASE_URL, DEFAULT_MODEL
from ui import style as s
from ui.components.update_panel import UpdatePanel, VersionRow
from ui.palette import c
from ui.theme import apply_theme_mode
from ui.utils import show_toast


class SettingsPage(ft.Column):
    """设置页：外观 / 文件 / 网络(OCR) / AI 生图 / 关于"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=12)
        self._page = page
        self.controls = [
            self._build_header(),
            self._build_appearance(),
            self._build_file(),
            self._build_ocr(),
            self._build_ai_image(),
            self._build_about(),
            ft.Container(height=12),
        ]

    # ── 页头 ──────────────────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[s.text("设置", "headline"), s.text("个性化配置与系统偏好", "small")],
                spacing=4,
            ),
            padding=ft.Padding.only(left=s.PAGE_X, top=28, right=s.PAGE_X, bottom=4),
        )

    # ── 外观 ──────────────────────────────────────────────────────────
    def _build_appearance(self) -> ft.Control:
        current_mode = settings_service.get("theme_mode", "system")
        self._theme_tabs = s.Segmented(
            [("system", "跟随系统"), ("light", "浅色"), ("dark", "深色")],
            current_mode, on_change=self._on_theme_change,
        )
        return self._card("外观", ft.Icons.PALETTE_OUTLINED, [
            self._row("主题模式", ft.Row(controls=[self._theme_tabs])),
        ])

    def _on_theme_change(self, mode: str) -> None:
        settings_service.set("theme_mode", mode)

        async def _apply() -> None:
            # 等指示条滑到位再重建界面
            import asyncio
            await asyncio.sleep(0.4)
            apply_theme_mode(self._page, mode)

        self._page.run_task(_apply)

    # ── 文件 ──────────────────────────────────────────────────────────
    def _build_file(self) -> ft.Control:
        current_dir = settings_service.get("default_output_dir", "")
        self._output_dir_text = s.text(
            current_dir or "输入文件旁的 output 文件夹", "body", color="ink-2", expand=True,
        )
        current_after = settings_service.get("after_complete", "open_dir")
        self._after_tabs = s.Segmented(
            [("open_dir", "打开输出目录"), ("notify", "仅提示"), ("silent", "静默")],
            current_after, on_change=lambda v: settings_service.set("after_complete", v),
        )
        current_limit = settings_service.get("history_limit", "30")
        self._history_limit = ft.Dropdown(
            value=current_limit,
            options=[
                ft.dropdown.Option("10", "最近 10 条"),
                ft.dropdown.Option("30", "最近 30 条"),
                ft.dropdown.Option("50", "最近 50 条"),
                ft.dropdown.Option("100", "最近 100 条"),
            ],
            width=180, **self._dropdown_style(),
            on_select=lambda e: settings_service.set("history_limit", e.control.value),
        )
        return self._card("文件", ft.Icons.FOLDER_OUTLINED, [
            self._row("默认输出目录", ft.Row(controls=[
                self._output_dir_text,
                s.button("更改", self._pick_output_dir, kind="secondary", icon=ft.Icons.FOLDER_OPEN_OUTLINED),
                s.icon_button(ft.Icons.RESTART_ALT_OUTLINED, self._reset_output_dir, tooltip="恢复默认",
                              size=32, color="ink-3"),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)),
            self._row("处理完成后", ft.Row(controls=[self._after_tabs])),
            self._row("保留任务历史", self._history_limit),
        ])

    def _pick_output_dir(self, _) -> None:
        self._page.run_task(self._pick_output_dir_async)

    async def _pick_output_dir_async(self) -> None:
        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker()
        picker = self._file_picker
        try:
            path = await picker.get_directory_path(dialog_title="选择默认输出目录")
        except RuntimeError:
            path = None
        if path:
            settings_service.set("default_output_dir", path)
            self._output_dir_text.value = path
            self._output_dir_text.update()
        self._page.update()

    def _reset_output_dir(self, _) -> None:
        settings_service.set("default_output_dir", "")
        self._output_dir_text.value = "输入文件旁的 output 文件夹"
        self._output_dir_text.update()
        show_toast(self._page, "已恢复为输入文件旁的 output 文件夹")

    # ── 文字识别（OCR）────────────────────────────────────────────────
    def _build_ocr(self) -> ft.Control:
        """OCR 全部在本地用 Tesseract 识别，这里只显示引擎状态和安装方法。"""
        tess = find_tesseract()
        if tess:
            langs = installed_languages(tess)
            names = [label for key, label in (("chi_sim", "简体中文"), ("eng", "英文"), ("jpn", "日文"))
                     if key in langs]
            status = s.text(f"已就绪 · {'、'.join(names) or '未检测到语言包'}", "body", color="ink-2")
            location = s.text(str(tess), "small", selectable=True, max_lines=1,
                              overflow=ft.TextOverflow.ELLIPSIS, expand=True)
            rows = [self._row("Tesseract", status), self._row("位置", location)]
        else:
            rows = [
                self._row("Tesseract", s.text("未安装，图片识别不可用（PDF 内嵌文字仍可提取）",
                                              "body", color="ink-2")),
                self._row("安装方法", s.text(INSTALL_HINT.split("\n", 1)[1], "small", selectable=True)),
            ]
        return self._card("文字识别（OCR）", ft.Icons.DOCUMENT_SCANNER_OUTLINED, rows)

    # ── AI 生图 ────────────────────────────────────────────────────────
    def _build_ai_image(self) -> ft.Control:
        current_key = settings_service.get("ai_image_api_key", "")
        current_base = settings_service.get("ai_image_base_url", "") or DEFAULT_BASE_URL
        current_model = settings_service.get("ai_image_model", "") or DEFAULT_MODEL

        self._ai_image_key = s.text_field(
            current_key, "sk-...（留空则不启用）", password=True, can_reveal_password=True, expand=True,
        )
        self._ai_image_base = s.text_field(current_base, DEFAULT_BASE_URL, expand=True)
        self._ai_image_model = s.text_field(current_model, DEFAULT_MODEL, expand=True)

        save_btn = s.button("保存生图配置", self._save_ai_image_config, icon=ft.Icons.SAVE_OUTLINED)
        test_btn = s.button("测试连接", self._test_ai_image_connection, kind="secondary",
                            icon=ft.Icons.SCIENCE_OUTLINED)

        return self._card("AI 生图", ft.Icons.AUTO_FIX_HIGH_OUTLINED, [
            self._row("API Key", self._ai_image_key),
            self._row("Base URL", self._ai_image_base),
            self._row("模型名称", self._ai_image_model),
            ft.Container(
                content=ft.Row(
                    controls=[save_btn, test_btn],
                    spacing=8,
                ),
                padding=ft.Padding.only(left=156, top=12),
            ),
        ])

    def _save_ai_image_config(self, _) -> None:
        settings_service.set("ai_image_api_key", self._ai_image_key.value or "")
        settings_service.set("ai_image_base_url", self._ai_image_base.value or "")
        settings_service.set("ai_image_model", self._ai_image_model.value or "")
        if _ is not None:
            show_toast(self._page, "AI 生图配置已保存", kind="success")

    def _test_ai_image_connection(self, _) -> None:
        # 保证使用最新输入进行测试
        self._save_ai_image_config(None)
        if not (self._ai_image_key.value or "").strip():
            show_toast(self._page, "请先填写 API Key", kind="warning")
            return
        show_toast(self._page, "正在测试连接…")
        self._page.run_task(self._test_ai_image_connection_async)

    async def _test_ai_image_connection_async(self) -> None:
        from services import prompt_image_service
        ok, message = await prompt_image_service.check_connection()
        show_toast(self._page, message, kind="success" if ok else "error", duration=2600 if ok else 4500)

    # ── 关于 ──────────────────────────────────────────────────────────
    def _build_about(self) -> ft.Control:
        auto_check = s.Segmented(
            [("1", "启动时检查"), ("0", "仅手动检查")],
            settings_service.get("auto_check_update", "1"),
            on_change=lambda v: settings_service.set("auto_check_update", v),
        )
        return self._card("关于", ft.Icons.INFO_OUTLINED, [
            self._row("版本", VersionRow(self._page)),
            UpdatePanel(self._page),
            self._row("自动检查更新", ft.Row(controls=[auto_check])),
            self._row("开源协议", s.text(app_license() or "Apache-2.0", "body", color="ink-2")),
            self._row("字体", s.text("Geist / Geist Mono（SIL Open Font License）", "body", color="ink-2")),
        ])

    # ── 通用布局 ──────────────────────────────────────────────────────
    @staticmethod
    def _dropdown_style() -> dict:
        opts = s.field_style()
        opts.pop("label_style", None)
        return opts

    def _card(self, title: str, icon: str, children: list) -> ft.Control:
        return s.card(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[ft.Icon(icon, color=c("ink-2", "fg"), size=16), s.text(title, "title")],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(controls=children, spacing=0),
                ],
                spacing=10,
            ),
            padding=ft.Padding.only(left=20, right=20, top=18, bottom=10),
            margin=ft.Margin.symmetric(horizontal=s.PAGE_X),
        )

    def _row(self, label: str, control: ft.Control) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    s.text(label, "body", color="ink-2", width=140),
                    ft.Container(content=control, expand=True),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
            ),
            padding=ft.Padding.symmetric(vertical=10),
            border=ft.Border.only(top=ft.BorderSide(1, c("line"))),
        )
