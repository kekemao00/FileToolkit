# File Toolkit — 技术开发文档

> 版本：v1.0 | 阶段：Windows MVP | 日期：2026-04-10
> 基于：需求文档 v1.0 + 设计原型文档 v0.1 + Stitch 设计稿 + 产品全景思维导图

---

## 一、项目概述

### 1.1 产品定位

| 维度 | 内容 |
|---|---|
| **产品名称** | File Toolkit（文件全能王） |
| **产品类型** | 跨平台本地文件处理桌面工具 |
| **核心价值** | 本地离线 · 安全可靠 · 现代美观 · 一站式文件处理 |
| **目标用户** | 有文件批处理需求的办公人群 |
| **竞品参考** | iLovePDF、CleanMyMac、HandBrake、Bandizip |

### 1.2 平台交付目标

```
Phase 1（当前）── Windows  → .exe NSIS 安装包
Phase 2         ── macOS   → .dmg/.app
                   Linux   → AppImage / .deb
Phase 3         ── Android → 原生 Kotlin + 本地 FastAPI 服务
                   iOS     → Flet 打包 / 原生
```

---

## 二、技术选型决策

### 2.1 核心技术栈

| 层级 | 选型 | 版本要求 | 选型理由 |
|---|---|---|---|
| **UI 框架** | Flet | >= 0.24 | Flutter 渲染引擎，Material Design 3，Python 原生调用 |
| **运行时** | Python | >= 3.11 | 充分利用异步特性，类型提示完备 |
| **打包工具** | PyInstaller + flet build | 最新稳定版 | Windows .exe 单文件输出，Flet 内置打包链路 |
| **异步模型** | asyncio + ThreadPoolExecutor | 内置 | 重型 CPU 任务跑线程池，I/O 任务用协程，UI 永不卡顿 |
| **本地存储** | SQLite（via sqlite3 内置） | 内置 | 任务历史记录，设置持久化 |
| **配置管理** | TOML（tomllib 内置）| 内置 | pyproject.toml 风格，可读性强 |

### 2.2 功能模块依赖库

| 模块 | 主库 | 辅助库 | 说明 |
|---|---|---|---|
| **PDF 处理** | `pypdf >= 4.0` | `pikepdf >= 9.0` | 分割/合并/加密，pypdf 负责结构，pikepdf 负责低层操作 |
| **PDF↔Office** | `pdf2docx >= 0.5.8` | `LibreOffice CLI` | pdf2docx 做 PDF→Word，LibreOffice CLI 做 Office→PDF（最可靠跨平台方案） |
| **图片处理** | `Pillow >= 10.0` | `pillow-heif >= 0.16` | HEIC/HEIF 格式支持，需额外注册解码器 |
| **音视频处理** | `ffmpeg-python >= 0.2.0` | 内嵌 FFmpeg 二进制 | 必须内嵌 LGPL 版 FFmpeg，不依赖系统安装 |
| **压缩解压** | `py7zr >= 0.21` | `rarfile >= 4.1` + `zipfile`(内置) | py7zr 覆盖 7z/tar，rarfile 解压 rar（仅解压），zipfile 内置 |
| **HTTP 客户端** | `httpx >= 0.27` | — | 联网 OCR API 调用，支持异步 |
| **UI 框架** | `flet >= 0.24` | — | 见 2.1 |

### 2.3 关键依赖版本锁定（pyproject.toml）

```toml
[project]
name = "file-toolkit"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "flet>=0.24,<1.0",
    "pypdf>=4.0,<5.0",
    "pikepdf>=9.0,<10.0",
    "pdf2docx>=0.5.8,<0.6.0",
    "Pillow>=10.0,<11.0",
    "pillow-heif>=0.16,<1.0",
    "ffmpeg-python>=0.2.0,<0.3.0",
    "py7zr>=0.21,<0.22",
    "rarfile>=4.1,<5.0",
    "httpx>=0.27,<1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 2.4 外部二进制依赖

| 依赖 | 版本 | 内嵌方式 | 授权 |
|---|---|---|---|
| FFmpeg | 7.x LGPL | `bin/ffmpeg.exe`（Windows），动态链接 | LGPL v2.1，商业合规 |
| LibreOffice | 24.x | 可选：按需下载或检测系统安装 | MPL v2，开源 |

> **LibreOffice 策略**：启动时检测系统是否已安装 LibreOffice，若未安装则在 Office→PDF 功能入口处提示引导下载，避免将 ~200MB 内嵌进安装包。

---

## 三、系统架构设计

### 3.1 整体分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer                              │
│  Flet (Flutter Engine) · Material Design 3 · 深色/浅色主题  │
│  pages/ · components/ · theme.py · router.py                │
└──────────────────────────┬──────────────────────────────────┘
                           │ 调用（纯函数接口，无 UI 依赖）
┌──────────────────────────▼──────────────────────────────────┐
│                      Service Layer                           │
│  TaskService · HistoryService · SettingsService              │
│  负责：参数验证、任务调度、进度回调、结果封装                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ 调用
┌──────────────────────────▼──────────────────────────────────┐
│                      Core Engine                             │
│  ┌───────────┐ ┌────────────┐ ┌──────────┐ ┌────────────┐  │
│  │ core/pdf/ │ │core/image/ │ │core/media│ │core/archive│  │
│  │ pypdf     │ │ Pillow     │ │ ffmpeg   │ │ py7zr      │  │
│  │ pikepdf   │ │ pillow-heif│ │ -python  │ │ rarfile    │  │
│  │ pdf2docx  │ │            │ │          │ │ zipfile    │  │
│  └───────────┘ └────────────┘ └──────────┘ └────────────┘  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  platform.py — LibreOffice/FFmpeg 路径检测与注入        │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │ 可选联网
┌──────────────────────────▼──────────────────────────────────┐
│                     Cloud API Layer                          │
│  OCR：百度 OCR API / 腾讯 OCR API（httpx 异步调用）          │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 异步任务流转图

```
用户点击"开始"
      │
      ▼
