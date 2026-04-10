"""设置页 — 外观/文件/网络/关于"""
import flet as ft

from services import settings_service


class SettingsPage(ft.Column):
    """设置页：主题切换、默认输出目录、OCR API Key、关于"""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self.spacing = 0
        self.controls = [
            self._build_header(),
            self._build_appearance_section(),
            self._build_file_section(),
            self._build_network_section(),
            self._build_about_section(),
        ]

    # ── 页头 ────────────────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Text(
                "设置",
                style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                font_family="Manrope",
                weight=ft.FontWeight.W_600,
            ),
            padding=ft.padding.fromLTRB(28, 28, 28, 20),
        )

    # ── 外观 ────────────────────────────────────────────────────────
    def _build_appearance_section(self) -> ft.Control:
        current_mode = settings_service.get("theme_mode", "system")
        mode_map = {"system": 0, "light": 1, "dark": 2}
        self._theme_radio = ft.RadioGroup(
            value=current_mode,
            content=ft.Row(
                controls=[
                    ft.Radio(value="system", label="跟随系统"),
                    ft.Radio(value="light",  label="浅色"),
                    ft.Radio(value="dark",   label="深色"),
                ],
                spacing=24,
            ),
            on_change=self._on_theme_change,
        )
        return self._build_section(
            title="🎨 外观",
            children=[
                self._build_row("主题模式", self._theme_radio),
            ],
        )

    def _on_theme_change(self, e: ft.ControlEvent) -> None:
        mode = e.data
        settings_service.set("theme_mode", mode)
        mode_enum = {
            "system": ft.ThemeMode.SYSTEM,
            "light":  ft.ThemeMode.LIGHT,
            "dark":   ft.ThemeMode.DARK,
        }
        self._page.theme_mode = mode_enum[mode]
        self._page.update()

    # ── 文件 ────────────────────────────────────────────────────────
    def _build_file_section(self) -> ft.Control:
        current_dir = settings_service.get("default_output_dir", "")
        self._output_dir_text = ft.Text(
            current_dir or "（使用输入文件所在目录）",
            color=ft.Colors.ON_SURFACE_VARIANT,
            size=13,
            expand=True,
        )

        current_after = settings_service.get("after_complete", "open_dir")
        self._after_radio = ft.RadioGroup(
            value=current_after,
            content=ft.Row(
                controls=[
                    ft.Radio(value="open_dir", label="打开输出目录"),
                    ft.Radio(value="notify",   label="仅提示"),
                    ft.Radio(value="silent",   label="静默"),
                ],
                spacing=24,
            ),
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
            width=180,
            on_change=lambda e: settings_service.set("history_limit", e.data),
        )

        return self._build_section(
            title="📁 文件",
            children=[
                self._build_row(
                    "默认输出目录",
                    ft.Row(
                        controls=[
                            self._output_dir_text,
                            ft.OutlinedButton(
                                "更改",
                                on_click=self._pick_output_dir,
                                icon=ft.Icons.FOLDER_OPEN,
                            ),
                        ],
                        spacing=12,
                    ),
                ),
                self._build_row("处理完成后", self._after_radio),
                self._build_row("保留任务历史", self._history_limit),
            ],
        )

    def _pick_output_dir(self, _: ft.ControlEvent) -> None:
        def on_result(e: ft.FilePickerResultEvent) -> None:
            if e.path:
                settings_service.set("default_output_dir", e.path)
                self._output_dir_text.value = e.path
                self._output_dir_text.update()

        picker = ft.FilePicker(on_result=on_result)
        self._page.overlay.append(picker)
        self._page.update()
        picker.get_directory_path(dialog_title="选择默认输出目录")

    # ── 网络（OCR）─────────────────────────────────────────────────
    def _build_network_section(self) -> ft.Control:
        current_provider = settings_service.get("ocr_provider", "baidu")
        self._ocr_provider = ft.Dropdown(
            value=current_provider,
            options=[
                ft.dropdown.Option("baidu",   "百度 OCR"),
                ft.dropdown.Option("tencent", "腾讯 OCR"),
            ],
            width=180,
            on_change=lambda e: settings_service.set("ocr_provider", e.data),
        )

        self._api_key_field = ft.TextField(
            value="",
            password=True,
            can_reveal_password=True,
            hint_text="API Key",
            border_radius=8,
            expand=True,
        )
        self._secret_key_field = ft.TextField(
            value="",
            password=True,
            can_reveal_password=True,
            hint_text="Secret Key",
            border_radius=8,
            expand=True,
        )

        return self._build_section(
            title="🌐 网络（OCR 高级功能）",
            children=[
                self._build_row("OCR 服务商", self._ocr_provider),
                self._build_row("API Key",    self._api_key_field),
                self._build_row("Secret Key", self._secret_key_field),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.FilledButton(
                                "保存 API 配置",
                                on_click=self._save_api_keys,
                                icon=ft.Icons.SAVE,
                            ),
                        ],
                    ),
                    padding=ft.padding.only(top=4),
                ),
            ],
        )

    def _save_api_keys(self, _: ft.ControlEvent) -> None:
        # 实际项目中应存 keyring，这里先存 SQLite 占位
        settings_service.set("ocr_api_key", self._api_key_field.value or "")
        settings_service.set("ocr_secret_key", self._secret_key_field.value or "")
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text("API 配置已保存"),
            bgcolor=ft.Colors.TERTIARY,
        )
        self._page.snack_bar.open = True
        self._page.update()

    # ── 关于 ────────────────────────────────────────────────────────
    def _build_about_section(self) -> ft.Control:
        return self._build_section(
            title="ℹ️ 关于",
            children=[
                self._build_row(
                    "版本",
                    ft.Text("v1.0.0  （Windows MVP）", color=ft.Colors.ON_SURFACE_VARIANT, size=13),
                ),
                self._build_row(
                    "开源协议",
                    ft.Text("MIT License", color=ft.Colors.ON_SURFACE_VARIANT, size=13),
                ),
            ],
        )

    # ── 通用布局辅助 ─────────────────────────────────────────────────
    def _build_section(self, title: str, children: list[ft.Control]) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        title,
                        weight=ft.FontWeight.W_600,
                        font_family="Manrope",
                        size=16,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    ft.Container(
                        content=ft.Column(controls=children, spacing=0),
                        border_radius=ft.border_radius.all(16),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    ),
                ],
                spacing=10,
            ),
            padding=ft.padding.fromLTRB(28, 8, 28, 8),
        )

    def _build_row(self, label: str, control: ft.Control) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        label,
                        size=14,
                        color=ft.Colors.ON_SURFACE,
                        width=140,
                    ),
                    ft.Container(content=control, expand=True),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
        )
