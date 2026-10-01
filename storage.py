import sqlite3
import os
import json
from pathlib import Path

DEFAULT_APP_DIR = Path(os.getenv("APPDATA", ".")) / "JpReader"
DEFAULT_APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = DEFAULT_APP_DIR / "config.json"


DEFAULT_CONFIG = {
    "base_url": "https://api.deepseek.com/v1/chat/completions",
    "api_key": "",
    "model": "deepseek-chat",
    "total_prompt_tokens": 0,
    "total_completion_tokens": 0,
    "total_requests": 0,
    "font_size": 20,
    "line_height": 1.95,
    "theme": "light",
    "jp_level": "N2",
    "bg_image": "",
    "bg_opacity": 0.08,
    "ui_font_size": 15,
    # v5 新增
    "data_dir": "",             # 数据目录，空则使用默认 %APPDATA%/JpReader
    "last_book_path": "",       # 上次打开的电子书路径
    # OPDS 在线书库
    "opds_servers": [],         # 已收藏的 OPDS 书库地址列表
    "opds_download_dir": "",    # OPDS 下载目录，空则用 <数据目录>/opds_downloads
}


def get_data_dir(config: dict) -> Path:
    """返回实际数据目录。若用户配置了自定义路径且有效，则使用之；否则用默认。"""
    custom = config.get("data_dir", "").strip()
    if custom:
        p = Path(custom)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    return DEFAULT_APP_DIR


def get_opds_download_dir(config: dict) -> Path:
    """OPDS 下载目录：用户自定义优先，否则 <数据目录>/opds_downloads。"""
    custom = config.get("opds_download_dir", "").strip()
    if custom:
        p = Path(custom)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    d = get_data_dir(config) / "opds_downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            # 把旧版纯字符串书库列表迁移为 {url, auth} 结构
            normalize_opds_servers(merged)
            return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


# ---------- OPDS 凭据的本地混淆 ----------
# 说明：这不是加密，无法抵御能读取本机文件的攻击者；
# 目的是避免密码以肉眼可读的明文直接出现在 config.json 中。
_OBFUSCATE_KEY = b"JpReader-OPDS-2026"


def _xor(data: bytes) -> bytes:
    key = _OBFUSCATE_KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def obfuscate(text: str) -> str:
    """把明文混淆为可安全写入 json 的字符串。空串原样返回。"""
    if not text:
        return ""
    import base64
    return "enc:" + base64.b64encode(_xor(text.encode("utf-8"))).decode("ascii")


def deobfuscate(text: str) -> str:
    """还原 obfuscate 的结果。兼容历史明文（无 enc: 前缀则原样返回）。"""
    if not text:
        return ""
    if not text.startswith("enc:"):
        return text
    import base64
    try:
        raw = base64.b64decode(text[4:].encode("ascii"))
        return _xor(raw).decode("utf-8")
    except Exception:
        return ""


def normalize_opds_servers(config: dict) -> dict:
    """把历史格式（纯字符串地址列表）统一为 {url, auth} 结构。"""
    servers = config.get("opds_servers", []) or []
    out = []
    changed = False
    for s in servers:
        if isinstance(s, str):
            out.append({"url": s, "auth": {"kind": "none"}})
            changed = True
        elif isinstance(s, dict) and s.get("url"):
            entry = {"url": s["url"], "auth": s.get("auth") or {"kind": "none"}}
            if entry["auth"].get("password"):
                entry["auth"]["password"] = obfuscate(
                    deobfuscate(entry["auth"]["password"])
                )
            if entry["auth"].get("token"):
                entry["auth"]["token"] = obfuscate(
                    deobfuscate(entry["auth"]["token"])
                )
            if entry["auth"].get("header_value"):
                entry["auth"]["header_value"] = obfuscate(
                    deobfuscate(entry["auth"]["header_value"])
                )
            if entry != s:
                changed = True
            out.append(entry)
        # 其余脏数据丢弃
        else:
            changed = True
    if changed:
        config["opds_servers"] = out
    return config


def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


