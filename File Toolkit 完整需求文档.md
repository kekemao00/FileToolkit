# File Toolkit — 完整需求文档

---

## 一、产品定位

| 项目 | 内容 |
|---|---|
| **产品名称** | File Toolkit（待定） |
| **产品类型** | 跨平台本地文件处理工具 |
| **目标用户** | 有文件处理需求的普通用户 / 办公人群 |
| **核心价值** | 本地离线、安全、现代美观、一站式文件处理 |
| **竞品参考** | CleanMyMac、iLovePDF、HandBrake、Bandizip |
| **UI 风格** | Material Design 3，深色/浅色主题，现代感 |

---

## 二、平台优先级与打包目标

```
Phase 1 ── Windows   → .exe 安装包（第一优先，跑通完整功能）
Phase 2 ── macOS     → .dmg/.app
           Linux     → AppImage / .deb
Phase 3 ── Android   → .apk / Google Play（原生开发主导）
           iOS       → .ipa / App Store
```

> **移动端策略**：Android 原生开发（Kotlin）通过本地 FastAPI 服务调用 Python Core Engine，充分发挥原生开发经验，UI 体验最佳，Core Engine 完全复用。

---

## 三、功能需求清单

### 🔴 必须有（MVP）

#### 📄 PDF 工具

| 功能 | 说明 | 离线 |
|---|---|:---:|
| PDF 分割 | 按页数 / 按范围 / 每页单独拆分 | ✅ |
| PDF 合并 | 多文件合并，支持拖拽排序 | ✅ |
| PDF 压缩 | 可选压缩质量（高/中/低） | ✅ |
| PDF → Word | 还原排版转为 .docx | ✅ |
| PDF → Excel | 表格提取转为 .xlsx | ✅ |
| PDF → PPT | 转为 .pptx | ✅ |
| Word/Excel/PPT → PDF | Office 文件转 PDF | ✅ |

#### 🖼️ 图片工具

| 功能 | 说明 | 离线 |
|---|---|:---:|
| 格式转换 | JPG/PNG/WebP/HEIC/BMP/TIFF 互转 | ✅ |
| 批量压缩 | 可设目标质量或目标文件大小 | ✅ |
| 水印 | 文字水印 / 图片水印，可设位置透明度 | ✅ |
| 批量重命名 | 支持规则模板 | ✅ |

#### 🎬 音视频工具

| 功能 | 说明 | 离线 |
|---|---|:---:|
| 视频格式转换 | MP4/AVI/MKV/MOV/WMV | ✅ |
| 音频提取 | 视频 → MP3/AAC/WAV | ✅ |
| 音频格式转换 | MP3/AAC/FLAC/WAV 互转 | ✅ |
| 视频压缩 | 可选分辨率/码率 | ✅ |
| 视频剪切 | 按时间段裁剪 | ✅ |

#### 📦 压缩解压

| 功能 | 说明 | 离线 |
|---|---|:---:|
| 压缩 | zip / 7z / tar.gz | ✅ |
| 解压 | zip / 7z / rar / tar.gz | ✅ |
| 加密压缩 | 支持密码保护 | ✅ |
| 分卷压缩 | 按大小分卷 | ✅ |

---

### 🟡 可以有（V2 迭代）

| 功能 | 说明 | 离线 |
|---|---|:---:|
| PDF OCR 识别 | 扫描件转可编辑文字 | ❌ 联网 API |
| PDF 加密/解密 | 密码保护 PDF | ✅ |
| PDF 水印 | 文字/图片水印 | ✅ |
| 图片裁剪/旋转 | 基础编辑 | ✅ |
| Excel ↔ CSV/JSON | 数据格式互转 | ✅ |
| 二维码生成/识别 | 文件/链接生成二维码 | ✅ |
| 文件哈希校验 | MD5/SHA256 | ✅ |
| 批量任务历史 | 记录操作历史可重复执行 | ✅ |

---

## 四、技术架构方案

```
┌─────────────────────────────────────────────────────┐
│                    UI Layer                          │
│              Flet (Flutter 渲染引擎)                  │
│         Material Design 3 / 深色浅色主题              │
└────────────────────┬────────────────────────────────┘
                     │ 调用
┌────────────────────▼────────────────────────────────┐
│                  Core Engine                         │
│              纯 Python 业务逻辑层                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ PDF模块  │ │ 图片模块  │ │ 音视频   │ │ 压缩   │ │
│  │ pypdf    │ │ Pillow   │ │ ffmpeg   │ │ py7zr  │ │
│  │ pdf2docx │ │          │ │ -python  │ │ zipfile│ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│  ┌─────────────────────────────────────────────────┐ │
│  │         Feature Flags（平台能力检测）             │ │
│  └─────────────────────────────────────────────────┘ │
└────────────────────┬────────────────────────────────┘
                     │ 重型功能
┌────────────────────▼────────────────────────────────┐
│              Cloud API（可选联网）                    │
│         OCR / 超大文件转换 / 云端备份                 │
└─────────────────────────────────────────────────────┘
```