TaskService.submit(task_params)
      │
      ├── 参数验证（同步，快速返回）
      │
      ▼
asyncio.get_event_loop().run_in_executor(
    ThreadPoolExecutor,
    core_function,        ← 阻塞型 CPU 任务跑在线程池
    *args
)
      │
      ├── 进度回调：core 函数通过 progress_callback(current, total) 定期上报
      │
      ▼
UI 层通过 page.update() 刷新进度条（Flet 线程安全）
      │
      ▼
完成 → HistoryService.save(task_result)
      │
      ▼
UI 展示结果页（文件列表 + 打开目录按钮）
```

### 3.3 设计系统要求（来自 Stitch 设计稿）

设计稿采用「The Fluid Architect」设计系统，关键规范如下：

**色彩系统（严格遵守）**

| Token | 值 | 用途 |
|---|---|---|
| `primary` | `#004d64` | 主按钮、主要强调色 |
| `primary-container` | `#006684` | 渐变搭配、CTA 渐变终点 |
| `secondary` | `#4d616c` | 图片模块强调 |
| `tertiary` | `#004f4f` | 音视频模块强调、成功状态 |
| `surface` | `#f7f9fe` | 页面底层背景 |
| `surface-container-low` | `#f1f4f8` | 功能区域背景 |
| `surface-container-lowest` | `#ffffff` | 卡片背景 |
| `on-surface` | `#181c1f` | 主文字（禁用纯黑 #000000）|
| `error` | `#ba1a1a` | 错误状态 |

**No-Line 规则**：禁止 1px solid 边框，用背景色渐变区分层级。若需无障碍兼容，边框用 `outline-variant`（`#bfc8cd`）且透明度 ≤ 15%。

**圆角规范**

| 元素 | 圆角 |
|---|---|
| 功能卡片（Action Card）| `1.5rem`（24px，xl 级） |
| 标准卡片 | `1rem`（16px，lg 级） |
| 按钮（分段控件） | `9999px`（full，pill 形） |
| 进度条 | `9999px`（full） |
| 输入框 | `0.5rem`（8px）|

**字体**

- 标题/Display：**Manrope**（`headlineFont`）
- 正文/Label：**Inter**（`bodyFont` + `labelFont`）

**CTA 按钮渐变**：`linear-gradient(135deg, #004d64, #006684)`

**模块色彩映射**（导航栏激活态 + 图标色）

| 模块 | 强调色 Token |
|---|---|
| PDF | `primary`（`#004d64`）|
| 图片 | `secondary`（`#4d616c`）|
| 音视频 | `tertiary`（`#004f4f`）|
| 压缩解压 | `surface-tint`（`#016684`）|
| OCR/AI | `primary-fixed-variant`（`#004d64` 深色）|

---

## 四、项目目录结构

