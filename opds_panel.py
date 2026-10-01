"""OPDS 在线书库浏览面板。

作为主窗口的一个 Tab：输入 OPDS 书库地址 → 浏览分类 → 下载电子书，
下载完成后直接交给阅读器打开。
"""

import re
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QFrame, QProgressBar,
    QMessageBox, QDialog,
)

from opds_client import (
    OPDSFeed, OPDSItem, fetch_feed, download_file, guess_extension,
    OPDSAuth, AuthRequired,
)
from opds_auth_dialog import OPDSAuthDialog
from storage import save_config, get_opds_download_dir

_ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _clean_filename(name: str) -> str:
    name = _ILLEGAL.sub("_", name).strip()
    name = name.replace(" ", "_").strip("_ ") or "book"
    return name[:120]


def _display_name(item: OPDSItem) -> str:
    if item.author:
        return f"{item.title} · {item.author}"
    return item.title


class OPDSLoadWorker(QThread):
    done = pyqtSignal(object)   # OPDSFeed
    error = pyqtSignal(str)
    auth_required = pyqtSignal(object)   # AuthRequired

    def __init__(self, url: str, auth: OPDSAuth):
        super().__init__()
        self.url = url
        self.auth = auth

    def run(self):
        try:
            self.done.emit(fetch_feed(self.url, auth=self.auth))
        except AuthRequired as e:
            self.auth_required.emit(e)
        except Exception as e:
            self.error.emit(str(e))


class OPDSDownloadWorker(QThread):
    progress = pyqtSignal(int, int)   # (done, total); total=-1 未知
    done = pyqtSignal(str)
    error = pyqtSignal(str)
    auth_required = pyqtSignal(object)   # AuthRequired

    def __init__(self, url: str, dest: str, auth: OPDSAuth):
        super().__init__()
        self.url = url
        self.dest = dest
        self.auth = auth

    def run(self):
        try:
            download_file(self.url, self.dest, auth=self.auth,
                          progress_cb=lambda d, t: self.progress.emit(d, t))
            self.done.emit(self.dest)
        except AuthRequired as e:
            self.auth_required.emit(e)
        except Exception as e:
            self.error.emit(str(e))


