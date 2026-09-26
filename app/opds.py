"""OPDS 1.2 目录服务（Atom XML）

- 数据源：output/*.epub 文件 + book_meta（封面/简介）
- 端点由 api.py 挂载
- 无第三方依赖，手写 XML
"""
import time
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from app import config
from app import db

OPDS_TYPE = "application/atom+xml;profile=opds-catalog;kind=acquisition"
NAV_TYPE = "application/atom+xml;profile=opds-catalog;kind=navigation"
ACQUISITION_REL = "http://opds-spec.org/acquisition"
IMAGE_REL = "http://opds-spec.org/image"


def _iso(ts):
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts)))
    except Exception:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _meta_for(title, author):
    """按书名/作者在 book_meta 里找封面+简介"""
    try:
        r = db.query_one(
            "SELECT book_id, cover_url, intro FROM book_meta "
            "WHERE title=? OR title LIKE ? LIMIT 1",
            (title, title + "%"),
        )
        if r:
            return dict(r)
    except Exception:
        pass
    return {}


def _book_entry(base, f):
    stat = f.stat()
    stem = f.stem
    if " - " in stem:
        title, author = stem.split(" - ", 1)
    else:
        title, author = stem, ""
    meta = _meta_for(title, author)
    updated = _iso(stat.st_mtime)
    dl_url = base + "/opds/download/" + quote(f.name)
    entry = [
        "  <entry>",
        "    <title>" + escape(title) + "</title>",
        "    <id>urn:weread:epub:" + escape(f.name) + "</id>",
        "    <updated>" + updated + "</updated>",
    ]
    if author:
        entry.append("    <author><name>" + escape(author) + "</name></author>")
    intro = (meta.get("intro") or "").strip()
    if intro:
        entry.append('    <content type="text">' + escape(intro[:500]) + "</content>")
    cover = (meta.get("cover_url") or "").strip()
    if cover:
        entry.append('    <link rel="%s" href="%s" type="image/jpeg"/>' % (IMAGE_REL, escape(cover)))
    entry.append(
        '    <link rel="%s" href="%s" type="application/epub+zip"/>'
        % (ACQUISITION_REL, escape(dl_url))
    )
    entry.append("  </entry>")
    return "\n".join(entry)


def _feed(base, feed_id, title, self_path, kind, entries, total=None):
    now = _iso(time.time())
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:dc="http://purl.org/dc/terms/" '
        'xmlns:opds="http://opds-spec.org/2010/catalog">',
        "  <id>" + escape(feed_id) + "</id>",
        "  <title>" + escape(title) + "</title>",
        "  <updated>" + now + "</updated>",
        "  <author><name>weread-docker</name></author>",
        '  <link rel="self" href="%s" type="%s"/>' % (escape(base + self_path), kind),
        '  <link rel="start" href="%s" type="%s"/>' % (escape(base + "/opds"), NAV_TYPE),
    ]
    if total is not None:
        lines.append("  <dc:totalResults>%d</dc:totalResults>" % total)
    lines.extend(entries)
    lines.append("</feed>")
    return "\n".join(lines)


def _list_files():
    out = Path(config.OUTPUT_DIR)
    if not out.exists():
        return []
    return sorted(out.glob("*.epub"), key=lambda f: f.stat().st_mtime, reverse=True)


def root_feed(base):
    entries = [
        '  <entry>',
        "    <title>全部书籍</title>",
        "    <id>urn:weread:opds:all</id>",
        "    <updated>" + _iso(time.time()) + "</updated>",
        '    <content type="text">下载目录里的全部 EPUB</content>',
        '    <link rel="subsection" href="%s" type="%s"/>' % (escape(base + "/opds/all"), OPDS_TYPE),
        "  </entry>",
        '  <entry>',
        "    <title>搜索</title>",
        "    <id>urn:weread:opds:search</id>",
        "    <updated>" + _iso(time.time()) + "</updated>",
        '    <link rel="search" href="%s" type="application/atom+xml"/>'
        % escape(base + "/opds/search"),
        "  </entry>",
    ]
    return _feed(base, "urn:weread:opds:root", "微信读书下载器", "/opds", NAV_TYPE, entries)


def all_feed(base):
    files = _list_files()
    entries = [_book_entry(base, f) for f in files]
    return _feed(base, "urn:weread:opds:all", "全部书籍", "/opds/all",
                 OPDS_TYPE, entries, total=len(files))


def search_feed(base, q):
    q = (q or "").strip().lower()
    files = _list_files()
    if q:
        files = [f for f in files if q in f.stem.lower()]
    entries = [_book_entry(base, f) for f in files]
    title = "搜索：" + q if q else "搜索"
    return _feed(base, "urn:weread:opds:search", title,
                 "/opds/search?q=" + quote(q), OPDS_TYPE, entries, total=len(files))


def find_download(name):
    """按文件名找 epub，返回 Path 或 None（防目录穿越）"""
    safe = Path(name).name
    if not safe.endswith(".epub"):
        return None
    p = Path(config.OUTPUT_DIR) / safe
    if p.exists() and p.is_file():
        return p
    return None