```
file-toolkit/
├── main.py                         # Flet app 入口，注册路由，启动窗口
├── pyproject.toml                  # 项目配置、依赖声明
├── assets/
│   ├── fonts/
│   │   ├── Manrope-*.ttf           # 标题字体（SemiBold、Bold）
│   │   └── Inter-*.ttf             # 正文字体（Regular、Medium）
│   ├── icons/
│   │   └── app_icon.ico            # 应用图标（Windows）
│   └── bin/
│       ├── ffmpeg.exe              # 内嵌 FFmpeg（Windows LGPL）
│       └── ffprobe.exe             # 内嵌 FFprobe
│
├── core/                           # 纯 Python 业务逻辑（无任何 UI 依赖）
│   ├── __init__.py
│   ├── platform.py                 # 检测 FFmpeg/LibreOffice 路径
│   ├── models.py                   # 任务参数/结果数据类（dataclass）
│   ├── exceptions.py               # 自定义异常类型
│   ├── pdf/
│   │   ├── __init__.py
│   │   ├── splitter.py             # PDF 分割
│   │   ├── merger.py               # PDF 合并（含拖拽排序输入）
│   │   ├── compressor.py           # PDF 压缩（pikepdf）
│   │   ├── converter.py            # PDF↔Office（pdf2docx + LibreOffice）
│   │   ├── watermark.py            # PDF 水印（V2）
│   │   └── encryptor.py            # PDF 加密/解密（V2）
│   ├── image/
│   │   ├── __init__.py
│   │   ├── converter.py            # 图片格式转换（含 HEIC）
│   │   ├── compressor.py           # 批量压缩（质量模式/大小模式）
│   │   ├── watermark.py            # 文字/图片水印
│   │   └── renamer.py              # 批量重命名（规则模板）
│   ├── media/
│   │   ├── __init__.py
│   │   ├── video.py                # 视频格式转换/压缩/剪切
│   │   └── audio.py                # 音频格式转换/提取
│   ├── archive/
│   │   ├── __init__.py
│   │   └── handler.py              # 压缩/解压（zip/7z/tar.gz/rar）
│   └── ocr/
│       ├── __init__.py
│       └── client.py               # OCR API 封装（百度/腾讯，httpx）
│
├── services/                       # 业务服务层（参数校验、调度、历史）
│   ├── __init__.py
│   ├── task_service.py             # 任务提交、线程池管理、进度回调
│   ├── history_service.py          # 任务历史 CRUD（SQLite）
│   └── settings_service.py         # 用户设置读写（TOML）
│
├── ui/                             # Flet UI 层
│   ├── __init__.py
│   ├── theme.py                    # 全局 ColorScheme、字体注册、主题切换
│   ├── router.py                   # 路由注册与导航管理
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── home_page.py            # 首页：快速入口 + 最近任务
│   │   ├── pdf_page.py             # PDF 工具集列表页
│   │   ├── pdf_split_page.py       # PDF 分割操作页
│   │   ├── pdf_merge_page.py       # PDF 合并操作页
│   │   ├── pdf_compress_page.py    # PDF 压缩操作页
│   │   ├── pdf_convert_page.py     # PDF↔Office 转换操作页
│   │   ├── image_page.py           # 图片工具集列表页
│   │   ├── image_convert_page.py   # 图片格式转换操作页
│   │   ├── image_compress_page.py  # 图片批量压缩操作页
│   │   ├── image_watermark_page.py # 图片水印操作页
│   │   ├── image_rename_page.py    # 批量重命名操作页
│   │   ├── media_page.py           # 音视频工具集列表页
│   │   ├── media_video_convert_page.py  # 视频格式转换操作页
│   │   ├── media_video_compress_page.py # 视频压缩操作页
│   │   ├── media_audio_extract_page.py  # 音频提取操作页
│   │   ├── media_audio_convert_page.py  # 音频格式转换操作页
│   │   ├── media_video_cut_page.py      # 视频剪切操作页
│   │   ├── archive_page.py         # 压缩解压操作页（Tab 切换）
│   │   ├── ocr_page.py             # OCR 识别操作页（联网）
│   │   └── settings_page.py        # 设置页
│   └── components/
│       ├── __init__.py
│       ├── nav_rail.py             # 侧边导航栏（展开/收起）
│       ├── drop_zone.py            # 文件拖拽区域（5种状态）
│       ├── file_list.py            # 文件列表（含移除/排序）
│       ├── progress_card.py        # 进度展示卡片
│       ├── result_card.py          # 处理结果卡片（文件列表+操作按钮）
│       ├── action_card.py          # 功能入口卡片（列表页用）
│       ├── segmented_button.py     # 分段控件（pill 形）
│       └── notification.py         # SnackBar / Dialog 封装
│
├── db/
│   └── schema.sql                  # SQLite 表结构
│
├── build/
│   ├── Makefile                    # 多平台打包命令
│   └── build_windows.bat           # Windows 打包脚本
│
└── tests/
    ├── core/
    │   ├── test_pdf_splitter.py
    │   ├── test_image_converter.py
    │   └── test_archive_handler.py
    └── services/
        └── test_task_service.py
```

---

## 五、核心模块实现规范

### 5.1 数据模型（core/models.py）

```python
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    status: TaskStatus
    output_files: list[Path] = field(default_factory=list)
    output_dir: Path | None = None
    error_message: str | None = None
    duration_seconds: float = 0.0


# 进度回调类型：(当前步骤, 总步骤, 描述文字)
ProgressCallback = Callable[[int, int, str], None]
```

### 5.2 Core Engine 接口规范

所有 core 函数必须遵循以下接口约定：

```python
# 标准签名示例（以 PDF 分割为例）
def split_pdf(
    input_file: Path,
    output_dir: Path,
    mode: Literal["pages", "range", "each"],
    pages_per_file: int = 5,          # mode="pages" 时生效
    page_ranges: list[str] | None = None,  # mode="range" 时生效
    filename_template: str = "{stem}_第{n}部分",
    progress_callback: ProgressCallback | None = None,
) -> TaskResult:
    ...
```

**约定**：
1. 入参全部使用 `Path` 对象，不使用字符串路径
2. `progress_callback` 可选，有则在每个文件处理完后调用
3. 函数内部捕获所有异常，返回 `TaskResult(status=FAILED, error_message=str(e))`
4. 不打印日志，异常信息通过 `TaskResult.error_message` 传递

### 5.3 任务服务层（services/task_service.py）

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from core.models import TaskResult, ProgressCallback
from typing import Callable

