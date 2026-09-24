"""内存日志缓冲：环形队列 + 订阅推送"""
import logging
import threading
from collections import deque


_MAX_LINES = 500
_buffer = deque(maxlen=_MAX_LINES)
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
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        root.addHandler(sh)


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