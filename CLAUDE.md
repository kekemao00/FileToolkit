## 1. 核心开发工作流 (plan.md)
**默认模式**: 除非任务极简（单文件/文档），否则必须遵循 `plan.md` 驱动开发：
1.  **Init**: 创建/更新根目录 `plan.md`。
2.  **Breakdown**: 将任务拆解为 Markdown Checklist (`- [ ] 任务`).
3.  **Execute**:
    - 顺序执行，原子提交 (每完成一项 -> 更新 `[x]` -> `git commit`).
    - **YOLO 模式**: 自主做技术决策，除非涉及重大架构变动，否则不要停下来询问。
    - **Commit**: 遵循 Conventional Commits (feat, fix, refactor, docs)。



## 2. 踩坑清单（必读）

### Flet 0.84 API 差异
- **FilePicker 必须懒加载**：不能在 `__init__` / `did_mount` 创建，Service 注册时机早于 page ready，会导致 RuntimeError
- **无 `Page.open()` 方法**：SnackBar 必须用 `page.overlay.append(snack); snack.open = True`
- **无 `ft.ImageFit`**：图片 fit 用 `ft.BoxFit`（如 `ft.BoxFit.CONTAIN`）
- **无 `src_base64` 参数**：ft.Image 用 `src="data:image/png;base64,..."` 代替
- **Dropdown 无 `on_change`**：用 `on_select` 代替
- **`control.page` 未挂载时抛 RuntimeError**：不能用 `if control.page:` 守卫，需 try/except

### 构建与 CI
- **flet build 参数名**：`--product`（非 --product-name）、`--build-version`（非 --product-version）、`--company`（非 --company-name）
- **CI 环境 flet 需要 `--yes`**：非 TTY 会阻塞等待用户输入
- **GitHub Actions working-directory**：cd 后的相对路径和 upload-artifact 的 path 要对应，别搞混
- **`uv run --`**：uv 后面传参数给子命令必须用 `--` 分隔，否则带空格的参数被截断

### UI 组件
- **show_toast 封装**：overlay 模式 + fallback + threading.Timer 清理，避免 snack_bar 泄漏

### Windows 环境
- **PowerShell 不支持 `Get-Content -Encoding Byte`**：用 `[System.IO.File]::ReadAllBytes` + `MemoryStream`
- **bat 文件必须用 ASCII 无 BOM 编码**：否则 cmd 第一行就炸
- **7z 打包中文目录名**：必须用 `cmd /c` 调用，PowerShell 进中文目录后 `.*` 不保留父目录名
- **7-Zip SFX 默认行为**：直接解压到当前目录，需用 `Directory="xxx"` 配置或文件夹包裹

---

你当前的开发环境是wsl-ubuntu22.04

运行：

```bash
  cd /mnt/b/FileToolkit/file-toolkit
  source .venv/bin/activate
  python main.py
```
