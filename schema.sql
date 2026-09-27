-- ============================================================
-- 微信读书下载工具 · 数据库结构
-- 类型通用（TEXT/INTEGER/BLOB），时间用整数时间戳（秒）
-- 主键用业务 ID，索引命名 idx_表_字段，换 MySQL 只改连接层
-- ============================================================

-- 1. 登录会话（单行，id 固定 1）
CREATE TABLE IF NOT EXISTS session (
    id           INTEGER PRIMARY KEY,             -- 固定 1
    cookies_json TEXT    NOT NULL DEFAULT '{}',   -- Cookie 字典 JSON
    uid          TEXT    NOT NULL DEFAULT '',     -- 登录 UID
    created_at   INTEGER NOT NULL DEFAULT 0,      -- 创建时间戳
    last_renewal INTEGER NOT NULL DEFAULT 0       -- 最近续期时间戳
);

-- 2. 已下载记录
CREATE TABLE IF NOT EXISTS downloaded (
    book_id     TEXT PRIMARY KEY,                 -- 微信读书 bookId
    title       TEXT    NOT NULL DEFAULT '',      -- 书名
    chapters    INTEGER NOT NULL DEFAULT 0,       -- 章节数
    finished_at INTEGER NOT NULL DEFAULT 0,       -- 完成时间戳
    deleted     INTEGER NOT NULL DEFAULT 0        -- 软删：0正常 1移除
);

-- 3. 月度下载限流
CREATE TABLE IF NOT EXISTS rate (
    month TEXT PRIMARY KEY,                       -- YYYY-MM
    count INTEGER NOT NULL DEFAULT 0              -- 当月已下本数
);

-- 4. 应用设置（键值对）
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,                       -- 配置项名
    value TEXT NOT NULL DEFAULT ''                -- 配置值（JSON 编码）
);

-- 5. 下载进度（未完成的书）
CREATE TABLE IF NOT EXISTS progress (
    book_id    TEXT PRIMARY KEY,                  -- 微信读书 bookId
    title      TEXT    NOT NULL DEFAULT '',       -- 书名
    total_ch   INTEGER NOT NULL DEFAULT 0,        -- 总章节
    done_ch    INTEGER NOT NULL DEFAULT 0,        -- 已完成
    updated_at INTEGER NOT NULL DEFAULT 0         -- 更新时间戳
);

-- 6. 下载队列（持久化顺序）
CREATE TABLE IF NOT EXISTS queue (
    book_id  TEXT PRIMARY KEY,                    -- 微信读书 bookId
    position INTEGER NOT NULL DEFAULT 0,          -- 队列顺序
    added_at INTEGER NOT NULL DEFAULT 0           -- 入队时间戳
);

-- 7. 书籍元数据（封面 + 简介，静态缓存）
CREATE TABLE IF NOT EXISTS book_meta (
    book_id    TEXT PRIMARY KEY,                  -- 微信读书 bookId
    title      TEXT    NOT NULL DEFAULT '',       -- 书名
    author     TEXT    NOT NULL DEFAULT '',       -- 作者
    cover_url  TEXT    NOT NULL DEFAULT '',       -- 封面 URL
    cover_data BLOB,                              -- 封面二进制
    cover_mime TEXT    NOT NULL DEFAULT '',       -- MIME 类型
    intro      TEXT    NOT NULL DEFAULT '',       -- 简介
    rating     INTEGER NOT NULL DEFAULT 0,        -- 评分 ×10
    category   TEXT    NOT NULL DEFAULT '',       -- 分类
    source     TEXT    NOT NULL DEFAULT 'wx',     -- 来源 wx/upload
    created_at INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL DEFAULT 0
);

-- 8. 书架快照（个人阅读数据）
CREATE TABLE IF NOT EXISTS shelf (
    book_id          TEXT PRIMARY KEY,
    title            TEXT    NOT NULL DEFAULT '',
    author           TEXT    NOT NULL DEFAULT '',
    cover            TEXT    NOT NULL DEFAULT '',
    category         TEXT    NOT NULL DEFAULT '',
    publish_time     TEXT    NOT NULL DEFAULT '',
    update_time      INTEGER NOT NULL DEFAULT 0,
    read_update_time INTEGER NOT NULL DEFAULT 0,
    cent_price       INTEGER NOT NULL DEFAULT 0,
    last_chapter_idx INTEGER NOT NULL DEFAULT 0,
    finished         INTEGER NOT NULL DEFAULT 0,
    finish_reading   INTEGER NOT NULL DEFAULT 0,
    reading_time     INTEGER NOT NULL DEFAULT 0,
    progress         INTEGER NOT NULL DEFAULT 0,
    chapter_idx      INTEGER NOT NULL DEFAULT 0,
    has_progress     INTEGER NOT NULL DEFAULT 0,
    position         INTEGER NOT NULL DEFAULT 0,  -- 原始顺序
    cached_at        INTEGER NOT NULL DEFAULT 0   -- 快照时间
);

-- ---------- 索引 ----------
CREATE INDEX IF NOT EXISTS idx_downloaded_finished ON downloaded(finished_at);
CREATE INDEX IF NOT EXISTS idx_progress_updated    ON progress(updated_at);
CREATE INDEX IF NOT EXISTS idx_queue_position      ON queue(position);
CREATE INDEX IF NOT EXISTS idx_book_meta_title     ON book_meta(title);
CREATE INDEX IF NOT EXISTS idx_book_meta_updated   ON book_meta(updated_at);
CREATE INDEX IF NOT EXISTS idx_shelf_cached        ON shelf(cached_at);
CREATE INDEX IF NOT EXISTS idx_shelf_position      ON shelf(position);
