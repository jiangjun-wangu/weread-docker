"""FastAPI 接口 + Web UI"""
import asyncio
import base64
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app import auth as auth_mod
from app import client as client_mod
from app import config
from app import store
from app import sorter
from app import auto_sync
from app import logger as log_mod
from app.downloader import Downloader

log_mod.install(logging.INFO)
log = logging.getLogger("api")

@asynccontextmanager
async def lifespan(app):
    sch = auto_sync.init_scheduler(
        _auto_sync_tick, _auto_sync_interval_hours, _auto_sync_is_enabled
    )
    sch.start()
    log.info(
        "自动同步调度器已启动（enabled=%s, interval=%sh）",
        _auto_sync_is_enabled(), _auto_sync_interval_hours(),
    )
    try:
        saved_q = store.load_queue()
        if saved_q:
            metas = {m.get("bookId"): m for m in store.list_progress()}
            _download_state["queue"] = [
                {
                    "bookId": bid,
                    "title": (metas.get(bid) or {}).get("title", bid),
                    "status": "pending",
                    "pct": 0,
                }
                for bid in saved_q
            ]
            _download_state["has_restore"] = True
            log.info("检测到未完成队列：%d 本（可恢复）", len(saved_q))
        else:
            _download_state["has_restore"] = False
    except Exception:
        log.exception("恢复队列失败")
    yield


app = FastAPI(title="weread-downloader", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------- 全局状态 ----------
_state_lock = threading.Lock()
_auth = None
_cli = None
_login_session = {"uid": "", "qr": "", "confirmed": False}

_pause_event = threading.Event()
_pause_event.set()
_cancel_ids = set()

_download_state = {
    "running": False,
    "paused": False,
    "current": "",
    "current_id": "",
    "queue": [],
    "done": 0,
    "total": 0,
    "chapter_done": 0,
    "chapter_total": 0,
    "log": [],
    "results": {"ok": 0, "skipped": 0, "failed": 0, "empty": 0},
    "started_at": 0,
    "has_restore": False,
}

_shelf_cache = {"data": None, "ts": 0}


def _check_rate_limit():
    """本月下载数达上限时抛 429"""
    month = time.strftime("%Y-%m")
    used = store.load_rate().get(month, 0)
    limit = config.load_settings().get("max_per_month", 100)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail="本月已达下载上限 %d 本，请下月再试或调高上限" % limit,
        )
SHELF_TTL = 30


def _get_shelf_cached(cli):
    now = time.time()
    if _shelf_cache["data"] is not None and now - _shelf_cache["ts"] < SHELF_TTL:
        return _shelf_cache["data"]
    books = cli.shelf()
    _shelf_cache["data"] = books
    _shelf_cache["ts"] = now
    return books


def _clear_shelf_cache():
    _shelf_cache["data"] = None
    _shelf_cache["ts"] = 0


def _get_client():
    global _auth, _cli
    if _cli is None:
        _auth = auth_mod.WeReadAuth()
        if not _auth.load():
            return None, None
        _cli = client_mod.WeReadClient(_auth)
    return _auth, _cli


def _clear_caches():
    """清所有内存缓存（登录/登出/换账号时调用）"""
    global _shelf_cache, _user_cache, _intro_cache, _match_cache
    try:
        _shelf_cache["data"] = None
        _shelf_cache["ts"] = 0
    except Exception:
        pass
    try:
        _user_cache["data"] = None
        _user_cache["ts"] = 0
    except Exception:
        pass
    try:
        _intro_cache.clear()
    except Exception:
        pass
    try:
        _match_cache.clear()
    except Exception:
        pass


def _reset_client():
    global _auth, _cli
    if _auth:
        try:
            _auth.close()
        except Exception:
            pass
    _auth = None
    _cli = None
    _clear_caches()


# ---------- 页面 ----------
@app.get("/", response_class=HTMLResponse)
async def index():
    f = STATIC_DIR / "index.html"
    if not f.exists():
        return HTMLResponse("<h1>index.html 不存在</h1>", status_code=500)
    return HTMLResponse(f.read_text(encoding="utf-8"))


