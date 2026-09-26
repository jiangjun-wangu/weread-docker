"""SQLite 数据库层：连接管理 + 建表 + 通用查询

- 表结构集中在 schema.sql，换库只需改本文件连接层
- 时间字段统一用整数时间戳（秒），跨库通用
- 连接用线程局部存储（threading.local），每线程一个连接
- 启用 WAL 模式（读写并发更好）；外键约束打开
"""
import sqlite3
import threading
from pathlib import Path

from app.config import CONFIG_DIR


DB_PATH = CONFIG_DIR / "weread.db"
SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """取当前线程的连接（懒创建）"""
    conn = getattr(_local, "conn", None)
    if conn is None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db() -> None:
    """建表（幂等，读 schema.sql）"""
    conn = get_conn()
    if SCHEMA_PATH.exists():
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()


def query(sql: str, params=()) -> list:
    """查询多行，返回 sqlite3.Row 列表"""
    return get_conn().execute(sql, params).fetchall()


def query_one(sql: str, params=()):
    """查询单行，无则 None"""
    rows = get_conn().execute(sql, params).fetchall()
    return rows[0] if rows else None


def execute(sql: str, params=()) -> None:
    """执行单条写语句并提交"""
    conn = get_conn()
    conn.execute(sql, params)
    conn.commit()


def executemany(sql: str, seq) -> None:
    """批量写并提交"""
    conn = get_conn()
    conn.executemany(sql, seq)
    conn.commit()