_executor = ThreadPoolExecutor(max_workers=4)  # 最多 4 并行任务


async def run_task(
    core_func: Callable,
    kwargs: dict,
    on_progress: Callable[[int, int, str], None],
    on_complete: Callable[[TaskResult], None],
) -> None:
    """
    将 core 函数提交到线程池执行，通过回调将进度/结果推回 UI 线程。
    调用方（UI层）持有 asyncio.Task 引用，可用于取消。
    """
    loop = asyncio.get_event_loop()
    kwargs["progress_callback"] = _make_thread_safe_callback(
        loop, on_progress
    )
    result = await loop.run_in_executor(
        _executor, lambda: core_func(**kwargs)
    )
    on_complete(result)


def _make_thread_safe_callback(loop, callback):
    """将回调包装为线程安全调用（从工作线程投递到事件循环）"""
    def wrapper(current, total, desc):
        loop.call_soon_threadsafe(callback, current, total, desc)
    return wrapper
```

### 5.4 FFmpeg 路径检测（core/platform.py）

```python
import sys
from pathlib import Path


def get_ffmpeg_path() -> Path:
    """
    优先使用内嵌二进制，其次检测系统 PATH。
    PyInstaller 打包后资源在 sys._MEIPASS 下。
    """
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "bin" / "ffmpeg.exe"
        if bundled.exists():
            return bundled
    # 开发环境：从项目 assets/bin 目录读取
    dev_path = Path(__file__).parent.parent / "assets" / "bin" / "ffmpeg.exe"
    if dev_path.exists():
        return dev_path
    # 兜底：依赖系统 PATH（要求用户自行安装）
    return Path("ffmpeg")


def get_libreoffice_path() -> Path | None:
    """
    检测系统 LibreOffice 安装路径，找不到返回 None。
    调用方据此决定是否显示「Office转PDF」功能引导。
    """
    candidates = [
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None
```

### 5.5 SQLite 数据库 Schema（db/schema.sql）

```sql
CREATE TABLE IF NOT EXISTS task_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    module      TEXT    NOT NULL,           -- 'pdf', 'image', 'media', 'archive'
    action      TEXT    NOT NULL,           -- 'split', 'merge', 'compress', ...
    status      TEXT    NOT NULL,           -- 'success', 'failed', 'cancelled'
    input_desc  TEXT    NOT NULL,           -- 输入文件描述（文件名或数量）
    output_dir  TEXT,                       -- 输出目录路径
    duration_s  REAL    DEFAULT 0,          -- 耗时秒数
    error_msg   TEXT                        -- 失败时的错误信息
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

-- 默认设置
INSERT OR IGNORE INTO settings VALUES ('theme_mode', 'system');  -- system/light/dark
INSERT OR IGNORE INTO settings VALUES ('default_output_dir', '');
INSERT OR IGNORE INTO settings VALUES ('after_complete', 'open_dir'); -- open_dir/notify/silent
INSERT OR IGNORE INTO settings VALUES ('history_limit', '30');
INSERT OR IGNORE INTO settings VALUES ('language', 'zh_CN');
INSERT OR IGNORE INTO settings VALUES ('ocr_provider', 'baidu');
INSERT OR IGNORE INTO settings VALUES ('ocr_api_key', '');
INSERT OR IGNORE INTO settings VALUES ('ocr_secret_key', '');
```

---

## 六、UI 实现规范

### 6.1 主题配置（ui/theme.py）

```python
import flet as ft


def build_color_scheme() -> ft.ColorScheme:
    """
    基于设计稿「The Fluid Architect」配置 Material You 色彩体系。
    注意：Flet 的 ColorScheme 参数名与 Material Design 3 Token 对应。
    """
    return ft.ColorScheme(
        primary="#004d64",
        on_primary="#ffffff",
        primary_container="#006684",
        on_primary_container="#a2e1ff",
        secondary="#4d616c",
        on_secondary="#ffffff",
        secondary_container="#d0e6f3",
        tertiary="#004f4f",
        on_tertiary="#ffffff",
        tertiary_container="#006969",
        background="#f7f9fe",
        on_background="#181c1f",
        surface="#f7f9fe",
        on_surface="#181c1f",
        surface_variant="#e0e3e7",
        on_surface_variant="#3f484d",
        outline="#70787e",
        outline_variant="#bfc8cd",
        error="#ba1a1a",
        on_error="#ffffff",
        error_container="#ffdad6",
    )


def build_text_theme() -> ft.TextTheme:
    return ft.TextTheme(
        display_large=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.BOLD),
        display_medium=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.BOLD),
        headline_large=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.SEMI_BOLD),
        headline_medium=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.SEMI_BOLD),
        title_large=ft.TextStyle(font_family="Manrope", weight=ft.FontWeight.MEDIUM),
        body_large=ft.TextStyle(font_family="Inter"),
        body_medium=ft.TextStyle(font_family="Inter"),
        label_large=ft.TextStyle(font_family="Inter", weight=ft.FontWeight.MEDIUM),
        label_medium=ft.TextStyle(font_family="Inter"),
        label_small=ft.TextStyle(font_family="Inter"),
    )