# ---------- 状态 ----------
@app.get("/api/status")
async def api_status():
    sess = store.load_session()
    rate = store.load_rate()
    month = time.strftime("%Y-%m")
    settings = config.load_settings()
    return {
        "logged_in": bool(sess.get("cookies")),
        "uid": sess.get("uid", ""),
        "month": month,
        "used": rate.get(month, 0),
        "limit": settings.get("max_per_month", 100),
        "download": dict(_download_state),
        "has_restore": _download_state.get("has_restore", False),
        "restore_count": len(_download_state.get("queue", [])),
    }


# ---------- 登录 ----------
@app.post("/api/login/start")
async def api_login_start():
    global _login_session
    _reset_client()
    a = auth_mod.WeReadAuth()
    try:
        uid = a.fetch_uid()
        qr_url = a.qr_url()
        png = a.qr_png_bytes()
        b64 = base64.b64encode(png).decode()
    except Exception as e:
        a.close()
        raise HTTPException(status_code=500, detail=str(e))
    _login_session = {"uid": uid, "qr": b64, "confirmed": False}
    # 后台轮询
    threading.Thread(target=_login_poll_worker, args=(a,), daemon=True).start()
    return {"uid": uid, "qr": b64}


def _login_poll_worker(a):
    global _login_session
    try:
        ok = a.wait_for_login(timeout=180)
        if ok:
            a.save()
            _login_session["confirmed"] = True
            _reset_client()
            log.info("登录成功 uid=%s", a.uid)
        else:
            log.warning("登录超时或失败")
    except Exception as e:
        log.exception("登录轮询出错: %s", e)
    finally:
        try:
            a.close()
        except Exception:
            pass


@app.get("/api/login/poll")
async def api_login_poll():
    return {"confirmed": _login_session.get("confirmed", False)}


@app.post("/api/logout")
async def api_logout():
    store.clear_session()
    _reset_client()
    return {"ok": True}


# ---------- 用户信息 ----------
_user_cache = {"data": None, "ts": 0}


@app.get("/api/user")
async def api_user():
    a, cli = _get_client()
    if not cli:
        raise HTTPException(status_code=401, detail="未登录")

    now = int(time.time())
    if _user_cache["data"] and now - _user_cache["ts"] < 300:
        return _user_cache["data"]

    sess = store.load_session()
    vid = (sess.get("cookies", {}) or {}).get("wr_vid", "")
    if not vid:
        raise HTTPException(status_code=500, detail="session 缺少 wr_vid")

    try:
        r = a.client.get("/web/user", params={"userVid": vid})
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail="获取用户信息失败: %d" % r.status_code)
        u = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        books = cli.shelf()
    except client_mod.SessionExpired:
        store.clear_session()
        _reset_client()
        raise HTTPException(status_code=401, detail="session 过期")
    except Exception:
        books = []

    total_books = len(books)
    reading_count = sum(1 for b in books if b.get("hasProgress") and not b.get("finishReading"))
    finished_count = sum(1 for b in books if b.get("finishReading"))
    total_seconds = sum(b.get("readingTime", 0) for b in books)
    latest = sorted(books, key=lambda b: b.get("readUpdateTime", 0), reverse=True)[:5]

    result = {
        "userVid": u.get("userVid", vid),
        "name": u.get("name", ""),
        "nick": u.get("nick", ""),
        "avatar": u.get("avatar", ""),
        "signature": u.get("signature", ""),
        "stats": {
            "total_books": total_books,
            "reading_count": reading_count,
            "finished_count": finished_count,
            "total_seconds": total_seconds,
        },
        "recent": [
            {
                "bookId": b.get("bookId", ""),
                "title": b.get("title", ""),
                "author": b.get("author", ""),
                "cover": b.get("cover", ""),
                "readingTime": b.get("readingTime", 0),
                "progress": b.get("progress", 0),
                "readUpdateTime": b.get("readUpdateTime", 0),
            }
            for b in latest
        ],
    }
    _user_cache["data"] = result
    _user_cache["ts"] = now
    return result


