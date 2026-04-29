# File Toolkit — 多平台打包 Makefile
# 在 file-toolkit/ 目录下执行

.PHONY: all run deps lint test clean windows macos

all: windows

# 安装所有依赖（含 dev 依赖）
deps:
	uv sync --all-extras

# 开发模式启动
run:
	uv run python main.py

# Windows 打包（需在 Windows 原生环境执行）
windows:
	flet build windows \
		--product-name "File Toolkit" \
		--product-version "1.0.0" \
		--company-name "FileToolkit" \
		--copyright "MIT License" \
		--icon assets/icons/app_icon.ico

# macOS 打包（需在 macOS 原生环境或 GitHub Actions macOS runner 执行）
macos:
	uv run bash build/build_macos.sh

# 代码检查
lint:
	uv run ruff check .
	uv run mypy .

# 运行测试
test:
	uv run pytest

# 清理构建产物
clean:
	rm -rf build/windows/ build/macos/ build/linux/
	rm -rf __pycache__ .ruff_cache .mypy_cache .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
