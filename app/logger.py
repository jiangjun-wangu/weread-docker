"""内存日志缓冲 + 文件落盘：环形队列 + 订阅推送 + RotatingFileHandler"""
import logging
import threading
from collections import deque
from logging.handlers import RotatingFileHandler


_MAX_LINES = 500
_buffer = deque(maxlen=_MAX_LINES)


def set_max_lines(n):
    """动态调整缓冲行数（保留最近的 n 行）"""
    global _MAX_LINES, _buffer
    try:
        n = max(50, min(int(n), 10000))
    except Exception:
        return
    if n == _MAX_LINES:
        return
    with _lock:
        _MAX_LINES = n
        _buffer = deque(_buffer, maxlen=n)
_lock = threading.Lock()
_subscribers = []


class BufferHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
        except Exception:
            return
        with _lock:
            _buffer.append(msg)
            subs = list(_subscribers)
        for q in subs:
            try:
                q.put_nowait(msg)
            except Exception:
                pass


def install(level=logging.INFO):
    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(h, BufferHandler) for h in root.handlers):
        h = BufferHandler()
        h.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        root.addHandler(h)
    if not any(isinstance(h, logging.StreamHandler)
               and not isinstance(h, RotatingFileHandler) for h in root.handlers):
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        root.addHandler(sh)


def install_file_handler(path, max_mb=10, backups=3):
    """添加/更新滚动文件日志 handler"""
    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, RotatingFileHandler):
            root.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass
    try:
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            str(p), maxBytes=max(1, int(max_mb)) * 1024 * 1024,
            backupCount=max(1, int(backups)), encoding="utf-8",
        )
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        root.addHandler(fh)
    except Exception:
        pass


def recent(n=200):
    with _lock:
        lines = list(_buffer)
    return lines[-n:]


def subscribe():
    import queue
    q = queue.Queue(maxsize=1000)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q):
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)