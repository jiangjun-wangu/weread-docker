"""HTTP 客户端：书架 / 目录 / reader / 分片"""
import random as _random
import re
import time

from app import protocol


READER_URL = "https://weread.qq.com/web/reader/{book}k{chapter}"
PSVTS_RE = re.compile(r'"psvts"\s*:\s*"([A-Za-z0-9_-]+)"')


class SessionExpired(Exception):
    pass


class ProtocolError(Exception):
    pass


class WeReadClient:
    def __init__(self, auth):
        self.auth = auth
        self.http = auth.client

    def _check(self, r):
        if r.status_code in (401, 403):
            raise SessionExpired("http %d" % r.status_code)
        r.raise_for_status()

    def shelf(self):
        r = self.http.get("/web/shelf/sync")
        self._check(r)
        data = r.json()
        err = data.get("errcode") or data.get("errCode") or 0
        if err == -2012:
            raise SessionExpired("shelf errcode=-2012")
        if err != 0:
            raise ProtocolError("shelf errcode=%s" % err)

        progress_map = {}
        for pg in data.get("bookProgress", []) or []:
            progress_map[pg.get("bookId", "")] = {
                "progress": pg.get("progress", 0),
                "chapterIdx": pg.get("chapterIdx", 0),
                "readingTime": pg.get("readingTime", 0),
                "updateTime": pg.get("updateTime", 0),
            }

        books = []
        for b in data.get("books", []) or []:
            bid = b.get("bookId", "")
            pg = progress_map.get(bid, {})
            books.append({
                "bookId": bid,
                "title": b.get("title", ""),
                "author": b.get("author", ""),
                "cover": b.get("cover", ""),
                "category": b.get("category", ""),
                "publishTime": b.get("publishTime", ""),
                "updateTime": b.get("updateTime", 0),
                "readUpdateTime": b.get("readUpdateTime", 0),
                "centPrice": b.get("centPrice", 0),
                "lastChapterIdx": b.get("lastChapterIdx", 0),
                "finished": b.get("finished", 0),
                "finishReading": b.get("finishReading", 0),
                "readingTime": pg.get("readingTime", 0),
                "progress": pg.get("progress", 0),
                "chapterIdx": pg.get("chapterIdx", 0),
                "hasProgress": bid in progress_map,
            })

        self.last_shelf_meta = {
            "bookCount": data.get("bookCount", len(books)),
            "pureBookCount": data.get("pureBookCount", len(books)),
        }
        return books

    def toc(self, book_id):
        body = {"bookIds": [book_id]}
        r = self.http.post("/web/book/chapterInfos", json=body)
        self._check(r)
        data = r.json()
        err = data.get("errcode") or data.get("errCode") or 0
        if err == -2012:
            raise SessionExpired("toc errcode=-2012")
        if err != 0:
            raise ProtocolError("toc errcode=%s" % err)
        chapters = []
        for entry in data.get("data", []) or []:
            for ch in entry.get("updated", []) or []:
                chapters.append({
                    "chapterUid": str(ch.get("chapterUid", "")),
                    "title": ch.get("title", ""),
                    "wordCount": ch.get("wordCount", 0),
                    "chapterIdx": ch.get("chapterIdx", 0),
                    "paid": ch.get("paid", 0),
                    "level": ch.get("level", 1),
                })
        chapters.sort(key=lambda c: c["chapterIdx"])
        return chapters

    def reader_referer(self, book_id, chapter_uid):
        book = protocol.encode_id(book_id)
        chapter = protocol.encode_id(chapter_uid)
        return READER_URL.format(book=book, chapter=chapter)

    def fetch_psvts(self, book_id, chapter_uid):
        url = self.reader_referer(book_id, chapter_uid)
        r = self.http.get(url)
        if r.status_code == 401:
            raise SessionExpired("reader 401")
        if r.status_code == 403:
            raise ProtocolError("reader 403")
        r.raise_for_status()
        m = PSVTS_RE.search(r.text)
        if not m:
            raise ProtocolError("psvts not found")
        return m.group(1), url

    def fetch_shard(self, book_id, chapter_uid, endpoint, psvts, referer):
        ts = int(time.time())
        rv = _random.randint(0, 10000)
        body = protocol.make_content_body(book_id, chapter_uid, psvts, ts, rv)
        headers = {"Referer": referer}
        r = self.http.post(endpoint, json=body, headers=headers)
        if r.status_code == 401:
            raise SessionExpired("shard 401")
        if r.status_code == 403:
            raise ProtocolError("shard 403")
        r.raise_for_status()
        return r.status_code, r.content


    def download_chapter(self, book_id, chapter_uid):
        psvts, referer = self.fetch_psvts(book_id, chapter_uid)
        status, shard0 = self.fetch_shard(book_id, chapter_uid, "/web/book/chapter/e_0", psvts, referer)
        kind = classify_chapter_response(status, is_empty_json_object(shard0))
        if kind == "auth":
            raise SessionExpired("primary 401")
        if kind == "retry":
            raise ProtocolError("primary retry")
        if kind == "error":
            raise ProtocolError("primary error status=" + str(status))
        pk = bytes([80, 75, 3, 4])
        if shard0[:4] == pk:
            return {"type": "epub", "data": shard0}
        if _text_metadata(shard0):
            s, s0 = self.fetch_shard(book_id, chapter_uid, "/web/book/chapter/t_0", psvts, referer)
            if s != 200:
                raise ProtocolError("t_0 status=" + str(s))
            s, s1 = self.fetch_shard(book_id, chapter_uid, "/web/book/chapter/t_1", psvts, referer)
            if s != 200:
                raise ProtocolError("t_1 status=" + str(s))
            decoded = protocol.combine_and_decode([s0, s1])
            return {"type": "xhtml", "data": decoded}
        s, s1 = self.fetch_shard(book_id, chapter_uid, "/web/book/chapter/e_1", psvts, referer)
        if s != 200:
            raise ProtocolError("e_1 status=" + str(s))
        s, s3 = self.fetch_shard(book_id, chapter_uid, "/web/book/chapter/e_3", psvts, referer)
        if s != 200:
            raise ProtocolError("e_3 status=" + str(s))
        decoded = protocol.combine_and_decode([shard0, s1, s3])
        if decoded[:4] == pk:
            return {"type": "epub", "data": decoded}
        return {"type": "xhtml", "data": decoded}

def _text_metadata(shard0):
    i = 0
    n = len(shard0)
    while i < n and shard0[i] in (32, 9, 10, 13):
        i += 1
    if i >= n or shard0[i] != 123:
        return False
    prefix = bytes([34, 98, 111, 111, 107, 73, 100, 34, 58, 34])
    pos = shard0.find(prefix)
    if pos < 0:
        return False
    j = pos + len(prefix)
    while j < n and shard0[j] != 34:
        j += 1
    return j > pos + len(prefix)


def classify_chapter_response(status, empty_object):
    if status == 401:
        return "auth"
    if status == 403 or (status == 200 and empty_object):
        return "retry"
    if status == 200:
        return "content"
    return "error"


def is_empty_json_object(data):
    state = 0
    for b in data:
        if b in (32, 9, 10, 13):
            continue
        if state == 0 and b == 123:
            state = 1
        elif state == 1 and b == 125:
            state = 2
        else:
            return False
    return state == 2

