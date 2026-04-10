-- File Toolkit — SQLite Schema
-- 运行时数据库（不入 git，.gitignore 已排除 *.db）
-- schema.sql 本身入库，由 history_service.init_db() 执行

CREATE TABLE IF NOT EXISTS task_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    module      TEXT    NOT NULL,           -- 'pdf', 'image', 'media', 'archive', 'ocr'
    action      TEXT    NOT NULL,           -- 'split', 'merge', 'compress', 'convert', ...
    status      TEXT    NOT NULL,           -- 'success', 'failed', 'cancelled'
    input_desc  TEXT    NOT NULL,           -- 输入文件描述（文件名或"X 个文件"）
    output_dir  TEXT,                       -- 输出目录路径
    duration_s  REAL    DEFAULT 0,          -- 耗时秒数
    error_msg   TEXT                        -- 失败时的错误信息
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

-- 默认设置（INSERT OR IGNORE 保证重复初始化幂等）
INSERT OR IGNORE INTO settings VALUES ('theme_mode', 'system');      -- system/light/dark
INSERT OR IGNORE INTO settings VALUES ('default_output_dir', '');    -- 空=输入文件同级 output/
INSERT OR IGNORE INTO settings VALUES ('after_complete', 'open_dir'); -- open_dir/notify/silent
INSERT OR IGNORE INTO settings VALUES ('history_limit', '30');
INSERT OR IGNORE INTO settings VALUES ('language', 'zh_CN');
INSERT OR IGNORE INTO settings VALUES ('ocr_provider', 'baidu');
INSERT OR IGNORE INTO settings VALUES ('ocr_api_key', '');           -- 实际值存 keyring
INSERT OR IGNORE INTO settings VALUES ('ocr_secret_key', '');        -- 实际值存 keyring
