"""下载引擎：编排整本书下载"""
import time
from pathlib import Path

from app import client
from app import epub
from app import store
from app.config import OUTPUT_DIR



class Downloader:
    def __init__(self, cli, output_dir=None, interval=3.0, retries=3):
        self.cli = cli
        self.output_dir = Path(output_dir) if output_dir else Path(OUTPUT_DIR)
        self.interval = interval
        self.retries = retries
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, book):
        title = (book.get('title') or '').strip()
        author = (book.get('author') or '').strip()
        if not title:
            title = book.get('bookId', 'unknown')
        bad = '/' + chr(92) + ':*?<>|'
        for c in bad:
            title = title.replace(c, '_')
            author = author.replace(c, '_')
        title = title.rstrip('.').strip()
        author = author.rstrip('.').strip()
        if author:
            name = title + ' - ' + author
        else:
            name = title
        if len(name) > 180:
            name = name[:180]
        return name + '.epub'

    def _target_path(self, book):
        return self.output_dir / self._safe_name(book)

    def _already_done(self, book):
        path = self._target_path(book)
        if not path.exists():
            return False
        if path.stat().st_size < 1024:
            return False
        return True

    def _fetch_chapter_with_retry(self, book_id, chapter_uid):
        last = None
        for attempt in range(self.retries):
            try:
                return self.cli.download_chapter(book_id, chapter_uid)
            except client.SessionExpired:
                raise
            except Exception as e:
                last = e
                print("  重试 " + str(attempt + 1) + "/" + str(self.retries) + " 失败: " + str(e))
                time.sleep(self.interval)
        raise last

    def download_book(self, book, on_progress=None):
        book_id = book['bookId']
        title = book.get('title', book_id)
        path = self._target_path(book)

        if self._already_done(book):
            store.clear_progress(book_id)
            print("跳过（已下载）: " + title)
            return "skipped"

        chapters = self.cli.toc(book_id)
        if not chapters:
            print("目录为空: " + title)
            return "empty"

        total_ch = len(chapters)
        store.save_progress_meta(book_id, {
            "title": title, "total_ch": total_ch, "done_ch": 0,
        })
        if on_progress:
            on_progress(0, total_ch)

        first = self._fetch_chapter_with_retry(book_id, chapters[0]['chapterUid'])
        if on_progress:
            on_progress(1, total_ch)
        if first['type'] == 'epub':
            path.write_bytes(first['data'])
            store.mark_downloaded(book_id, title, 1)
            store.clear_progress(book_id)
            print("完成（整本）: " + title)
            return "ok"

        collected = [dict(chapters[0], xhtml=first['data'])]
        store.save_progress_meta(book_id, {
            "title": title, "total_ch": total_ch, "done_ch": 1,
        })
        for i, ch in enumerate(chapters[1:], 2):
            time.sleep(self.interval)
            r = self._fetch_chapter_with_retry(book_id, ch['chapterUid'])
            if on_progress:
                on_progress(i, total_ch)
            if r['type'] == 'epub':
                path.write_bytes(r['data'])
                store.mark_downloaded(book_id, title, 1)
                store.clear_progress(book_id)
                print("完成（整本，中间章判定）: " + title)
                return "ok"
            collected.append(dict(ch, xhtml=r['data']))
            store.save_progress_meta(book_id, {
                "title": title, "total_ch": total_ch, "done_ch": i,
            })

        epub_bytes = epub.pack_epub(book, collected)
        path.write_bytes(epub_bytes)
        store.mark_downloaded(book_id, title, len(collected))
        store.clear_progress(book_id)
        print("完成: " + title + " (" + str(len(collected)) + " 章)")
        return "ok"

    def download_all(self, books, progress=None):
        results = {"ok": 0, "skipped": 0, "failed": 0, "empty": 0}
        total = len(books)
        for i, book in enumerate(books):
            title = book.get('title', book.get('bookId', ''))
            try:
                r = self.download_book(book)
                results[r] += 1
            except client.SessionExpired:
                print("Session 过期，中止: " + title)
                raise
            except Exception as e:
                print("失败: " + title + " - " + str(e))
                results["failed"] += 1
            if progress:
                progress(i + 1, total, title)
            time.sleep(self.interval)
        return results
