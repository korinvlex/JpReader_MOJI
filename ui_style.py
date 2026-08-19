def build_qss(theme: str = "light", ui_font_size: int = 15) -> str:
    # QSS 中的 px 是逻辑像素。把所有控件的间距与字号一起缩放，
    # 避免用户调大界面字体后出现文字拥挤，或调小时控件显得过于松散。
    ui_font_size = max(11, min(24, int(ui_font_size)))
    tab_v_padding = max(7, round(ui_font_size * 0.75))
    tab_h_padding = max(12, round(ui_font_size * 1.5))
    list_v_padding = max(6, round(ui_font_size * 0.65))
    list_h_padding = max(8, round(ui_font_size * 0.8))
    field_padding = max(7, round(ui_font_size * 0.65))
    button_v_padding = max(6, round(ui_font_size * 0.5))
    button_h_padding = max(10, round(ui_font_size * 1.0))

    if theme == "dark":
        bg = "#1e1e20"
        surface = "#2a2a2d"
        border = "#3a3a3e"
        text = "#e4e4e4"
        sub = "#9a9a9a"
        hover = "#35353a"
        accent = "#e4e4e4"
        accent_bg = "#3a3a3e"
        selbg = "#5a4a1f"
        status_bg = "#242427"
    else:
        bg = "#fafafa"
        surface = "#ffffff"
        border = "#ececec"
        text = "#2b2b2b"
        sub = "#888888"
        hover = "#f4f4f4"
        accent = "#2b2b2b"
        accent_bg = "#ececec"
        selbg = "#b3d4fc"
        status_bg = "#f4f4f4"

    return f"""
* {{
    font-family: "Inter", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: {ui_font_size}px;
    color: {text};
}}
QMainWindow, QDialog, QWidget {{ background: {bg}; }}

QTabWidget::pane {{ border: none; background: {bg}; }}
QTabBar::tab {{
    background: transparent; padding: {tab_v_padding}px {tab_h_padding}px; margin-right: 4px;
    color: {sub}; border: none; border-bottom: 2px solid transparent;
    font-size: {ui_font_size + 1}px;
}}
QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {accent}; }}
QTabBar::tab:hover {{ color: {text}; }}

QListWidget {{
    background: {surface}; border: 1px solid {border}; border-radius: 8px;
    padding: 6px; outline: 0;
}}
QListWidget::item {{ padding: {list_v_padding}px {list_h_padding}px; border-radius: 6px; color: {text}; }}
QListWidget::item:selected {{ background: {accent_bg}; }}
QListWidget::item:hover {{ background: {hover}; }}

QTextBrowser, QTextEdit, QLineEdit {{
    background: {surface}; border: 1px solid {border}; border-radius: 8px;
    padding: {field_padding}px; selection-background-color: {selbg}; selection-color: #000;
    color: {text};
}}

QPushButton {{
    background: {surface}; border: 1px solid {border}; border-radius: 6px;
    padding: {button_v_padding}px {button_h_padding}px; color: {text};
}}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {accent_bg}; }}

QLabel#h1 {{ font-size: {ui_font_size + 6}px; font-weight: 600; color: {text}; }}
QLabel#h2 {{ font-size: {ui_font_size + 2}px; font-weight: 600; color: {text}; }}
QLabel#muted {{ color: {sub}; }}

QMenuBar {{ background: {bg}; border-bottom: 1px solid {border}; }}
QMenuBar::item {{ padding: {button_v_padding}px {button_h_padding}px; background: transparent; font-size: {ui_font_size}px; }}
QMenuBar::item:selected {{ background: {accent_bg}; border-radius: 4px; }}

QMenu {{ background: {surface}; border: 1px solid {border}; border-radius: 6px; padding: 4px; }}
QMenu::item {{ padding: {button_v_padding}px {tab_h_padding}px; border-radius: 4px; color: {text}; }}
QMenu::item:selected {{ background: {accent_bg}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {sub}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QStatusBar {{ background: {status_bg}; color: {sub}; border-top: 1px solid {border}; font-size: {ui_font_size - 1}px; }}

QComboBox {{
    background: {surface}; border: 1px solid {border}; border-radius: 6px;
    padding: 7px 12px; color: {text};
}}
QComboBox QAbstractItemView {{
    background: {surface}; border: 1px solid {border}; color: {text};
    selection-background-color: {accent_bg};
}}

QGroupBox {{
    border: 1px solid {border}; border-radius: 8px; margin-top: 14px;
    padding-top: 10px; background: {surface};
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: {sub}; font-weight: 600;
}}

QSlider::groove:horizontal {{
    height: 4px; background: {border}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {accent}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}}
"""


def build_reader_css(theme: str = "light", font_size: int = 20, line_height: float = 1.95) -> str:
    font_size = max(12, min(40, int(font_size)))
    line_height = max(1.2, min(2.8, float(line_height)))
    if theme == "dark":
        color = "#e4e4e4"
        bg = "transparent"
        h_color = "#f0f0f0"
        rt_color = "#aaaaaa"
    else:
        color = "#2b2b2b"
        bg = "transparent"
        h_color = "#111111"
        rt_color = "#888888"

    return f"""
<style>
  body {{
    font-family: "Source Han Serif SC","Source Han Serif","Noto Serif CJK JP",
                 "Yu Mincho","MS Mincho","Hiragino Mincho ProN",serif;
    font-size: {font_size}px;
    line-height: {line_height};
    color: {color};
    background: {bg};
    padding: 1em 2em;
    max-width: 39em;
    margin: 0 auto;
  }}
  p {{ margin: 0.9em 0; }}
  h1,h2,h3,h4 {{ font-weight: 600; color: {h_color}; }}
  ruby rt {{ font-size: 0.55em; color: {rt_color}; }}
</style>
"""
