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
    vip            BOOLEAN NOT NULL DEFAULT FALSE,
    vip_expires_at TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 兼容旧库补充列
ALTER TABLE users ADD COLUMN IF NOT EXISTS vip BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_expires_at TIMESTAMPTZ;

-- VIP 订单表（支付宝）
CREATE TABLE IF NOT EXISTS vip_orders (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_no   TEXT NOT NULL UNIQUE,
    plan       TEXT NOT NULL,
    amount     TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',  -- pending | paid | closed
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at    TIMESTAMPTZ
);

-- 用户题目心得（Markdown 文档，按用户独立）
CREATE TABLE IF NOT EXISTS user_notes (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug       TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, slug)
);

-- 登录会话表
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 分组表（user_id NULL = 共享分组，如 hot100）
CREATE TABLE IF NOT EXISTS groups (
    name       TEXT NOT NULL,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 记录表（user_id NULL = 免费共享目录 hot100，只读）
-- 无主键约束，改用部分唯一索引：
--   共享记录 slug 全局唯一；用户记录 (user_id, slug) 唯一
CREATE TABLE IF NOT EXISTS records (
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
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

-- 兼容旧库：原 slug 主键改为部分唯一索引
ALTER TABLE records DROP CONSTRAINT IF EXISTS records_pkey;
ALTER TABLE records ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE groups   ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;

-- 唯一性约束
CREATE UNIQUE INDEX IF NOT EXISTS uq_records_shared_slug ON records (slug) WHERE user_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_records_user_slug   ON records (user_id, slug) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_groups_shared_name  ON groups (name) WHERE user_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_groups_user_name    ON groups (name, user_id) WHERE user_id IS NOT NULL;

-- 常用查询索引
CREATE INDEX IF NOT EXISTS idx_records_user_id     ON records (user_id);
CREATE INDEX IF NOT EXISTS idx_records_group_name  ON records (group_name);
CREATE INDEX IF NOT EXISTS idx_records_category    ON records (category);
CREATE INDEX IF NOT EXISTS idx_records_difficulty  ON records (difficulty);
CREATE INDEX IF NOT EXISTS idx_records_updated_at  ON records (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_groups_user_id      ON groups (user_id);
