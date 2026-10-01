"""OPDS 书库认证对话框。

用于为需要登录的书库填写凭据，支持：
  - 账号密码（HTTP Basic / Digest）
  - Bearer 令牌（OAuth 2.0）
  - 自定义请求头（自建服务常见）
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QComboBox, QDialogButtonBox, QStackedWidget,
    QWidget,
)

from opds_client import OPDSAuth


class OPDSAuthDialog(QDialog):
    """返回 self.result_auth（OPDSAuth）供调用方保存。"""

    def __init__(self, url: str, current: OPDSAuth | None = None,
                 hint_scheme: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("书库登录")
        self.setMinimumWidth(460)

        auth = current or OPDSAuth()
        self.result_auth = auth

        root = QVBoxLayout(self)

        info = QLabel(f"书库地址：\n{url}")
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info.setObjectName("muted")
        root.addWidget(info)

        form = QFormLayout()
        self.kind = QComboBox()
        self.kind.addItem("无需认证（公开书库）", "none")
        self.kind.addItem("账号密码 — HTTP Basic", "basic")
        self.kind.addItem("账号密码 — HTTP Digest", "digest")
        self.kind.addItem("Bearer 令牌（OAuth 2.0）", "bearer")
        self.kind.addItem("自定义请求头", "header")
        form.addRow("认证方式：", self.kind)
        root.addLayout(form)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # --- 页 0：无认证 ---
        p_none = QWidget()
        QVBoxLayout(p_none).addWidget(
            QLabel("此页无需填写。若书库实际需要登录，请在上方选择对应的认证方式。")
        )

        # --- 页 1：账号密码 ---
        p_pw = QWidget()
        f_pw = QFormLayout(p_pw)
        self.username = QLineEdit(auth.username)
        self.password = QLineEdit(auth.password)
        self.password.setEchoMode(QLineEdit.Password)
        f_pw.addRow("用户名：", self.username)
        f_pw.addRow("密　码：", self.password)
        pw_hint = QLabel("凭据仅保存在本机配置文件中，不会上传。")
        pw_hint.setObjectName("muted")
        pw_hint.setWordWrap(True)
        f_pw.addRow(pw_hint)

        # --- 页 2：Bearer 令牌 ---
        p_token = QWidget()
        f_token = QFormLayout(p_token)
        self.token = QLineEdit(auth.token)
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("粘贴访问令牌（access token）")
        f_token.addRow("令　牌：", self.token)
        token_hint = QLabel(
            "在书库网页版「账户设置 / 开发者」处生成访问令牌后粘贴到此处。"
        )
        token_hint.setObjectName("muted")
        token_hint.setWordWrap(True)
        f_token.addRow(token_hint)

        # --- 页 3：自定义请求头 ---
        p_hdr = QWidget()
        f_hdr = QFormLayout(p_hdr)
        self.header_name = QLineEdit(auth.header_name)
        self.header_name.setPlaceholderText("例如 X-Api-Key")
        self.header_value = QLineEdit(auth.header_value)
        self.header_value.setEchoMode(QLineEdit.Password)
        f_hdr.addRow("请求头名：", self.header_name)
        f_hdr.addRow("请求头值：", self.header_value)

        for w in (p_none, p_pw, p_token, p_hdr):
            self.stack.addWidget(w)

        # 服务器已声明认证方式时，自动预选对应项
        initial = "none"
        if auth.kind != "none":
            initial = auth.kind
        elif hint_scheme in ("basic", "digest", "bearer"):
            initial = hint_scheme
        idx = self.kind.findData(initial)
        self.kind.setCurrentIndex(idx if idx >= 0 else 0)
        self._sync_stack()

        self.kind.currentIndexChanged.connect(self._sync_stack)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("保存并连接")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _sync_stack(self):
        kind = self.kind.currentData()
        page = {"none": 0, "basic": 1, "digest": 1, "bearer": 2, "header": 3}
        self.stack.setCurrentIndex(page.get(kind, 0))

    def _on_accept(self):
        kind = self.kind.currentData()
        self.result_auth = OPDSAuth(
            kind=kind,
            username=self.username.text().strip(),
            password=self.password.text(),
            token=self.token.text().strip(),
            header_name=self.header_name.text().strip(),
            header_value=self.header_value.text(),
        )
        self.accept()
