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
    credits        INTEGER NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 兼容旧库补充列
ALTER TABLE users ADD COLUMN IF NOT EXISTS vip BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_expires_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER NOT NULL DEFAULT 0;
-- 账户余额（元）：生成题目按题扣费，管理员手动充值/调整
ALTER TABLE users ADD COLUMN IF NOT EXISTS balance NUMERIC(10,2) NOT NULL DEFAULT 0;

-- 余额流水（管理员调整 / 生成扣费）
CREATE TABLE IF NOT EXISTS balance_log (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount     NUMERIC(10,2) NOT NULL,           -- 正=收入 负=支出
    type       TEXT NOT NULL DEFAULT 'adjust',   -- adjust=管理员调整 | usage=生成扣费
    note       TEXT NOT NULL DEFAULT '',
    admin_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_balance_log_user ON balance_log (user_id, created_at);

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

-- 用户自定义算法模板（增删改，按用户独立；内置模板在 backend/templates.py）
CREATE TABLE IF NOT EXISTS user_templates (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category   TEXT NOT NULL,
    name       TEXT NOT NULL,
    when_use   TEXT NOT NULL DEFAULT '',
    python     TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_templates_user ON user_templates (user_id, category);

-- 每日生成额度（每账号每天 200 题上限）
CREATE TABLE IF NOT EXISTS daily_usage (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day     DATE NOT NULL DEFAULT CURRENT_DATE,
    count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

-- 题目-分组 多对多（同一题可属于多个分组，内容共享；组内不重复）
CREATE TABLE IF NOT EXISTS record_groups (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug       TEXT NOT NULL,
    group_name TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, slug, group_name)
);
CREATE INDEX IF NOT EXISTS idx_record_groups_user ON record_groups (user_id, group_name);

-- 迁移：把旧 records.group_name 归属转入关联表（用户私有记录）
INSERT INTO record_groups (user_id, slug, group_name)
SELECT user_id, slug, group_name FROM records
WHERE user_id IS NOT NULL AND group_name <> ''
ON CONFLICT DO NOTHING;

-- 计费流水（普通 1 元/题，VIP 0.1 元/题，按量记录用于结算）
CREATE TABLE IF NOT EXISTS usage_log (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug       TEXT NOT NULL,
    price      NUMERIC(6,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_usage_log_user_day ON usage_log (user_id, created_at);

-- 捐赠记录（自愿捐赠 / 拒绝捐赠直接开通 / 支付宝订单），管理员可查每个用户的捐赠金额
CREATE TABLE IF NOT EXISTS donations (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount     NUMERIC(8,2) NOT NULL DEFAULT 0,
    source     TEXT NOT NULL DEFAULT 'donate',  -- donate=自愿捐赠 | free=拒绝捐赠直接开通 | order=支付宝订单
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_donations_user ON donations (user_id);

-- 题目视频讲解（管理员上传，按 slug 关联；文件存 data/videos/，也可配置外站链接如 B站）
CREATE TABLE IF NOT EXISTS videos (
    slug         TEXT PRIMARY KEY,
    filename     TEXT NOT NULL DEFAULT '',
    external_url TEXT NOT NULL DEFAULT '',
    uploaded_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE videos ADD COLUMN IF NOT EXISTS external_url TEXT NOT NULL DEFAULT '';

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
