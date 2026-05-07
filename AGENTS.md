# Repository Guidelines



> 你的主要职责是负责review，将建议输出，不直接修改代码

## Project Structure & Module Organization

This repository contains a Flet desktop app in `file-toolkit/`. Core file-processing logic lives in `file-toolkit/core/` (`pdf/`, `image/`, `media/`, `archive/`, `ocr/`). UI code is under `file-toolkit/ui/`, with reusable controls in `ui/components/` and screens in `ui/pages/`. Application services, including task execution, settings, and history, live in `file-toolkit/services/`. SQLite schema files are in `file-toolkit/db/`, assets in `file-toolkit/assets/`, build scripts in `file-toolkit/build/`, and tests in `file-toolkit/tests/`.

## Build, Test, and Development Commands

Run commands from `file-toolkit/` unless noted.

- `uv sync --all-extras`: install runtime and development dependencies.
- `uv run python main.py` or `make -C file-toolkit/build run`: start the app locally.
- `uv run pytest`: run the full test suite.
- `uv run ruff check .`: run lint checks.
- `uv run mypy .`: run type checks.
- `flet build windows ...` or `make -C file-toolkit/build windows`: build the Windows app in a native Windows environment.

## Coding Style & Naming Conventions

Use Python 3.11+, 4-space indentation, and explicit type hints for public functions and service/core APIs. Keep modules focused: core functions should accept `Path` objects and return `TaskResult` where applicable. Use snake_case for functions, variables, and modules; PascalCase for Flet page/component classes. Ruff is configured with a 100-character line length and import sorting; avoid unrelated formatting churn.

## Testing Guidelines

Tests use `pytest` and `pytest-asyncio`. Place tests under `file-toolkit/tests/`, mirroring the source area, for example `tests/core/test_pdf_splitter.py` or `tests/services/test_task_service.py`. Name files `test_*.py`, classes `Test*`, and functions `test_*`. Add focused tests for new core behavior and service contracts; UI-only changes should at least pass lint and compile checks.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commit-style prefixes, often with concise Chinese descriptions, such as `fix: 修复 AI 页输入框可读性与控制台视觉分层` and `feat: 实现 OCR 识别 core/ocr/client.py`. Use `feat:`, `fix:`, `chore:`, or similar prefixes. PRs should describe the user-visible change, list validation commands run, link related issues, and include screenshots or short recordings for UI changes.

## Security & Configuration Tips

Runtime data is stored in `file-toolkit/.data/` and should not be committed. Do not commit API keys, generated databases, virtual environments, caches, or build outputs. Settings are stored via `services/settings_service.py`; keep secrets out of source and test fixtures.