def get_app_theme(mode: str = "system") -> tuple[ft.Theme, ft.Theme]:
    """
    返回 (light_theme, dark_theme)。
    深色模式暂按 MD3 自动暗化处理，V2 再精细化。
    """
    color_scheme = build_color_scheme()
    text_theme = build_text_theme()

    light = ft.Theme(
        color_scheme=color_scheme,
        text_theme=text_theme,
        font_family="Inter",
    )
    dark = ft.Theme(
        color_scheme=color_scheme,  # Flet 深色模式会自动反转
        text_theme=text_theme,
        font_family="Inter",
    )
    return light, dark
```

### 6.2 路由与导航（ui/router.py）

路由表（与设计原型文档第六章保持一致）：

| 路由 | 页面类 | 说明 |
|---|---|---|
| `/` | `HomePage` | 首页，快速入口 + 最近任务 |
| `/pdf` | `PdfPage` | PDF 工具集列表 |
| `/pdf/split` | `PdfSplitPage` | PDF 分割 |
| `/pdf/merge` | `PdfMergePage` | PDF 合并 |
| `/pdf/compress` | `PdfCompressPage` | PDF 压缩 |
| `/pdf/to-office` | `PdfConvertPage` | PDF 转 Office |
| `/pdf/from-office` | `PdfConvertPage` | Office 转 PDF |
| `/pdf/ocr` | `OcrPage` | OCR 识别（联网）|
| `/image` | `ImagePage` | 图片工具集列表 |
| `/image/convert` | `ImageConvertPage` | 格式转换 |
| `/image/compress` | `ImageCompressPage` | 批量压缩 |
| `/image/watermark` | `ImageWatermarkPage` | 添加水印 |
| `/image/rename` | `ImageRenamePage` | 批量重命名 |
| `/media` | `MediaPage` | 音视频工具集列表 |
| `/media/video-convert` | `VideoConvertPage` | 视频格式转换 |
| `/media/video-compress` | `VideoCompressPage` | 视频压缩 |
| `/media/audio-extract` | `AudioExtractPage` | 音频提取 |
| `/media/audio-convert` | `AudioConvertPage` | 音频格式转换 |
| `/media/video-cut` | `VideoCutPage` | 视频剪切 |
| `/archive` | `ArchivePage` | 压缩解压（Tab）|
| `/settings` | `SettingsPage` | 设置 |

### 6.3 通用组件规范

#### DropZone（文件拖拽区域）

状态机（5种状态）：

```
IDLE ──拖拽进入──► DRAG_HOVER ──文件放下──► FILE_SELECTED
  ▲                   │                          │
  │              非法格式                    点击 × 移除
  │                   ▼                          ▼
  └─────────────── ERROR ◄────────────────── IDLE
```

样式要求（来自设计稿）：
- **IDLE**：背景色 `surface-container-low`（`#f1f4f8`），无实线边框，圆角 16px，中央提示文字
- **DRAG_HOVER**：背景色 `primary-container`（`#006684`，5% opacity overlay），`backdrop-filter: blur(20px)` 效果（Flet 近似实现）
- **FILE_SELECTED**：显示文件名、大小信息，右上角 × 移除按钮

#### ActionCard（功能入口卡片）

```
状态   背景                  效果
默认   surface-container-low  无阴影
悬停   surface-container-high  + box-shadow: 0 12px 40px rgba(0,77,100,0.08)
```

圆角：`xl`（`1.5rem` = 24px）

#### ProgressCard（进度展示）

- 进度条高度 8px，圆角 full，track 色 `secondary-container`，fill 渐变 `tertiary→primary`
- 确定进度：显示百分比 + 步骤描述文字
- 不确定进度：循环动画（Flet 的 `ProgressBar(value=None)`）

#### Notification（通知）

| 类型 | 实现 | 颜色 | 自动关闭 |
|---|---|---|---|
| 成功 | `SnackBar` | `tertiary`（`#004f4f`）| 3秒 |
| 警告 | `SnackBar` + 操作按钮 | `#FF9800` | 5秒，含「知道了」|
| 错误 | `AlertDialog` | `error`（`#ba1a1a`）| 手动关闭 |
| 信息 | `SnackBar` | `primary`（`#004d64`）| 3秒 |

### 6.4 窗口初始化（main.py）

```python
import flet as ft
from ui.theme import get_app_theme
from ui.router import setup_router


def main(page: ft.Page):
    # 窗口配置
    page.title = "File Toolkit"
    page.window_width = 1280
    page.window_height = 800
    page.window_min_width = 900
    page.window_min_height = 600

    # 主题
    light_theme, dark_theme = get_app_theme()
    page.theme = light_theme
    page.dark_theme = dark_theme
    page.theme_mode = ft.ThemeMode.SYSTEM

    # 字体注册（Manrope + Inter）
    page.fonts = {
        "Manrope": "fonts/Manrope-VariableFont_wght.ttf",
        "Inter": "fonts/Inter-VariableFont_opsz,wght.ttf",
    }

    # 路由
    setup_router(page)
    page.update()


ft.app(target=main, assets_dir="assets")
```

