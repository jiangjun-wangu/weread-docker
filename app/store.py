"""session.json / downloaded.json 读写"""
import json
import time
from pathlib import Path

from app.config import CONFIG_DIR, ensure_dirs, SETTINGS_PATH


SESSION_PATH = CONFIG_DIR / "session.json"
DOWNLOADED_PATH = CONFIG_DIR / "downloaded.json"
RATE_PATH = CONFIG_DIR / "rate.json"
PROGRESS_DIR = CONFIG_DIR / "progress"
QUEUE_PATH = PROGRESS_DIR / "_queue.json"


def save_session(cookies: dict, uid: str = "") -> None:
    from app import db
    now = int(time.time())
    db.execute(
        "INSERT INTO session(id, cookies_json, uid, created_at, last_renewal) "
        "VALUES(1, ?, ?, ?, 0) "
        "ON CONFLICT(id) DO UPDATE SET cookies_json=excluded.cookies_json, "
        "uid=excluded.uid, created_at=excluded.created_at",
        (json.dumps(cookies, ensure_ascii=False), uid, now),
    )


def load_session() -> dict:
    from app import db
    try:
        r = db.query_one("SELECT cookies_json, uid, created_at, last_renewal FROM session WHERE id=1")
        if r:
            return {
                "cookies": json.loads(r["cookies_json"] or "{}"),
                "uid": r["uid"] or "",
                "created_at": r["created_at"] or 0,
                "last_renewal": r["last_renewal"] or 0,
            }
    except Exception:
        pass
    # 回退：旧 JSON
    if SESSION_PATH.exists():
        try:
            return json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def clear_session() -> None:
    from app import db
    try:
        db.execute("DELETE FROM session WHERE id=1")
    except Exception:
        pass
    if SESSION_PATH.exists():
        SESSION_PATH.unlink()


def migrate_from_json() -> None:
    """一次性把旧 JSON 数据导入 DB（幂等：DB 已有数据则跳过）"""
    from app import db
    # session
    try:
        if not db.query_one("SELECT id FROM session WHERE id=1") and SESSION_PATH.exists():
            data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
            if data.get("cookies"):
                save_session(data.get("cookies", {}), data.get("uid", ""))
    except Exception:
        pass
    # rate
    try:
        if not db.query("SELECT month FROM rate") and RATE_PATH.exists():
            data = json.loads(RATE_PATH.read_text(encoding="utf-8"))
            for m, c in (data or {}).items():
                db.execute("INSERT INTO rate(month, count) VALUES(?, ?)", (m, int(c)))
    except Exception:
        pass
    # settings（逐条补齐：DB 缺的 key 才补，不覆盖已有）
    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            for k, v in (data or {}).items():
                if not db.query_one("SELECT key FROM settings WHERE key=?", (k,)):
                    db.execute("INSERT INTO settings(key, value) VALUES(?, ?)",
                               (k, json.dumps(v, ensure_ascii=False)))
    except Exception:
        pass
    # downloaded
    try:
        if not db.query("SELECT book_id FROM downloaded") and DOWNLOADED_PATH.exists():
            data = json.loads(DOWNLOADED_PATH.read_text(encoding="utf-8"))
            for bid, v in (data or {}).items():
                db.execute(
                    "INSERT INTO downloaded(book_id, title, chapters, finished_at, deleted) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (bid, v.get("title", ""), int(v.get("chapters", 0)),
                     int(v.get("finished_at", 0)), 1 if v.get("deleted") else 0),
                )
    except Exception:
        pass
    # queue
    try:
        if not db.query("SELECT book_id FROM queue") and QUEUE_PATH.exists():
            ids = json.loads(QUEUE_PATH.read_text(encoding="utf-8")) or []
            now = int(time.time())
            for i, bid in enumerate(ids):
                db.execute("INSERT INTO queue(book_id, position, added_at) VALUES(?, ?, ?)",
                           (bid, i, now))
    except Exception:
        pass
    # progress
    try:
        if not db.query("SELECT book_id FROM progress") and PROGRESS_DIR.exists():
            for f in PROGRESS_DIR.glob("*.meta.json"):
                bid = f.name[:-len(".meta.json")]
                try:
                    v = json.loads(f.read_text(encoding="utf-8"))
                    db.execute(
                        "INSERT INTO progress(book_id, title, total_ch, done_ch, updated_at) "
                        "VALUES(?, ?, ?, ?, ?)",
                        (bid, v.get("title", ""), int(v.get("total_ch", 0)),
                         int(v.get("done_ch", 0)), int(v.get("updated_at", 0))),
                    )
                except Exception:
                    continue
    except Exception:
        pass


SHELF_COLUMNS = [
    ("bookId", "book_id"), ("title", "title"), ("author", "author"),
    ("cover", "cover"), ("category", "category"), ("publishTime", "publish_time"),
    ("updateTime", "update_time"), ("readUpdateTime", "read_update_time"),
    ("centPrice", "cent_price"), ("lastChapterIdx", "last_chapter_idx"),
    ("finished", "finished"), ("finishReading", "finish_reading"),
    ("readingTime", "reading_time"), ("progress", "progress"),
    ("chapterIdx", "chapter_idx"), ("hasProgress", "has_progress"),
]


