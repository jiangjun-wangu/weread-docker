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
AUTO_SYNC_MAX_PER_RUN = int(os.environ.get("AUTO_SYNC_MAX_PER_RUN", "10"))
AUTO_RESTORE_ENABLED = os.environ.get("AUTO_RESTORE_ENABLED", "false").lower() == "true"
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info")
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "500"))
LOG_FILE_MAX_MB = int(os.environ.get("LOG_FILE_MAX_MB", "10"))
LOG_FILE_BACKUPS = int(os.environ.get("LOG_FILE_BACKUPS", "3"))


SETTINGS_PATH = CONFIG_DIR / "settings.json"

# 环境变量覆盖表：key → (env 名, 类型转换)
ENV_OVERRIDES = {
    "download_interval": ("DOWNLOAD_INTERVAL", float),
    "max_per_month": ("MAX_PER_MONTH", int),
    "auto_sync_enabled": ("AUTO_SYNC_ENABLED", lambda v: str(v).lower() == "true"),
    "auto_sync_interval_hours": ("AUTO_SYNC_INTERVAL_HOURS", float),
    "auto_sync_max_per_run": ("AUTO_SYNC_MAX_PER_RUN", int),
    "auto_restore_enabled": ("AUTO_RESTORE_ENABLED", lambda v: str(v).lower() == "true"),
    "log_buffer_size": ("LOG_BUFFER_SIZE", int),
    "log_file_max_mb": ("LOG_FILE_MAX_MB", int),
    "log_file_backups": ("LOG_FILE_BACKUPS", int),
}


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
    "auto_sync_max_per_run": AUTO_SYNC_MAX_PER_RUN,
    "auto_restore_enabled": AUTO_RESTORE_ENABLED,
    "log_buffer_size": LOG_BUFFER_SIZE,
    "log_file_max_mb": LOG_FILE_MAX_MB,
    "log_file_backups": LOG_FILE_BACKUPS,
    "output_dir": str(OUTPUT_DIR),
}


def _apply_env_overrides(data: dict) -> dict:
    for key, (env, cast) in ENV_OVERRIDES.items():
        val = os.environ.get(env)
        if val is not None and val != "":
            try:
                data[key] = cast(val)
            except Exception:
                pass
    return data


def load_settings() -> dict:
    from app import db
    try:
        rows = db.query("SELECT key, value FROM settings")
        if rows:
            data = {}
            for r in rows:
                try:
                    data[r["key"]] = json.loads(r["value"])
                except Exception:
                    data[r["key"]] = r["value"]
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            if "auto_sync" in data and "auto_sync_enabled" not in data:
                merged["auto_sync_enabled"] = bool(data["auto_sync"])
            return _apply_env_overrides(merged)
    except Exception:
        pass
    # 回退：旧 JSON
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            if "auto_sync" in data and "auto_sync_enabled" not in data:
                merged["auto_sync_enabled"] = bool(data["auto_sync"])
            return _apply_env_overrides(merged)
        except Exception:
            pass
    return _apply_env_overrides(dict(DEFAULT_SETTINGS))


def save_settings(data: dict) -> None:
    from app import db
    db.executemany(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        [(k, json.dumps(v, ensure_ascii=False)) for k, v in data.items()],
    )
