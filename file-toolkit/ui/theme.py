"""
File Toolkit — 全局主题配置（暖灰黑白 · 弹簧动效风格）

色彩：见 ui/palette.py 的令牌。浅暖灰底、白色表面、墨黑元素、单一强调色 #2F5BFF。
字体：Geist（拉丁字母和数字）、Geist Mono（编号、大小等等宽数字），
      中文由系统字体回落（PingFang SC / Microsoft YaHei UI / Noto Sans SC）。
无阴影、无涟漪、无渐变：层次靠 canvas / surface 的明度差和 1px 描边表达。
"""
from collections.abc import Callable

import flet as ft

from ui import style as s
from ui.palette import c, resolve_dark, set_dark, t


def build_color_scheme() -> ft.ColorScheme:
    """按当前深浅色生成 ColorScheme（调用前先 set_dark）。"""
    return ft.ColorScheme(
        primary=t("ink"),
        on_primary=t("on-ink"),
        primary_container=t("surface-3"),
        on_primary_container=t("ink"),
        secondary=t("ink-2"),
        on_secondary=t("surface"),
        secondary_container=t("surface-3"),
        on_secondary_container=t("ink"),
        tertiary=t("accent"),
        on_tertiary=t("on-accent"),
        tertiary_container=t("accent-soft"),
        on_tertiary_container=t("ink"),
        surface=t("surface"),
        on_surface=t("ink"),
        on_surface_variant=t("ink-2"),
        surface_container_lowest=t("surface"),
        surface_container_low=t("surface"),
        surface_container=t("surface"),
        surface_container_high=t("surface"),
        surface_container_highest=t("surface-2"),
        surface_bright=t("surface"),
        surface_dim=t("surface-2"),
        surface_tint=ft.Colors.TRANSPARENT,
        outline=t("line-strong"),
        outline_variant=t("line"),
        shadow=ft.Colors.TRANSPARENT,
        scrim=t("scrim"),
        error=t("danger"),
        on_error="#FFFFFF",
        error_container=t("danger-soft"),
        on_error_container=t("danger"),
        inverse_surface=t("ink"),
        on_inverse_surface=t("on-ink"),
        inverse_primary=t("surface"),
    )


def build_text_theme() -> ft.TextTheme:
    """color 显式写入：Flet 不会按深浅色替换自定义 TextStyle 的默认文字色。"""
    ink, ink2 = t("ink"), t("ink-2")

    def ts(size: float, weight: ft.FontWeight, color: str = ink) -> ft.TextStyle:
        return ft.TextStyle(size=size, weight=weight, color=color, font_family=s.FONT)

    return ft.TextTheme(
        display_large=ts(28, ft.FontWeight.W_600),
        display_medium=ts(24, ft.FontWeight.W_600),
        display_small=ts(22, ft.FontWeight.W_600),
        headline_large=ts(22, ft.FontWeight.W_600),
        headline_medium=ts(20, ft.FontWeight.W_600),
        headline_small=ts(17, ft.FontWeight.W_600),
        title_large=ts(15, ft.FontWeight.W_600),
        title_medium=ts(14, ft.FontWeight.W_500),
        title_small=ts(13, ft.FontWeight.W_500),
        body_large=ts(14, ft.FontWeight.W_400),
        body_medium=ts(13, ft.FontWeight.W_400),
        body_small=ts(12, ft.FontWeight.W_400, ink2),
        label_large=ts(13, ft.FontWeight.W_500),
        label_medium=ts(12, ft.FontWeight.W_500),
        label_small=ts(11, ft.FontWeight.W_500, ink2),
    )


def _button_style(bg: str | None, fg: str, border: str | None = None) -> ft.ButtonStyle:
    hover_bg = t("ink-hover") if bg == t("ink") else t("surface-2") if bg else None
    return ft.ButtonStyle(
        bgcolor={ft.ControlState.HOVERED: hover_bg, ft.ControlState.DEFAULT: bg} if bg else None,
        color=fg,
        icon_color=fg,
        overlay_color=ft.Colors.TRANSPARENT if bg else ft.Colors.with_opacity(0.75, t("surface-3")),
        shadow_color=ft.Colors.TRANSPARENT,
        elevation=0,
        side=ft.BorderSide(1, border) if border else None,
        shape=ft.RoundedRectangleBorder(radius=s.R_BUTTON),
        padding=ft.Padding.symmetric(horizontal=14, vertical=0),
        text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_500, font_family=s.FONT),
        animation_duration=s.DUR_SNAPPY,
    )


