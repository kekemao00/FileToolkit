@echo off
REM File Toolkit - Windows build (run on native Windows with uv installed).
REM Product name, version, etc. come from pyproject.toml ([project] / [tool.flet]).
REM Put ffmpeg.exe at assets\bin\ffmpeg.exe first to bundle it into the app.

cd /d %~dp0..

if not exist "assets\bin\ffmpeg.exe" (
    echo [warn] assets\bin\ffmpeg.exe not found - audio/video tools will need a system FFmpeg.
    echo        Download: https://github.com/BtbN/FFmpeg-Builds/releases
)

echo [1/2] flet build windows ...
uv run --group build -- flet build windows --yes %*
if errorlevel 1 exit /b 1

echo [2/2] Done. Output: build\windows\