# ---------- 书架 ----------
@app.get("/api/shelf")
async def api_shelf(sort: str = "recent", order: str = "desc", filter: str = "all", q: str = "", page: int = 1, page_size: int = 30, nocache: int = 0):
    a, cli = _get_client()
    if not cli:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        if nocache:
            _clear_shelf_cache()
        books = _get_shelf_cached(cli)
    except client_mod.SessionExpired:
        store.clear_session()
        _reset_client()
        raise HTTPException(status_code=401, detail="session 过期")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    downloaded = store.load_downloaded()
    out_dir = Path(config.OUTPUT_DIR)
    files = []
    if out_dir.exists():
        files = [f.name for f in out_dir.glob("*.epub")]
    for b in books:
        bid = b["bookId"]
        b["downloaded"] = bid in downloaded
        title_key = b.get("title", "")[:20]
        b["has_file"] = any(f.startswith(title_key) for f in files)

    books = sorter.filter_books(books, filter)
    books = sorter.search_books(books, q)
    books = sorter.sort_books(books, sort, order)

    total = len(books)
    page_size = max(1, min(page_size, 200))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "books": books[start:end],
        "count": len(books[start:end]),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }

def _set_queue(book_id, status=None, pct=None):
    for q in _download_state["queue"]:
        if q.get("bookId") == book_id:
            if status is not None:
                q["status"] = status
            if pct is not None:
                q["pct"] = pct
            return


def _download_worker(book_ids):
    global _download_state
    try:
        a, cli = _get_client()
        if not cli:
            _download_state["running"] = False
            return
        books = cli.shelf()
        targets = [b for b in books if b["bookId"] in book_ids]
        _download_state["total"] = len(targets)
        _download_state["done"] = 0
        _download_state["chapter_done"] = 0
        _download_state["chapter_total"] = 0
        _download_state["started_at"] = int(time.time())
        _download_state["results"] = {"ok": 0, "skipped": 0, "failed": 0, "empty": 0}
        _download_state["queue"] = [
            {"bookId": b["bookId"], "title": b.get("title", b["bookId"]),
             "status": "pending", "pct": 0}
            for b in targets
        ]
        _cancel_ids.clear()
        _pause_event.set()
        _download_state["paused"] = False
        _download_state["has_restore"] = False
        store.save_queue([b["bookId"] for b in targets])

        d = Downloader(cli, interval=config.DOWNLOAD_INTERVAL)

        for i, book in enumerate(targets):
            _pause_event.wait()
            _cur_bid = book.get("bookId", "")
            if _cur_bid in _cancel_ids:
                _set_queue(_cur_bid, status="cancelled")
                continue
            title = book.get("title", book["bookId"])
            _bid = book.get("bookId", "")
            _download_state["current"] = title
            _download_state["current_id"] = _bid
            _download_state["chapter_done"] = 0
            _download_state["chapter_total"] = 0
            _set_queue(_bid, status="downloading", pct=0)

            def on_progress(done_ch, total_ch, _b=_bid):
                _pause_event.wait()
                if _b in _cancel_ids:
                    raise KeyboardInterrupt("cancelled")
                _download_state["chapter_done"] = done_ch
                _download_state["chapter_total"] = total_ch
                _qpct = round(done_ch * 100 / total_ch) if total_ch > 0 else 0
                _set_queue(_b, pct=_qpct)

            try:
                r = d.download_book(book, on_progress=on_progress)
                _download_state["results"][r] += 1
                if r == "ok":
                    store.bump_rate()
                    log.info("本月计数 +1")
                _set_queue(_bid, status="done" if r in ("ok", "skipped") else "failed",
                           pct=100 if r in ("ok", "skipped") else None)
                log.info("[%d/%d] %s: %s", i + 1, len(targets), title, r)
            except KeyboardInterrupt:
                _set_queue(_bid, status="cancelled")
                log.info("下载被用户取消")
            except client_mod.SessionExpired:
                log.error("session 过期，中止")
                _reset_client()
                break
            except Exception as e:
                _download_state["results"]["failed"] += 1
                _set_queue(_bid, status="failed")
                log.exception("下载失败 %s: %s", title, e)
            _download_state["done"] = i + 1
    finally:
        _clear_shelf_cache()
        _download_state["running"] = False
        _download_state["paused"] = False
        _download_state["current"] = ""
        _download_state["current_id"] = ""
        _pause_event.set()
        _cancel_ids.clear()
        try:
            remaining = [
                q["bookId"] for q in _download_state.get("queue", [])
                if q.get("status") in ("pending", "downloading", "failed")
            ]
            if remaining:
                store.save_queue(remaining)
                log.info("保留未完成队列：%d 本", len(remaining))
            else:
                store.clear_queue()
        except Exception:
            log.exception("保存未完成队列失败")




