# File Toolkit — 开发 TODO & 进度追踪

> 最后更新：2026-05-07 12:35
> Figma 设计稿：https://www.figma.com/design/KexCp8dbqlHhT2O2Po1u9A/
> 工作流：屎蛋儿(调度) → CC(开发) → Codex(Review)

---

## 📐 Figma 设计稿 Frame 清单（32 个）

| # | Frame 名称 | Node ID | 对应页面 | 状态 |
|---|---|---|---|---|
| 1 | 首页 | 1:2 | home_page.py | 🔄 全局基础已对齐，页面细节待 Phase 2 |
| 2 | AI智能任务 | 1:325 | ai_task_page.py | ⏳ 待对齐 |
| 3 | AI智能任务-拖拽文件 | 1:2083 | ai_task_page.py | ⏳ 待对齐 |
| 4 | PDF工具 | 1:473 | pdf_page.py | ⏳ 待对齐 |
| 5 | PDF工具-正在处理 | 3:2 | pdf_page.py | ⏳ 待对齐 |
| 6 | PDF工具-处理完成 | 10:2 | pdf_page.py | ⏳ 待对齐 |
| 7 | PDF工具-删除文件 | 10:690 | pdf_page.py | ⏳ 待对齐 |
| 8 | 图片工具-正在处理 | 11:1182 | image_*_page.py | ⏳ 待对齐 |
| 9 | 图片工具-处理完成 | 12:1955 | image_*_page.py | ⏳ 待对齐 |
| 10 | 压缩解压 | 1:1155 | archive_page.py | ⏳ 待对齐 |
| 11 | 压缩解压-待处理 | 20:5416 | archive_page.py | ⏳ 待对齐 |
| 12 | 压缩解压-正在处理 | 21:6757 | archive_page.py | ⏳ 待对齐 |
| 13 | 压缩解压-处理完成 | 21:7206 | archive_page.py | ⏳ 待对齐 |
| 14 | OCR识别 | 1:1395 | ocr_page.py | ⏳ 待对齐 |
| 15 | OCR识别-正在上传 | 22:8484 | ocr_page.py | ⏳ 待对齐 |
| 16 | OCR识别-上传完成 | 22:8763 | ocr_page.py | ⏳ 待对齐 |
| 17 | OCR识别-处理完成 | 23:9485 | ocr_page.py | ⏳ 待对齐 |
| 18 | 最近操作 | 1:1590 | history_page.py | ⏳ 待对齐 |
| 19 | 个人中心-专业版-未签到 | 31:10473 | settings_page.py(?) | ⏳ 待对齐 |
| 20 | 个人中心-免费版-已签到 | 31:11931 | settings_page.py(?) | ⏳ 待对齐 |
| 21 | 个人中心-免费版-未签到 | 31:12696 | settings_page.py(?) | ⏳ 待对齐 |
| 22 | 个人中心-专业版-已签到 | 31:11129 | settings_page.py(?) | ⏳ 待对齐 |
| 23 | AI智能任务-添加文件 | 1:2393 | ai_task_page.py | ⏳ 待对齐 |
| 24 | AI智能任务-文件上传中 | 1:2852 | ai_task_page.py | ⏳ 待对齐 |
| 25 | AI智能任务-文件上传完成 | 1:2997 | ai_task_page.py | ⏳ 待对齐 |
| 26 | AI智能任务-文件处理中 | 1:3224 | ai_task_page.py | ⏳ 待对齐 |
| 27 | AI智能任务-文件处理完成 | 1:3714 | ai_task_page.py | ⏳ 待对齐 |
| 28 | 音视频工具 | 13:2953 | media_page.py | ⏳ 待对齐 |
| 29 | 音视频工具-等待处理 | 14:3295 | media_*_page.py | ⏳ 待对齐 |
| 30 | 音视频工具-正在处理 | 14:3988 | media_*_page.py | ⏳ 待对齐 |
| 31 | 音视频工具-处理完成 | 15:4206 | media_*_page.py | ⏳ 待对齐 |
| 32 | 图片工具 | 17:4715 | image_page.py | ⏳ 待对齐 |