class Storage:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = DEFAULT_APP_DIR / "data.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                book_id TEXT PRIMARY KEY,
                path TEXT,
                title TEXT,
                last_chapter INTEGER DEFAULT 0,
                last_scroll INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS highlights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT,
                book_title TEXT,
                chapter INTEGER,
                chapter_title TEXT,
                text TEXT,
                start_pos INTEGER DEFAULT -1,
                end_pos   INTEGER DEFAULT -1,
                color TEXT DEFAULT '#fff59d',
                ai_analysis TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS study_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                tags TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reading_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT,
                book_title TEXT,
                chapter INTEGER,
                title TEXT,
                content TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cols = [r[1] for r in c.execute("PRAGMA table_info(highlights)").fetchall()]
        if "start_pos" not in cols:
            c.execute("ALTER TABLE highlights ADD COLUMN start_pos INTEGER DEFAULT -1")
        if "end_pos" not in cols:
            c.execute("ALTER TABLE highlights ADD COLUMN end_pos INTEGER DEFAULT -1")
        self.conn.commit()

    # --- 进度 ---
    def save_progress(self, book_id, path, title, chapter, scroll):
        self.conn.execute("""
            INSERT INTO books(book_id, path, title, last_chapter, last_scroll)
            VALUES(?,?,?,?,?)
            ON CONFLICT(book_id) DO UPDATE SET
                last_chapter=excluded.last_chapter,
                last_scroll=excluded.last_scroll,
                path=excluded.path
        """, (book_id, path, title, chapter, scroll))
        self.conn.commit()

    def get_progress(self, book_id):
        row = self.conn.execute(
            "SELECT last_chapter, last_scroll FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
        return (row["last_chapter"], row["last_scroll"]) if row else (0, 0)

    # --- 高亮 ---
    def add_highlight(self, book_id, book_title, chapter, chapter_title, text,
                      start_pos=-1, end_pos=-1, color="#fff59d", ai_analysis=""):
        cur = self.conn.execute("""
            INSERT INTO highlights(book_id, book_title, chapter, chapter_title,
                                  text, start_pos, end_pos, color, ai_analysis)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (book_id, book_title, chapter, chapter_title, text,
              start_pos, end_pos, color, ai_analysis))
        self.conn.commit()
        return cur.lastrowid

    def list_highlights_for_chapter(self, book_id, chapter):
        rows = self.conn.execute("""
            SELECT * FROM highlights WHERE book_id=? AND chapter=? ORDER BY id
        """, (book_id, chapter)).fetchall()
        return [dict(r) for r in rows]

    def update_highlight_analysis(self, hid, analysis):
        self.conn.execute("UPDATE highlights SET ai_analysis=? WHERE id=?", (analysis, hid))
        self.conn.commit()

    def list_highlights(self, book_id=None):
        if book_id:
            rows = self.conn.execute(
                "SELECT * FROM highlights WHERE book_id=? ORDER BY id DESC", (book_id,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM highlights ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_highlight(self, hid):
        self.conn.execute("DELETE FROM highlights WHERE id=?", (hid,))
        self.conn.commit()

    # --- 学习笔记 ---
    def add_study_note(self, title, content, tags=""):
        cur = self.conn.execute(
            "INSERT INTO study_notes(title, content, tags) VALUES(?,?,?)",
            (title, content, tags),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_study_note(self, nid, title, content, tags=""):
        self.conn.execute("""
            UPDATE study_notes SET title=?, content=?, tags=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (title, content, tags, nid))
        self.conn.commit()

    def list_study_notes(self):
        rows = self.conn.execute("SELECT * FROM study_notes ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_study_note(self, nid):
        self.conn.execute("DELETE FROM study_notes WHERE id=?", (nid,))
        self.conn.commit()

    # --- 阅读笔记 ---
    def add_reading_note(self, book_id, book_title, chapter, title, content):
        cur = self.conn.execute("""
            INSERT INTO reading_notes(book_id, book_title, chapter, title, content)
            VALUES(?,?,?,?,?)
        """, (book_id, book_title, chapter, title, content))
        self.conn.commit()
        return cur.lastrowid

    def update_reading_note(self, nid, title, content):
        self.conn.execute("""
            UPDATE reading_notes SET title=?, content=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
        """, (title, content, nid))
        self.conn.commit()

    def list_reading_notes(self, book_id=None):
        if book_id:
            rows = self.conn.execute(
                "SELECT * FROM reading_notes WHERE book_id=? ORDER BY updated_at DESC", (book_id,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM reading_notes ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_reading_note(self, nid):
        self.conn.execute("DELETE FROM reading_notes WHERE id=?", (nid,))
        self.conn.commit()