---

## 七、各模块详细实现说明

### 7.1 PDF 模块

#### 7.1.1 PDF 分割（core/pdf/splitter.py）

**入参**：
- `input_file: Path` — 源 PDF
- `output_dir: Path` — 输出目录
- `mode: Literal["pages", "range", "each"]`
- `pages_per_file: int = 5` — mode="pages" 时每份页数
- `page_ranges: list[str] | None` — mode="range" 时格式如 `["1-5", "6-10"]`
- `filename_template: str = "{stem}_第{n}部分"` — 支持 `{stem}` `{n}` `{start}` `{end}` 占位符

**实现要点**：
- 使用 `pypdf.PdfWriter` 按范围提取页面
- `progress_callback(i, total, f"生成第 {i} 份")` 每写完一个文件调用一次

#### 7.1.2 PDF 合并（core/pdf/merger.py）

**入参**：
- `input_files: list[Path]` — 有序文件列表（UI 层传入用户排序结果）
- `output_file: Path`

**实现要点**：
- 使用 `pypdf.PdfMerger`，按顺序 `append` 每个文件
- 进度按文件数量回调

#### 7.1.3 PDF 压缩（core/pdf/compressor.py）

**入参**：
- `input_file: Path`
- `output_file: Path`
- `quality: Literal["high", "medium", "low"]`

**实现要点**：
- 使用 `pikepdf.Pdf`，根据 quality 设置图片重采样参数
- `high`：保留图片质量，仅去除元数据冗余
- `medium`：JPEG 重编码，quality=75
- `low`：JPEG 重编码，quality=50，降采样至 150dpi

#### 7.1.4 PDF↔Office 转换（core/pdf/converter.py）

```python
# PDF→Word
def pdf_to_docx(input_file, output_file, progress_callback=None) -> TaskResult:
    from pdf2docx import Converter
    cv = Converter(str(input_file))
    # pdf2docx 自带 start/end 进度支持
    cv.convert(str(output_file), start=0, end=None)
    cv.close()

# Office→PDF（依赖 LibreOffice CLI）
def office_to_pdf(input_file, output_dir, progress_callback=None) -> TaskResult:
    from core.platform import get_libreoffice_path
    lo = get_libreoffice_path()
    if lo is None:
        return TaskResult(status=TaskStatus.FAILED,
                          error_message="未检测到 LibreOffice，请先安装")
    import subprocess
    result = subprocess.run(
        [str(lo), "--headless", "--convert-to", "pdf",
         "--outdir", str(output_dir), str(input_file)],
        capture_output=True, timeout=120
    )
    if result.returncode != 0:
        return TaskResult(status=TaskStatus.FAILED,
                          error_message=result.stderr.decode())
```

### 7.2 图片模块

#### 7.2.1 格式转换（core/image/converter.py）

**支持格式**：JPG/JPEG、PNG、WebP、HEIC、BMP、TIFF

**实现要点**：
```python
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()  # 必须在模块顶部注册

def convert_image(input_file, output_file, target_format, quality=95):
    with Image.open(input_file) as img:
        # HEIC 转出后需处理色彩空间
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        save_kwargs = {"format": target_format.upper()}
        if target_format.lower() in ("jpg", "jpeg", "webp"):
            save_kwargs["quality"] = quality
        img.save(output_file, **save_kwargs)
```

#### 7.2.2 批量压缩（core/image/compressor.py）

**两种模式**：
- **质量模式**：直接设 JPEG/WebP quality 参数
- **目标大小模式**：二分法逼近目标文件大小（precision: ±5%），最多迭代 10 次

#### 7.2.3 批量重命名（core/image/renamer.py）

**模板变量**：

| 占位符 | 说明 |
|---|---|
| `{n}` | 序号（从 1 开始） |
| `{n:03d}` | 零填充序号 |
| `{date}` | 文件修改日期 YYYYMMDD |
| `{stem}` | 原文件名（不含扩展名）|
| `{ext}` | 原扩展名 |

**预览**：重命名前 UI 展示新旧文件名对比列表（不执行，仅预览）

### 7.3 音视频模块

#### 7.3.1 通用 FFmpeg 封装原则

```python
import ffmpeg
from core.platform import get_ffmpeg_path

def _run_ffmpeg(stream, progress_callback, total_duration_s):
    """
    运行 ffmpeg，通过 stderr 解析进度（time= 字段）。
    ffmpeg-python 的 .run() 支持 quiet=True 避免控制台输出。
    """
    cmd = stream.compile()
    cmd.insert(0, str(get_ffmpeg_path()))
    # 使用 subprocess 读取 stderr 实时进度
    ...
```

**进度解析**：从 ffmpeg stderr 中匹配 `time=HH:MM:SS.ms`，换算为百分比。

#### 7.3.2 视频格式转换

