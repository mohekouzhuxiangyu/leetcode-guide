-- ============================================================
-- 力扣算法学习助手 · 数据库初始化脚本 (PostgreSQL)
--
-- 部署步骤（新环境）：
--   1. 创建数据库（只需一次）：
--        createdb leetcode_guide
--      或
--        psql -U postgres -c "CREATE DATABASE leetcode_guide;"
--   2. 执行本脚本创建表结构：
--        psql -U <你的用户> -d leetcode_guide -f db/init.sql
--   3. 在 .env 中配置连接串：
--        DATABASE_URL=postgresql://localhost:5432/leetcode_guide
-- ============================================================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id             SERIAL PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    email          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verify_token   TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 登录会话表
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 分组表
CREATE TABLE IF NOT EXISTS groups (
    name       TEXT NOT NULL,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (name, user_id)
);

-- 记录表（slug 为力扣题目唯一标识）
CREATE TABLE IF NOT EXISTS records (
    slug        TEXT PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL DEFAULT '',
    difficulty  TEXT NOT NULL DEFAULT 'Unknown',
    tags        JSONB NOT NULL DEFAULT '[]'::jsonb,
    category    TEXT NOT NULL DEFAULT '其他',
    group_name  TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    problem     JSONB NOT NULL DEFAULT '{}'::jsonb,
    problem_zh  TEXT NOT NULL DEFAULT '',
    analysis    TEXT NOT NULL DEFAULT '',
    walkthrough TEXT NOT NULL DEFAULT '',
    flowchart   TEXT NOT NULL DEFAULT '',
    code        JSONB NOT NULL DEFAULT '{}'::jsonb,
    errors      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 兼容旧库：补充列与索引（新库已包含，重复执行无副作用）
ALTER TABLE records ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE groups   ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;

-- 常用查询索引
CREATE INDEX IF NOT EXISTS idx_records_user_id     ON records (user_id);
CREATE INDEX IF NOT EXISTS idx_records_group_name  ON records (group_name);
CREATE INDEX IF NOT EXISTS idx_records_category    ON records (category);
CREATE INDEX IF NOT EXISTS idx_records_difficulty  ON records (difficulty);
CREATE INDEX IF NOT EXISTS idx_records_updated_at  ON records (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_groups_user_id      ON groups (user_id);
