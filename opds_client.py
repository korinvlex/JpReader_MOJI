"""OPDS（Open Publication Distribution System）客户端。

支持解析 OPDS 1.x / 2.x 目录（Atom XML），用于在线浏览书库并下载电子书。
参照 https://specs.opds.io/ 实现。

认证：支持 Basic（账号密码）、Digest（挑战应答）、Bearer（OAuth 令牌）、
自定义请求头四种方式，通过 OPDSAuth 统一承载。
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth, AuthBase

ACQUISITION = "http://opds-spec.org/acquisition"
USER_AGENT = "JpReader/1.0 (+OPDS)"

# 常见电子书 MIME（用于识别“可下载的书”）
BOOK_MIMES = (
    "application/epub+zip",
    "application/x-mobipocket-ebook",
    "application/x-mobi8-ebook",
    "application/x-mobipocket",
    "application/pdf",
    "application/x-cbz",
    "application/vnd.comicbook+zip",
    "application/octet-stream",
)

# MIME -> 建议扩展名（用于本地保存）
MIME_EXT = {
    "application/epub+zip": ".epub",
    "application/x-mobipocket-ebook": ".mobi",
    "application/x-mobi8-ebook": ".azw3",
    "application/x-mobipocket": ".mobi",
    "application/pdf": ".pdf",
    "application/x-cbz": ".cbz",
    "application/vnd.comicbook+zip": ".cbz",
    "application/octet-stream": "",
}


def _lname(tag: str) -> str:
    """取 XML 标签本地名（去掉 {namespace} 前缀）。"""
    return tag.rsplit("}", 1)[-1]


class AuthRequired(Exception):
    """服务器要求认证（401）。携带服务器声明的认证方式，便于弹出对应登录框。"""

    def __init__(self, message: str, scheme: str = "unknown", realm: str = ""):
        super().__init__(message)
        self.scheme = scheme      # basic / digest / bearer / unknown
        self.realm = realm        # 服务器提示的认证域，用于展示

    @property
    def needs_credentials(self) -> bool:
        """是否为“账号密码”型认证（Basic / Digest）。"""
        return self.scheme in ("basic", "digest")


def detect_auth_scheme(response) -> tuple:
    """从 401 响应的 WWW-Authenticate 头判断认证方式。

    返回 (scheme, realm)：scheme 为 basic / digest / bearer / unknown。
    """
    header = response.headers.get("WWW-Authenticate", "") or ""
    low = header.lower()
    realm = ""
    if "realm=" in low:
        # 形如 Basic realm="Calibre-Web"
        raw = header.split("realm=", 1)[1].strip()
        realm = raw.strip('"').split('"')[0].strip()
    if low.startswith("basic"):
        return "basic", realm
    if low.startswith("digest"):
        return "digest", realm
    if low.startswith("bearer"):
        return "bearer", realm
    return "unknown", realm


@dataclass
class OPDSAuth:
    """OPDS 书库认证配置。

    kind 取值：
      - "none"   ：无需认证（公开书库）
      - "basic"  ：HTTP Basic，用户名 + 密码
      - "digest" ：HTTP Digest，用户名 + 密码（requests 自动完成挑战应答）
      - "bearer" ：OAuth 2.0 / 令牌，直接放在 Authorization: Bearer <token>
      - "header" ：自定义请求头（部分自建服务用 X-Api-Key 之类）
    """

    kind: str = "none"
    username: str = ""
    password: str = ""
    token: str = ""
    header_name: str = ""
    header_value: str = ""

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "OPDSAuth":
        """从配置字典还原。密码类字段会做本地去混淆。"""
        data = data or {}
        try:
            from storage import deobfuscate
        except Exception:
            deobfuscate = lambda x: x  # noqa: E731
        return cls(
            kind=(data.get("kind") or "none").lower(),
            username=data.get("username", "") or "",
            password=deobfuscate(data.get("password", "") or ""),
            token=deobfuscate(data.get("token", "") or ""),
            header_name=data.get("header_name", "") or "",
            header_value=deobfuscate(data.get("header_value", "") or ""),
        )

    def to_dict(self) -> dict:
        """序列化为配置字典。密码类字段做本地混淆，避免明文落盘。"""
        try:
            from storage import obfuscate
        except Exception:
            obfuscate = lambda x: x  # noqa: E731
        return {
            "kind": self.kind,
            "username": self.username,
            "password": obfuscate(self.password),
            "token": obfuscate(self.token),
            "header_name": self.header_name,
            "header_value": obfuscate(self.header_value),
        }

    @property
    def has_credentials(self) -> bool:
        if self.kind in ("basic", "digest"):
            return bool(self.username)
        if self.kind == "bearer":
            return bool(self.token)
        if self.kind == "header":
            return bool(self.header_name)
        return False

    def describe(self) -> str:
        """人类可读的简短描述，用于书库下拉框。"""
        labels = {
            "none": "公开",
            "basic": f"Basic · {self.username}",
            "digest": f"Digest · {self.username}",
            "bearer": "Bearer 令牌",
            "header": f"Header · {self.header_name}",
        }
        return labels.get(self.kind, self.kind)

    def requests_auth(self) -> Optional[AuthBase]:
        """返回 requests 的 auth 对象（Basic / Digest），其余类型返回 None。"""
        if self.kind == "basic" and self.username:
            return HTTPBasicAuth(self.username, self.password)
        if self.kind == "digest" and self.username:
            return HTTPDigestAuth(self.username, self.password)
        return None

    def extra_headers(self) -> dict:
        """Bearer / 自定义请求头产生的附加头。"""
        if self.kind == "bearer" and self.token:
            return {"Authorization": f"Bearer {self.token}"}
        if self.kind == "header" and self.header_name:
            return {self.header_name: self.header_value}
        return {}

    def build_headers(self) -> dict:
        headers = {"User-Agent": USER_AGENT}
        headers.update(self.extra_headers())
        return headers


def _absurl(base: str, href: str) -> str:
    if not base:
        return href
    return urljoin(base, href)


def _text(el, name: str) -> str:
    for child in list(el):
        if _lname(child.tag) == name:
            return "".join(child.itertext()).strip()
    return ""


def _author(el) -> str:
    for child in list(el):
        if _lname(child.tag) == "author":
            return "".join(child.itertext()).strip()
    return ""


@dataclass
class OPDSLink:
    href: str = ""
    rel: str = ""
    type: str = ""
    title: str = ""
    length: str = ""


@dataclass
class OPDSItem:
    """feed 中的一项：子目录（kind='feed'）或可下载的书（kind='book'）。"""

    kind: str
    title: str
    summary: str = ""
    author: str = ""
    updated: str = ""
    links: List[OPDSLink] = field(default_factory=list)

    @property
    def is_feed(self) -> bool:
        return self.kind == "feed"

    def download_links(self) -> List[OPDSLink]:
        """所有可用于下载电子书的 acquisition 链接（open-access 优先）。"""
        out = [l for l in self.links
               if l.rel.startswith(ACQUISITION) and l.href]
        out.sort(key=lambda l: 0 if "open-access" in l.rel else 1)
        return out

    def open_link(self) -> Optional[OPDSLink]:
        """进入子目录所用的链接。"""
        for l in self.links:
            if l.href:
                return l
        return None

    def web_page_link(self) -> Optional[OPDSLink]:
        """适合在浏览器打开的网页链接（优先 alternate/related，排除下载链接）。"""
        for l in self.links:
            rel = l.rel
            if rel.startswith(ACQUISITION):
                continue
            if "text/html" in (l.type or "") or rel in ("alternate", "related"):
                return l
        return None


@dataclass
class OPDSFeed:
    title: str
    items: List[OPDSItem]
    url: str
    next_url: str = ""
    previous_url: str = ""


def _parse_feed_links(root, base_url: str) -> dict:
    out = {}
    for child in list(root):
        if _lname(child.tag) != "link":
            continue
        rel = child.get("rel", "")
        href = child.get("href", "")
        if not href or rel not in ("next", "previous"):
            continue
        out[rel] = _absurl(base_url, href)
    return out


def _parse_item(el, base_url: str) -> Optional[OPDSItem]:
    title = _text(el, "title") or "（无标题）"
    summary = _text(el, "summary")
    author = _author(el)
    updated = _text(el, "updated") or ""

    links = []
    for child in list(el):
        if _lname(child.tag) == "link":
            links.append(OPDSLink(
                href=_absurl(base_url, child.get("href", "")),
                rel=child.get("rel", ""),
                type=child.get("type", ""),
                title=child.get("title", ""),
            ))
    if not links:
        return None

    # 有 acquisition 链接 → 书
    if any(l.rel.startswith(ACQUISITION) and l.href for l in links):
        return OPDSItem(kind="book", title=title, summary=summary,
                        author=author, updated=updated, links=links)

    # 否则尝试识别为子目录（OPDS 1.x subsection / OPDS 2.x navigation）
    for l in links:
        if not l.href:
            continue
        if l.rel == "subsection":
            return OPDSItem(kind="feed", title=title, summary=summary,
                            author=author, updated=updated, links=links)
        if ("kind=navigation" in (l.type or "")
                or (l.rel in ("self", "alternate")
                    and "profile=opds-catalog" in (l.type or ""))):
            return OPDSItem(kind="feed", title=title, summary=summary,
                            author=author, updated=updated, links=links)
    return None


def parse_feed(data: bytes, base_url: str = "") -> OPDSFeed:
    root = ET.fromstring(data)
    title = _text(root, "title") or (base_url or "OPDS 书库")
    nav = _parse_feed_links(root, base_url)

    items = []
    for child in list(root):
        if _lname(child.tag) != "entry":
            continue
        item = _parse_item(child, base_url)
        if item:
            items.append(item)

    return OPDSFeed(
        title=title,
        items=items,
        url=base_url,
        next_url=nav.get("next", ""),
        previous_url=nav.get("previous", ""),
    )


def fetch_feed(url: str, timeout: int = 30,
               auth: Optional[OPDSAuth] = None) -> OPDSFeed:
    """GET 并解析一个 OPDS feed。

    401 时抛出 AuthRequired（携带服务器声明的认证方式），
    其余网络错误按 requests 异常抛出。
    """
    auth = auth or OPDSAuth()
    r = requests.get(url, headers=auth.build_headers(),
                     auth=auth.requests_auth(), timeout=timeout)
    if r.status_code == 401:
        scheme, realm = detect_auth_scheme(r)
        raise AuthRequired(
            f"书库需要登录（{scheme}）" + (f"，认证域：{realm}" if realm else ""),
            scheme=scheme, realm=realm,
        )
    r.raise_for_status()
    return parse_feed(r.content, url)


def download_file(url: str, dest_path: str | Path, timeout: int = 120,
                  chunk: int = 64 * 1024,
                  progress_cb: Optional[Callable[[int, int], None]] = None,
                  auth: Optional[OPDSAuth] = None) -> Path:
    """流式下载文件。progress_cb(done, total)；total 为 -1 表示未知长度。

    与 fetch_feed 共用同一套认证配置，避免浏览到下载二次登录。
    """
    auth = auth or OPDSAuth()
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=auth.build_headers(),
                      auth=auth.requests_auth(), timeout=timeout,
                      stream=True) as r:
        if r.status_code == 401:
            scheme, realm = detect_auth_scheme(r)
            raise AuthRequired(
                f"下载需要登录（{scheme}）" + (f"，认证域：{realm}" if realm else ""),
                scheme=scheme, realm=realm,
            )
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or -1)
        done = 0
        with open(dest_path, "wb") as f:
            for c in r.iter_content(chunk_size=chunk):
                if c:
                    f.write(c)
                    done += len(c)
                    if progress_cb:
                        progress_cb(done, total if total >= 0 else -1)
    return dest_path


def guess_extension(link: OPDSLink) -> str:
    """根据链接的 MIME 与 URL 推断本地文件扩展名；无法推断返回空字符串。"""
    mime = (link.type or "").lower()
    for m, ext in MIME_EXT.items():
        if mime.startswith(m):
            if ext:
                return ext
            break
    # 从 URL 后缀猜测
    path = (link.href or "").split("?", 1)[0]
    suffix = Path(path).suffix.lower()
    if suffix in (".epub", ".mobi", ".azw", ".azw3", ".pdf", ".cbz"):
        return suffix
    return ""