```python
def convert_video(input_file, output_file, video_codec="libx264",
                  audio_codec="aac", resolution=None, bitrate=None,
                  fps=None, progress_callback=None) -> TaskResult:
    stream = ffmpeg.input(str(input_file))
    kwargs = {"vcodec": video_codec, "acodec": audio_codec}
    if resolution:
        kwargs["vf"] = f"scale={resolution}"
    if bitrate:
        kwargs["b:v"] = bitrate
    if fps:
        kwargs["r"] = fps
    stream = ffmpeg.output(stream, str(output_file), **kwargs)
    ...
```

**支持编码组合**：

| 容器格式 | 视频编码 | 音频编码 |
|---|---|---|
| MP4 | H.264 / H.265 / AV1 | AAC / MP3 |
| MKV | H.264 / H.265 / AV1 / VP9 | AAC / AC3 / FLAC |
| AVI | H.264 / MPEG4 | MP3 / AAC |
| MOV | H.264 / HEVC | AAC |
| WMV | WMV2 | WMA |

#### 7.3.3 视频剪切

```python
def cut_video(input_file, output_file, start_time, end_time,
              progress_callback=None) -> TaskResult:
    """
    start_time/end_time 格式：秒数（float）或 "HH:MM:SS"。
    使用 -ss 精确定位（关键帧对齐），-c copy 避免重编码（速度快）。
    """
```

### 7.4 压缩解压模块

#### 7.4.1 统一接口

```python
# 压缩
def compress(
    input_paths: list[Path],      # 可以是文件或文件夹
    output_file: Path,
    format: Literal["zip", "7z", "tar.gz"],
    level: Literal["fast", "standard", "maximum"] = "standard",
    password: str | None = None,
    volume_size_mb: int | None = None,  # 分卷大小，None=不分卷
    progress_callback: ProgressCallback | None = None,
) -> TaskResult: ...

# 解压
def extract(
    input_file: Path,
    output_dir: Path,
    password: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> TaskResult: ...
```

**格式路由逻辑**：
- `.zip` → `zipfile`（内置，无需额外依赖）
- `.7z` → `py7zr`
- `.tar.gz` / `.tar.bz2` → `tarfile`（内置）
- `.rar` → `rarfile`（**仅解压**，压缩不支持，需在 UI 层过滤）

---

## 八、设置系统

### 8.1 设置项完整清单

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `theme_mode` | str | `"system"` | `system`/`light`/`dark` |
| `theme_color` | str | `"#004d64"` | 自定义主色（V2 支持）|
| `language` | str | `"zh_CN"` | 界面语言（V2 支持多语言）|
| `default_output_dir` | str | `""` | 空字符串表示使用原文件夹 |
| `after_complete` | str | `"open_dir"` | `open_dir`/`notify`/`silent` |
| `history_limit` | int | `30` | 最近任务条数上限 |
| `ocr_provider` | str | `"baidu"` | `baidu`/`tencent` |
| `ocr_api_key` | str | `""` | OCR API Key（加密存储）|
| `ocr_secret_key` | str | `""` | OCR Secret Key（加密存储）|

> **安全性**：`ocr_api_key`、`ocr_secret_key` 存储时使用系统 Keychain（Windows：`keyring` 库），SQLite 中仅存占位标记，不明文写入。

### 8.2 默认输出目录逻辑

```python
def resolve_output_dir(input_file: Path, user_setting: str) -> Path:
    """
    user_setting 为空时：在输入文件所在目录下创建子目录。
    否则：使用用户指定路径。
    """
    if not user_setting:
        return input_file.parent / "output"
    return Path(user_setting)
```

---

## 九、打包与分发

### 9.1 Windows 打包流程

```bash
# 1. 安装打包工具
pip install pyinstaller

# 2. 确保 FFmpeg 二进制在 assets/bin/ 目录
# 3. 执行 Flet 打包
flet build windows \
  --product-name "File Toolkit" \
  --product-version "1.0.0" \
  --company-name "FileToolkit" \
  --copyright "MIT License" \
  --icon assets/icons/app_icon.ico
```

### 9.2 PyInstaller spec 关键配置

```python
# file_toolkit.spec（关键片段）
a = Analysis(
    ['main.py'],
    binaries=[
        ('assets/bin/ffmpeg.exe', 'bin'),
        ('assets/bin/ffprobe.exe', 'bin'),
    ],
    datas=[
        ('assets/fonts', 'fonts'),
        ('assets/icons', 'icons'),
        ('db/schema.sql', 'db'),
    ],
    hiddenimports=[
        'pillow_heif',
        'rarfile',
        'py7zr',
    ],
)
```

### 9.3 安装包体积预估

| 组件 | 大小 |
|---|---|
| Python 运行时 | ~30MB |
| Flet（Flutter Engine）| ~50MB |
| FFmpeg 二进制 | ~80MB |
| 依赖库（Pillow/pypdf 等）| ~40MB |
| **合计（不含 LibreOffice）** | **~200MB** |

> LibreOffice 不内嵌，按需引导用户下载，可降低安装包体积。

---

## 十、开发阶段规划

### 10.1 Phase 1（Windows MVP）开发顺序

按依赖关系排序，后置任务依赖前置完成：

