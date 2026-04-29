## 1. 核心开发工作流 (plan.md)
**默认模式**: 除非任务极简（单文件/文档），否则必须遵循 `plan.md` 驱动开发：
1.  **Init**: 创建/更新根目录 `plan.md`。
2.  **Breakdown**: 将任务拆解为 Markdown Checklist (`- [ ] 任务`).
3.  **Execute**:
    - 顺序执行，原子提交 (每完成一项 -> 更新 `[x]` -> `git commit`).
    - **YOLO 模式**: 自主做技术决策，除非涉及重大架构变动，否则不要停下来询问。
    - **Commit**: 遵循 Conventional Commits (feat, fix, refactor, docs)。



你当前的开发环境是wsl-ubuntu22.04

运行：

```bash
  cd /mnt/b/FileToolkit/file-toolkit
  source .venv/bin/activate
  python main.py
```