### 核心依赖库

| 模块 | 库 | 说明 |
|---|---|---|
| PDF | `pypdf` + `pdf2docx` + `pikepdf` | 分割合并转换加密 |
| Office→PDF | `LibreOffice CLI`（桌面内嵌） | 最稳跨平台方案 |
| 图片 | `Pillow` + `pillow-heif` | 含 HEIC 支持 |
| 音视频 | `ffmpeg-python` + 内嵌 FFmpeg | 必须内嵌二进制 |
| 压缩 | `py7zr` + `rarfile` + `zipfile` | 全格式覆盖 |
| UI | `flet >= 0.21` | Flutter 渲染 |
| 异步任务 | `asyncio` + `concurrent.futures` | 大文件不卡 UI |
| OCR API | `httpx` + 百度OCR / 腾讯OCR | 联网调用 |

---

## 五、移动端专项策略

| 方案 | 说明 | 推荐度 |
|---|---|:---:|
| **方案A：Flet 统一打包** | Python 一套代码直接 `flet build apk`，UI 自动适配 | ⭐⭐⭐ |
| **方案B：原生 App + Chaquopy** | Android 原生 UI（Kotlin），通过 Chaquopy 调用 Python Core | ⭐⭐⭐⭐ |
| **方案C：原生 App + 本地 API** ✅ | Android 原生 UI，启动本地 FastAPI 服务，HTTP 调用 | ⭐⭐⭐⭐⭐ |

> **推荐方案 C**：充分发挥 Android 10 年经验，UI 体验最好，Core Engine 完全复用，架构最清晰。

---

## 六、开发阶段规划

```
Phase 1（Windows MVP）  预计 4~6 周
  ├── Core Engine 搭建（PDF + 图片 + 压缩）
  ├── Flet UI 框架搭建（主题/路由/组件库）
  ├── 音视频模块（内嵌 FFmpeg）
  └── Windows 打包为 .exe 安装包

Phase 2（桌面完善）  预计 2~3 周
  ├── Office ↔ PDF（内嵌 LibreOffice）
  ├── V2 功能（水印/加密/OCR接入）
  ├── macOS / Linux 打包
  └── 自动更新机制

Phase 3（移动端）  预计 4~8 周
  ├── Android（方案C：原生UI + Python后端）
  └── iOS（Flet 打包 或 原生）
```

---

## 七、关键风险与应对

| 风险 | 影响 | 应对方案 |
|---|---|---|
| LibreOffice 内嵌包体积大（~200MB） | 安装包过大 | 首次启动按需下载，或云端转换兜底 |
| FFmpeg 授权问题 | 商业分发合规 | 使用 LGPL 版本 FFmpeg，动态链接 |
| iOS 沙箱限制 | 文件访问受限 | 使用系统 Files API，支持 iCloud |
| pdf2docx 复杂排版还原度不足 | 用户体验差 | 标注"复杂排版可能有偏差"，提供云端高精度转换选项 |
| Flet 移动端性能 | UI 卡顿 | 大任务放线程池，UI 只做进度展示 |

---

## 八、产品分发与商业化（初步）

| 类型 | 内容 |
|---|---|
| **免费功能** | 所有核心离线功能（PDF/图片/压缩/音视频） |
| **付费功能** | OCR识别 / 云端高精度转换 / 批量任务无限制 |
| **Windows 分发** | 官网直接下载 .exe 安装包 |
| **Android 分发** | Google Play / 直接分发 APK |
| **iOS 分发** | App Store |

---

## 九、项目目录结构（规划）

```
file-toolkit/
├── main.py                      # Flet 统一入口
├── pyproject.toml
├── core/                        # 纯 Python 业务逻辑（无 UI 依赖）
│   ├── pdf/
│   │   ├── splitter.py
│   │   ├── merger.py
│   │   ├── compressor.py
│   │   ├── converter.py         # PDF ↔ Office
│   │   ├── watermark.py
│   │   └── encryptor.py
│   ├── image/
│   │   ├── converter.py
│   │   ├── compressor.py
│   │   └── watermark.py
│   ├── media/
│   │   ├── video.py
│   │   └── audio.py
│   ├── archive/
│   │   └── handler.py
│   └── feature_flags.py         # 平台能力检测
├── ui/
│   ├── theme.py                 # 全局主题配置
│   ├── router.py                # 路由管理
│   ├── pages/
│   │   ├── home.py
│   │   ├── pdf_page.py
│   │   ├── image_page.py
│   │   ├── media_page.py
│   │   └── archive_page.py
│   └── components/
│       ├── file_picker.py
│       ├── progress_card.py
│       └── action_card.py
├── api/                         # 移动端本地 FastAPI 服务（可选）
│   ├── main.py
│   └── routers/
│       ├── pdf.py
│       ├── image.py
│       └── media.py
└── build/
    ├── Makefile                 # 一键多平台打包
    └── build_all.sh
```