```
Week 1  [基础设施]
  ├── 搭建项目结构（目录/pyproject.toml/虚拟环境）
  ├── core/platform.py（FFmpeg 路径检测）
  ├── core/models.py（数据类）
  ├── services/settings_service.py（SQLite 初始化）
  └── ui/theme.py + ui/router.py（主题配置 + 路由骨架）

Week 2  [UI 框架]
  ├── main.py（窗口初始化）
  ├── ui/components/nav_rail.py（侧边栏）
  ├── ui/components/drop_zone.py（文件拖拽区域）
  ├── ui/pages/home_page.py（首页骨架）
  └── ui/pages/settings_page.py（设置页）

Week 3  [PDF 模块]
  ├── core/pdf/splitter.py
  ├── core/pdf/merger.py
  ├── core/pdf/compressor.py
  ├── 对应 UI 页面（pdf_split/merge/compress_page.py）
  └── 端到端联调测试

Week 4  [图片模块]
  ├── core/image/converter.py（含 HEIC）
  ├── core/image/compressor.py
  ├── core/image/renamer.py
  ├── 对应 UI 页面
  └── 端到端联调测试

Week 5  [音视频 + 压缩模块]
  ├── core/media/video.py + core/media/audio.py
  ├── core/archive/handler.py
  ├── 对应 UI 页面
  ├── services/history_service.py（任务历史）
  └── 首页最近任务接入

Week 6  [打包 + 收尾]
  ├── assets/bin/ 内嵌 FFmpeg
  ├── Windows 打包（flet build windows）
  ├── 安装包测试（全功能验收清单）
  └── PDF↔Office（LibreOffice CLI，按可用性决定是否纳入 MVP）
```

### 10.2 Phase 1 验收清单

- [ ] 导航栏展开/收起，路由切换无闪烁
- [ ] 所有功能页文件拖拽区域 5 种状态正常
- [ ] PDF 分割/合并/压缩完整流程，进度回调正常
- [ ] 图片格式转换（含 HEIC）/批量压缩完整流程
- [ ] 视频格式转换进度条正常（FFmpeg 进度解析）
- [ ] 压缩/解压 zip/7z/tar.gz 完整流程
- [ ] 深色/浅色/跟随系统主题切换正常
- [ ] 首页最近任务记录正常（成功/失败/再次执行）
- [ ] 设置页默认输出目录生效
- [ ] 所有错误状态有友好提示（Dialog 或 SnackBar）
- [ ] `.exe` 安装包在干净 Windows 10/11 环境运行正常

---

## 十一、关键风险与应对

| 风险 | 概率 | 影响 | 应对方案 |
|---|---|---|---|
| Flet 与 PyInstaller 版本兼容性 | 中 | 打包失败 | 锁定经验证的 Flet/PyInstaller 组合，提前验证打包链路 |
| FFmpeg LGPL 内嵌授权 | 低 | 法律风险 | 使用官方 LGPL 版本 FFmpeg，动态链接，避免修改源码 |
| pdf2docx 复杂排版还原度不足 | 高 | 用户体验差 | UI 显示「复杂排版可能有偏差」说明，V2 接云端高精度 API |
| 大文件处理（>2GB 视频）UI 卡顿 | 中 | 体验差 | 所有 core 函数跑线程池，进度回调 call_soon_threadsafe |
| LibreOffice 未安装导致功能不可用 | 高 | 功能缺失 | 检测不到时，功能入口显示「需安装 LibreOffice」引导，而非直接隐藏 |
| pillow-heif 在 Windows 缺少依赖 | 中 | HEIC 不可用 | pillow-heif Windows 版已内置 libheif，PyInstaller 打包时需加入 hiddenimports |
| rarfile 解压需 unrar.exe | 高 | rar 解压失败 | 内嵌 UnRAR.exe（freeware 授权），与 ffmpeg 同样处理 |

---

## 十二、附录：技术选型备选对比

### A. 为何选 Flet 而非 Electron/Tauri？

| 维度 | Flet | Electron | Tauri |
|---|---|---|---|
| **语言** | Python | JavaScript | Rust + JavaScript |
| **包体积** | ~200MB | ~150MB | ~10MB |
| **性能** | Flutter 渲染，流畅 | Chromium，内存大 | 原生 WebView，轻量 |
| **Python 集成** | 原生 | 需 child_process | 需 sidecar |
| **开发效率** | 极高（熟悉 Python）| 中 | 低（需学 Rust）|
| **决策** | ✅ 首选 | — | — |

### B. 为何选 pypdf + pikepdf 双库而非单一方案？

- `pypdf`：纯 Python，接口简洁，处理分割/合并/读取元数据
- `pikepdf`：基于 QPDF，C++ 底层，压缩/加密/低层结构操作性能更好
- 两者互补，覆盖所有 PDF 操作场景

### C. Office→PDF 方案对比

| 方案 | 效果 | 依赖 | 授权 |
|---|---|---|---|
| LibreOffice CLI | 最佳 | 需安装（~200MB）| 开源 MPL |
| python-docx 手动排版 | 差（只支持 docx）| 轻量 | MIT |
| Microsoft Word COM API | 最佳（仅 Windows）| 需 Office 安装 | 商业 |
| **决策** | **LibreOffice CLI，检测引导安装** | | |
