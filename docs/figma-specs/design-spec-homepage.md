# Figma Design Spec — 首页 (Homepage)

> Extracted from Figma REST API node 1:2
> Frame size: 1280 x 1472
> Background: #F4F6FF

---

## 字体系统

| 用途 | 字体 | 字号 | 字重 | 颜色 |
|---|---|---|---|---|
| Hero 标题 | 42dot Sans | 48px | 500 | #162F50 |
| 区域标题 | 42dot Sans | 20px | 500 | #162F50 |
| Logo 文字 | 42dot Sans | 18px | 500 | #001D33 |
| 副标题描述 | 42dot Sans | 18px | 500 | #455C7F |
| 卡片标题 | 42dot Sans | 16px | 500 | #162F50 |
| CTA 按钮文字 | 42dot Sans | 16px | 500 | #ECF3FF |
| 次要按钮文字 | 42dot Sans | 16px | 500 | #005F98 |
| 导航项激活 | 42dot Sans | 14px | 500 | #00A3FF |
| 导航项未激活 | 42dot Sans | 14px | 500 | #475569 |
| 导航项未激活(灰) | 42dot Sans | 14px | 500 | #64748B |
| 查看全部链接 | 42dot Sans | 14px | 500 | #005F98 |
| 搜索占位符 | 42dot Sans | 13px | 500 | #94A3B8 |
| 卡片副标题 | 42dot Sans | 12px | 500 | #455C7F |
| 徽章文字 | 42dot Sans | 10px | 500 | #455C7F / #005F98 / #047857 / #B91C1C |
| 小标签 | 42dot Sans | 8px | 500 | #162F50 |
| 历史文件名 | Plus Jakarta Sans | 14px | 700 | #162F50 |
| 模块标题(卡片) | Plus Jakarta Sans | 16px | 700 | #162F50 |
| 历史操作名 | Plus Jakarta Sans | 12px | 500 | #455C7F |
| 文件大小 | Plus Jakarta Sans | 10px | 400 | #455C7F |
| 用户名 | Plus Jakarta Sans | 14px | 700 | #0F172A |

## 色彩系统

### 文字色
| 色值 | 用途 |
|---|---|
| #162F50 | 主要文字（标题、卡片标题）|
| #001D33 | Logo 文字、深色强调 |
| #0F172A | 用户名 |
| #455C7F | 次要文字（描述、标签）|
| #475569 | 导航未激活项 |
| #64748B | 弱化文字（免费用户标签、部分导航）|
| #94A3B8 | 占位符文字 |
| #ECF3FF | 深色背景上的文字（CTA 按钮）|

### 品牌色
| 色值 | 用途 |
|---|---|
| #005F98 | 主色调（链接、按钮、徽章）|
| #00A3FF | 激活态（导航激活、强调）|

### 状态色
| 色值 | 用途 |
|---|---|
| #047857 | 成功/已完成 |
| #B91C1C | 错误/失败 |

### 背景色
| 色值 | 用途 |
|---|---|
| #F4F6FF | 页面主背景 |
| #FFFFFF | 侧边栏、顶栏、卡片 |

## 布局结构

```
Frame: 1280 x 1472
├── Aside - Sidebar Navigation: 256px wide
│   ├── padding: 16px
│   ├── gap: 8px (nav items)
│   ├── bg: #FFFFFF (shadow layer)
│   └── Nav items: 223px wide, gap 4px
│
└── Main Content Area: 1024px wide
    ├── Header - Top Bar: 1024 x 80, bg #FFFFFF
    │
    └── Dashboard Content: padding 40px, gap 40px
        ├── Hero Section
        ├── Tool Cards Grid
        └── History Table
```

## 待补充
- [ ] 侧边栏详细结构（Logo区、导航项、用户区）
- [ ] Hero 区域详细结构（左侧文字+右侧特性卡片）
- [ ] 工具卡片网格详细结构（5列、图标、徽章）
- [ ] 历史操作表格详细结构
- [ ] 阴影、圆角、边框具体值