def _auto_sync_tick():
    """一次自动同步：拉书架 → 过滤已下载 → 无任务则启动下载线程"""
    with _state_lock:
        if _download_state["running"]:
            log.info("自动同步：已有下载任务，跳过")
            return {"queued": 0, "reason": "busy"}
    a, cli = _get_client()
    if not cli:
        log.info("自动同步：未登录，跳过")
        return {"queued": 0, "reason": "not_logged_in"}
    try:
        books = cli.shelf()
    except client_mod.SessionExpired:
        log.warning("自动同步：session 过期")
        _reset_client()
        return {"queued": 0, "reason": "session_expired"}
    except Exception as e:
        log.exception("自动同步：拉书架失败 %s", e)
        return {"queued": 0, "reason": "shelf_error"}
    downloaded = store.load_downloaded()
    new_ids = [b["bookId"] for b in books
               if b.get("bookId") and b["bookId"] not in downloaded]
    if not new_ids:
        log.info("自动同步：没有新书")
        return {"queued": 0, "reason": "no_new"}
    month = time.strftime("%Y-%m")
    used = store.load_rate().get(month, 0)
    limit = config.load_settings().get("max_per_month", 100)
    if used >= limit:
        log.info("自动同步：本月已达上限 %d", limit)
        return {"queued": 0, "reason": "rate_limit"}
    with _state_lock:
        if _download_state["running"]:
            return {"queued": 0, "reason": "busy"}
        _download_state["running"] = True
        _download_state["log"] = []
    log.info("自动同步：发现 %d 本新书，开始下载", len(new_ids))
    threading.Thread(target=_download_worker, args=(new_ids,), daemon=True).start()
    return {"queued": len(new_ids), "book_ids": new_ids}


def _auto_sync_interval_hours():
    s = config.load_settings()
    return float(s.get("auto_sync_interval_hours", 6))


def _auto_sync_is_enabled():
    s = config.load_settings()
    return bool(s.get("auto_sync_enabled", False))


@app.post("/api/sync/now")
async def api_sync_now():
    return _auto_sync_tick()


@app.post("/api/download")
async def api_download(req: Request):
    body = await req.json()
    book_ids = body.get("book_ids", [])
    if not book_ids:
        raise HTTPException(status_code=400, detail="book_ids 为空")
    _check_rate_limit()
    with _state_lock:
        if _download_state["running"]:
            raise HTTPException(status_code=409, detail="已有下载任务进行中")
        _download_state["running"] = True
        _download_state["log"] = []
    threading.Thread(target=_download_worker, args=(book_ids,), daemon=True).start()
    return {"ok": True}


@app.post("/api/download/pause")
async def api_download_pause():
    _pause_event.clear()
    _download_state["paused"] = True
    log.info("下载已暂停")
    return {"ok": True}


@app.post("/api/download/resume")
async def api_download_resume():
    _pause_event.set()
    _download_state["paused"] = False
    log.info("下载已继续")
    return {"ok": True}


@app.post("/api/download/resume_queue")
async def api_download_resume_queue():
    q = _download_state.get("queue", [])
    ids = [it["bookId"] for it in q if it.get("status") != "done"]
    if not ids:
        raise HTTPException(status_code=400, detail="无未完成队列")
    with _state_lock:
        if _download_state["running"]:
            raise HTTPException(status_code=409, detail="已有任务进行中")
        _download_state["running"] = True
        _download_state["log"] = []
        _download_state["has_restore"] = False
    threading.Thread(target=_download_worker, args=(ids,), daemon=True).start()
    log.info("恢复队列：%d 本", len(ids))
    return {"ok": True, "count": len(ids)}


