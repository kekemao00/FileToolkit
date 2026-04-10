# File Toolkit（文件全能王）

本地离线 · 安全可靠 · 现代美观 · 一站式文件处理

## 功能模块

| 模块 | 功能 |
|---|---|
| PDF | 分割 / 合并 / 压缩 / Office 互转 |
| 图片 | 格式转换 / 批量压缩 / 水印 / 批量重命名 |
| 音视频 | 格式转换 / 压缩 / 剪切 / 音频提取 |
| 压缩解压 | zip / 7z / tar.gz，含 rar 解压 |
| OCR | 在线识别（百度/腾讯 API）|

## 开发环境

```bash
cd file-toolkit
uv sync
uv run python main.py
```

## 打包（需 Windows 原生环境）

```bat
cd file-toolkit
flet build windows --product-name "File Toolkit" --product-version "1.0.0"
```

## 文档

- [需求文档](File%20Toolkit%20完整需求文档.md)
- [技术开发文档](File%20Toolkit%20技术开发文档.md)
- [设计原型文档](File%20Toolkit%20设计原型文档.md)

## 授权

MIT License
