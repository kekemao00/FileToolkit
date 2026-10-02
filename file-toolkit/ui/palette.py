"""
调色板 — 浅色 / 深色两套颜色的唯一来源。

页面里的颜色统一写成 `c("#162f50")` / `c("#ffffff", "fg")`：
  - 参数是浅色设计稿里的色值（保持与 Figma 对照可读）
  - 浅色模式原样返回；深色模式按下表换成对应深色值
  - role 区分同一色值的不同用途：
        "bg"（默认）填充、背景、边框、进度条轨道
        "fg"        文字、图标、强调色前景
    例如 #ffffff 作卡片背景时深色下变深灰，作蓝色按钮上的文字时保持白色。

页面在每次导航时重建，切换主题时 router 会重建侧栏和当前页，
因此 c() 在构建控件时求值即可，无需响应式绑定。

新增颜色时：浅色值直接写在页面里，再到下面两张表补上深色值；
没登记的色值在深色模式下原样输出（不会报错，但会显得突兀）。
"""
import flet as ft

_dark = False

# ── 深色：填充 / 背景 / 边框 ─────────────────────────────────────────
_DARK_BG: dict[str, str] = {
    # 中性面
    "#ffffff": "#1a2332",   # 卡片、面板
    "#f4f6ff": "#0f1620",   # 页面底色
    "#f8fafc": "#151d29",   # 次级面 / 输入框
    "#f1f5f9": "#1e2836",
    "#e2e8f0": "#2a3546",   # 分隔线、边框
    "#ebf1ff": "#16233a",   # 首页 Hero
    "#f0f7ff": "#16233a",
    "#000000": "#000000",   # 阴影
    "#1e3a8a": "#000000",
    # 品牌蓝 & 浅蓝 tint
    "#005f98": "#0a6aa8",
    "#00a3ff": "#0090e0",
    "#2aa7ff": "#2aa7ff",
    "#2563eb": "#2563eb",
    "#d5e3ff": "#1f3352",
    "#dee9ff": "#1f3150",
    "#cbdeff": "#23395c",
    "#dbeafe": "#1b3150",
    "#eff6ff": "#16304a",
    "#e0f4ff": "#16304a",
    "#e0f0ff": "#16304a",
    "#e0f2fe": "#16304a",
    "#ecf3ff": "#16304a",
    "#162f50": "#2b3a52",
    "#455c7f": "#2b3a52",
    "#61789c": "#3a4a66",
    "#94a3b8": "#3a4658",
    "#97aed5": "#3a4a66",
    # 绿
    "#16a34a": "#16a34a",
    "#059669": "#059669",
    "#10b981": "#10b981",
    "#d1fae5": "#0f2e22",
    "#dcfce7": "#10291d",
    "#f0fdf4": "#10291d",
    "#bbf7d0": "#1a4a33",
    # 红
    "#dc2626": "#dc2626",
    "#b91c1c": "#b91c1c",
    "#be123c": "#be123c",
    "#fb5151": "#fb5151",
    "#fee2e2": "#3a1a1f",
    "#fef2f2": "#3a1a1f",
    "#fff1f2": "#3a1a1f",
    "#ffe4e6": "#3a1a1f",
    "#fecdd3": "#5a2a30",
    "#fecaca": "#5a2a30",
    # 琥珀 / 橙
    "#fef3c7": "#33270f",
    "#fffbeb": "#33270f",
    "#fff7ed": "#33220f",
    "#ffedd5": "#33220f",
    "#fcd34d": "#5a4a1a",
    # 紫
    "#7c3aed": "#7c3aed",
    "#ede9fe": "#261a3d",
    "#faf5ff": "#261a3d",
    "#f3e8ff": "#261a3d",
    "#d9caff": "#3a2a60",
    # 青
    "#cffafe": "#0f2a30",
    "#ecfeff": "#0f2a30",
    "#00e3fd": "#00e3fd",
}

# ── 深色：文字 / 图标 / 前景强调色（没登记的回落到 _DARK_BG）─────────
_DARK_FG: dict[str, str] = {
    "#ffffff": "#ffffff",   # 彩色按钮上的白字
    "#ecf3ff": "#ecf3ff",
    "#f8fafc": "#f8fafc",
    "#000000": "#000000",
    "#1e3a8a": "#000000",
    # 文字层级
    "#162f50": "#e3eaf5",
    "#0f172a": "#f1f5f9",
    "#001d33": "#e3eaf5",
    "#00253f": "#cfe3ff",
    "#455c7f": "#a3b3cc",
    "#475569": "#a3b3cc",
    "#64748b": "#8b99ad",
    "#61789c": "#93a6c4",
    "#94a3b8": "#7c8aa0",
    "#97aed5": "#6d82a6",
    # 品牌
    "#005f98": "#6cb8f0",
    "#00a3ff": "#4dbbff",
    "#2aa7ff": "#5cbcff",
    "#2563eb": "#6b9bff",
    "#004d64": "#6cc6e0",
    "#d5e3ff": "#1f3352",
    "#cbdeff": "#9fc2ff",
    "#e2e8f0": "#2a3546",
    # 绿
    "#16a34a": "#4ade80",
    "#047857": "#34d399",
    "#059669": "#34d399",
    # 红
    "#dc2626": "#f87171",
    "#b91c1c": "#f87171",
    "#b31b25": "#f87171",
    "#be123c": "#fb7185",
    "#e11d48": "#fb7185",
    "#7f1d1d": "#fecaca",
    # 琥珀 / 橙
    "#d97706": "#fbbf24",
    "#b45309": "#fbbf24",
    "#92400e": "#fcd34d",
    "#ea580c": "#fb923c",
    # 紫
    "#7c3aed": "#a78bfa",
    "#6b1ef3": "#a78bfa",
    "#9333ea": "#c084fc",
    "#5500cd": "#c4b5fd",
    # 青
    "#0891b2": "#22d3ee",
    "#006571": "#5eead4",
    "#007276": "#5eead4",
    "#004d57": "#5eead4",
}


def c(color: str, role: str = "bg") -> str:
    """把浅色设计稿色值映射为当前主题下的色值。"""
    if not _dark:
        return color
    key = color.lower()
    if role == "fg":
        return _DARK_FG.get(key) or _DARK_BG.get(key, color)
    # 只登记在前景表里的是纯文字色，被当作参数传给辅助函数时也按文字处理
    return _DARK_BG.get(key) or _DARK_FG.get(key, color)


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