@app.post("/api/download/cancel")
async def api_download_cancel_all():
    for q in _download_state.get("queue", []):
        if q.get("status") in ("pending", "downloading"):
            _cancel_ids.add(q["bookId"])
            if q.get("status") == "pending":
                q["status"] = "cancelled"
    # 用户放弃：清持久化队列，下次重启不恢复
    try:
        for q in _download_state.get("queue", []):
            store.clear_progress(q.get("bookId", ""))
        store.clear_queue()
    except Exception:
        log.exception("清队列失败")
    _pause_event.set()
    _download_state["paused"] = False
    _download_state["has_restore"] = False
    log.info("全部下载已请求取消，队列已清")
    return {"ok": True}


@app.post("/api/download/cancel/{book_id}")
async def api_download_cancel_one(book_id: str):
    _cancel_ids.add(book_id)
    _set_queue(book_id, status="cancelled")
    _pause_event.set()
    return {"ok": True}


@app.get("/api/download/status")
async def api_download_status():
    return dict(_download_state)


@app.get("/api/download/stream")
async def api_download_stream():
    async def gen():
        last = -1
        while True:
            s = dict(_download_state)
            payload = json.dumps(s, ensure_ascii=False)
            if hash(payload) != last:
                yield f"data: {payload}\n\n"
                last = hash(payload)
            if not s["running"] and s["total"] > 0:
                yield "event: done\ndata: {}\n\n"
                break
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------- 已下载 ----------
@app.get("/api/records")
async def api_records(page: int = 1, page_size: int = 30):
    d = store.load_downloaded()
    items = [{"bookId": k, **v} for k, v in d.items() if not v.get("deleted")]
    items.sort(key=lambda x: x.get("finished_at", 0), reverse=True)
    total = len(items)
    page_size = max(1, min(page_size, 200))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "count": len(items[start:end]),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@app.delete("/api/records/{book_id}")
async def api_records_delete(book_id: str):
    d = store.load_downloaded()
    if book_id in d:
        d[book_id]["deleted"] = True
        store.DOWNLOADED_PATH.write_text(
            json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    _clear_shelf_cache()
    return {"ok": True}


@app.delete("/api/records/{book_id}/file")
async def api_records_delete_file(book_id: str):
    d = store.load_downloaded()
    rec = d.get(book_id)
    if rec and rec.get("title"):
        out_dir = Path(config.OUTPUT_DIR)
        prefix = rec["title"][:20]
        if out_dir.exists():
            for f in out_dir.glob("*.epub"):
                if f.stem.startswith(prefix):
                    try:
                        f.unlink()
                    except Exception as e:
                        log.warning("删文件失败 %s: %s", f.name, e)
    d.pop(book_id, None)
    store.DOWNLOADED_PATH.write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _clear_shelf_cache()
    return {"ok": True}


# ---------- 配置 ----------
ALLOWED_EXT = {".epub", ".pdf", ".txt", ".mobi", ".azw3", ".md", ".doc", ".docx"}
MAX_UPLOAD_MB = 200


def _safe_filename(raw: str) -> str:
    fname = Path(raw or "").name
    for ch in "/\\:*?<>|":
        fname = fname.replace(ch, "_")
    return fname.strip()


@app.post("/api/upload")
async def api_upload(files: list[UploadFile] = File(...)):
    out_dir = Path(config.OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok, skipped, failed = [], [], []
    for uf in files:
        fname = _safe_filename(uf.filename)
        if not fname:
            failed.append({"name": uf.filename or "", "reason": "非法文件名"})
            continue
        ext = Path(fname).suffix.lower()
        if ext not in ALLOWED_EXT:
            failed.append({"name": fname, "reason": "不支持类型 " + ext})
            continue
        dst = out_dir / fname
        if dst.exists():
            skipped.append(fname)
            continue
        try:
            content = await uf.read()
            if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
                failed.append({"name": fname, "reason": "超过 %dMB" % MAX_UPLOAD_MB})
                continue
            dst.write_bytes(content)
            ok.append(fname)
        except Exception as e:
            failed.append({"name": fname, "reason": str(e)})
    log.info("上传：成功 %d，跳过 %d，失败 %d", len(ok), len(skipped), len(failed))
    _clear_shelf_cache()
    return {"ok": ok, "skipped": skipped, "failed": failed}


@app.get("/api/outputs")
async def api_outputs(page: int = 1, page_size: int = 30):
    out_dir = Path(config.OUTPUT_DIR)
    downloaded = store.load_downloaded()
    wx_titles = [(v.get("title") or "")[:20] for v in downloaded.values() if v.get("title")]
    items = []
    if out_dir.exists():
        for f in out_dir.iterdir():
            if not f.is_file() or f.suffix.lower() not in ALLOWED_EXT:
                continue
            stem = f.stem
            if any(stem.startswith(t) for t in wx_titles):
                continue
            st = f.stat()
            items.append({
                "name": f.name,
                "size": st.st_size,
                "mtime": int(st.st_mtime),
            })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    total = len(items)
    page_size = max(1, min(page_size, 200))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "count": len(items[start:end]),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@app.delete("/api/outputs/{name}")
async def api_outputs_delete(name: str):
    fname = _safe_filename(name)
    if not fname:
        raise HTTPException(status_code=400, detail="非法文件名")
    fp = Path(config.OUTPUT_DIR) / fname
    try:
        if fp.exists():
            fp.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail="删除失败: %s" % e)
    _clear_shelf_cache()
    return {"ok": True}


_intro_cache = {}


@app.get("/api/book/{book_id}/intro")
async def api_book_intro(book_id: str):
    if book_id in _intro_cache:
        return _intro_cache[book_id]
    a, cli = _get_client()
    if not cli:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        r = cli.http.get("/web/book/info", params={"bookId": book_id})
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail="获取失败: %d" % r.status_code)
        d = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    result = {
        "bookId": book_id,
        "title": d.get("title", ""),
        "author": d.get("author", ""),
        "intro": d.get("intro", "") or "",
        "rating": d.get("newRating", 0) or 0,
        "category": d.get("category", "") or "",
    }
    _intro_cache[book_id] = result
    return result


