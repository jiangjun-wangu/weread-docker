"""session.json / downloaded.json 读写"""
import json
import time
from pathlib import Path

from app.config import CONFIG_DIR, ensure_dirs


SESSION_PATH = CONFIG_DIR / "session.json"
DOWNLOADED_PATH = CONFIG_DIR / "downloaded.json"
RATE_PATH = CONFIG_DIR / "rate.json"
PROGRESS_DIR = CONFIG_DIR / "progress"
QUEUE_PATH = PROGRESS_DIR / "_queue.json"


def save_session(cookies: dict, uid: str = "") -> None:
    ensure_dirs()
    data = {
        "cookies": cookies,
        "uid": uid,
        "created_at": int(time.time()),
        "last_renewal": 0,
    }
    SESSION_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_session() -> dict:
    if not SESSION_PATH.exists():
        return {}
    try:
        return json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def clear_session() -> None:
    if SESSION_PATH.exists():
        SESSION_PATH.unlink()


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
    data = load_rate()
    data[month] = count
    ensure_dirs()
    RATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_rate() -> dict:
    if not RATE_PATH.exists():
        return {}
    try:
        return json.loads(RATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def bump_rate(count: int = 1) -> dict:
    ensure_dirs()
    data = load_rate()
    month = time.strftime("%Y-%m")
    data[month] = data.get(month, 0) + count
    RATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


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