class OPDSBrowser(QWidget):
    open_book_requested = pyqtSignal(str)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.history = []          # 每层 (层级标题, url)
        self.current_url = ""
        self.current_items: list[OPDSItem] = []
        self.current_item: OPDSItem | None = None
        self._next_url = ""
        self._prev_url = ""
        self._dl_worker = None
        self._retry_on_auth = False   # 记住本次请求失败后是否需要重试
        self._pending_download = None  # (item, open_after) 认证后继续的下载
        self._current_auth = OPDSAuth()   # 当前书库生效的认证配置

        self._build_ui()
        # 从下拉框选中书库时，地址栏只保留纯 URL
        self.server_combo.activated.connect(self._on_server_picked)

        servers = config.get("opds_servers", [])
        if servers:
            for s in servers:
                self._add_server_to_combo(s)
            self.url_edit.setText(self._server_url(servers[0]))
            self._open_home()

    # ---------- 书库条目读写 ----------
    @staticmethod
    def _server_url(entry) -> str:
        """兼容两种历史格式：字符串地址，或 {url, auth} 字典。"""
        if isinstance(entry, dict):
            return entry.get("url", "") or ""
        return str(entry)

    @staticmethod
    def _server_auth(entry) -> OPDSAuth:
        if isinstance(entry, dict):
            return OPDSAuth.from_dict(entry.get("auth"))
        return OPDSAuth()

    def _add_server_to_combo(self, entry):
        url = self._server_url(entry)
        if not url:
            return
        auth = self._server_auth(entry)
        label = url if auth.kind == "none" else f"{url}    [{auth.describe()}]"
        self.server_combo.addItem(label, entry)
        # 下拉显示带认证标记，但输入框只放纯地址
        self.server_combo.setItemData(self.server_combo.count() - 1, url, Qt.ToolTipRole)

    def _find_server_entry(self, url: str):
        """按 URL 查找已保存的书库条目（含认证信息）。"""
        for i in range(self.server_combo.count()):
            entry = self.server_combo.itemData(i)
            if self._server_url(entry) == url:
                return entry
        for entry in self.config.get("opds_servers", []):
            if isinstance(entry, dict) and entry.get("url") == url:
                return entry
        return None

    def _auth_for_url(self, url: str) -> OPDSAuth:
        entry = self._find_server_entry(url)
        if entry is not None:
            return self._server_auth(entry)
        return self._current_auth

    # ---------- UI ----------
    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 10, 16, 12)
        v.setSpacing(8)

        # 地址栏
        top = QHBoxLayout()
        self.server_combo = QComboBox()
        self.server_combo.setEditable(True)
        self.server_combo.setInsertPolicy(QComboBox.NoInsert)
        self.server_combo.setMinimumHeight(32)
        self.url_edit = self.server_combo.lineEdit()
        self.url_edit.setPlaceholderText(
            "输入 OPDS 书库地址，例如 https://feedbooks.com/opds 或 …/opds/root.xml"
        )
        self.btn_add = QPushButton("☆ 收藏")
        self.btn_login = QPushButton("🔑 登录")
        self.btn_load = QPushButton("打开书库")
        self.btn_add.clicked.connect(self._on_add_server)
        self.btn_login.clicked.connect(self._on_manual_login)
        self.btn_load.clicked.connect(self._on_load)
        top.addWidget(self.server_combo, 1)
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_login)
        top.addWidget(self.btn_load)
        v.addLayout(top)

        # 导航
        nav = QHBoxLayout()
        self.btn_back = QPushButton("← 返回")
        self.btn_home = QPushButton("首页")
        self.btn_prev = QPushButton("上一页")
        self.btn_next = QPushButton("下一页")
        self.crumb = QLabel("")
        self.crumb.setObjectName("muted")
        self.crumb.setWordWrap(True)
        for b in (self.btn_back, self.btn_home, self.btn_prev, self.btn_next):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(30)
        self.btn_back.clicked.connect(self._go_back)
        self.btn_home.clicked.connect(self._open_home)
        self.btn_prev.clicked.connect(self._go_prev)
        self.btn_next.clicked.connect(self._go_next)
        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_home)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        nav.addWidget(self.crumb, 1)
        v.addLayout(nav)

        # 书目列表
        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(self._on_double_click)
        self.listw.currentItemChanged.connect(self._on_select_item)
        v.addWidget(self.listw, 1)

        # 详情区
        self.detail = QFrame()
        dv = QVBoxLayout(self.detail)
        dv.setContentsMargins(0, 8, 0, 0)
        dv.setSpacing(4)
        self.detail_title = QLabel("")
        self.detail_title.setObjectName("h2")
        self.detail_title.setWordWrap(True)
        self.detail_meta = QLabel("")
        self.detail_meta.setObjectName("muted")
        self.detail_summary = QLabel("")
        self.detail_summary.setWordWrap(True)
        self.detail_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        btn_row = QHBoxLayout()
        self.btn_download = QPushButton("下载")
        self.btn_open = QPushButton("下载并阅读")
        self.btn_web = QPushButton("在浏览器打开")
        btn_row.addWidget(self.btn_download)
        btn_row.addWidget(self.btn_open)
        btn_row.addWidget(self.btn_web)
        btn_row.addStretch(1)
        dv.addWidget(self.detail_title)
        dv.addWidget(self.detail_meta)
        dv.addWidget(self.detail_summary)
        dv.addLayout(btn_row)
        self.btn_download.clicked.connect(lambda: self._start_download(open_after=False))
        self.btn_open.clicked.connect(lambda: self._start_download(open_after=True))
        self.btn_web.clicked.connect(self._open_in_browser)
        v.addWidget(self.detail)
        self.detail.hide()

        # 下载进度
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.hide()
        v.addWidget(self.progress)
        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        v.addWidget(self.status_label)

        self._enable_nav(False)

    def _enable_nav(self, enabled: bool):
        self.btn_back.setEnabled(enabled and bool(self.history))
        self.btn_prev.setEnabled(enabled and bool(self._prev_url))
        self.btn_next.setEnabled(enabled and bool(self._next_url))

    # ---------- 加载 ----------
    def _normalize_url(self, url: str) -> str:
        url = url.strip()
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    def _on_server_picked(self, index: int):
        """下拉选中书库：地址栏回填纯 URL，并切换对应认证配置。"""
        entry = self.server_combo.itemData(index)
        if entry is None:
            return
        url = self._normalize_url(self._server_url(entry))
        self.url_edit.setText(url)
        self._current_auth = self._server_auth(entry)

    def _on_load(self):
        url = self._normalize_url(self.url_edit.text())
        # 切换书库时同步切换认证配置
        self._current_auth = self._auth_for_url(url)
        self._load_url(url, push=False)

    def _load_url(self, url: str, push: bool, auth=None):
        if not url:
            QMessageBox.information(self, "提示", "请先输入 OPDS 书库地址。")
            return
        if auth is not None:
            self._current_auth = auth
        self.status_label.setText(f"正在加载：{url} …")
        self.btn_load.setEnabled(False)
        self.worker = OPDSLoadWorker(url, self._current_auth)
        self.worker.done.connect(self._on_feed_loaded)
        self.worker.error.connect(self._on_load_error)
        self.worker.auth_required.connect(
            lambda info, u=url: self._on_load_auth_required(u, info)
        )
        self.worker.start()

    def _on_load_auth_required(self, url: str, info: AuthRequired):
        """书库要求登录：弹出登录框，成功后自动重试。"""
        self.btn_load.setEnabled(True)
        self.status_label.setText("")

        if not info.needs_credentials and info.scheme == "unknown":
            QMessageBox.warning(
                self, "需要登录",
                f"书库拒绝了访问（401），但未声明认证方式。\n"
                f"可尝试在「🔑 登录」中手动选择认证方式。",
            )
            return

        dlg = OPDSAuthDialog(url, self._current_auth, info.scheme, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        auth = dlg.result_auth
        self._current_auth = auth
        # 记住认证，下次直接用
        self._save_server_auth(url, auth)
        self.status_label.setText("正在使用新凭据重试 …")
        self._load_url(url, push=False, auth=auth)

    def _on_feed_loaded(self, feed: OPDSFeed):
        self.btn_load.setEnabled(True)
        self.current_url = feed.url
        self.current_items = feed.items
        self.current_item = None
        self._next_url = feed.next_url
        self._prev_url = feed.previous_url
        self.detail.hide()

        self.crumb.setText(" / ".join([h[0] for h in self.history] + [feed.title]))
        self._render_items(feed.items)
        self._enable_nav(True)
        suffix = f" · 已登录（{self._current_auth.describe()}）" if self._current_auth.kind != "none" else ""
        self.status_label.setText(f"共 {len(feed.items)} 项" + (" · 已翻页" if feed.next_url else "") + suffix)

    def _on_load_error(self, msg: str):
        self.btn_load.setEnabled(True)
        self._enable_nav(True)
        self.status_label.setText("")
        QMessageBox.warning(self, "无法加载书库", f"请求失败：\n{msg}")

    def _render_items(self, items):
        self.listw.clear()
        if not items:
            self.listw.addItem("（此目录为空）")
            return
        for it in items:
            label = f"📂  {it.title}" if it.is_feed else f"📕  {_display_name(it)}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, it)
            item.setToolTip(it.summary or "")
            self.listw.addItem(item)

    # ---------- 导航 ----------
    def _open_feed(self, item: OPDSItem):
        link = item.open_link()
        if not link:
            return
        self.history.append((self.crumb.text() or "书库", self.current_url))
        self._load_url(link.href, push=False)

    def _open_home(self):
        self.history.clear()
        # 优先用下拉框中选中项的纯地址，其次用输入框内容
        url = ""
        entry = self.server_combo.currentData()
        if entry is not None:
            url = self._normalize_url(self._server_url(entry))
        if not url:
            url = self._normalize_url(self.url_edit.text().strip())
        self._current_auth = self._auth_for_url(url)
        self._load_url(url, push=False)

    def _go_back(self):
        if not self.history:
            return
        _, url = self.history.pop()
        self._load_url(url, push=False)

    def _go_next(self):
        if not self._next_url:
            return
        self.history.append((self.crumb.text() or "书库", self.current_url))
        self._load_url(self._next_url, push=False)

    def _go_prev(self):
        if not self._prev_url:
            return
        self.history.append((self.crumb.text() or "书库", self.current_url))
        self._load_url(self._prev_url, push=False)

    # ---------- 列表交互 ----------
    def _on_double_click(self, item: QListWidgetItem):
        obj = item.data(Qt.UserRole)
        if obj is None:
            return
        if obj.is_feed:
            self._open_feed(obj)
        else:
            self._show_detail(obj)

    def _on_select_item(self, cur, _prev):
        obj = cur.data(Qt.UserRole) if cur else None
        if obj is None or obj.is_feed:
            self.detail.hide()
            return
        self._show_detail(obj)

    def _show_detail(self, item: OPDSItem):
        self.current_item = item
        self.detail_title.setText(item.title)
        meta = []
        if item.author:
            meta.append(f"作者：{item.author}")
        if item.updated:
            meta.append(f"更新：{item.updated[:10].replace('-', '.')}")
        self.detail_meta.setText("  ·  ".join(meta))
        self.detail_summary.setText(item.summary or "（无简介）")
        has_link = bool(item.download_links())
        self.btn_download.setEnabled(has_link)
        self.btn_open.setEnabled(has_link)
        self.detail.show()

    # ---------- 下载 ----------
    def _pick_download(self, item: OPDSItem):
        links = item.download_links()
        if not links:
            return None, ""
        link = links[0]
        ext = guess_extension(link)
        return link.href, ext

    def _start_download(self, open_after: bool):
        item = getattr(self, "current_item", None)
        if not item:
            return
        href, ext = self._pick_download(item)
        if not href:
            QMessageBox.information(
                self, "提示",
                "此书未提供开放下载链接（可能需要购买或仅在线阅读）。\n"
                "可尝试「在浏览器打开」查看详情页。",
            )
            return
        if not ext:
            QMessageBox.information(
                self, "无法确定格式",
                "无法确定该下载链接的文件格式，已跳过下载。",
            )
            return

        dl_dir = get_opds_download_dir(self.config)
        dest = dl_dir / (_clean_filename(item.title) + ext)

        if dest.exists() and dest.stat().st_size > 0:
            ret = QMessageBox.question(
                self, "文件已存在",
                f"已下载过：\n{dest}\n\n要重新下载覆盖吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                if open_after:
                    self._open_if_supported(dest)
                return

        self.btn_download.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.status_label.setText(f"正在下载《{item.title}》…")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.show()

        self._dl_worker = OPDSDownloadWorker(href, str(dest), self._current_auth)
        self._dl_worker.progress.connect(self._on_dl_progress)
        self._dl_worker.done.connect(
            lambda p, i=item, oa=open_after: self._on_dl_done(p, i, oa)
        )
        self._dl_worker.error.connect(self._on_dl_error)
        self._dl_worker.auth_required.connect(
            lambda info, i=item, oa=open_after: self._on_dl_auth_required(i, oa, info)
        )
        self._dl_worker.start()

    def _on_dl_auth_required(self, item: OPDSItem, open_after: bool, info: AuthRequired):
        """下载时要求登录：弹登录框，保存后自动重下。"""
        self.progress.hide()
        self.btn_download.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.status_label.setText("")

        dlg = OPDSAuthDialog(self.current_url, self._current_auth, info.scheme, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        auth = dlg.result_auth
        self._current_auth = auth
        self._save_server_auth(self.current_url, auth)
        # 用新凭据自动重试下载
        self._start_download(open_after)

    def _on_dl_progress(self, done: int, total: int):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            pct = done * 100 // total
            size = done / 1024 / 1024
            self.status_label.setText(f"下载中 … {size:.1f} MB（{pct}%）")
        else:
            self.progress.setRange(0, 0)
            self.progress.setValue(0)
            self.status_label.setText("下载中 …")

    def _on_dl_done(self, dest: str, item: OPDSItem, open_after: bool):
        self.progress.hide()
        self.btn_download.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.status_label.setText(f"已下载：{dest}")
        if open_after:
            self._open_if_supported(Path(dest))
        else:
            QMessageBox.information(self, "下载完成", f"已保存到：\n{dest}")

    def _on_dl_error(self, msg: str):
        self.progress.hide()
        self.btn_download.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.status_label.setText("")
        QMessageBox.warning(self, "下载失败", f"{msg}")

    def _open_if_supported(self, path: Path):
        ext = path.suffix.lower()
        if ext in (".epub", ".mobi", ".azw", ".azw3"):
            self.open_book_requested.emit(str(path))
        else:
            QMessageBox.information(
                self, "下载完成",
                f"格式 {ext} 无法在此阅读器中直接打开，请手动打开：\n{path}",
            )

    def _open_in_browser(self):
        item = getattr(self, "current_item", None)
        url = ""
        if item:
            page = item.web_page_link()
            if page:
                url = page.href
        if not url:
            url = self.current_url
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # ---------- 收藏 / 认证 ----------
    def _save_server_auth(self, url: str, auth: OPDSAuth):
        """把认证信息写入已保存的书库条目（存在则更新，不存在则新增）。"""
        url = self._normalize_url(url)
        if not url:
            return
        servers = self.config.setdefault("opds_servers", [])
        entry = {"url": url, "auth": auth.to_dict()}
        for i, s in enumerate(servers):
            if self._server_url(s) == url:
                servers[i] = entry
                break
        else:
            servers.insert(0, entry)
        save_config(self.config)
        self._reload_servers(url, keep_auth=True)

    def _on_add_server(self):
        # 输入框里是纯地址；若用户从下拉直接触发，则用选中项
        url = self._normalize_url(self.url_edit.text().strip())
        if not url:
            entry = self.server_combo.currentData()
            if entry is not None:
                url = self._normalize_url(self._server_url(entry))
        if not url:
            QMessageBox.information(self, "提示", "请先输入书库地址。")
            return
        # 收藏时若已有认证配置，一并保存
        auth = self._current_auth if self._current_auth.kind != "none" else self._auth_for_url(url)
        self._save_server_auth(url, auth)
        desc = "" if auth.kind == "none" else f"\n认证方式：{auth.describe()}"
        QMessageBox.information(self, "已收藏", f"已保存书库：\n{url}{desc}")

    def _on_manual_login(self):
        """手动为当前地址配置认证。"""
        url = self._normalize_url(self.url_edit.text().strip())
        if not url:
            QMessageBox.information(self, "提示", "请先输入书库地址，再配置登录信息。")
            return
        current = self._auth_for_url(url)
        dlg = OPDSAuthDialog(url, current, "", self)
        if dlg.exec_() != QDialog.Accepted:
            return
        auth = dlg.result_auth
        self._current_auth = auth
        self._save_server_auth(url, auth)
        if auth.kind == "none":
            QMessageBox.information(self, "已清除", "已将该书库设为无需认证。")
        else:
            QMessageBox.information(
                self, "已保存",
                f"已保存认证信息：{auth.describe()}\n正在重新加载书库 …"
            )
            self._load_url(url, push=False, auth=auth)

    def _reload_servers(self, keep: str, keep_auth: bool = False):
        self.server_combo.clear()
        servers = self.config.get("opds_servers", [])
        for s in servers:
            self._add_server_to_combo(s)
        # 恢复输入框的纯地址（不带认证标记）
        self.url_edit.setText(self._normalize_url(keep) if keep else "")
        # 同步当前生效的认证
        entry = self._find_server_entry(self._normalize_url(keep))
        self._current_auth = self._server_auth(entry) if entry else OPDSAuth()
