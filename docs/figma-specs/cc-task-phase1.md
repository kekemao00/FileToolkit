# CC Task: Phase 1 — 全局基础 1:1 Figma 还原

## 目标
将 File Toolkit 的全局 UI 组件（字体、色彩、导航栏、顶栏）与 Figma 设计稿 1:1 对齐。

## Figma 设计稿参考
- 截图目录: `docs/figma-exports/` (32 张 PNG)
- 重点参考: `01-home.png` (首页完整截图)
- 设计数据: `docs/figma-specs/homepage-full.json`

## 任务清单

### 1. 字体系统更新

**当前代码** 使用 Manrope + Inter
**Figma 设计** 使用 42dot Sans + Plus Jakarta Sans

行动:
- 下载 42dot Sans 字体（Google Fonts: https://fonts.google.com/specimen/42dot+Sans）
- 下载 Plus Jakarta Sans 字体（Google Fonts: https://fonts.google.com/specimen/Plus+Jakarta+Sans）
- 放到 `file-toolkit/assets/fonts/` 目录
- 更新 `ui/theme.py` 的 font_family 引用
- 更新 `main.py` 的 page.fonts 注册
- 全局替换所有页面中的 `font_family="Manrope"` → `font_family="42dot Sans"`
- 全局替换所有页面中的 `font_family="Inter"` → `font_family="Plus Jakarta Sans"`（仅在需要 Plus Jakarta Sans 的地方）

### 2. 色彩系统对齐

**Figma 精确色值** (从设计稿提取):

```
# 主要文字色
PRIMARY_TEXT = "#162F50"      # 标题、卡片标题
DARK_TEXT = "#001D33"         # Logo 文字、深色强调
DARK_TEXT_2 = "#0F172A"      # 用户名

# 次要文字色
SECONDARY_TEXT = "#455C7F"   # 描述、标签
TERTIARY_TEXT = "#475569"    # 导航未激活
MUTED_TEXT = "#64748B"       # 弱化文字
PLACEHOLDER_TEXT = "#94A3B8" # 占位符

# 品牌色
PRIMARY = "#005F98"          # 主色调
PRIMARY_ACTIVE = "#00A3FF"   # 激活态
CTA_TEXT = "#ECF3FF"         # CTA 按钮文字

# 状态色
SUCCESS = "#047857"          # 成功/已完成
ERROR = "#B91C1C"            # 错误/失败

# 背景色
PAGE_BG = "#F4F6FF"          # 页面主背景
CARD_BG = "#FFFFFF"          # 卡片、侧边栏、顶栏
HERO_BG = "#EBF1FF"          # Hero 区域背景
SEARCH_BG = "#F8FAFC"        # 搜索框背景
NAV_ACTIVE_BG = "#00A3FF"    # 导航激活背景(实色)
NAV_ACTIVE_TEXT = "#FFFFFF"  # 导航激活文字

# 边框/分割线
BORDER = "#E2E8F0"           # 边框
```

行动:
- 更新 `ui/theme.py` 的 ColorScheme，对齐上述色值
- 确保所有页面使用统一的色彩 token

### 3. 侧边导航栏 (nav_rail.py) 1:1 还原

**Figma 设计规格:**
- 整体宽度: 256px
- 背景: #FFFFFF，阴影 offset=(0,20) blur=25 spread=-5 rgba(30,58,138,0.05)
- 内边距: 16px
- Logo 区: 高 80px，图标 48x48 r=8 + 标题+副标题，右侧 margin 32px
- 导航项: 223x44, r=12, padding=[12,16,12,16], gap=12px (icon+text), 间距 4px
- 激活态: bg=#00A3FF (实色!), r=12, 文字白色, 图标白色
- 未激活态: 无背景, r=12, 文字 #475569, 图标 #475569
- 底部用户区: 223x73, 分隔线, r=8

**当前代码差异:**
- 激活态用 rgba(0,163,255,0.08) 半透明 → 应改为 #00A3FF 实色
- 激活态文字颜色需要调整为白色
- 阴影参数需要对齐
- 导航项高度/间距需要精确匹配

行动:
- 重写 `ui/components/nav_rail.py`，严格按 Figma 规格
- 特别注意激活态的实色背景 #00A3FF

### 4. 顶部栏 (topbar) 1:1 还原

**Figma 设计规格:**
- 高度: 80px，背景: #FFFFFF
- 阴影: offset=(0,1) blur=2 spread=0 rgba(0,0,0,0.05)
- 搜索框: 288x54, bg=#F8FAFC, r=9999 (pill 形), padding=[6,14,6,14]
- 搜索框占位符: "搜索功能或指令...", 13px, #94A3B8
- 右侧按钮区: gap ~12

**当前代码差异:**
- 搜索框高度 36px → 应为 54px
- 搜索框圆角 18px → 应为 9999px (pill)
- 背景色可能不匹配

行动:
- 更新 `home_page.py` 的 `_build_topbar()` 方法
- 精确匹配 Figma 规格

## 执行顺序
1. 先下载字体文件
2. 更新 theme.py (色彩+字体)
3. 更新 main.py (字体注册)
4. 重写 nav_rail.py
5. 更新 topbar (home_page.py)
6. 全局替换字体引用
7. 运行 `uv run python main.py` 验证效果

## 注意事项
- 字体文件放到 `file-toolkit/assets/fonts/` 目录
- 保留旧字体文件作为 fallback
- 每完成一步 git commit
- 运行时使用 WSL: `cd /mnt/b/FileToolkit/file-toolkit && source .venv/bin/activate && python main.py`
