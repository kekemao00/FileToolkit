<div align="center">

# File Toolkit · 文件全能王

**本地处理 PDF、图片、音视频与压缩包的跨平台桌面工具箱**

文件只在你自己的电脑上处理，不经过任何服务器。

[![CI](https://github.com/kekemao00/FileToolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/kekemao00/FileToolkit/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/kekemao00/FileToolkit?include_prereleases&sort=semver)](https://github.com/kekemao00/FileToolkit/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-informational)](#下载安装)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[下载](#下载安装) · [功能](#功能) · [从源码运行](#从源码运行) · [打包与发布](#打包与发布)

<img src="docs/screenshots/home.png" alt="File Toolkit 首页" width="720">

</div>

## 下载安装

到 [Releases](https://github.com/kekemao00/FileToolkit/releases/latest) 下载对应平台的安装包：

| 平台 | 文件 | 说明 |
|---|---|---|
| Windows 10/11 (x64) | `FileToolkit-<版本>-windows-x64.zip` | 解压后运行 `FileToolkit` 文件夹里的 `.exe`；SmartScreen 拦截时选「更多信息 → 仍要运行」 |
| macOS (Apple 芯片) | `FileToolkit-<版本>-macos-arm64.zip` | 解压后把 `.app` 拖进「应用程序」，首次打开请右键 → 打开（应用暂未签名） |
| Linux (x64) | `FileToolkit-<版本>-linux-x64.tar.gz` | `tar -xzf` 解压后运行 `FileToolkit/` 里的可执行文件 |

每个版本都附带 `SHA256SUMS.txt`，可用 `sha256sum -c SHA256SUMS.txt` 校验下载是否完整。

> macOS 提示「已损坏，无法打开」时，执行 `xattr -dr com.apple.quarantine "/Applications/<应用名>.app"` 后再打开。

## 功能

✅ 开箱即用 &nbsp; 🔧 需要先装外部程序或填写 API Key（见[外部依赖](#外部依赖)） &nbsp; 🚧 开发中

| 分类 | 功能 | 状态 |
|---|---|:---:|
| **PDF** | 合并、拆分（按页数 / 范围 / 逐页）、压缩 | ✅ |
| | 合并 / 压缩时顺带加文字水印、设置打开密码 | ✅ |
| | PDF 转 Word、Excel（表格提取）、PPT | ✅ |
| | Word / Excel / PPT 转 PDF | 🔧 LibreOffice |
| **图片** | 格式转换（JPG / PNG / WebP / BMP / TIFF / HEIC） | ✅ |
| | 批量压缩、尺寸调整、文字水印、批量重命名（`{name}` `{n}` `{date}` `{ext}` 模板） | ✅ |
| **音视频** | 视频格式转换、压缩（可选分辨率）、按时间段剪辑 | 🔧 FFmpeg |
| | 从视频提取音频、音频格式转换 | 🔧 FFmpeg |
| **压缩解压** | 压缩为 ZIP / 7Z / TAR.GZ；解压 ZIP / 7Z / TAR | ✅ |
| | 解压 RAR | 🔧 unrar |
| **文字识别** | 从图片识别文字 | 🔧 Tesseract |
| | 提取 PDF 内嵌文字 | ✅ |
| **AI** | 提示词出图（OpenAI Images 兼容接口） | 🔧 API Key |
| | 用自然语言描述任务、自动执行 | 🚧 |
| **应用** | 全局功能搜索、最近操作记录、偏好设置 | ✅ |

### 外部依赖

只有对应功能才需要，其他功能不受影响。

| 程序 | 用于 | 获取方式 |
|---|---|---|
| FFmpeg | 音视频全部功能 | **Windows / Linux 安装包已内置**；macOS：`brew install ffmpeg`；源码运行时放到 `file-toolkit/assets/bin/` 或装到系统 PATH |
| LibreOffice | Office 转 PDF | [官网下载](https://www.libreoffice.org/download/)，装在默认位置或 PATH 中即可被识别 |
| Tesseract | 图片文字识别 | Windows：[UB-Mannheim 安装包](https://github.com/UB-Mannheim/tesseract/wiki)；macOS：`brew install tesseract tesseract-lang`；Linux：`sudo apt install tesseract-ocr tesseract-ocr-chi-sim` |
| unrar | 解压 RAR | macOS：`brew install rar`；Linux：`sudo apt install unrar`；Windows：安装 [WinRAR](https://www.win-rar.com/) 或 7-Zip 并加入 PATH |
| API Key | 提示词出图 | 在应用「设置」里填写 API Key，可改 Base URL 与模型以接入兼容服务 |

## 从源码运行

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。

```bash
git clone https://github.com/kekemao00/FileToolkit.git
cd FileToolkit/file-toolkit
uv sync
uv run python main.py
```

运行数据（数据库、设置）保存在 `file-toolkit/.data/`，打包后的应用改存到系统的用户数据目录。

## 开发

```bash
cd file-toolkit
uv sync --all-groups   # 运行、测试、打包依赖全部装上
uv run ruff check .    # 代码检查
uv run pytest          # 单元测试
```

每次推送到 `main` 和每个 PR 都会在 [CI](.github/workflows/ci.yml) 里跑上面两项检查。

```
file-toolkit/
├── main.py        # 入口：窗口、字体、主题、路由
├── core/          # 处理引擎（纯 Python，不依赖 UI）：pdf / image / media / archive / ocr
├── services/      # 任务调度、历史记录、设置持久化（SQLite）
├── ui/            # Flet 界面：router、主题、组件、页面
│   └── features.py  # 功能目录，首页入口与全局搜索共用；新增功能在这里登记
├── assets/        # 字体、图标；打包时 FFmpeg 放到 assets/bin/
├── build/         # 各平台打包脚本
└── tests/         # pytest 单元测试，目录结构与源码对应
```

技术栈：[Flet](https://flet.dev) 0.84（Flutter 渲染）、pypdf / pikepdf / pdf2docx、Pillow、FFmpeg、py7zr。更多设计细节见 [docs/](docs/) 下的需求、技术与设计文档。

## 打包与发布

### 本地打包

桌面应用只能在对应系统上打包（flet 不支持交叉编译）。产品名、Bundle ID 等元数据写在 `pyproject.toml` 的 `[tool.flet]`，版本号取自 `[project].version`。首次打包会自动下载所需的 Flutter SDK。

```bash
cd file-toolkit
bash build/build_macos.sh          # macOS，MACOS_ARCH=x86_64 / universal 可切换架构
bash build/build_linux.sh          # Linux，需 libgtk-3-dev clang cmake ninja-build
build\build_windows.bat            # Windows
```

产物在 `file-toolkit/build/<平台>/`。想把 FFmpeg 打进包里，先把二进制放到 `file-toolkit/assets/bin/`。

### 发布新版本

[Release 工作流](.github/workflows/release.yml) 在推送版本 tag 时自动测试、三平台打包并创建 GitHub Release：

1. 修改 `file-toolkit/pyproject.toml` 里的 `version`，然后在 `file-toolkit/` 下执行 `uv lock` 同步锁文件。
2. 提交并合入 `main`。
3. 打 tag 并推送，tag 必须是 `v` + 同一个版本号：
   ```bash
   git tag v1.1.0
   git push origin v1.1.0
   ```

tag 与 `pyproject.toml` 版本不一致时工作流会直接失败，不会发出错误版本号的安装包。带 `-` 的版本（如 `v1.1.0-beta.1`）发布为预发布版。Release 说明由 GitHub 根据合入的 PR 自动生成。

只想试打包、不发布时，在 Actions 页面手动运行 Release 工作流，安装包会作为构建产物上传；改动打包相关文件的 PR 也会自动试打包一次。

## 许可证

[MIT](LICENSE) © 2026 kekemao00

Windows / Linux 安装包内置的 FFmpeg 来自 [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds)，以 GPL 授权单独分发。
