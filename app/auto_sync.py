"""自动同步调度器

后台线程按小时间隔轮询，到点回调 tick_fn（在 api.py 注入）。
不 import api，避免循环导入。
"""
import logging
import threading
import time

log = logging.getLogger("auto_sync")


class AutoSyncScheduler:
    def __init__(self, tick_fn, get_interval_hours, is_enabled, poll_seconds=60):
        self._tick = tick_fn
        self._get_interval = get_interval_hours
        self._is_enabled = is_enabled
        self._poll = poll_seconds
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._last_run = time.time()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._last_run = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="auto-sync")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def trigger_now(self):
        with self._lock:
            self._last_run = time.time()
        return self._tick()

    def _loop(self):
        while not self._stop.wait(self._poll):
            try:
                if not self._is_enabled():
                    continue
                hours = max(0.1, float(self._get_interval()))
                if time.time() - self._last_run < hours * 3600:
                    continue
                with self._lock:
                    self._last_run = time.time()
                self._tick()
            except Exception:
                log.exception("自动同步 tick 失败")


_scheduler = None


def init_scheduler(tick_fn, get_interval_hours, is_enabled):
    global _scheduler
    _scheduler = AutoSyncScheduler(tick_fn, get_interval_hours, is_enabled)
    return _scheduler


def get_scheduler():
    return _scheduler
