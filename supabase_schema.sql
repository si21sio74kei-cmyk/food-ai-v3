-- ============================================================
-- FoodGuardian AI - 账号系统数据库表结构
-- 使用方法：Supabase 控制台 → SQL Editor → 新建查询 → 粘贴本文件全部内容 → Run
-- ============================================================

-- 1. 用户表（账号信息，密码只存哈希值）
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    recovery_hash TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 兼容已经建好的旧 users 表。
ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_hash TEXT;

-- 2. 用户概览数据（昵称、环保统计、冰箱库存和采购偏好）。
--    AI 聊天不入库，每餐摄入记录单独存入 intake_records。
CREATE TABLE IF NOT EXISTS user_data (
    user_id    UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data       JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. 独立每餐摄入表，便于按账号、日期查询和自动清理。
CREATE TABLE IF NOT EXISTS intake_records (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    record_date DATE NOT NULL,
    record_time TIME NOT NULL,
    meal_type   TEXT NOT NULL DEFAULT 'snack'
                CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    vegetables  NUMERIC(10,1) NOT NULL DEFAULT 0,
    fruits      NUMERIC(10,1) NOT NULL DEFAULT 0,
    meat        NUMERIC(10,1) NOT NULL DEFAULT 0,
    eggs        NUMERIC(10,1) NOT NULL DEFAULT 0,
    source      TEXT NOT NULL DEFAULT 'manual',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_intake_records_user_date
    ON intake_records(user_id, record_date);

-- 4. updated_at 自动更新触发器
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_data_updated ON user_data;
CREATE TRIGGER trg_user_data_updated
    BEFORE UPDATE ON user_data
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trg_intake_records_updated ON intake_records;
CREATE TRIGGER trg_intake_records_updated
    BEFORE UPDATE ON intake_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 5. 行级安全 (RLS)：开启且不添加任何 policy，
--    意味着匿名请求（anon key / 前端直连）完全无法读写这两张表。
--    Flask 服务器端使用 service_role key 访问，自动绕过 RLS。
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE intake_records ENABLE ROW LEVEL SECURITY;