def _build_theme() -> ft.Theme:
    ink = t("ink")
    return ft.Theme(
        color_scheme=build_color_scheme(),
        text_theme=build_text_theme(),
        primary_text_theme=build_text_theme(),
        font_family=s.FONT,
        use_material3=True,
        visual_density=ft.VisualDensity.COMPACT,
        scaffold_bgcolor=t("canvas"),
        canvas_color=t("surface"),
        card_bgcolor=t("surface"),
        divider_color=t("line"),
        hint_color=t("ink-3"),
        splash_color=ft.Colors.TRANSPARENT,
        highlight_color=ft.Colors.TRANSPARENT,
        hover_color=ft.Colors.with_opacity(0.75, t("surface-3")),
        focus_color=ft.Colors.with_opacity(0.22, t("accent")),
        button_theme=ft.ButtonTheme(style=_button_style(ink, t("on-ink"))),
        filled_button_theme=ft.FilledButtonTheme(style=_button_style(ink, t("on-ink"))),
        outlined_button_theme=ft.OutlinedButtonTheme(
            style=_button_style(t("surface"), ink, t("line"))
        ),
        text_button_theme=ft.TextButtonTheme(style=_button_style(None, t("ink-2"))),
        icon_button_theme=ft.IconButtonTheme(style=ft.ButtonStyle(
            overlay_color=ft.Colors.with_opacity(0.75, t("surface-3")),
            shape=ft.RoundedRectangleBorder(radius=s.R_BUTTON),
            animation_duration=s.DUR_SNAPPY,
        )),
        scrollbar_theme=ft.ScrollbarTheme(
            thickness={ft.ControlState.HOVERED: 8, ft.ControlState.DEFAULT: 5},
            radius=8,
            thumb_color={
                ft.ControlState.HOVERED: ft.Colors.with_opacity(0.42, ink),
                ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.22, ink),
            },
            track_visibility=False,
            cross_axis_margin=2,
        ),
        tooltip_theme=ft.TooltipTheme(
            text_style=ft.TextStyle(size=12, color=t("on-ink"), font_family=s.FONT),
            padding=ft.Padding.symmetric(horizontal=9, vertical=6),
            wait_duration=450,
            decoration=ft.BoxDecoration(bgcolor=ink, border_radius=8),
        ),
        dialog_theme=ft.DialogTheme(
            bgcolor=t("surface"),
            elevation=0,
            shadow_color=ft.Colors.TRANSPARENT,
            barrier_color=ft.Colors.with_opacity(0.26, t("scrim")),
            shape=ft.RoundedRectangleBorder(
                radius=s.R_PANEL, side=ft.BorderSide(1, t("line"))
            ),
            title_text_style=ft.TextStyle(
                size=15, weight=ft.FontWeight.W_600, color=ink, font_family=s.FONT
            ),
            content_text_style=ft.TextStyle(size=13, color=t("ink-2"), font_family=s.FONT),
        ),
        popup_menu_theme=ft.PopupMenuTheme(
            color=t("surface"),
            elevation=0,
            shadow_color=ft.Colors.TRANSPARENT,
            shape=ft.RoundedRectangleBorder(radius=10, side=ft.BorderSide(1, t("line-strong"))),
            label_text_style=ft.TextStyle(size=13, color=ink, font_family=s.FONT),
        ),
        progress_indicator_theme=ft.ProgressIndicatorTheme(
            color=ink,
            linear_track_color=t("surface-3"),
            circular_track_color=ft.Colors.TRANSPARENT,
        ),
        divider_theme=ft.DividerTheme(color=t("line"), thickness=1, space=1),
        checkbox_theme=ft.CheckboxTheme(
            fill_color={ft.ControlState.SELECTED: ink, ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT},
            check_color=t("on-ink"),
            border_side=ft.BorderSide(1.5, t("line-strong")),
            shape=ft.RoundedRectangleBorder(radius=5),
            overlay_color=ft.Colors.TRANSPARENT,
        ),
        radio_theme=ft.RadioTheme(
            fill_color={ft.ControlState.SELECTED: ink, ft.ControlState.DEFAULT: t("line-strong")},
            overlay_color=ft.Colors.TRANSPARENT,
        ),
        switch_theme=ft.SwitchTheme(
            thumb_color={ft.ControlState.SELECTED: t("on-ink"), ft.ControlState.DEFAULT: t("surface")},
            track_color={ft.ControlState.SELECTED: ink, ft.ControlState.DEFAULT: t("line-strong")},
            track_outline_color={ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT},
            overlay_color=ft.Colors.TRANSPARENT,
        ),
        slider_theme=ft.SliderTheme(
            active_track_color=ink,
            inactive_track_color=t("surface-3"),
            thumb_color=ink,
            overlay_color=ft.Colors.TRANSPARENT,
            value_indicator_color=ink,
        ),
        list_tile_theme=ft.ListTileTheme(
            text_color=ink,
            icon_color=t("ink-2"),
            selected_tile_color=t("accent-soft"),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
        snackbar_theme=ft.SnackBarTheme(
            bgcolor=ink,
            elevation=0,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=20),
            content_text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_500, color=t("on-ink"),
                                            font_family=s.FONT),
        ),
    )


def get_app_theme() -> tuple[ft.Theme, ft.Theme]:
    set_dark(False)
    light = _build_theme()
    set_dark(True)
    dark = _build_theme()
    set_dark(False)
    return light, dark


# ── 主题切换 ─────────────────────────────────────────────────────────
# 页面颜色在构建时通过 c() 求值，切换主题后需要重建界面；
# router 在初始化时注册重建函数。
_rebuild_hooks: dict[int, Callable[[], None]] = {}


def set_rebuild_hook(page: ft.Page, hook: Callable[[], None]) -> None:
    _rebuild_hooks[id(page)] = hook


def apply_theme_mode(page: ft.Page, mode: str) -> None:
    """应用主题模式（system / light / dark）并重建界面。"""
    dark = resolve_dark(mode, page)
    set_dark(dark)
    page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
    page.bgcolor = c("canvas")
    hook = _rebuild_hooks.get(id(page))
    if hook:
        hook()
