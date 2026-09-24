"""配置读写：环境变量 + settings.json"""
import json
import os
from pathlib import Path


def _resolve_dir(env_name, fallback):
    env = os.environ.get(env_name)
    if env:
        return Path(env)
    app_root = Path("/app")
    if app_root.is_dir() and os.access("/app", os.W_OK):
        return app_root / fallback
    return Path(fallback)

CONFIG_DIR = _resolve_dir("CONFIG_DIR", "config")
OUTPUT_DIR = _resolve_dir("OUTPUT_DIR", "output")
PORT = int(os.environ.get("PORT", "8765"))
DOWNLOAD_INTERVAL = float(os.environ.get("DOWNLOAD_INTERVAL", "3"))
MAX_PER_MONTH = int(os.environ.get("MAX_PER_MONTH", "100"))
AUTO_SYNC = os.environ.get("AUTO_SYNC", "false").lower() == "true"
AUTO_SYNC_CRON = os.environ.get("AUTO_SYNC_CRON", "")
AUTO_SYNC_ENABLED = os.environ.get(
    "AUTO_SYNC_ENABLED", os.environ.get("AUTO_SYNC", "false")
).lower() == "true"
AUTO_SYNC_INTERVAL_HOURS = float(os.environ.get("AUTO_SYNC_INTERVAL_HOURS", "6"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info")


SETTINGS_PATH = CONFIG_DIR / "settings.json"


def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "logs").mkdir(exist_ok=True)
    (CONFIG_DIR / "progress").mkdir(exist_ok=True)


DEFAULT_SETTINGS = {
    "download_interval": DOWNLOAD_INTERVAL,
    "max_per_month": MAX_PER_MONTH,
    "auto_sync": AUTO_SYNC,
    "auto_sync_cron": AUTO_SYNC_CRON,
    "auto_sync_enabled": AUTO_SYNC_ENABLED,
    "auto_sync_interval_hours": AUTO_SYNC_INTERVAL_HOURS,
    "output_dir": str(OUTPUT_DIR),
}


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        # 旧字段 auto_sync → 新字段 auto_sync_enabled 迁移
        if "auto_sync" in data and "auto_sync_enabled" not in data:
            merged["auto_sync_enabled"] = bool(data["auto_sync"])
        return merged
    except Exception:
        return dict(DEFAULT_SETTINGS)


def save_settings(data: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