def save_shelf(books: list) -> None:
    """全量覆盖书架快照"""
    from app import db
    now = int(time.time())
    db.execute("DELETE FROM shelf")
    if not books:
        return
    rows = []
    for i, b in enumerate(books):
        rows.append((
            b.get("bookId", ""), b.get("title", ""), b.get("author", ""),
            b.get("cover", ""), b.get("category", ""), b.get("publishTime", ""),
            int(b.get("updateTime", 0) or 0), int(b.get("readUpdateTime", 0) or 0),
            int(b.get("centPrice", 0) or 0), int(b.get("lastChapterIdx", 0) or 0),
            1 if b.get("finished") else 0, 1 if b.get("finishReading") else 0,
            int(b.get("readingTime", 0) or 0), int(b.get("progress", 0) or 0),
            int(b.get("chapterIdx", 0) or 0), 1 if b.get("hasProgress") else 0,
            i, now,
        ))
    db.executemany(
        "INSERT INTO shelf(book_id, title, author, cover, category, publish_time, "
        "update_time, read_update_time, cent_price, last_chapter_idx, finished, "
        "finish_reading, reading_time, progress, chapter_idx, has_progress, position, cached_at) "
        "VALUES(" + ",".join(["?"] * 18) + ")",
        rows,
    )


def load_shelf() -> list:
    """按 position 读书架快照"""
    from app import db
    try:
        rows = db.query("SELECT * FROM shelf ORDER BY position")
    except Exception:
        return []
    out = []
    for r in rows:
        out.append({
            "bookId": r["book_id"], "title": r["title"], "author": r["author"],
            "cover": r["cover"], "category": r["category"],
            "publishTime": r["publish_time"], "updateTime": r["update_time"],
            "readUpdateTime": r["read_update_time"], "centPrice": r["cent_price"],
            "lastChapterIdx": r["last_chapter_idx"],
            "finished": r["finished"], "finishReading": r["finish_reading"],
            "readingTime": r["reading_time"], "progress": r["progress"],
            "chapterIdx": r["chapter_idx"], "hasProgress": r["has_progress"],
        })
    return out


def shelf_cached_at() -> int:
    """书架快照时间戳（0=无缓存）"""
    from app import db
    try:
        r = db.query_one("SELECT MAX(cached_at) AS ts FROM shelf")
        return int(r["ts"] or 0) if r else 0
    except Exception:
        return 0


def clear_shelf() -> None:
    from app import db
    try:
        db.execute("DELETE FROM shelf")
    except Exception:
        pass


def save_book_meta(data: dict) -> None:
    """保存书籍元数据（按 book_id upsert；封面存 URL，BLOB 留空）"""
    from app import db
    now = int(time.time())
    db.execute(
        "INSERT INTO book_meta(book_id, title, author, cover_url, cover_data, cover_mime, "
        "intro, rating, category, source, created_at, updated_at) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(book_id) DO UPDATE SET title=excluded.title, author=excluded.author, "
        "cover_url=excluded.cover_url, intro=excluded.intro, rating=excluded.rating, "
        "category=excluded.category, updated_at=excluded.updated_at",
        (
            data.get("bookId") or data.get("book_id", ""),
            data.get("title", ""),
            data.get("author", ""),
            data.get("cover", "") or data.get("cover_url", ""),
            data.get("cover_data"),
            data.get("cover_mime", ""),
            data.get("intro", ""),
            int(data.get("rating", 0)),
            data.get("category", ""),
            data.get("source", "wx"),
            now, now,
        ),
    )


def get_book_meta(book_id: str) -> dict:
    """按 bookId 取元数据（返回前端友好字段名）"""
    from app import db
    try:
        r = db.query_one("SELECT * FROM book_meta WHERE book_id=?", (book_id,))
    except Exception:
        return {}
    if not r:
        return {}
    return {
        "bookId": r["book_id"],
        "title": r["title"],
        "author": r["author"],
        "cover": r["cover_url"],
        "intro": r["intro"],
        "rating": r["rating"],
        "category": r["category"],
        "source": r["source"],
        "updated_at": r["updated_at"],
    }