_match_cache = {}


def _clean_bookname(name: str) -> str:
    if "." in name:
        name = name.rsplit(".", 1)[0]
    if " - " in name:
        name = name.split(" - ", 1)[0]
    return name.strip()


@app.get("/api/match")
async def api_match(name: str = ""):
    q = _clean_bookname(name)
    if not q:
        raise HTTPException(status_code=400, detail="name 为空")
    if q in _match_cache:
        return _match_cache[q]
    a, cli = _get_client()
    if not cli:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        r = cli.http.get("/web/search/global", params={"keyword": q})
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail="搜索失败: %d" % r.status_code)
        books = r.json().get("books") or []
        if not books:
            result = {"matched": False, "query": q}
        else:
            bi = books[0].get("bookInfo") or {}
            result = {
                "matched": True,
                "query": q,
                "bookId": bi.get("bookId", ""),
                "title": bi.get("title", ""),
                "author": bi.get("author", ""),
                "cover": bi.get("cover", ""),
                "intro": bi.get("intro", ""),
                "rating": bi.get("newRating", 0) or 0,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    _match_cache[q] = result
    return result


@app.get("/api/config")
async def api_config_get():
    return config.load_settings()


@app.put("/api/config")
async def api_config_put(req: Request):
    body = await req.json()
    cur = config.load_settings()
    cur.update(body)
    config.save_settings(cur)
    return cur


# ---------- 日志 ----------
@app.get("/api/logs")
async def api_logs(n: int = 200):
    return {"lines": log_mod.recent(n)}


@app.get("/api/logs/stream")
async def api_logs_stream():
    q = log_mod.subscribe()

    async def gen():
        try:
            for line in log_mod.recent(100):
                yield f"data: {json.dumps(line, ensure_ascii=False)}\n\n"
            while True:
                try:
                    line = q.get_nowait()
                    yield f"data: {json.dumps(line, ensure_ascii=False)}\n\n"
                except Exception:
                    await asyncio.sleep(0.5)
        finally:
            log_mod.unsubscribe(q)
    return StreamingResponse(gen(), media_type="text/event-stream")



# ---------- 启动钩子 ----------
def main():
    import uvicorn
    uvicorn.run("app.api:app", host="0.0.0.0", port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()