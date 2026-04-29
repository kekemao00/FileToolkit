"""设置页 — Figma 设计语言统一"""
import flet as ft

from services import settings_service


class SettingsPage(ft.Column):
    """设置页：外观 / 文件 / 网络(OCR) / 关于"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._page = page
        self.controls = [
            self._build_header(),
            self._build_appearance(),
            self._build_file(),
            self._build_network(),
            self._build_about(),
            ft.Container(height=40),
        ]

    # ── 页头 ──────────────────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.SETTINGS, color="#005f98", size=24),
                        width=48, height=48, bgcolor="#dee9ff", border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("设置", size=24, weight=ft.FontWeight.W_600, color="#162f50", font_family="Manrope"),
                            ft.Text("个性化配置与系统偏好", size=14, color="#455c7f", font_family="Manrope"),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=40, top=32, right=40, bottom=24),
        )

    # ── 外观 ──────────────────────────────────────────────────────────
    def _build_appearance(self) -> ft.Control:
        current_mode = settings_service.get("theme_mode", "system")
        self._theme_radio = ft.RadioGroup(
            value=current_mode,
            content=ft.Row(controls=[
                ft.Radio(value="system", label="跟随系统"),
                ft.Radio(value="light", label="浅色"),
                ft.Radio(value="dark", label="深色"),
            ], spacing=24),
            on_change=self._on_theme_change,
        )
        return self._card("外观", ft.Icons.PALETTE_OUTLINED, "#9333ea", "#faf5ff", [
            self._row("主题模式", self._theme_radio),
        ])

    def _on_theme_change(self, e: ft.ControlEvent) -> None:
        mode = e.data
        settings_service.set("theme_mode", mode)
        mode_enum = {"system": ft.ThemeMode.SYSTEM, "light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK}
        self._page.theme_mode = mode_enum[mode]
        self._page.update()

    # ── 文件 ──────────────────────────────────────────────────────────
    def _build_file(self) -> ft.Control:
        current_dir = settings_service.get("default_output_dir", "")
        self._output_dir_text = ft.Text(
            current_dir or "（使用输入文件所在目录）",
            size=13, color="#455c7f", expand=True,
        )
        current_after = settings_service.get("after_complete", "open_dir")
        self._after_radio = ft.RadioGroup(
            value=current_after,
            content=ft.Row(controls=[
                ft.Radio(value="open_dir", label="打开输出目录"),
                ft.Radio(value="notify", label="仅提示"),
                ft.Radio(value="silent", label="静默"),
            ], spacing=24),
            on_change=lambda e: settings_service.set("after_complete", e.data),
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
            width=180, border_radius=12,
            on_select=lambda e: settings_service.set("history_limit", e.control.value),
        )
        return self._card("文件", ft.Icons.FOLDER_OUTLINED, "#2563eb", "#eff6ff", [
            self._row("默认输出目录", ft.Row(controls=[
                self._output_dir_text,
                ft.OutlinedButton(
                    "更改", on_click=self._pick_output_dir,
                    icon=ft.Icons.FOLDER_OPEN,
                    style=ft.ButtonStyle(
                        color="#005f98",
                        side=ft.BorderSide(1, "#d5e3ff"),
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                ),
            ], spacing=12)),
            self._row("处理完成后", self._after_radio),
            self._row("保留任务历史", self._history_limit),
        ])

    def _pick_output_dir(self, _) -> None:
        self._page.run_task(self._pick_output_dir_async)

    async def _pick_output_dir_async(self) -> None:
        picker = ft.FilePicker()
        self._page.overlay.append(picker)
        self._page.update()
        try:
            path = await picker.get_directory_path(dialog_title="选择默认输出目录")
        except RuntimeError:
            path = None
        finally:
            self._page.overlay.remove(picker)
        if path:
            settings_service.set("default_output_dir", path)
            self._output_dir_text.value = path
            self._output_dir_text.update()
        self._page.update()

    # ── 网络（OCR）────────────────────────────────────────────────────
    def _build_network(self) -> ft.Control:
        current_provider = settings_service.get("ocr_provider", "baidu")
        self._ocr_provider = ft.Dropdown(
            value=current_provider,
            options=[
                ft.dropdown.Option("baidu", "百度 OCR"),
                ft.dropdown.Option("tencent", "腾讯 OCR"),
            ],
            width=180, border_radius=12,
            on_select=lambda e: settings_service.set("ocr_provider", e.control.value),
        )
        self._api_key_field = ft.TextField(
            value="", password=True, can_reveal_password=True,
            hint_text="API Key", border_radius=12, expand=True,
            bgcolor="#f8fafc", border_color="transparent",
        )
        self._secret_key_field = ft.TextField(
            value="", password=True, can_reveal_password=True,
            hint_text="Secret Key", border_radius=12, expand=True,
            bgcolor="#f8fafc", border_color="transparent",
        )
        return self._card("网络（OCR 高级功能）", ft.Icons.LANGUAGE, "#0891b2", "#ecfeff", [
            self._row("OCR 服务商", self._ocr_provider),
            self._row("API Key", self._api_key_field),
            self._row("Secret Key", self._secret_key_field),
            ft.Container(
                content=self._build_save_button(),
                padding=ft.padding.only(left=156, top=4),
            ),
        ])

    def _build_save_button(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE, color="#ffffff", size=16),
                    ft.Text(
                        "保存 API 配置", size=14, color="#ffffff",
                        font_family="Manrope", weight=ft.FontWeight.W_500,
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
            border_radius=12,
            padding=ft.padding.symmetric(vertical=10, horizontal=20),
            shadow=ft.BoxShadow(
                blur_radius=12, spread_radius=-3,
                color=ft.Colors.with_opacity(0.15, "#005f98"),
                offset=ft.Offset(0, 6),
            ),
            on_click=self._save_api_keys,
            ink=True,
        )

    def _save_api_keys(self, _) -> None:
        settings_service.set("ocr_api_key", self._api_key_field.value or "")
        settings_service.set("ocr_secret_key", self._secret_key_field.value or "")
        self._page.snack_bar = ft.SnackBar(content=ft.Text("API 配置已保存"), bgcolor="#005f98")
        self._page.snack_bar.open = True
        self._page.update()

    # ── 关于 ──────────────────────────────────────────────────────────
    def _build_about(self) -> ft.Control:
        return self._card("关于", ft.Icons.INFO_OUTLINED, "#005f98", "#dee9ff", [
            self._row("版本", ft.Text("v1.0.0（Windows MVP）", size=13, color="#455c7f")),
            self._row("开源协议", ft.Text("MIT License", size=13, color="#455c7f")),
        ])

    # ── 通用布局 ──────────────────────────────────────────────────────
    def _card(self, title: str, icon: str, icon_color: str, icon_bg: str, children: list) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(icon, color=icon_color, size=18),
                                width=36, height=36, bgcolor=icon_bg, border_radius=10,
                                alignment=ft.Alignment(0, 0),
                            ),
                            ft.Text(title, size=16, weight=ft.FontWeight.W_600, color="#162f50", font_family="Manrope"),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(controls=children, spacing=0),
                ],
                spacing=16,
            ),
            bgcolor="#ffffff",
            border_radius=16,
            padding=ft.padding.all(24),
            margin=ft.margin.only(left=40, right=40, top=8, bottom=8),
            shadow=ft.BoxShadow(blur_radius=1, color=ft.Colors.with_opacity(0.05, "#000000"), offset=ft.Offset(0, 1)),
        )

    def _row(self, label: str, control: ft.Control) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(label, size=14, color="#162f50", width=140, font_family="Manrope"),
                    ft.Container(content=control, expand=True),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
            ),
            padding=ft.padding.symmetric(vertical=12),
            border=ft.border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.3, "#dee9ff"))),
        )