def load_downloaded() -> dict:
    from app import db
    try:
        rows = db.query("SELECT book_id, title, chapters, finished_at, deleted FROM downloaded")
        if rows:
            return {
                r["book_id"]: {
                    "title": r["title"],
                    "chapters": r["chapters"],
                    "finished_at": r["finished_at"],
                    "deleted": r["deleted"],
                }
                for r in rows
            }
    except Exception:
        pass
    # 回退：旧 JSON
    if DOWNLOADED_PATH.exists():
        try:
            return json.loads(DOWNLOADED_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def mark_downloaded(book_id: str, title: str, chapters: int) -> None:
    from app import db
    db.execute(
        "INSERT INTO downloaded(book_id, title, chapters, finished_at, deleted) "
        "VALUES(?, ?, ?, ?, 0) "
        "ON CONFLICT(book_id) DO UPDATE SET title=excluded.title, "
        "chapters=excluded.chapters, finished_at=excluded.finished_at, deleted=0",
        (book_id, title, chapters, int(time.time())),
    )


def mark_deleted(book_id: str) -> None:
    """软删：标记 deleted=1，保留文件"""
    from app import db
    db.execute("UPDATE downloaded SET deleted=1 WHERE book_id=?", (book_id,))


def remove_downloaded(book_id: str) -> None:
    """硬删：从 downloaded 表移除记录"""
    from app import db
    db.execute("DELETE FROM downloaded WHERE book_id=?", (book_id,))


def recount_rate_from_downloaded() -> dict:
    """按 downloaded.json 的 finished_at 重算本月计数（覆盖，幂等）"""
    downloaded = load_downloaded()
    month = time.strftime("%Y-%m")
    count = 0
    for v in downloaded.values():
        ts = v.get("finished_at", 0)
        if not ts:
            continue
        if time.strftime("%Y-%m", time.localtime(ts)) == month:
            count += 1
    from app import db
    db.execute(
        "INSERT INTO rate(month, count) VALUES(?, ?) "
        "ON CONFLICT(month) DO UPDATE SET count=excluded.count",
        (month, count),
    )
    return load_rate()


def load_rate() -> dict:
    from app import db
    try:
        rows = db.query("SELECT month, count FROM rate")
        if rows:
            return {r["month"]: r["count"] for r in rows}
    except Exception:
        pass
    # 回退：旧 JSON
    if RATE_PATH.exists():
        try:
            return json.loads(RATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def bump_rate(count: int = 1) -> dict:
    from app import db
    month = time.strftime("%Y-%m")
    db.execute(
        "INSERT INTO rate(month, count) VALUES(?, ?) "
        "ON CONFLICT(month) DO UPDATE SET count = count + ?",
        (month, count, count),
    )
    return load_rate()


# ---------- 下载进度（仅记录状态，不存章节） ----------

def _ensure_progress_dir() -> Path:
    ensure_dirs()
    PROGRESS_DIR.mkdir(exist_ok=True)
    return PROGRESS_DIR


def _meta_path(book_id: str) -> Path:
    return _ensure_progress_dir() / (book_id + ".meta.json")


def save_queue(book_ids: list) -> None:
    from app import db
    db.execute("DELETE FROM queue")
    if book_ids:
        now = int(time.time())
        db.executemany(
            "INSERT INTO queue(book_id, position, added_at) VALUES(?, ?, ?)",
            [(bid, i, now) for i, bid in enumerate(book_ids)],
        )


def load_queue() -> list:
    from app import db
    try:
        rows = db.query("SELECT book_id FROM queue ORDER BY position")
        if rows:
            return [r["book_id"] for r in rows]
    except Exception:
        pass
    # 回退：旧 JSON
    if QUEUE_PATH.exists():
        try:
            return json.loads(QUEUE_PATH.read_text(encoding="utf-8")) or []
        except Exception:
            pass
    return []


def clear_queue() -> None:
    from app import db
    try:
        db.execute("DELETE FROM queue")
    except Exception:
        pass
    if QUEUE_PATH.exists():
        QUEUE_PATH.unlink()


def save_progress_meta(book_id: str, data: dict) -> None:
    from app import db
    data = dict(data)
    db.execute(
        "INSERT INTO progress(book_id, title, total_ch, done_ch, updated_at) "
        "VALUES(?, ?, ?, ?, ?) "
        "ON CONFLICT(book_id) DO UPDATE SET title=excluded.title, "
        "total_ch=excluded.total_ch, done_ch=excluded.done_ch, updated_at=excluded.updated_at",
        (book_id, data.get("title", ""), int(data.get("total_ch", 0)),
         int(data.get("done_ch", 0)), int(time.time())),
    )


def load_progress_meta(book_id: str) -> dict:
    from app import db
    try:
        r = db.query_one(
            "SELECT title, total_ch, done_ch, updated_at FROM progress WHERE book_id=?",
            (book_id,),
        )
        if r:
            return {"title": r["title"], "total_ch": r["total_ch"],
                    "done_ch": r["done_ch"], "updated_at": r["updated_at"]}
    except Exception:
        pass
    # 回退：旧 JSON
    p = _meta_path(book_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def clear_progress(book_id: str) -> None:
    from app import db
    try:
        db.execute("DELETE FROM progress WHERE book_id=?", (book_id,))
    except Exception:
        pass
    p = _meta_path(book_id)
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def list_progress() -> list:
    from app import db
    try:
        rows = db.query("SELECT book_id, title, total_ch, done_ch, updated_at FROM progress")
        if rows:
            return [
                {"bookId": r["book_id"], "title": r["title"], "total_ch": r["total_ch"],
                 "done_ch": r["done_ch"], "updated_at": r["updated_at"]}
                for r in rows
            ]
    except Exception:
        pass
    # 回退：旧 JSON
    _ensure_progress_dir()
    out = []
    for p in PROGRESS_DIR.glob("*.meta.json"):
        bid = p.name[:-len(".meta.json")]
        meta = load_progress_meta(bid)
        if meta:
            out.append({"bookId": bid, **meta})
    return out
