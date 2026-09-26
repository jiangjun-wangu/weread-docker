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
    # settings
    try:
        if not db.query("SELECT key FROM settings") and SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            for k, v in (data or {}).items():
                db.execute("INSERT INTO settings(key, value) VALUES(?, ?)",
                           (k, json.dumps(v, ensure_ascii=False)))
    except Exception:
        pass


def load_downloaded() -> dict:
    if not DOWNLOADED_PATH.exists():
        return {}
    try:
        return json.loads(DOWNLOADED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def mark_downloaded(book_id: str, title: str, chapters: int) -> None:
    ensure_dirs()
    data = load_downloaded()
    data[book_id] = {
        "title": title,
        "chapters": chapters,
        "finished_at": int(time.time()),
    }
    DOWNLOADED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
    _ensure_progress_dir()
    QUEUE_PATH.write_text(json.dumps(book_ids, ensure_ascii=False), encoding="utf-8")


def load_queue() -> list:
    if not QUEUE_PATH.exists():
        return []
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8")) or []
    except Exception:
        return []


def clear_queue() -> None:
    if QUEUE_PATH.exists():
        QUEUE_PATH.unlink()


def save_progress_meta(book_id: str, data: dict) -> None:
    data = dict(data)
    data["updated_at"] = int(time.time())
    _meta_path(book_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_progress_meta(book_id: str) -> dict:
    p = _meta_path(book_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def clear_progress(book_id: str) -> None:
    p = _meta_path(book_id)
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def list_progress() -> list:
    _ensure_progress_dir()
    out = []
    for p in PROGRESS_DIR.glob("*.meta.json"):
        bid = p.name[:-len(".meta.json")]
        meta = load_progress_meta(bid)
        if meta:
            out.append({"bookId": bid, **meta})
    return out
