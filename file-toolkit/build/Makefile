# File Toolkit — 开发与打包命令（任意目录执行均可，如 make -C file-toolkit/build test）
# 打包元数据（产品名、Bundle ID、版本号）统一写在 pyproject.toml 的 [project] / [tool.flet]

.PHONY: deps run lint test check macos linux windows clean

# file-toolkit/ 目录，所有命令都在这里执行
APP := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)

deps:
	cd "$(APP)" && uv sync --all-groups

run:
	cd "$(APP)" && uv run python main.py

lint:
	cd "$(APP)" && uv run ruff check .

test:
	cd "$(APP)" && uv run pytest

# CI 同款检查
check: lint test

# 各平台打包需在对应系统上执行（flet 不支持交叉编译桌面应用）
macos:
	cd "$(APP)" && bash build/build_macos.sh

linux:
	cd "$(APP)" && bash build/build_linux.sh

windows:
	cmd /c "$(APP)\\build\\build_windows.bat"

clean:
	cd "$(APP)" && rm -rf build/windows/ build/macos/ build/linux/ build/flutter/ build/site-packages/
	cd "$(APP)" && rm -rf .ruff_cache .mypy_cache .pytest_cache
	cd "$(APP)" && find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
