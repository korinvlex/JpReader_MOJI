from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QMessageBox, QGroupBox, QComboBox,
    QWidget, QSlider, QFileDialog, QScrollArea
)
from PyQt5.QtCore import Qt
from storage import DEFAULT_APP_DIR, get_data_dir


PRESET_ENDPOINTS = {
    "DeepSeek":   ("https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
    "OpenAI":     ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
    "Moonshot":   ("https://api.moonshot.cn/v1/chat/completions", "moonshot-v1-8k"),
    "Ollama本地": ("http://localhost:11434/v1/chat/completions", "qwen2.5:7b"),
    "自定义":     ("", ""),
}


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(440, 420)
        self.resize(560, 680)
        self.config = config.copy()
        self._old_data_dir = config.get("data_dir", "").strip()

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        scroll.setWidget(content)
        root.addWidget(scroll)

        # --- API 配置 ---
        api_box = QGroupBox("API 配置")
        form = QFormLayout(api_box)

        self.preset = QComboBox()
        self.preset.addItems(PRESET_ENDPOINTS.keys())
        self.preset.currentTextChanged.connect(self._on_preset)
        form.addRow("服务商预设：", self.preset)

        self.base_url = QLineEdit(self.config.get("base_url", ""))
        self.api_key = QLineEdit(self.config.get("api_key", ""))
        self.api_key.setEchoMode(QLineEdit.Password)
        self.model = QLineEdit(self.config.get("model", ""))

        form.addRow("Base URL：", self.base_url)
        form.addRow("API Key：", self.api_key)
        form.addRow("模型名：", self.model)

        self.jp_level = QComboBox()
        self.jp_level.addItems(["N5", "N4", "N3", "N2", "N1"])
        self.jp_level.setCurrentText(self.config.get("jp_level", "N2"))
        form.addRow("日语水平：", self.jp_level)

        layout.addWidget(api_box)

        # --- 外观 ---
        look_box = QGroupBox("外观")
        look_form = QFormLayout(look_box)

        # 界面字号
        self.ui_font_slider = QSlider(Qt.Horizontal)
        self.ui_font_slider.setRange(12, 20)
        self.ui_font_slider.setValue(int(self.config.get("ui_font_size", 15)))
        self.ui_font_label = QLabel(f"{self.ui_font_slider.value()}px")
        self.ui_font_slider.valueChanged.connect(
            lambda v: self.ui_font_label.setText(f"{v}px")
        )
        ui_font_row = QHBoxLayout()
        ui_font_row.addWidget(self.ui_font_slider, 1)
        ui_font_row.addWidget(self.ui_font_label)
        ui_font_wrap = QWidget()
        ui_font_wrap.setLayout(ui_font_row)
        look_form.addRow("界面字号：", ui_font_wrap)

        # 阅读正文可独立于界面字号调整；窗口较窄时可适当减小以保留每行字数。
        self.reader_font_slider = QSlider(Qt.Horizontal)
        self.reader_font_slider.setRange(12, 36)
        self.reader_font_slider.setValue(int(self.config.get("font_size", 20)))
        self.reader_font_label = QLabel(f"{self.reader_font_slider.value()}px")
        self.reader_font_slider.valueChanged.connect(
            lambda v: self.reader_font_label.setText(f"{v}px")
        )
        reader_font_row = QHBoxLayout()
        reader_font_row.addWidget(self.reader_font_slider, 1)
        reader_font_row.addWidget(self.reader_font_label)
        reader_font_wrap = QWidget()
        reader_font_wrap.setLayout(reader_font_row)
        look_form.addRow("正文字号：", reader_font_wrap)

        # 背景图
        bg_row = QHBoxLayout()
        self.bg_path = QLineEdit(self.config.get("bg_image", ""))
        bg_pick = QPushButton("选择…")
        bg_clear = QPushButton("清除")
        bg_row.addWidget(self.bg_path, 1)
        bg_row.addWidget(bg_pick)
        bg_row.addWidget(bg_clear)
        bg_wrap = QWidget()
        bg_wrap.setLayout(bg_row)
        look_form.addRow("背景图片：", bg_wrap)

        def _pick_bg():
            p, _ = QFileDialog.getOpenFileName(
                self, "选择背景图", "",
                "图片 (*.png *.jpg *.jpeg *.bmp *.webp)"
            )
            if p:
                self.bg_path.setText(p)

        bg_pick.clicked.connect(_pick_bg)
        bg_clear.clicked.connect(lambda: self.bg_path.clear())

        # 背景透明度
        self.bg_opacity = QSlider(Qt.Horizontal)
        self.bg_opacity.setRange(0, 30)
        self.bg_opacity.setValue(int(self.config.get("bg_opacity", 0.08) * 100))
        self.bg_opacity_label = QLabel(f"{self.bg_opacity.value()}%")
        self.bg_opacity.valueChanged.connect(
            lambda v: self.bg_opacity_label.setText(f"{v}%")
        )
        op_row = QHBoxLayout()
        op_row.addWidget(self.bg_opacity, 1)
        op_row.addWidget(self.bg_opacity_label)
        op_wrap = QWidget()
        op_wrap.setLayout(op_row)
        look_form.addRow("背景透明度：", op_wrap)

        layout.addWidget(look_box)

        # --- 数据存储 ---
        data_box = QGroupBox("数据存储")
        data_form = QFormLayout(data_box)

        # 当前数据路径（只读显示）
        current_dir = get_data_dir(self.config)
        self.lbl_current_dir = QLabel(str(current_dir))
        self.lbl_current_dir.setWordWrap(True)
        self.lbl_current_dir.setTextInteractionFlags(Qt.TextSelectableByMouse)
        data_form.addRow("当前数据位置：", self.lbl_current_dir)

        # 自定义数据目录
        dir_row = QHBoxLayout()
        self.data_dir_edit = QLineEdit(self.config.get("data_dir", ""))
        self.data_dir_edit.setPlaceholderText(f"留空使用默认：{DEFAULT_APP_DIR}")
        dir_pick = QPushButton("选择…")
        dir_clear = QPushButton("恢复默认")
        dir_row.addWidget(self.data_dir_edit, 1)
        dir_row.addWidget(dir_pick)
        dir_row.addWidget(dir_clear)
        dir_wrap = QWidget()
        dir_wrap.setLayout(dir_row)
        data_form.addRow("自定义目录：", dir_wrap)

        def _pick_dir():
            d = QFileDialog.getExistingDirectory(self, "选择数据目录")
            if d:
                self.data_dir_edit.setText(d)

        dir_pick.clicked.connect(_pick_dir)
        dir_clear.clicked.connect(lambda: self.data_dir_edit.clear())

        hint = QLabel("提示：修改数据目录后需重启应用生效，已有数据需手动迁移。")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        data_form.addRow(hint)

        layout.addWidget(data_box)

        # --- 用量统计 ---
        usage_box = QGroupBox("用量统计")
        ul = QFormLayout(usage_box)
        self.lbl_model = QLabel(self.config.get("model", "-"))
        self.lbl_req = QLabel(str(self.config.get("total_requests", 0)))
        self.lbl_pt = QLabel(f"{self.config.get('total_prompt_tokens', 0):,}")
        self.lbl_ct = QLabel(f"{self.config.get('total_completion_tokens', 0):,}")
        total = (self.config.get("total_prompt_tokens", 0)
                 + self.config.get("total_completion_tokens", 0))
        self.lbl_total = QLabel(f"<b>{total:,}</b>")
        ul.addRow("当前模型：", self.lbl_model)
        ul.addRow("总请求次数：", self.lbl_req)
        ul.addRow("Prompt tokens：", self.lbl_pt)
        ul.addRow("Completion tokens：", self.lbl_ct)
        ul.addRow("合计 tokens：", self.lbl_total)

        reset_btn = QPushButton("重置用量统计")
        reset_btn.clicked.connect(self._reset_usage)
        ul.addRow(reset_btn)

        layout.addWidget(usage_box)

        # --- 按钮 ---
        btns = QHBoxLayout()
        ok = QPushButton("保存")
        ok.clicked.connect(self._on_accept)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def _on_preset(self, name):
        url, model = PRESET_ENDPOINTS.get(name, ("", ""))
        if url:
            self.base_url.setText(url)
        if model:
            self.model.setText(model)

    def _reset_usage(self):
        if QMessageBox.question(self, "确认", "确定要清零用量统计吗？") == QMessageBox.Yes:
            self.config["total_prompt_tokens"] = 0
            self.config["total_completion_tokens"] = 0
            self.config["total_requests"] = 0
            self.lbl_pt.setText("0")
            self.lbl_ct.setText("0")
            self.lbl_req.setText("0")
            self.lbl_total.setText("<b>0</b>")

    def _on_accept(self):
        new_dir = self.data_dir_edit.text().strip()
        if new_dir != self._old_data_dir:
            QMessageBox.information(
                self, "数据目录已变更",
                "数据目录变更将在下次启动时生效。\n"
                "如需保留已有数据，请手动将旧目录中的 data.db 复制到新目录。"
            )
        self.accept()

    def get_config(self) -> dict:
        self.config["base_url"] = self.base_url.text().strip()
        self.config["api_key"] = self.api_key.text().strip()
        self.config["model"] = self.model.text().strip()
        self.config["jp_level"] = self.jp_level.currentText()
        self.config["bg_image"] = self.bg_path.text().strip()
        self.config["bg_opacity"] = self.bg_opacity.value() / 100.0
        self.config["ui_font_size"] = self.ui_font_slider.value()
        self.config["font_size"] = self.reader_font_slider.value()
        self.config["data_dir"] = self.data_dir_edit.text().strip()
        return self.config
