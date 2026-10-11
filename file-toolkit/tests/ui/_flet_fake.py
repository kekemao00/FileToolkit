"""测试用假 Page 的公共检查。"""
import inspect


def check_run_task(handler) -> None:
    """和 Flet 的 Page.run_task 一样，只接受协程函数（否则真实环境里会抛 TypeError，点击无反应）。"""
    if not inspect.iscoroutinefunction(handler):
        raise TypeError(f"run_task 需要协程函数，收到 {handler!r}")
