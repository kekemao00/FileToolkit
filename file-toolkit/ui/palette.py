"""
调色板 — 浅色 / 深色两套颜色的唯一来源（暖灰黑白风格）。

设计令牌（warm-mono）：浅暖灰底、白色表面、墨黑元素，强调色只有一个 #2F5BFF，
只用在主操作、选中态、焦点态；danger 只用于错误和危险操作。

新代码直接写令牌名：`c("ink")`、`c("surface")`、`c("accent")`。

旧页面里的写法 `c("#162f50")` / `c("#ffffff", "fg")` 继续有效：
  - 参数是旧设计稿里的色值，下表把它映射到对应令牌
  - role 区分同一色值的不同用途：
        "bg"（默认）填充、背景、边框、进度条轨道
        "fg"        文字、图标、强调色前景
    例如 #ffffff 作卡片背景时是 surface，作实心按钮上的文字时是 on-ink
    （深色模式下主按钮反转为浅底深字，on-ink 随之变成深色）。

页面在每次导航时重建，切换主题时 router 会重建侧栏和当前页，
因此 c() 在构建控件时求值即可，无需响应式绑定。

没登记的色值原样输出（不会报错，但会显得突兀），新增颜色请用令牌。
"""
import flet as ft

_dark = False

# ── 令牌：(浅色, 深色) ────────────────────────────────────────────────
TOKENS: dict[str, tuple[str, str]] = {
    "canvas":      ("#EFEEEA", "#161614"),   # 窗口 / 页面背景
    "surface":     ("#FFFFFF", "#1E1E1C"),   # 卡片、输入框、面板
    "surface-2":   ("#F6F5F2", "#252523"),   # 表面上的悬停、次级填充
    "surface-3":   ("#ECEBE7", "#2C2B28"),   # 按下态、头像底、幽灵按钮悬停
    "ink":         ("#141413", "#F2F1ED"),   # 主文字、主按钮、指示条
    "ink-hover":   ("#2B2A28", "#DCDAD4"),   # 主按钮悬停
    "ink-2":       ("#5E5B56", "#A8A49C"),   # 次级文字
    "ink-3":       ("#9A968F", "#6F6B64"),   # 占位符、提示、表头
    "on-ink":      ("#FFFFFF", "#141413"),   # 墨黑实心块上的文字 / 图标
    "line":        ("#E3E1DC", "#2E2D2A"),   # 分隔线、默认描边
    "line-strong": ("#CFCCC5", "#3D3B37"),   # 悬停描边、标签描边
    "accent":      ("#2F5BFF", "#2F5BFF"),   # 唯一强调色（填充）
    "accent-fg":   ("#2F5BFF", "#7391FF"),   # 强调色作文字 / 图标（深色下提亮保证可读）
    "accent-soft": ("#E8EDFF", "#1D2442"),   # 选中行底色
    "on-accent":   ("#FFFFFF", "#FFFFFF"),
    "danger":      ("#D93B2B", "#E5574A"),
    "danger-soft": ("#FCEBE8", "#3A201C"),
    "scrim":       ("#1A1814", "#000000"),
    "shadow":      ("#000000", "#000000"),
}

