@echo off
REM File Toolkit — Windows 打包脚本（在 Windows 原生环境运行）
REM 需要：Python 3.11+，flet 已安装（pip install flet）

cd /d %~dp0..

echo [1/3] 检查 FFmpeg 二进制...
if not exist "assets\bin\ffmpeg.exe" (
    echo 错误：assets\bin\ffmpeg.exe 不存在
    echo 请下载 FFmpeg LGPL 版并放置到 assets\bin\ 目录
    echo 下载地址：https://github.com/BtbN/FFmpeg-Builds/releases
    exit /b 1
)

echo [2/3] 执行 flet build windows...
flet build windows ^
    --product-name "File Toolkit" ^
    --product-version "1.0.0" ^
    --company-name "FileToolkit" ^
    --copyright "MIT License" ^
    --icon assets\icons\app_icon.ico

echo [3/3] 构建完成，输出目录：build\windows\
pause