---

## 🎯 执行计划（按优先级排序）

### Phase 0 — 基础设施 ✅
- [x] Figma MCP 配置（mcporter + Personal Access Token）
- [x] Figma REST API 验证通过
- [x] 导出所有 Frame 截图到 `docs/figma-exports/`（32 张 PNG）
- [x] 创建本 TODO 文档
- [x] 提取首页设计规格到 `docs/figma-specs/design-spec-homepage.md`
- [x] 详细结构解析到 `docs/figma-specs/cc-task-phase1.md`

### Phase 1 — 全局基础组件 ✅
- [x] 字体系统更新（42dot Sans + Plus Jakarta Sans 替换 Manrope + Inter）
- [x] 色彩系统对齐（12 种文字色 + 品牌色 + 状态色 + 背景色）
- [x] 导航栏 (nav_rail.py) — 1:1 还原（激活态 #00A3FF 实色）
- [x] 顶部栏 (topbar) — 搜索框 pill 形 r=9999, 高 54px
- Commits: `915888b` `0f523fd` `fd7af61` `9346aab` `14a635f`

### Phase 2 — 首页 ✅
- [x] Hero 区域：标题 48px Bold + 副标题 italic + CTA 按钮
- [x] 工具卡片网格：左侧彩色竖条 + 图标颜色对齐 Figma
- [x] 最近操作表格：表头 #F8FAFC + 状态标签颜色
- Commit: `6fa39e1` (256 行改动)

### Phase 3 — PDF 模块（核心页面，最复杂）
- [ ] PDF 工具列表页（功能卡片布局）
- [ ] PDF 合并页面（拖拽区+文件列表+参数面板）
- [ ] 正在处理状态
- [ ] 处理完成状态
- [ ] 删除文件确认态

### Phase 4 — 图片模块
- [ ] 图片工具列表页
- [ ] 各操作页面的拖拽区+参数面板
- [ ] 正在处理/处理完成状态

### Phase 5 — 音视频模块
- [ ] 音视频工具列表页
- [ ] 各操作页面
- [ ] 等待/处理中/完成状态

### Phase 6 — 压缩解压模块
- [ ] 压缩解压主页（Tab 切换）
- [ ] 待处理/处理中/完成状态

### Phase 7 — AI 智能任务
- [ ] AI 任务主页
- [ ] 拖拽/添加/上传/处理 全流程状态

### Phase 8 — OCR 识别
- [ ] OCR 主页
- [ ] 上传/处理 全流程状态

### Phase 9 — 最近操作 & 个人中心
- [ ] 最近操作列表页
- [ ] 个人中心页面（免费版/专业版 × 签到/未签到）

### Phase 10 — 收尾
- [ ] 深色主题适配
- [ ] 响应式布局
- [ ] 交互状态完善（hover/drag/error）
- [ ] Windows 打包测试

---

## 📝 开发日志

### 2026-05-07
- **11:34** 项目启动，大佬提供 Figma Token
- **12:00** Figma API 验证成功，获取 32 个 Frame 结构
- **12:01** 开始批量导出 Frame 截图（6 张/批次，共 6 批次）
- **12:05** 创建 TODO.md 开发追踪文档
- **12:15** CC 配置修复（AUTH_TOKEN + API_KEY 双设置），Codex 执行 Phase 1
- **12:30** ✅ Phase 1 完成！5 个 commit 全局基础组件 1:1 对齐 Figma
  - 字体：Manrope+Inter → 42dot Sans+Plus Jakarta Sans
  - 色彩：完整 Figma 色彩系统（12 种文字色 + 品牌色 + 状态色 + 背景色）
  - 导航栏：激活态 #00A3FF 实色、白色文字、r=12、shadow 对齐
  - 顶部栏：搜索框 pill 形 r=9999、h=54px、bg #F8FAFC
  - 全局：所有页面 Manrope → 42dot Sans 替换
- **12:35** 大佬重新配置 CC，准备 Phase 2 开发
