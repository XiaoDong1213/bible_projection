"""检查更新：后台下载，底栏进度，下完再询问是否安装。"""

from __future__ import annotations

import threading
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.version import APP_NAME, APP_VERSION, RELEASES_PAGE
from core.updater import (
    DownloadCancelled,
    UpdateInfo,
    check_for_update_safe,
    download_installer,
    launch_installer_and_exit,
)

_PROGRESS_QSS = """
QProgressBar {
  border: 1px solid rgba(127, 140, 160, 0.45);
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.18);
  text-align: center;
  min-height: 14px;
  max-height: 14px;
  min-width: 120px;
  max-width: 160px;
  color: #e8edf5;
  font-size: 11px;
}
QProgressBar::chunk {
  background-color: #2f6fed;
  border-radius: 2px;
}
"""

_CANCEL_QSS = """
QLabel {
  padding: 0 8px;
  margin: 0;
  border: none;
  background: transparent;
  color: #9EC5FF;
  font-size: 13px;
  font-weight: 600;
}
QLabel:hover {
  color: #C8DEFF;
  text-decoration: underline;
}
"""


class _CheckWorker(QObject):
    finished = pyqtSignal(object, object)

    def run(self):
        info, err = check_for_update_safe()
        self.finished.emit(info, err)


class _DownloadWorker(QObject):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object, object)

    def __init__(self, info: UpdateInfo, cancel_event: threading.Event):
        super().__init__()
        self._info = info
        self._cancel = cancel_event

    def run(self):
        try:
            path = download_installer(
                self._info,
                on_progress=lambda done, total: self.progress.emit(int(done), int(total)),
                cancel_event=self._cancel,
            )
            self.finished.emit(path, None)
        except DownloadCancelled:
            self.finished.emit(None, "__cancelled__")
        except Exception as exc:  # noqa: BLE001
            self.finished.emit(None, str(exc) or "下载失败")


def _stop_thread(thread: QThread | None, timeout_ms: int = 8000) -> None:
    if thread is None:
        return
    if thread.isRunning():
        thread.quit()
        if not thread.wait(timeout_ms):
            thread.terminate()
            thread.wait(1000)


class UpdateOfferDialog(QDialog):
    """仅询问是否后台下载，不含进度条。"""

    def __init__(self, info: UpdateInfo, parent=None):
        super().__init__(parent)
        self._info = info
        self.setWindowTitle("发现新版本")
        self.setMinimumWidth(380)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)
        title = QLabel(f"{APP_NAME} 有新版本可用")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        root.addWidget(title)
        meta = QLabel(
            f"当前版本 {APP_VERSION}  →  最新 {info.version}\n"
            "可后台下载，不影响继续使用；下载完成后会询问是否安装。"
        )
        meta.setWordWrap(True)
        root.addWidget(meta)
        row = QHBoxLayout()
        row.addStretch(1)
        later = QPushButton("稍后")
        later.clicked.connect(self.reject)
        download = QPushButton("后台下载")
        download.setDefault(True)
        download.clicked.connect(self.accept)
        row.addWidget(later)
        row.addWidget(download)
        root.addLayout(row)