# ── 旧色值 → (作填充时的令牌, 作文字时的令牌) ─────────────────────────
_NEUTRAL_TINT = ("surface-3", "ink-2")
_LEGACY: dict[str, tuple[str, str]] = {
    # 中性面
    "#ffffff": ("surface", "on-ink"),
    "#f4f6ff": ("canvas", "canvas"),
    "#f8fafc": ("surface-2", "surface-2"),
    "#f1f5f9": ("surface-2", "surface-2"),
    "#ebf1ff": ("surface-2", "surface-2"),
    "#f0f7ff": ("surface-2", "surface-2"),
    "#e2e8f0": ("line", "line"),
    "#000000": ("shadow", "shadow"),
    "#1e3a8a": ("shadow", "shadow"),
    # 品牌蓝 → 墨黑（主操作、图标、链接）
    "#005f98": ("ink", "ink"),
    "#00a3ff": ("ink", "ink"),
    "#2aa7ff": ("ink", "ink"),
    "#2563eb": ("ink", "ink"),
    "#162f50": ("ink", "ink"),
    "#0f172a": ("ink", "ink"),
    "#001d33": ("ink", "ink"),
    "#00253f": ("ink", "ink"),
    # 浅蓝 tint → 中性灰
    "#d5e3ff": ("surface-3", "ink-2"),
    "#dee9ff": ("surface-3", "ink-2"),
    "#cbdeff": ("surface-3", "on-ink"),
    "#dbeafe": ("surface-3", "ink-2"),
    "#eff6ff": ("surface-3", "ink-2"),
    "#e0f4ff": ("surface-3", "ink-2"),
    "#e0f0ff": ("surface-3", "ink-2"),
    "#e0f2fe": ("surface-3", "ink-2"),
    "#ecf3ff": ("surface-3", "on-ink"),
    # 次级 / 三级文字
    "#455c7f": ("ink-2", "ink-2"),
    "#475569": ("ink-2", "ink-2"),
    "#64748b": ("ink-2", "ink-2"),
    "#61789c": ("ink-3", "ink-2"),
    "#94a3b8": ("line-strong", "ink-3"),
    "#97aed5": ("line-strong", "ink-3"),
    # 绿（成功）→ 强调色
    "#16a34a": ("accent", "accent-fg"),
    "#059669": ("accent", "accent-fg"),
    "#10b981": ("accent", "accent-fg"),
    "#047857": ("accent", "accent-fg"),
    "#d1fae5": ("accent-soft", "accent-fg"),
    "#dcfce7": ("accent-soft", "accent-fg"),
    "#f0fdf4": ("accent-soft", "accent-fg"),
    "#bbf7d0": ("accent-soft", "accent-fg"),
    # 红（错误）→ danger
    "#dc2626": ("danger", "danger"),
    "#b91c1c": ("danger", "danger"),
    "#be123c": ("danger", "danger"),
    "#fb5151": ("danger", "danger"),
    "#e11d48": ("danger", "danger"),
    "#b31b25": ("danger", "danger"),
    "#7f1d1d": ("danger", "danger"),
    "#fee2e2": ("danger-soft", "danger"),
    "#fef2f2": ("danger-soft", "danger"),
    "#fff1f2": ("danger-soft", "danger"),
    "#ffe4e6": ("danger-soft", "danger"),
    "#fecdd3": ("danger-soft", "danger"),
    "#fecaca": ("danger-soft", "danger"),
    # 琥珀 / 橙（提醒）→ 墨黑，不另设颜色
    "#d97706": ("ink", "ink"),
    "#b45309": ("ink", "ink"),
    "#92400e": ("ink", "ink"),
    "#ea580c": ("ink", "ink"),
    "#f59e0b": ("ink", "ink"),
    "#fef3c7": _NEUTRAL_TINT,
    "#fffbeb": _NEUTRAL_TINT,
    "#fff7ed": _NEUTRAL_TINT,
    "#ffedd5": _NEUTRAL_TINT,
    "#fcd34d": ("line-strong", "ink-2"),
    # 紫 / 青 → 墨黑与中性灰
    "#7c3aed": ("ink", "ink"),
    "#6b1ef3": ("ink", "ink"),
    "#9333ea": ("ink", "ink"),
    "#5500cd": ("ink", "ink"),
    "#ede9fe": _NEUTRAL_TINT,
    "#faf5ff": _NEUTRAL_TINT,
    "#f3e8ff": _NEUTRAL_TINT,
    "#d9caff": _NEUTRAL_TINT,
    "#0891b2": ("ink", "ink"),
    "#006571": ("ink-2", "ink-2"),
    "#007276": ("ink-2", "ink-2"),
    "#004d57": ("ink-2", "ink-2"),
    "#004d64": ("ink-2", "ink-2"),
    "#00e3fd": ("surface-3", "ink-2"),
    "#cffafe": _NEUTRAL_TINT,
    "#ecfeff": _NEUTRAL_TINT,
}


def t(token: str) -> str:
    """令牌名 → 当前主题下的色值。"""
    light, dark = TOKENS[token]
    return dark if _dark else light


def c(color: str, role: str = "bg") -> str:
    """令牌名或旧设计稿色值 → 当前主题下的色值。"""
    if color in TOKENS:
        return t(color)
    entry = _LEGACY.get(color.lower())
    if entry is None:
        return color
    return t(entry[1] if role == "fg" else entry[0])


def is_dark() -> bool:
    return _dark


def set_dark(dark: bool) -> None:
    global _dark
    _dark = dark


def resolve_dark(mode: str, page: ft.Page) -> bool:
    """theme_mode 设置值 → 是否深色。system 跟随系统亮度。"""
    if mode == "dark":
        return True
    if mode == "light":
        return False
    return page.platform_brightness == ft.Brightness.DARK
