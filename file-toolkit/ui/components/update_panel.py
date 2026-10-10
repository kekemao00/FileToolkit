"""检查更新 — 设置页「关于」卡片里的版本行和新版本面板。

VersionRow：当前版本 + 状态文字 + 「检查更新」按钮。
UpdatePanel：发现新版本后展开，显示更新说明 → 下载进度 → 「重启并更新」。

两者都订阅 update_service.state，所以切换主题重建页面、或者离开设置页再回来，
下载进度都不会丢。
"""
import asyncio
import time

import flet as ft

from core.version import app_version
from services import update_installer, update_service
from services.update_service import UpdateState
from ui import style as s
from ui.palette import c
from ui.utils import open_folder, show_toast


def _mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def _ago(ts: float) -> str:
    if not ts:
        return ""
    sec = time.time() - ts
    if sec < 60:
        return "刚刚检查"
    if sec < 3600:
        return f"{int(sec // 60)} 分钟前检查"
    return f"{int(sec // 3600)} 小时前检查"


def _download_failed(st: UpdateState) -> bool:
    """出错时如果已经知道有新版本，说明是下载 / 解压阶段失败，面板保留并提供重试。"""
    return (st.status == "error" and st.release is not None
            and update_service.is_newer(st.release.version, app_version()))


class _Subscriber:
    """挂载时订阅更新状态、卸载时退订。"""

    _unsubscribe = None

    def did_mount(self) -> None:
        self._unsubscribe = update_service.subscribe(self._on_state)
        self._on_state(update_service.state)

    def will_unmount(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def _on_state(self, st: UpdateState) -> None:
        self.render(st)
        try:
            self.update()  # type: ignore[attr-defined]
        except RuntimeError:
            pass

    def render(self, st: UpdateState) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError


class VersionRow(_Subscriber, ft.Row):
    def __init__(self, page: ft.Page) -> None:
        self._page = page
        self._ring = ft.ProgressRing(width=12, height=12, stroke_width=1.5, color=c("ink-2", "fg"),
                                     visible=False)
        self._status = s.text("", "small")
        self._button = s.button("检查更新", self._check, kind="secondary", icon=ft.Icons.SYNC_ROUNDED)
        super().__init__(
            controls=[
                s.text(f"v{app_version()}", "mono"),
                ft.Container(expand=True),
                ft.Row(controls=[self._ring, self._status], spacing=6,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self._button,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.render(update_service.state)

    def _check(self, _) -> None:
        async def _run() -> None:
            st = await update_service.check()
            if st.status == "latest":
                show_toast(self._page, "已是最新版本", kind="success")
            elif st.status == "error" and not _download_failed(st):
                show_toast(self._page, st.error, kind="error", duration=4000)

        self._page.run_task(_run)

    def render(self, st: UpdateState) -> None:
        self._ring.visible = st.status == "checking"
        self._button.disabled = st.busy
        self._status.color = c("ink-3", "fg")
        if st.status == "checking":
            self._status.value = "正在检查…"
        elif st.status == "latest":
            self._status.value = f"已是最新版本 · {_ago(st.checked_at)}"
        elif st.status == "error" and not _download_failed(st):
            self._status.value = st.error
            self._status.color = c("danger", "fg")
        elif st.release and st.status != "error":
            self._status.value = f"新版本 v{st.release.version}"
            self._status.color = c("accent-fg", "fg")
        else:
            self._status.value = ""


class UpdatePanel(_Subscriber, ft.Container):
    """新版本面板；没有新版本时收起（高度 0）。"""

    NOTES_MAX_H = 220

    def __init__(self, page: ft.Page) -> None:
        self._page = page
        self._title = s.text("", "title")
        self._meta = s.text("", "small")
        self._notes = ft.Markdown(
            "",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            on_tap_link=lambda e: self._open_url(e.data),
            md_style_sheet=ft.MarkdownStyleSheet(
                p_text_style=ft.TextStyle(size=13, color=c("ink-2", "fg"), font_family=s.FONT),
                list_bullet_text_style=ft.TextStyle(size=13, color=c("ink-3", "fg")),
                a_text_style=ft.TextStyle(color=c("accent-fg", "fg")),
                h2_text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600,
                                           color=c("ink", "fg"), font_family=s.FONT),
                h3_text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600,
                                           color=c("ink", "fg"), font_family=s.FONT),
                strong_text_style=ft.TextStyle(weight=ft.FontWeight.W_600, color=c("ink", "fg")),
                code_text_style=ft.TextStyle(size=12, font_family=s.MONO, color=c("ink", "fg"),
                                             bgcolor=c("surface-3")),
                block_spacing=8,
            ),
        )
        self._notes_box = ft.Container(
            content=ft.Column(controls=[self._notes], scroll=ft.ScrollMode.AUTO, spacing=0),
            height=None,
        )
        self._progress = ft.ProgressBar(value=0, color=c("ink"), bgcolor=c("surface-3"),
                                        bar_height=4, border_radius=2)
        self._progress_text = s.text("", "mono")
        self._progress_row = ft.Column(
            controls=[self._progress, self._progress_text], spacing=8, visible=False,
        )
        self._message = s.text("", "small")
        self._actions = ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        inner = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            s.icon_tile(ft.Icons.NEW_RELEASES_OUTLINED, active=True),
                            ft.Column(controls=[self._title, self._meta], spacing=2, expand=True),
                            s.button("发布页", self._open_release, kind="ghost",
                                     icon=ft.Icons.OPEN_IN_NEW_ROUNDED),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self._notes_box,
                    self._progress_row,
                    self._message,
                    self._actions,
                ],
                spacing=14,
                tight=True,
            ),
            bgcolor=c("surface-2"),
            border=ft.border.all(1, c("line")),
            border_radius=12,
            padding=ft.padding.only(left=16, right=12, top=14, bottom=16),
        )
        super().__init__(
            content=inner,
            padding=ft.padding.only(top=4, bottom=10),
            opacity=0,
            visible=False,
            offset=ft.Offset(0, -0.02),
            animate_opacity=s.smooth(),
            animate_offset=s.smooth(),
        )
        self._shown_for = ""
        self.render(update_service.state)

    # ── 渲染 ─────────────────────────────────────────────────────────
    def render(self, st: UpdateState) -> None:
        rel = st.release
        show = rel is not None and (
            st.status in ("available", "downloading", "installing", "ready", "manual")
            or _download_failed(st)
        )
        if not show:
            self.visible, self.opacity = False, 0
            self._shown_for = ""
            return
        assert rel is not None

        if self._shown_for != rel.version:
            # 首次出现时从略高处淡入
            self._shown_for = rel.version
            self.visible, self.opacity, self.offset = True, 0, ft.Offset(0, -0.02)
            self._page.run_task(self._reveal)

        asset = rel.package()
        self._title.value = f"发现新版本 v{rel.version}"
        meta = [m for m in (rel.published_at and f"{rel.published_at} 发布",
                            asset and _mb(asset.size)) if m]
        self._meta.value = " · ".join(meta) or rel.name
        notes = rel.notes or "这个版本没有填写更新说明。"
        if self._notes.value != notes:
            self._notes.value = notes
        # 说明不长就不给固定高度，免得留白
        self._notes_box.height = self.NOTES_MAX_H if notes.count("\n") > 9 else None

        self._progress_row.visible = st.status in ("downloading", "installing")
        self._message.visible = False
        self._message.color = c("ink-2", "fg")

        if st.status == "downloading":
            total = st.total or (asset.size if asset else 0)
            self._progress.value = (st.received / total) if total else None
            pct = f" · {int(st.received * 100 / total)}%" if total else ""
            self._progress_text.value = (f"{_mb(st.received)} / {_mb(total)}{pct}" if total
                                         else _mb(st.received))
            self._actions.controls = [s.button("取消", lambda _: update_service.cancel_download(),
                                               kind="secondary")]
        elif st.status == "installing":
            self._progress.value = None
            self._progress_text.value = "校验通过，正在解压…"
            self._actions.controls = []
        elif st.status == "ready":
            self._say("已下载并校验通过。重启应用即可完成更新，正在处理的任务会被中断。")
            self._actions.controls = [
                s.button("重启并更新", self._restart, icon=ft.Icons.RESTART_ALT_ROUNDED),
            ]
        elif st.status == "manual":
            plan = st.plan
            reason = getattr(plan, "reason", "") or "当前无法自动替换"
            self._say(f"{reason}。新版本已下载并校验，解压在打开的文件夹里："
                      "请关闭应用，用它替换现在的程序后再打开。")
            self._actions.controls = [
                s.button("打开文件夹", self._reveal_folder, icon=ft.Icons.FOLDER_OPEN_OUTLINED),
            ]
        elif _download_failed(st):
            self._say(st.error, danger=True)
            self._actions.controls = [
                s.button("重试", self._download, icon=ft.Icons.REFRESH_ROUNDED),
            ]
        elif asset is None:
            self._say("这个版本没有适用于当前系统的安装包，请在发布页手动下载。")
            self._actions.controls = []
        else:
            self._actions.controls = [
                s.button("下载并更新", self._download, icon=ft.Icons.DOWNLOAD_ROUNDED),
            ]

    def _say(self, text: str, danger: bool = False) -> None:
        self._message.value = text
        self._message.visible = True
        self._message.color = c("danger" if danger else "ink-2", "fg")

    async def _reveal(self) -> None:
        await asyncio.sleep(0.016)
        self.opacity, self.offset = 1, ft.Offset(0, 0)
        try:
            self.update()
        except RuntimeError:
            pass

    # ── 操作 ─────────────────────────────────────────────────────────
    def _download(self, _) -> None:
        async def _run() -> None:
            st = await update_service.download_and_prepare()
            if st.status == "manual" and st.plan is not None:
                open_folder(st.plan.reveal)  # type: ignore[attr-defined]

        self._page.run_task(_run)

    def _restart(self, _) -> None:
        plan = update_service.state.plan
        rel = update_service.state.release
        if plan is None or rel is None:
            return
        try:
            update_installer.launch(plan, update_service.download_dir())  # type: ignore[arg-type]
        except update_installer.InstallError as exc:
            show_toast(self._page, str(exc), kind="error", duration=4000)
            return
        update_service.mark_pending(rel.version)
        show_toast(self._page, "正在重启以完成更新…")

        async def _quit() -> None:
            await asyncio.sleep(0.8)
            await self._page.window.destroy()

        self._page.run_task(_quit)

    def _reveal_folder(self, _) -> None:
        plan = update_service.state.plan
        if plan is not None:
            open_folder(plan.reveal)  # type: ignore[attr-defined]

    def _open_release(self, _) -> None:
        rel = update_service.state.release
        self._open_url(rel.html_url if rel else update_service.RELEASES_PAGE)

    def _open_url(self, url: str | None) -> None:
        if url:
            self._page.run_task(self._page.launch_url, url)