class UpdateController(QObject):
    """挂在主窗口上：底栏进度 + 后台下载 + 完成后可随时点安装。"""

    def __init__(self, window: QWidget):
        super().__init__(window)
        self._window = window
        self._info: UpdateInfo | None = None
        self._thread: QThread | None = None
        self._worker: _DownloadWorker | None = None
        self._cancel = threading.Event()
        self._busy = False
        self._pending_setup: Path | None = None
        self._action = "cancel"  # cancel | install

        bar = window.statusBar() if hasattr(window, "statusBar") else None
        if not isinstance(bar, QStatusBar):
            bar = None
        self._host_bar = bar

        self._label = QLabel("")
        self._label.setVisible(False)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p%")
        self._progress.setStyleSheet(_PROGRESS_QSS)
        self._progress.setFixedHeight(14)
        self._progress.setVisible(False)
        # 用可点文字，避免 QPushButton 边框在默认状态栏高度里裁切字形
        self._action_btn = QLabel("取消")
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._action_btn.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        self._action_btn.setStyleSheet(_CANCEL_QSS)
        self._action_btn.setVisible(False)
        self._action_btn.setEnabled(True)
        self._action_btn.mousePressEvent = self._on_action_press  # type: ignore[method-assign]

        if bar is not None:
            bar.addPermanentWidget(self._label)
            bar.addPermanentWidget(self._progress)
            bar.addPermanentWidget(self._action_btn)

    def is_downloading(self) -> bool:
        return self._busy

    def has_pending_install(self) -> bool:
        return self._pending_setup is not None and self._pending_setup.is_file()

    def shutdown(self) -> None:
        """窗口关闭前停下载线程，避免 QThread Destroyed while running。"""
        self._cancel.set()
        _stop_thread(self._thread, timeout_ms=3000)
        self._thread = None
        self._worker = None
        self._busy = False

    def offer_and_maybe_download(self, info: UpdateInfo) -> None:
        if self._busy:
            QMessageBox.information(self._window, "检查更新", "正在下载更新，请看窗口底部进度。")
            return
        if self.has_pending_install():
            self.prompt_install()
            return
        dlg = UpdateOfferDialog(info, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.start_download(info)

    def start_download(self, info: UpdateInfo) -> None:
        if self._busy:
            return
        self._pending_setup = None
        self._info = info
        self._cancel.clear()
        self._busy = True
        self._action = "cancel"
        self._label.setText(f"下载更新 {info.version}")
        self._label.setVisible(True)
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._action_btn.setText("取消")
        self._action_btn.setStyleSheet(_CANCEL_QSS)
        self._action_btn.setVisible(True)
        self._action_btn.setEnabled(True)
        if self._host_bar is not None:
            self._host_bar.showMessage("正在高速下载更新…", 0)

        self._thread = QThread(self)
        self._worker = _DownloadWorker(info, self._cancel)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def _on_action_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._action_btn.isEnabled():
            if self._action == "install":
                self.prompt_install()
            else:
                self.cancel_download()
        QLabel.mousePressEvent(self._action_btn, event)

    def cancel_download(self) -> None:
        if not self._busy:
            return
        self._cancel.set()
        self._action_btn.setEnabled(False)
        self._action_btn.setStyleSheet(
            "QLabel { padding: 0 8px; border: none; background: transparent;"
            " color: #8899aa; font-size: 13px; font-weight: 600; }"
        )
        self._label.setText("正在取消…")

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            pct = max(0, min(100, int(done * 100 / total)))
            self._progress.setValue(pct)
            mb = done / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self._label.setText(f"下载更新 {mb:.1f}/{total_mb:.1f} MB")
        else:
            self._progress.setValue(min(95, self._progress.value() + 1))
            self._label.setText(f"下载更新 {done / (1024 * 1024):.1f} MB")

    def _hide_download_chrome(self) -> None:
        self._busy = False
        self._progress.setVisible(False)
        self._progress.setValue(0)
        if self._host_bar is not None:
            self._host_bar.clearMessage()

    def _show_ready_chrome(self, setup: Path, ver: str) -> None:
        self._pending_setup = setup
        self._busy = False
        self._action = "install"
        self._progress.setVisible(False)
        self._progress.setValue(0)
        self._label.setText(f"新版本 {ver} 已就绪" if ver else "更新已就绪")
        self._label.setVisible(True)
        self._action_btn.setText("安装")
        self._action_btn.setStyleSheet(_CANCEL_QSS)
        self._action_btn.setEnabled(True)
        self._action_btn.setVisible(True)
        if self._host_bar is not None:
            self._host_bar.showMessage(
                f"更新已下载，可点底栏「安装」。包：{setup}",
                0,
            )

    def _clear_ready_chrome(self) -> None:
        self._pending_setup = None
        self._action = "cancel"
        self._label.setVisible(False)
        self._progress.setVisible(False)
        self._action_btn.setVisible(False)
        self._progress.setValue(0)
        if self._host_bar is not None:
            self._host_bar.clearMessage()

    def prompt_install(self) -> None:
        setup = self._pending_setup
        if setup is None or not setup.is_file():
            self._clear_ready_chrome()
            QMessageBox.information(
                self._window,
                "安装更新",
                "本地安装包已不存在，请重新检查更新并下载。",
            )
            return
        ver = self._info.version if self._info is not None else ""
        reply = QMessageBox.question(
            self._window,
            "安装更新",
            f"新版本 {ver} 已下载完成。\n是否现在安装？\n（安装时程序会退出；装完会自动删临时安装包）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            # 保留底栏「安装」，别让人找不到入口
            self._show_ready_chrome(setup, ver)
            return
        try:
            launch_installer_and_exit(setup)
        except Exception as exc:  # noqa: BLE001
            self._show_ready_chrome(setup, ver)
            QMessageBox.warning(self._window, "更新失败", f"无法启动安装程序：{exc}")

    def _on_finished(self, path, err) -> None:
        info = self._info
        self._hide_download_chrome()
        if err == "__cancelled__":
            self._clear_ready_chrome()
            if self._host_bar is not None:
                self._host_bar.showMessage("已取消更新下载", 4000)
            return
        if err or path is None:
            self._clear_ready_chrome()
            tip = str(err) or "下载失败"
            if "10060" in tip or "超时" in tip or "timed out" in tip.lower():
                tip += "\n\n网络不稳定时可稍后重试，或打开 Release 页手动下载。"
            QMessageBox.warning(self._window, "更新失败", tip)
            return

        setup = Path(path)
        ver = info.version if info is not None else ""
        self._show_ready_chrome(setup, ver)
        self.prompt_install()


def ensure_update_controller(window: QWidget) -> UpdateController:
    ctrl = getattr(window, "_update_controller", None)
    if isinstance(ctrl, UpdateController):
        return ctrl
    ctrl = UpdateController(window)
    window._update_controller = ctrl  # noqa: SLF001
    return ctrl


def shutdown_update_threads(window: QWidget | None) -> None:
    """关闭窗口时调用：停检查/下载线程。"""
    if window is None:
        return
    host = window.window() if hasattr(window, "window") else window
    ctrl = getattr(host, "_update_controller", None)
    if isinstance(ctrl, UpdateController):
        ctrl.shutdown()
    thread = getattr(host, "_update_check_thread", None)
    if isinstance(thread, QThread):
        _stop_thread(thread, timeout_ms=3000)
    host._update_check_thread = None  # noqa: SLF001
    host._update_check_worker = None  # noqa: SLF001


def run_update_check(parent: QWidget | None, *, quiet: bool = False) -> None:
    """检查更新。quiet=True 时仅在有新版本时询问是否后台下载。"""

    host = parent.window() if parent is not None else None
    if host is None:
        return

    old = getattr(host, "_update_check_thread", None)
    if isinstance(old, QThread) and old.isRunning():
        return
    ctrl = ensure_update_controller(host)
    if ctrl.is_downloading():
        if not quiet:
            QMessageBox.information(host, "检查更新", "正在后台下载更新，请看窗口底部进度。")
        return
    if ctrl.has_pending_install():
        if quiet:
            return
        ctrl.prompt_install()
        return

    def _busy(on: bool):
        bar = host.statusBar() if hasattr(host, "statusBar") else None
        if isinstance(bar, QStatusBar):
            if on:
                bar.showMessage("正在检查更新…", 0)
            else:
                bar.clearMessage()

    _busy(True)
    # 挂到主窗口上，避免函数返回后无父对象被提前析构
    thread = QThread(host)
    worker = _CheckWorker()
    worker.moveToThread(thread)

    def _clear_refs():
        if getattr(host, "_update_check_thread", None) is thread:
            host._update_check_thread = None  # noqa: SLF001
        if getattr(host, "_update_check_worker", None) is worker:
            host._update_check_worker = None  # noqa: SLF001

    def _done(info, err):
        _busy(False)
        _clear_refs()
        if err:
            if not quiet:
                QMessageBox.information(
                    host,
                    "检查更新",
                    f"{err}\n\n也可打开：\n{RELEASES_PAGE}",
                )
            return
        if info is None:
            if not quiet:
                QMessageBox.information(
                    host,
                    "检查更新",
                    f"当前已是最新版本（{APP_VERSION}）。",
                )
            return
        ensure_update_controller(host).offer_and_maybe_download(info)

    thread.started.connect(worker.run)
    # 必须排队回主线程：禁止在工作线程里 wait 自己
    worker.finished.connect(_done, Qt.ConnectionType.QueuedConnection)
    worker.finished.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(_clear_refs)
    host._update_check_thread = thread  # noqa: SLF001
    host._update_check_worker = worker  # noqa: SLF001
    thread.start()
