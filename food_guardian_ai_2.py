# -*- coding: utf-8 -*-
"""
FoodGuardian AI v2.0 - 智能食谱助手 (Web版)
Modern Web Application with iOS-style UI

运行方式:
python food_guardian_ai_2.py

访问地址: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, send_from_directory, Response, stream_with_context, session, g
import json
import os
import re
import secrets
import sqlite3
import requests
import sys
import time
import threading
import uuid
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 读取本地环境变量文件，确保本地运行时也能读取 API Key 和数据库配置
load_dotenv(os.path.join(BASE_DIR, '.env'))
load_dotenv(os.path.join(BASE_DIR, '数据库.env'))
load_dotenv(os.path.join(BASE_DIR, 'database.env'))

# Windows 控制台默认 GBK 编码会导致 emoji 打印失败，统一设置为 UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# 中国时区 (UTC+8)
CHINA_TZ = timezone(timedelta(hours=8))

def get_china_time():
    """获取中国标准时间"""
    return datetime.now(CHINA_TZ)

app = Flask(__name__, static_folder='static', template_folder='templates')

# 🔐 账号会话配置（生产环境请在 Vercel 环境变量中设置 SESSION_SECRET）
app.secret_key = os.getenv('SESSION_SECRET', 'fgai-dev-secret-change-me')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = bool(os.getenv('VERCEL'))  # Vercel 强制 HTTPS
AUTH_INACTIVITY_TIMEOUT = timedelta(days=3)
AUTH_FAILURE_WINDOW = timedelta(minutes=15)
AUTH_LOCK_DURATION = timedelta(minutes=15)
AUTH_MAX_FAILURES = 5
app.config['PERMANENT_SESSION_LIFETIME'] = AUTH_INACTIVITY_TIMEOUT
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

_auth_failures = {}
_auth_failures_lock = threading.Lock()


@app.before_request
def expire_inactive_session():
    """账号连续 3 天无活动时自动退出，并在本次响应中标记过期原因。"""
    if not session.get('user_id'):
        return

    now = get_china_time()
    last_activity = session.get('last_activity_at')
    try:
        last_activity_time = datetime.fromisoformat(last_activity) if last_activity else None
        if last_activity_time and last_activity_time.tzinfo is None:
            last_activity_time = last_activity_time.replace(tzinfo=CHINA_TZ)
    except (TypeError, ValueError):
        last_activity_time = None

    if not last_activity_time or now - last_activity_time >= AUTH_INACTIVITY_TIMEOUT:
        try:
            compact_user_storage(
                session.get('user_id'),
                session.get('auth_backend') or ('supabase' if is_db_configured() else 'local')
            )
        except Exception as exc:
            print(f'⚠️ [Auth] 会话过期前数据整理失败: {exc}')
        session.clear()
        g.auth_session_expired = True
        return

    session['last_activity_at'] = now.isoformat()

# ====================== Supabase 数据库配置 ======================
SUPABASE_URL = (os.getenv('SUPABASE_URL') or '').rstrip('/')
SUPABASE_KEY = os.getenv('SUPABASE_KEY') or ''  # secret/service_role key，仅服务器端使用
LOCAL_ACCOUNT_DB = os.getenv('LOCAL_ACCOUNT_DB') or os.path.join(BASE_DIR, 'fgai_accounts.db')

def is_db_configured():
    """是否已配置 Supabase 数据库"""
    return bool(SUPABASE_URL and SUPABASE_KEY)

def is_local_auth_enabled():
    """本地桌面运行时的账号兜底库；Vercel 等只读环境禁用。"""
    return (not os.getenv('VERCEL')) and os.getenv('ENABLE_LOCAL_ACCOUNTS', '1') != '0'

def is_auth_enabled():
    """前端是否应启用账号系统。"""
    return is_db_configured() or is_local_auth_enabled()

# ====================== AI API 全局配置 ======================
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
# 🔒 安全修复：必须使用环境变量，禁止硬编码 API Key
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_API_KEY_TEXT = os.getenv("ZHIPU_API_KEY_TEXT")
TEXT_GENERATION_API_KEY = ZHIPU_API_KEY_TEXT or ZHIPU_API_KEY

# 检查API密钥是否配置
if not ZHIPU_API_KEY or not TEXT_GENERATION_API_KEY:
    print("\n⚠️  警告: 未检测到API密钥！")
    print("请在Vercel环境变量中配置 ZHIPU_API_KEY 和 ZHIPU_API_KEY_TEXT")
    print("或创建 .env 文件（仅本地开发使用）\n")

API_TIMEOUT = 120
API_MAX_RETRIES = 3
AI_CONNECTION_ERROR_MESSAGE = (
    "无法连接 AI 服务，请检查网络、防火墙或代理是否允许访问 "
    "open.bigmodel.cn:443"
)

# 启用详细日志
ENABLE_DETAILED_LOGS = True

# ====================== 常量定义 ======================
COLORS = {
    'primary': '#FF8C42',
    'secondary': '#FFB347',
    'tertiary': '#FFD93D',
    'background': '#FFF9F0',
    'card_bg': '#FFFFFF',
    'text_primary': '#2C2C2C',
    'text_secondary': '#5A5A5A',
    'danger': '#FF6B6B',
    'separator': '#E0E0E0'
}

# ====================== 食材数据库加载 ======================
def load_ingredient_database():
    """加载食材数据库"""
    db_path = os.path.join(os.path.dirname(__file__), 'ingredient_database.json')
    
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 加载食材数据库失败: {e}，使用默认配置")
    
    # 返回空配置（未知食材将由AI自动识别）
    return {
        'base_portions': {},
        'ingredient_map': {}
    }

# 全局加载一次
INGREDIENT_DB = load_ingredient_database()
BASE_PORTIONS = INGREDIENT_DB.get('base_portions', {})
INGREDIENT_MAP = INGREDIENT_DB.get('ingredient_map', {})

MEAL_MULTIPLIERS = {'home': 1.0, 'healthy': 0.9, 'vegetarian': 0.85, 'banquet': 1.15}

ENV_FACTORS = {'water_per_g': 0.5, 'co2_per_g': 3.0}
WASTE_RATIO = 0.25

# ====================== 账号系统 (Supabase REST API) ======================
def build_supabase_headers(extra_headers=None):
    """按 Supabase Key 类型构造请求头，兼容新版 secret key 和旧 JWT。"""
    headers = {
        'apikey': SUPABASE_KEY,
        'Content-Type': 'application/json'
    }
    # sb_secret_/sb_publishable_ 是 API Key，不是 JWT，不能作为 Bearer token。
    if not SUPABASE_KEY.startswith(('sb_secret_', 'sb_publishable_')):
        headers['Authorization'] = f'Bearer {SUPABASE_KEY}'
    if extra_headers:
        headers.update(extra_headers)
    return headers


def db_request(method, path, params=None, json_body=None, extra_headers=None):
    """调用 Supabase PostgREST API
    返回: 解析后的 JSON (list/dict)，请求失败时返回 None（调用方据此降级）
    """
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = build_supabase_headers(extra_headers)
    try:
        resp = requests.request(method, url, headers=headers, params=params,
                                json=json_body, timeout=15)
        if resp.status_code == 204:
            return []
        if resp.status_code not in (200, 201):
            print(f"⚠️ [DB] {method} {path} → [{resp.status_code}] {resp.text[:200]}")
            return None
        return resp.json() if resp.text else []
    except Exception as e:
        print(f"⚠️ [DB] 请求异常: {e}")
        return None


def local_db_connect():
    """连接本地账号数据库，并确保表结构存在。"""
    conn = sqlite3.connect(LOCAL_ACCOUNT_DB)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            user_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    user_columns = {
        row['name'] for row in conn.execute('PRAGMA table_info(users)').fetchall()
    }
    if 'recovery_hash' not in user_columns:
        conn.execute('ALTER TABLE users ADD COLUMN recovery_hash TEXT')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS intake_records (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            record_date TEXT NOT NULL,
            record_time TEXT NOT NULL,
            meal_type TEXT NOT NULL DEFAULT 'snack',
            vegetables REAL NOT NULL DEFAULT 0,
            fruits REAL NOT NULL DEFAULT 0,
            meat REAL NOT NULL DEFAULT 0,
            eggs REAL NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_intake_records_user_date
        ON intake_records(user_id, record_date)
    ''')
    conn.commit()
    return conn


def local_get_user_by_username(username):
    """从本地 SQLite 账号库读取用户。"""
    if not is_local_auth_enabled():
        return None
    conn = None
    try:
        conn = local_db_connect()
        row = conn.execute(
            'SELECT id, username, password_hash, recovery_hash FROM users WHERE username = ?',
            (username,)
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ [LocalDB] 查询用户失败: {e}")
        return None
    finally:
        if conn:
            conn.close()


def local_create_user(username, password_hash, recovery_hash=None):
    """在本地 SQLite 账号库创建用户。"""
    if not is_local_auth_enabled():
        return None
    user = {
        'id': str(uuid.uuid4()),
        'username': username,
        'password_hash': password_hash,
        'recovery_hash': recovery_hash
    }
    conn = None
    try:
        conn = local_db_connect()
        conn.execute(
            '''INSERT INTO users
               (id, username, password_hash, recovery_hash, created_at)
               VALUES (?, ?, ?, ?, ?)''',
            (user['id'], user['username'], user['password_hash'],
             user['recovery_hash'], get_china_time().isoformat())
        )
        conn.commit()
        return user
    except sqlite3.IntegrityError:
        return {'error': 'exists'}
    except Exception as e:
        print(f"⚠️ [LocalDB] 创建用户失败: {e}")
        return None
    finally:
        if conn:
            conn.close()


def local_load_user_data(user_id):
    """读取本地账号专属数据。"""
    if not is_local_auth_enabled():
        return None
    conn = None
    try:
        conn = local_db_connect()
        row = conn.execute('SELECT data FROM user_data WHERE user_id = ?', (user_id,)).fetchone()
        if not row:
            return None
        stored = json.loads(row['data'])
        data = default_user_data()
        if isinstance(stored, dict):
            data.update(stored)
        return data
    except Exception as e:
        print(f"⚠️ [LocalDB] 读取用户数据失败: {e}")
        return None
    finally:
        if conn:
            conn.close()


def local_save_user_data(user_id, data):
    """写入本地账号专属数据。"""
    if not is_local_auth_enabled():
        return False
    conn = None
    try:
        profile = dict(data) if isinstance(data, dict) else {}
        # 每餐记录已拆分到 intake_records，用户概览 JSON 不再重复存放。
        profile.pop('daily_intake_records', None)
        conn = local_db_connect()
        conn.execute(
            '''
            INSERT INTO user_data (user_id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            ''',
            (user_id, json.dumps(profile, ensure_ascii=False), get_china_time().isoformat())
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"⚠️ [LocalDB] 保存用户数据失败: {e}")
        return False
    finally:
        if conn:
            conn.close()


VALID_MEAL_TYPES = {'breakfast', 'lunch', 'dinner', 'snack'}


def intake_date_bounds():
    """返回滚动 7 天的最早日期和今日。"""
    today = get_china_time().date()
    return today - timedelta(days=6), today


def infer_meal_type(record_time):
    """为升级前的旧记录按时间补全餐次标签。"""
    try:
        hour = int(str(record_time or '12:00').split(':', 1)[0])
    except (TypeError, ValueError):
        hour = 12
    if hour < 10:
        return 'breakfast'
    if hour < 15:
        return 'lunch'
    if hour < 21:
        return 'dinner'
    return 'snack'


def normalize_intake_record(record, user_id='', position=0):
    """清洗并补全单条摄入记录，保证旧数据可自动迁移。"""
    if not isinstance(record, dict):
        return None
    record_date = str(record.get('date') or record.get('record_date') or '')[:10]
    record_time = str(record.get('time') or record.get('record_time') or '00:00')[:5]
    meal_type = str(record.get('meal_type') or infer_meal_type(record_time))
    if meal_type not in VALID_MEAL_TYPES:
        meal_type = infer_meal_type(record_time)
    seed = '|'.join([
        user_id, record_date, record_time, str(position),
        str(record.get('vegetables', 0)), str(record.get('fruits', 0)),
        str(record.get('meat', 0)), str(record.get('eggs', 0))
    ])
    record_id = str(record.get('id') or uuid.uuid5(uuid.NAMESPACE_URL, seed))

    clean = {
        'id': record_id,
        'date': record_date,
        'time': record_time,
        'meal_type': meal_type,
        'source': str(record.get('source') or 'manual')[:24]
    }
    for field in ('vegetables', 'fruits', 'meat', 'eggs'):
        try:
            amount = round(max(0, min(float(record.get(field, 0)), 100000)), 1)
            clean[field] = int(amount) if amount.is_integer() else amount
        except (TypeError, ValueError):
            clean[field] = 0
    return clean


def local_load_intake_records(user_id):
    """从独立摄入表读取当前账号近 7 天记录。"""
    conn = None
    try:
        start, today = intake_date_bounds()
        conn = local_db_connect()
        conn.execute(
            'DELETE FROM intake_records WHERE user_id = ? AND (record_date < ? OR record_date > ?)',
            (user_id, start.isoformat(), today.isoformat())
        )
        rows = conn.execute(
            '''SELECT id, record_date, record_time, meal_type, vegetables,
                      fruits, meat, eggs, source
               FROM intake_records
               WHERE user_id = ?
               ORDER BY record_date, record_time, created_at''',
            (user_id,)
        ).fetchall()
        conn.commit()
        return [{
            'id': row['id'], 'date': row['record_date'], 'time': row['record_time'],
            'meal_type': row['meal_type'], 'vegetables': row['vegetables'],
            'fruits': row['fruits'], 'meat': row['meat'], 'eggs': row['eggs'],
            'source': row['source']
        } for row in rows]
    except Exception as exc:
        print(f'⚠️ [LocalDB] 读取摄入记录失败: {exc}')
        return None
    finally:
        if conn:
            conn.close()


def local_replace_intake_records(user_id, records):
    """将近 7 天记录同步到独立数据表。"""
    conn = None
    try:
        now = get_china_time().isoformat()
        conn = local_db_connect()
        conn.execute('DELETE FROM intake_records WHERE user_id = ?', (user_id,))
        for position, raw in enumerate(records or []):
            record = normalize_intake_record(raw, user_id, position)
            if not record:
                continue
            conn.execute(
                '''INSERT INTO intake_records
                   (id, user_id, record_date, record_time, meal_type, vegetables,
                    fruits, meat, eggs, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (record['id'], user_id, record['date'], record['time'],
                 record['meal_type'], record['vegetables'], record['fruits'],
                 record['meat'], record['eggs'], record['source'], now, now)
            )
        conn.commit()
        return True
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f'⚠️ [LocalDB] 同步摄入记录失败: {exc}')
        return False
    finally:
        if conn:
            conn.close()


def local_update_credentials(user_id, password_hash=None, recovery_hash=None):
    """更新本地账号密码或恢复码哈希。"""
    updates, values = [], []
    if password_hash is not None:
        updates.append('password_hash = ?')
        values.append(password_hash)
    if recovery_hash is not None:
        updates.append('recovery_hash = ?')
        values.append(recovery_hash)
    if not updates:
        return True
    conn = None
    try:
        conn = local_db_connect()
        values.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        return True
    except Exception as exc:
        print(f'⚠️ [LocalDB] 更新账号凭证失败: {exc}')
        return False
    finally:
        if conn:
            conn.close()


def local_ensure_user_data_row(user_id, username):
    """确保本地账号有一行数据。"""
    if local_load_user_data(user_id) is not None:
        return True
    return local_save_user_data(user_id, build_initial_user_data(username))


def get_current_user():
    """获取当前登录用户（来自签名会话 Cookie）"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return {'id': user_id, 'username': session.get('username', '')}


def get_current_auth_backend():
    """当前会话使用的账号后端：supabase 或 local。"""
    return session.get('auth_backend') or ('supabase' if is_db_configured() else 'local')


def default_user_data():
    """新账号的默认数据结构"""
    return {
        'nickname': '',
        'waste_reduced': 0,
        'water_saved': 0,
        'co2_reduced': 0,
        'population_group': 'adults',
        'daily_intake_records': [],
        'fridge_inventory': [],
        'generation_count': 0,
        'shopping_preferences': {
            'province': '',
            'city': '',
            'price_samples': []
        }
    }


def sanitize_persisted_user_data(data):
    """只持久化应用需要跨设备保留的数据，聊天记录不入库。"""
    clean = default_user_data()
    if isinstance(data, dict):
        for key in clean:
            if key in data:
                clean[key] = data[key]

    # 摄入记录使用滚动 7 天窗口：今天及之前 6 天保留，第 8 天起自动删除。
    today = get_china_time().date()
    allowed_dates = {
        (today - timedelta(days=i)).isoformat()
        for i in range(7)
    }
    records = clean.get('daily_intake_records') or []
    if isinstance(records, list):
        normalized_records = []
        for position, record in enumerate(records):
            normalized = normalize_intake_record(record, position=position)
            if normalized and normalized.get('date') in allowed_dates:
                normalized_records.append(normalized)
        clean['daily_intake_records'] = normalized_records
    else:
        clean['daily_intake_records'] = []

    preferences = clean.get('shopping_preferences')
    if not isinstance(preferences, dict):
        preferences = {}
    samples = preferences.get('price_samples')
    if not isinstance(samples, list):
        samples = []
    clean['shopping_preferences'] = {
        'province': str(preferences.get('province') or '')[:30],
        'city': str(preferences.get('city') or '')[:30],
        'price_samples': [s for s in samples[-20:] if isinstance(s, dict)]
    }

    return clean


def build_initial_user_data(username):
    """为新账号生成干净的初始数据，避免继承游客或其他账号的记录。"""
    initial_data = default_user_data()
    initial_data['nickname'] = username
    return sanitize_persisted_user_data(initial_data)


def ensure_user_data_row(user_id, username):
    """确保登录用户有一行云端数据，避免旧账号登录后没有可加载的数据。"""
    if get_current_auth_backend() == 'local':
        return local_ensure_user_data_row(user_id, username)

    rows = db_request('GET', 'user_data',
                      params={'user_id': f'eq.{user_id}', 'select': 'user_id'})
    if rows is None:
        return False
    if rows:
        return True

    created = db_request('POST', 'user_data',
                         json_body=[{'user_id': user_id,
                                     'data': build_initial_user_data(username),
                                     'updated_at': get_china_time().isoformat()}],
                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
    return created is not None


def cloud_load_intake_records(user_id):
    """读取 Supabase 独立摄入表；表未部署时返回 None 以便兼容旧 JSON。"""
    start, today = intake_date_bounds()
    rows = db_request('GET', 'intake_records', params={
        'user_id': f'eq.{user_id}',
        'record_date': f'gte.{start.isoformat()}',
        'select': ('id,record_date,record_time,meal_type,vegetables,fruits,'
                   'meat,eggs,source'),
        'order': 'record_date.asc,record_time.asc,created_at.asc'
    })
    if rows is None:
        return None
    records = []
    for position, row in enumerate(rows):
        record = normalize_intake_record(row, user_id, position)
        if record and start.isoformat() <= record['date'] <= today.isoformat():
            records.append(record)
    return records


def cloud_replace_intake_records(user_id, records):
    """把当前用户的滚动 7 天记录写入 Supabase 独立表。"""
    now = get_china_time().isoformat()
    payload = []
    for position, raw in enumerate(records or []):
        record = normalize_intake_record(raw, user_id, position)
        if not record:
            continue
        payload.append({
            'id': record['id'], 'user_id': user_id,
            'record_date': record['date'], 'record_time': record['time'],
            'meal_type': record['meal_type'], 'vegetables': record['vegetables'],
            'fruits': record['fruits'], 'meat': record['meat'],
            'eggs': record['eggs'], 'source': record['source'],
            'created_at': now, 'updated_at': now
        })
    if payload:
        written = db_request(
            'POST', 'intake_records', json_body=payload,
            extra_headers={'Prefer': 'resolution=merge-duplicates'}
        )
        if written is None:
            return False
        ids = ','.join(row['id'] for row in payload)
        deleted = db_request('DELETE', 'intake_records', params={
            'user_id': f'eq.{user_id}', 'id': f'not.in.({ids})'
        })
    else:
        deleted = db_request('DELETE', 'intake_records', params={
            'user_id': f'eq.{user_id}'
        })
    return deleted is not None


def compact_user_storage(user_id, backend):
    """在退出前清理第 8 天及更早的记录，已保存数据不会随会话丢失。"""
    if not user_id:
        return
    start, today = intake_date_bounds()
    if backend == 'local':
        conn = local_db_connect()
        try:
            conn.execute(
                'DELETE FROM intake_records WHERE user_id = ? AND (record_date < ? OR record_date > ?)',
                (user_id, start.isoformat(), today.isoformat())
            )
            conn.commit()
        finally:
            conn.close()
        return
    if backend == 'supabase' and is_db_configured():
        db_request('DELETE', 'intake_records', params={
            'user_id': f'eq.{user_id}', 'record_date': f'lt.{start.isoformat()}'
        })
        db_request('DELETE', 'intake_records', params={
            'user_id': f'eq.{user_id}', 'record_date': f'gt.{today.isoformat()}'
        })

# ====================== 数据持久化（已登录 → 云端按账号隔离；游客 → 本地/内存） ======================
def load_data():
    """加载数据"""
    # ① 已登录 → 从该账号对应后端加载专属数据
    user = get_current_user()
    if user and get_current_auth_backend() == 'local':
        data = local_load_user_data(user['id'])
        if data is not None:
            legacy_records = data.get('daily_intake_records') or []
            table_records = local_load_intake_records(user['id'])
            if table_records is not None:
                if not table_records and legacy_records:
                    local_replace_intake_records(user['id'], legacy_records)
                    table_records = local_load_intake_records(user['id']) or []
                data['daily_intake_records'] = table_records
            clean = sanitize_persisted_user_data(data)
            if clean != data or legacy_records:
                local_save_user_data(user['id'], clean)
            return clean
        print('⚠️ [LocalDB] 读取账号数据失败，降级为本地游客数据')

    if user and is_db_configured():
        rows = db_request('GET', 'user_data',
                          params={'user_id': f"eq.{user['id']}", 'select': 'data'})
        if rows is not None:
            stored = rows[0].get('data') if rows and isinstance(rows[0], dict) else {}
            data = default_user_data()
            if isinstance(stored, dict):
                data.update(stored)
            legacy_records = data.get('daily_intake_records') or []
            table_records = cloud_load_intake_records(user['id'])
            if table_records is not None:
                if not table_records and legacy_records:
                    if cloud_replace_intake_records(user['id'], legacy_records):
                        table_records = cloud_load_intake_records(user['id']) or []
                data['daily_intake_records'] = table_records
            clean = sanitize_persisted_user_data(data)
            if clean != data or (table_records is not None and legacy_records):
                profile = dict(clean)
                if table_records is not None:
                    profile.pop('daily_intake_records', None)
                db_request('POST', 'user_data', json_body=[{
                    'user_id': user['id'],
                    'data': profile,
                    'updated_at': get_china_time().isoformat()
                }], extra_headers={'Prefer': 'resolution=merge-duplicates'})
            return clean
        # 数据库请求失败 → 降级为游客模式，保证应用可用
        print('⚠️ [DB] 读取账号数据失败，降级为本地数据')

    # ② 游客模式（原有逻辑）
    # Vercel 环境使用内存存储（只读文件系统）
    if os.getenv('VERCEL'):
        clean = sanitize_persisted_user_data(
            getattr(load_data, '_memory_data', default_user_data())
        )
        load_data._memory_data = clean
        return clean

    # 本地环境使用文件存储
    if os.path.exists('fgai_local_data.json'):
        try:
            with open('fgai_local_data.json', 'r', encoding='utf-8') as f:
                raw = json.load(f)
            clean = sanitize_persisted_user_data(raw)
            if clean != raw:
                with open('fgai_local_data.json', 'w', encoding='utf-8') as f:
                    json.dump(clean, f, ensure_ascii=False, indent=2)
            return clean
        except:
            pass
    return default_user_data()

def save_data(data):
    """保存数据"""
    data = sanitize_persisted_user_data(data)

    # ① 已登录 → 写入该账号对应后端
    user = get_current_user()
    if user and get_current_auth_backend() == 'local':
        records_ok = local_replace_intake_records(
            user['id'], data.get('daily_intake_records', [])
        )
        if records_ok and local_save_user_data(user['id'], data):
            return
        print('⚠️ [LocalDB] 保存账号数据失败，降级为本地游客保存')

    if user and is_db_configured():
        profile = dict(data)
        if cloud_replace_intake_records(user['id'], data.get('daily_intake_records', [])):
            profile.pop('daily_intake_records', None)
        payload = {
            'user_id': user['id'],
            'data': profile,
            'updated_at': get_china_time().isoformat()
        }
        result = db_request('POST', 'user_data', json_body=[payload],
                            extra_headers={'Prefer': 'resolution=merge-duplicates'})
        if result is not None:
            return
        print('⚠️ [DB] 保存账号数据失败，降级为本地保存')

    # ② 游客模式（原有逻辑）
    # Vercel 环境使用内存存储（只读文件系统）
    if os.getenv('VERCEL'):
        load_data._memory_data = data
        return

    # 本地环境使用文件存储
    try:
        with open('fgai_local_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存数据失败: {e}")

# ====================== AI API 调用 ======================
def get_user_facing_ai_error(exc):
    """将底层网络异常转换为不泄露系统细节的用户提示。"""
    if isinstance(exc, requests.exceptions.Timeout):
        return "AI 服务响应超时，请稍后重试"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return AI_CONNECTION_ERROR_MESSAGE
    return "AI 服务暂时不可用，请稍后重试"


def _call_zhipu_api(url, api_key, prompt, max_retries):
    """智谱 AI GLM-4 API 调用(智能降级策略)"""
    if ENABLE_DETAILED_LOGS:
        print(f"\n🤖 [AI调用] 开始调用智谱 API...")
        print(f"   - Prompt长度: {len(prompt)} 字符")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    model_priority = [
        {"name": "glm-4-air", "desc": "GLM-4-Air"},
        {"name": "glm-4-flash", "desc": "GLM-4-Flash"}
    ]
    
    last_error = None
    
    for model_info in model_priority:
        model_name = model_info["name"]
        
        if ENABLE_DETAILED_LOGS:
            print(f"   🔄 尝试模型: {model_info['desc']}")
        
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2500,  # 🔑 关键修复：增加到2500，允许AI输出完整内容
            "temperature": 0.7
        }
        
        for attempt in range(max_retries + 1):
            try:
                if ENABLE_DETAILED_LOGS and attempt > 0:
                    print(f"      ⏳ 第{attempt + 1}次重试...")
                
                response = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
                
                # 📊 记录配额信息（如果API返回）
                if ENABLE_DETAILED_LOGS:
                    rate_limit = response.headers.get('X-RateLimit-Limit', 'N/A')
                    rate_remaining = response.headers.get('X-RateLimit-Remaining', 'N/A')
                    rate_reset = response.headers.get('X-RateLimit-Reset', 'N/A')
                    if rate_limit != 'N/A':
                        print(f"      📊 配额信息: 总额度={rate_limit}, 剩余={rate_remaining}, 重置时间={rate_reset}")
                
                response.raise_for_status()
                
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    if ENABLE_DETAILED_LOGS:
                        print(f"   ✅ 成功! 使用模型: {model_name}")
                        print(f"   - 响应长度: {len(content)} 字符\n")
                    return {
                        'success': True,
                        'content': content,
                        'error': None,
                        'model_used': model_name
                    }
                else:
                    last_error = '返回格式异常'
                    break
                    
            except requests.exceptions.Timeout:
                last_error = f"{model_name} 超时"
                if ENABLE_DETAILED_LOGS:
                    print(f"      ❌ 超时: {last_error}")
                break

            except requests.exceptions.ConnectionError as e:
                last_error = get_user_facing_ai_error(e)
                if ENABLE_DETAILED_LOGS:
                    print(f"      ❌ 网络连接失败: {e!r}")
                break
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if hasattr(e, 'response') else 'Unknown'
                last_error = f"HTTP {status_code}"
                
                if ENABLE_DETAILED_LOGS:
                    print(f"      ❌ HTTP错误: {last_error}")
                
                if status_code in [401, 403, 429]:
                    break
                if attempt < max_retries:
                    time.sleep(1)
                continue
                
            except Exception as e:
                last_error = get_user_facing_ai_error(e)
                if ENABLE_DETAILED_LOGS:
                    print(f"      ❌ 异常: {e!r}")
                if attempt < max_retries:
                    time.sleep(1)
                continue
    
    if ENABLE_DETAILED_LOGS:
        print(f"   ❌ 所有模型调用失败: {last_error}\n")
    
    return {
        'success': False,
        'content': None,
        'error': last_error or '调用失败',
        'model_used': 'none'
    }

def _call_zhipu_api_stream(url, api_key, prompt):
    """智谱 AI GLM-4 API 流式调用(SSE生成器)"""
    if ENABLE_DETAILED_LOGS:
        print(f"\n🤖 [AI流式调用] 开始调用智谱 API...")
        print(f"   - Prompt长度: {len(prompt)} 字符")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    model_priority = [
        {"name": "glm-4-air", "desc": "GLM-4-Air"},
        {"name": "glm-4-flash", "desc": "GLM-4-Flash"}
    ]

    last_error = None

    for model_info in model_priority:
        model_name = model_info["name"]

        if ENABLE_DETAILED_LOGS:
            print(f"   🔄 尝试模型: {model_info['desc']}")

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2500,
            "temperature": 0.7,
            "stream": True  # 🔑 启用流式输出
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT, stream=True)
            response.raise_for_status()

            if ENABLE_DETAILED_LOGS:
                print(f"   ✅ 流式连接建立! 使用模型: {model_name}")

            # 逐行读取SSE事件
            for line in response.iter_lines(decode_unicode=True):
                if line is None:
                    continue

                line = line.strip()
                if not line:
                    continue

                # 智谱API SSE格式: data: {...}
                if line.startswith('data: '):
                    data_str = line[6:]  # 去掉 "data: " 前缀

                    # 检查是否是结束标记
                    if data_str == '[DONE]':
                        if ENABLE_DETAILED_LOGS:
                            print(f"   ✅ 流式输出完成\n")
                        return

                    try:
                        data = json.loads(data_str)
                        if 'choices' in data and len(data['choices']) > 0:
                            delta = data['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue

            # 如果正常结束(没有收到[DONE]标记)
            return

        except requests.exceptions.Timeout:
            last_error = f"{model_name} 请求超时"
            if ENABLE_DETAILED_LOGS:
                print(f"      ❌ 超时: {model_name}")
            continue

        except requests.exceptions.ConnectionError as e:
            last_error = get_user_facing_ai_error(e)
            if ENABLE_DETAILED_LOGS:
                print(f"      ❌ 网络连接失败: {e!r}")
            break

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') else 'Unknown'
            if status_code in (401, 403):
                last_error = "AI API Key 无效或权限不足，请检查 ZHIPU_API_KEY_TEXT"
            elif status_code == 429:
                last_error = "AI 调用额度不足或请求过于频繁，请稍后再试"
            else:
                last_error = f"AI 服务返回 HTTP {status_code}"
            if ENABLE_DETAILED_LOGS:
                print(f"      ❌ HTTP错误: {status_code} ({last_error})")

            continue

        except Exception as e:
            last_error = get_user_facing_ai_error(e)
            if ENABLE_DETAILED_LOGS:
                print(f"      ❌ 异常: {e!r}")
            continue

    # 所有模型都失败
    if ENABLE_DETAILED_LOGS:
        print(f"   ❌ 所有模型流式调用失败: {last_error}\n")
    yield f"\n[错误: {last_error or 'AI 服务暂时不可用，请稍后重试'}]"


def call_ai_api_stream(prompt):
    """智能 AI API 流式调用 - 返回SSE生成器"""
    if TEXT_GENERATION_API_KEY:
        return _call_zhipu_api_stream(ZHIPU_API_URL, TEXT_GENERATION_API_KEY, prompt)
    else:
        # 返回一个单次生成器
        def error_gen():
            yield "\n[错误: 未配置 ZHIPU_API_KEY_TEXT]"
        return error_gen()


def extract_ai_stream_error(chunk):
    """识别 AI 流式生成器返回的错误标记，避免把错误文本当成正文展示。"""
    if not isinstance(chunk, str):
        return None
    text = chunk.strip()
    if text.startswith('[错误:') and text.endswith(']'):
        return text[len('[错误:'):-1].strip()
    return None


def call_ai_api(prompt, api_type="auto"):
    """智能 AI API 调用函数"""
    max_retries = API_MAX_RETRIES
    api_list = []

    if api_type == "auto" and TEXT_GENERATION_API_KEY:
        api_list.append({"type": "zhipu", "url": ZHIPU_API_URL, "key": TEXT_GENERATION_API_KEY})

    if not api_list:
        return {
            'success': False,
            'content': None,
            'error': '未配置 API Key',
            'api_used': 'none'
        }

    for api_info in api_list:
        api_name = api_info["type"]
        current_url = api_info["url"]
        current_key = api_info["key"]

        try:
            if api_name == "zhipu":
                result = _call_zhipu_api(current_url, current_key, prompt, max_retries)

            if result['success']:
                result['api_used'] = api_name
                return result

        except Exception as e:
            continue

    return {
        'success': False,
        'content': None,
        'error': '所有 API 调用失败',
        'api_used': 'none'
    }

# ====================== 营养评估引擎 ======================
def load_nutrition_standards():
    """加载 WHO 健康饮食原则与食物膳食指南参考框架。"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(script_dir, 'un_nutrition_standards.json')
        
        with open(json_path, 'r', encoding='utf-8') as f:
            standards = json.load(f)
        standards_dict = {s['population_group']: s for s in standards}
        return standards_dict
    except Exception as e:
        print(f"❌ 加载营养标准失败:{e}")
        return {}

def get_nutrition_standard(population_group):
    """获取指定人群的营养标准"""
    standards = load_nutrition_standards()
    return standards.get(population_group, standards.get('adults', None))


WHO_HEALTHY_DIET_URL = 'https://www.who.int/news-room/fact-sheets/detail/healthy-diet'
FAO_CHINA_GUIDELINES_URL = 'https://www.fao.org/nutrition/education/dietary-guidelines/regions/china/en/'


def nutrition_reference_block(population_group='all', language='zh-CN'):
    """向每份评估附上可追溯的来源、口径和适用范围。"""
    standard = get_nutrition_standard(population_group) if population_group != 'all' else None
    age_range = standard.get('age_range', '') if standard else '多人群对比'
    if language == 'en-US':
        return (
            "\n---\n\n## Reference framework and calculation\n\n"
            f"- **Population / age**: {age_range or population_group}\n"
            "- **Assessment unit**: total recorded intake for one person on the current day; "
            "recipe-generated records use a per-person estimate.\n"
            "- **Calculation**: each category is the sum of all saved meals, compared with the "
            "configured age-group range. WHO independently recommends at least 400 g/day of "
            "fruit and vegetables combined for people over 10.\n"
            f"- **WHO source**: [Healthy diet]({WHO_HEALTHY_DIET_URL})\n"
            f"- **Food-group reference**: [FAO country profile for the Chinese Dietary Guidelines (2022)]({FAO_CHINA_GUIDELINES_URL})\n"
            "- **Scope**: educational dietary reference only. It is not a diagnosis or an "
            "individual medical prescription; medical conditions require professional advice.\n"
        )
    return (
        "\n---\n\n## 参考依据与计算口径\n\n"
        f"- **适用人群 / 年龄**：{age_range or population_group}\n"
        "- **评估口径**：按 1 人当日已保存的全部餐次汇总；食谱自动记录按每人份估算。\n"
        "- **计算方法**：各类别摄入量 = 当日每餐记录之和，再与应用内的年龄组参考区间比较。"
        "WHO 另行建议 10 岁以上人群每日水果和蔬菜合计至少 400 克。\n"
        f"- **WHO 来源**：[健康饮食事实清单]({WHO_HEALTHY_DIET_URL})\n"
        f"- **分类食物参考**：[FAO 收录的《中国居民膳食指南（2022）》国别页]({FAO_CHINA_GUIDELINES_URL})\n"
        "- **适用范围**：仅用于饮食教育和趋势参考，不构成诊断或个体医疗处方；有疾病或特殊需求时应咨询专业人员。\n"
    )

def generate_multi_group_nutrition_report(user_intake, language='zh-CN'):
    """生成多人群营养对比报告（Markdown格式）"""
    print(f"\n👥 [generate_multi_group_nutrition_report] 用户摄入: {user_intake}, 语言: {language}")
    
    groups = ['adults', 'teens', 'children', 'elderly']
    
    if language == 'en-US':
        group_names = {
            'adults': 'Adults (18-60 years)',
            'teens': 'Teens (13-17 years)',
            'children': 'Children (6-12 years)',
            'elderly': 'Elderly (60+ years)'
        }
        food_names = {'vegetables': 'Vegetables', 'fruits': 'Fruits', 'meat': 'Meat', 'eggs': 'Eggs'}
        status_names = {'达标': 'Meets Standard', '不足': 'Insufficient', '超标': 'Excessive'}
        status_icons = {'达标': '✅', '不足': '⬇️', '超标': '⬆️'}
        
        report = "# 👥 Multi-Population Nutrition Assessment Report\n\n"
        report += "*Reference assessment using WHO healthy-diet principles and food-based dietary guidelines*\n\n"
        
        report += "## 【Your Current Intake】\n\n"
        report += f"- **Vegetables**: {user_intake.get('vegetables', 0)}g\n"
        report += f"- **Fruits**: {user_intake.get('fruits', 0)}g\n"
        report += f"- **Meat**: {user_intake.get('meat', 0)}g\n"
        report += f"- **Eggs**: {user_intake.get('eggs', 0)}g\n\n"
        
        for group in groups:
            standard = get_nutrition_standard(group)
            if not standard:
                continue
            
            group_name = group_names[group]
            characteristics_en = standard.get('characteristics_en', standard.get('characteristics', ''))
            
            report += f"---\n\n## 📋 {group_name}\n\n"
            
            if characteristics_en:
                report += f"**Group Characteristics**: {characteristics_en}\n\n"
            
            report += "### Nutrition Standards Comparison\n\n"
            report += "| Food Type | Recommended Range | Your Intake | Status |\n"
            report += "|----------|-------------------|-------------|--------|\n"
            
            recommendations = standard.get('daily_recommendations', {})
            
            for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
                rec = recommendations.get(food_type, {})
                food_name = food_names[food_type]
                intake_amount = user_intake.get(food_type, 0)
                min_val = rec.get('min', 0)
                max_val = rec.get('max', 0)
                
                if intake_amount < min_val:
                    status = '不足'
                    gap = min_val - intake_amount
                    gap_text = f" (needs {gap}g more)"
                elif intake_amount > max_val:
                    status = '超标'
                    gap = intake_amount - max_val
                    gap_text = f" (exceeds by {gap}g)"
                else:
                    status = '达标'
                    gap = 0
                    gap_text = ''
                
                icon = status_icons[status]
                status_text = f"{icon} {status_names[status]}{gap_text}"
                
                report += f"| {food_name} | {min_val}-{max_val}g | {intake_amount}g | {status_text} |\n"
            
            report += "\n"
            
            report += "### 💡 Targeted Recommendations\n\n"
            
            has_issue = False
            for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
                rec = recommendations.get(food_type, {})
                food_name = food_names[food_type]
                intake_amount = user_intake.get(food_type, 0)
                min_val = rec.get('min', 0)
                max_val = rec.get('max', 0)
                
                if intake_amount < min_val:
                    gap = min_val - intake_amount
                    report += f"- ⬇️ **Insufficient {food_name}**: For {group_name}, recommend increasing by {gap}g to reach above {min_val}g\n"
                    has_issue = True
                elif intake_amount > max_val:
                    gap = intake_amount - max_val
                    report += f"- ️ **Excessive {food_name}**: For {group_name}, recommend reducing by {gap}g to stay within {max_val}g\n"
                    has_issue = True
            
            if not has_issue:
                report += f"- ✅ **All Standards Met**: Current intake meets the nutritional needs of {group_name}, please keep it up!\n"
            
            report += "\n"
        
        report += "---\n\n## 🎯 Overall Recommendations\n\n"
        report += "Since different population groups have varying nutritional needs, we recommend:\n\n"
        report += "1. **Separate Meals**: Prepare food portions suitable for each group's nutritional needs\n"
        report += "2. **Key Focus**: Prioritize meeting the special nutritional needs of children and elderly\n"
        report += "3. **Flexible Adjustment**: Adjust food portions according to actual dining situations\n"
        report += "4. **Diverse Diet**: Ensure food variety and balanced nutrition\n\n"
        
        report += nutrition_reference_block('all', language)
    else:
        group_names = {
            'adults': '成年人 (18-60 岁)',
            'teens': '青少年 (13-17 岁)',
            'children': '儿童 (6-12 岁)',
            'elderly': '老年人 (60 岁以上)'
        }
        
        report = "# 👥 多人群营养评估报告\n\n"
        report += "*参考 WHO 健康饮食原则与食物膳食指南的多人群评估*\n\n"
        
        report += "## 【您当前摄入】\n\n"
        report += f"- **蔬菜**: {user_intake.get('vegetables', 0)}g\n"
        report += f"- **水果**: {user_intake.get('fruits', 0)}g\n"
        report += f"- **肉类**: {user_intake.get('meat', 0)}g\n"
        report += f"- **蛋类**: {user_intake.get('eggs', 0)}g\n\n"
        
        for group in groups:
            standard = get_nutrition_standard(group)
            if not standard:
                continue
            
            group_name = group_names[group]
            report += f"---\n\n## 📋 {group_name}\n\n"
            
            if standard.get('characteristics'):
                report += f"**群体特点**: {standard['characteristics']}\n\n"
            
            report += "### 营养标准对比\n\n"
            report += "| 食物类型 | 推荐范围 | 您的摄入 | 状态 |\n"
            report += "|---------|---------|---------|------|\n"
            
            icons = {'达标': '✅', '不足': '⬇️', '超标': '⬆️'}
            recommendations = standard.get('daily_recommendations', {})
            
            for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
                rec = recommendations.get(food_type, {})
                chinese_name = {'vegetables': '蔬菜', 'fruits': '水果', 'meat': '肉类', 'eggs': '蛋类'}[food_type]
                intake_amount = user_intake.get(food_type, 0)
                min_val = rec.get('min', 0)
                max_val = rec.get('max', 0)
                
                if intake_amount < min_val:
                    status = '不足'
                    gap = min_val - intake_amount
                elif intake_amount > max_val:
                    status = '超标'
                    gap = intake_amount - max_val
                else:
                    status = '达标'
                    gap = 0
                
                icon = icons.get(status, '❓')
                status_text = f"{icon} {status}"
                if gap > 0:
                    if status == '不足':
                        status_text += f" (还差 {gap}g)"
                    else:
                        status_text += f" (超出 {gap}g)"
                
                report += f"| {chinese_name} | {min_val}-{max_val}g | {intake_amount}g | {status_text} |\n"
            
            report += "\n"
            
            report += "### 💡 针对性建议\n\n"
            
            has_issue = False
            for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
                rec = recommendations.get(food_type, {})
                chinese_name = {'vegetables': '蔬菜', 'fruits': '水果', 'meat': '肉类', 'eggs': '蛋类'}[food_type]
                intake_amount = user_intake.get(food_type, 0)
                min_val = rec.get('min', 0)
                max_val = rec.get('max', 0)
                
                if intake_amount < min_val:
                    gap = min_val - intake_amount
                    report += f"- ️ **{chinese_name}不足**: 对于{group_name}，建议增加{gap}g，达到{min_val}g以上\n"
                    has_issue = True
                elif intake_amount > max_val:
                    gap = intake_amount - max_val
                    report += f"- ⬆️ **{chinese_name}超标**: 对于{group_name}，建议减少{gap}g，控制在{max_val}g以内\n"
                    has_issue = True
            
            if not has_issue:
                report += f"- ✅ **全部达标**: 当前摄入量符合{group_name}的营养需求，请继续保持！\n"
            
            report += "\n"
        
        report += "---\n\n## 🎯 综合建议\n\n"
        report += "由于不同人群的营养需求存在差异，建议：\n\n"
        report += "1. **分餐准备**: 为不同人群准备适合其营养需求的食物份量\n"
        report += "2. **重点关注**: 优先满足儿童和老年人的特殊营养需求\n"
        report += "3. **灵活调整**: 根据实际用餐情况，适当增减各类食物的份量\n"
        report += "4. **多样化饮食**: 确保食物种类丰富，营养均衡\n\n"
        
        report += nutrition_reference_block('all', language)
    
    return report

def generate_nutrition_report(user_intake, population_group, language='zh-CN'):
    """生成完整的营养评估报告（Markdown格式）"""
    assessment = nutrition_assessment(user_intake, population_group, language)
    
    if 'error' in assessment:
        return assessment['error']
    
    # 🌐 根据语言生成不同的报告
    if language == 'en-US':
        return generate_nutrition_report_en(user_intake, population_group, assessment)
    else:
        return generate_nutrition_report_zh(user_intake, population_group, assessment)

def generate_nutrition_report_en(user_intake, population_group, assessment):
    """Generate English nutrition assessment report"""
    group_names = {
        'adults': 'Adults (18-60 years)',
        'teens': 'Teens (13-17 years)',
        'children': 'Children (6-12 years)',
        'elderly': 'Elderly (60+ years)'
    }
    group_name = group_names.get(population_group, population_group)
    
    food_names = {
        'vegetables': 'Vegetables',
        'fruits': 'Fruits',
        'meat': 'Meat',
        'eggs': 'Eggs'
    }
    
    status_names = {
        'Meets Standard': 'Meets Standard',
        'Insufficient': 'Insufficient',
        'Excessive': 'Excessive',
        'Not Recorded': 'Not Recorded',
        # 保持中文键以兼容旧代码
        '达标': 'Meets Standard',
        '不足': 'Insufficient',
        '超标': 'Excessive',
        '未录入': 'Not Recorded'
    }
    
    status_icons = {
        'Meets Standard': '✅',
        'Insufficient': '⬇️',
        'Excessive': '⬆️',
        'Not Recorded': '⏸️',
        # 保持中文键以兼容旧代码
        '达标': '✅',
        '不足': '⬇️',
        '超标': '⬆️',
        '未录入': '⏸️'
    }
    
    standard = get_nutrition_standard(population_group)
    
    report = "# 📊 Nutrition Assessment Report\n\n"
    
    # Basic Information
    report += "## [Basic Information]\n\n"
    report += f"- **Assessment Date**: {get_china_time().strftime('%Y-%m-%d %H:%M')}\n"
    report += f"- **Population Group**: {group_name}\n"
    
    total_intake = sum(user_intake.get(food, 0) for food in ['vegetables', 'fruits', 'meat', 'eggs'])
    report += f"- **Total Intake**: {total_intake}g\n\n"
    
    # Intake Data Comparison
    report += "## [Intake Data Comparison]\n\n"
    report += "| Food Type | Current Intake | Recommended Range | Status |\n"
    report += "|-----------|----------------|-------------------|--------|\n"
    
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        data = assessment[food_type]
        intake_amount = data['intake']
        english_name = food_names.get(food_type, food_type)
        status = data['status']
        status_en = status_names.get(status, status)
        icon = status_icons.get(status, '❓')
        
        if standard and status not in ['未录入', 'Not Recorded']:
            recommendations = standard['daily_recommendations'].get(food_type, {})
            min_rec = recommendations.get('min', 0)
            max_rec = recommendations.get('max', 0)
            range_str = f"{min_rec}-{max_rec}g"
        else:
            range_str = "-"
        
        report += f"| {english_name} | {intake_amount}g | {range_str} | {icon} {status_en} |\n"
    
    report += "\n"
    
    # Detailed Analysis
    report += "## [Detailed Analysis]\n\n"
    
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        data = assessment[food_type]
        english_name = food_names.get(food_type, food_type)
        status = data['status']
        icon = status_icons.get(status, '❓')
        
        report += f"### {icon} {english_name}\n\n"
        report += f"- **Current Intake**: {data['intake']}g\n"
        
        if data['gap'] > 0:
            if status == 'Insufficient':
                report += f"- **Gap**: {data['gap']}g below minimum recommendation\n"
            elif status == 'Excessive':
                report += f"- **Excess**: {data['gap']}g above maximum recommendation\n"
        
        # 🔧 直接使用已翻译的 suggestion，无需再次翻译
        report += f"- **Suggestion**: {data['suggestion']}\n\n"
    
    # Comprehensive Evaluation
    report += "## [Comprehensive Evaluation]\n\n"
    
    status_count = {'Meets Standard': 0, 'Insufficient': 0, 'Excessive': 0, 'Not Recorded': 0}
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        status = assessment[food_type]['status']
        status_count[status] = status_count.get(status, 0) + 1
    
    if status_count['Meets Standard'] == 4:
        report += "🎉 **Excellent!** All food categories meet the recommended standards. Please continue to maintain a balanced diet!\n\n"
    elif status_count['Meets Standard'] >= 2:
        report += "👍 **Good!** Most food categories are reasonable. Pay attention to adjusting insufficient or excessive categories.\n\n"
    elif status_count['Not Recorded'] > 0:
        report += "️ **To be improved** Some food categories have not been recorded yet. It is recommended to supplement them for more accurate assessment.\n\n"
    else:
        report += "💡 **Needs improvement** Most food categories do not meet the standards. It is recommended to refer to the health tips below for adjustments.\n\n"
    
    # Health Tips
    report += "## [Health Tips]\n\n"
    
    tips = []
    if assessment['vegetables']['status'] == 'Insufficient':
        tips.append("🥬 Insufficient vegetable intake may lack dietary fiber and vitamins. It is recommended to increase green leafy vegetables.")
    if assessment['fruits']['status'] == 'Insufficient':
        tips.append("🍎 Insufficient fruit intake may lack vitamin C. It is recommended to add fresh fruits appropriately.")
    if assessment['meat']['status'] == 'Excessive':
        tips.append(" Excessive meat intake may increase fat intake. It is recommended to reduce red meat and increase fish and poultry.")
    if assessment['eggs']['status'] == 'Excessive':
        tips.append(" Excessive egg intake requires attention to cholesterol. It is recommended to control daily egg intake.")
    
    if not tips:
        tips.append("✨ Current diet structure is relatively reasonable. It is recommended to continue maintaining a diverse diet.")
        tips.append("💧 Don't forget to drink enough water every day (recommended 1500-2000ml).")
        tips.append("🏃 Combine with appropriate exercise for better results.")
    
    for tip in tips:
        report += f"- {tip}\n"
    
    report += nutrition_reference_block(population_group, 'en-US')
    
    return report

def generate_nutrition_report_zh(user_intake, population_group, assessment):
    """生成中文营养评估报告"""
    # 人群名称映射
    group_names = {
        'adults': '成年人 (18-60 岁)',
        'teens': '青少年 (13-17 岁)',
        'children': '儿童 (6-12 岁)',
        'elderly': '老年人 (60 岁以上)'
    }
    group_name = group_names.get(population_group, population_group)
    
    # 加载营养标准
    standard = get_nutrition_standard(population_group)
    
    # 生成报告
    report = "# 📊 营养评估报告\n\n"
    
    # 基本信息
    report += "## 【基本信息】\n\n"
    report += f"- **评估日期**: {get_china_time().strftime('%Y-%m-%d %H:%M')}\n"
    report += f"- **人群分类**: {group_name}\n"
    
    # 计算总摄入量
    total_intake = sum(user_intake.get(food, 0) for food in ['vegetables', 'fruits', 'meat', 'eggs'])
    report += f"- **总摄入量**: {total_intake}g\n\n"
    
    # 摄入数据对比
    report += "## 【摄入数据对比】\n\n"
    report += "| 食物类型 | 当前摄入 | 推荐范围 | 状态 |\n"
    report += "|---------|---------|---------|------|\n"
    
    icons = {'达标': '✅', '不足': '⬇️', '超标': '⬆️', '未录入': '⏸️'}
    
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        data = assessment[food_type]
        intake_amount = data['intake']
        chinese_name = data['chinese_name']
        status = data['status']
        icon = icons.get(status, '❓')
        
        if standard and status != '未录入':
            recommendations = standard['daily_recommendations'].get(food_type, {})
            min_rec = recommendations.get('min', 0)
            max_rec = recommendations.get('max', 0)
            range_str = f"{min_rec}-{max_rec}g"
        else:
            range_str = "-"
        
        report += f"| {chinese_name} | {intake_amount}g | {range_str} | {icon} {status} |\n"
    
    report += "\n"
    
    # 详细分析
    report += "## 【详细分析】\n\n"
    
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        data = assessment[food_type]
        chinese_name = data['chinese_name']
        status = data['status']
        suggestion = data['suggestion']
        
        icon = icons.get(status, '❓')
        report += f"### {icon} {chinese_name}\n\n"
        report += f"- **当前摄入**: {data['intake']}g\n"
        
        if data['gap'] > 0:
            if status == '不足':
                report += f"- **差距**: 还差 {data['gap']}g 达到最低推荐量\n"
            elif status == '超标':
                report += f"- **超出**: 超过最高推荐量 {data['gap']}g\n"
        
        report += f"- **建议**: {suggestion}\n\n"
    
    # 综合评价
    report += "## 【综合评价】\n\n"
    
    # 统计各种状态的数量
    status_count = {'达标': 0, '不足': 0, '超标': 0, '未录入': 0}
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        status = assessment[food_type]['status']
        status_count[status] = status_count.get(status, 0) + 1
    
    if status_count['达标'] == 4:
        report += "🎉 **优秀！** 所有食物类别摄入均符合推荐标准，请继续保持均衡饮食！\n\n"
    elif status_count['达标'] >= 2:
        report += "👍 **良好！** 大部分食物类别摄入合理，注意调整不足或超标的类别。\n\n"
    elif status_count['未录入'] > 0:
        report += "⚠️ **待完善** 部分食物类别尚未录入，建议补充完整以获得更准确的评估。\n\n"
    else:
        report += "💡 **需改进** 多数食物类别摄入不达标，建议参考下方健康提示进行调整。\n\n"
    
    # 健康提示
    report += "## 【健康提示】\n\n"
    
    tips = []
    if assessment['vegetables']['status'] == '不足':
        tips.append("🥬 蔬菜摄入不足可能缺乏膳食纤维和维生素，建议增加绿叶蔬菜摄入")
    if assessment['fruits']['status'] == '不足':
        tips.append("🍎 水果摄入不足可能缺乏维生素C，建议适量增加新鲜水果")
    if assessment['meat']['status'] == '超标':
        tips.append("🥩 肉类摄入过多可能增加脂肪摄入，建议减少红肉，增加鱼类和禽类")
    if assessment['eggs']['status'] == '超标':
        tips.append("🥚 蛋类摄入过多需注意胆固醇，建议控制每日蛋类摄入量")
    
    if not tips:
        tips.append("✨ 当前饮食结构较为合理，建议继续保持多样化饮食")
        tips.append("💧 别忘了每天喝足够的水（建议1500-2000ml）")
        tips.append("🏃 配合适量运动，效果更佳")
    
    for tip in tips:
        report += f"- {tip}\n"
    
    report += nutrition_reference_block(population_group, 'zh-CN')
    
    return report

def translate_suggestion_to_en(suggestion):
    """Translate Chinese suggestion to English"""
    # Simple translation mapping
    translations = {
        '建议增加': 'Recommend increasing',
        '摄入': 'intake',
        '当前': 'current',
        '还差': 'still need',
        '达到最低推荐量': 'to reach minimum recommendation',
        '建议减少': 'Recommend reducing',
        '已超过推荐最大值': 'exceeds maximum recommendation by',
        '摄入充足': 'Intake is sufficient',
        '请继续保持': 'please keep it up',
        '暂未录入': 'Not yet recorded',
        '如已摄入请补充录入': 'if consumed, please supplement the record',
        '摄入较少': 'Intake is relatively low',
        '建议适当增加': 'recommend appropriate increase',  # 🔧 修复：移除中文残留
        '摄入略多': 'Intake is slightly high',
        '建议后续餐次适当控制': 'recommend controlling in subsequent meals',
    }
    
    result = suggestion
    for cn, en in translations.items():
        result = result.replace(cn, en)
    
    return result

def nutrition_assessment(user_intake, population_group, language='zh-CN'):
    """全维度营养健康评估引擎（支持多语言）"""
    standard = get_nutrition_standard(population_group)
    if not standard:
        error_msg = f'未找到人群 {population_group} 的营养标准' if language == 'zh-CN' else f'Nutrition standard for {population_group} not found'
        return {'error': error_msg}
    
    #  多语言食物名称映射
    if language == 'en-US':
        food_names = {
            'vegetables': 'Vegetables',
            'fruits': 'Fruits',
            'meat': 'Meat',
            'eggs': 'Eggs'
        }
    else:  # zh-CN
        food_names = {
            'vegetables': '蔬菜',
            'fruits': '水果',
            'meat': '肉类',
            'eggs': '蛋类'
        }
    
    food_types = ['vegetables', 'fruits', 'meat', 'eggs']
    recorded_foods = []
    for food_type in food_types:
        v = user_intake.get(food_type, 0)
        try:
            if int(v) > 0:
                recorded_foods.append(food_type)
        except (ValueError, TypeError):
            pass
    is_partial_entry = len(recorded_foods) < 4
    
    assessment = {}
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        intake = user_intake.get(food_type, 0)
        recommendations = standard['daily_recommendations'].get(food_type, {})
        min_rec = recommendations.get('min', 0)
        max_rec = recommendations.get('max', 0)
        food_name = food_names[food_type]
        
        if is_partial_entry and intake == 0:
            status = '未录入' if language == 'zh-CN' else 'Not Recorded'
            gap = 0  # 未录入时差距为0
            if language == 'en-US':
                suggestion = f"Not yet recorded {food_name}, if consumed please supplement the record"
            else:
                suggestion = f"暂未录入{food_name},如已摄入请补充录入"
        elif intake < min_rec:
            status = "不足" if language == 'zh-CN' else "Insufficient"
            gap = min_rec - intake
            if language == 'en-US':
                suggestion = f"Recommend increasing {food_name} intake, current {intake}g, still need {gap}g to reach minimum recommendation"
                if is_partial_entry:
                    suggestion = f"{food_name} intake is relatively low ({intake}g), recommend appropriate increase"
            else:
                suggestion = f"建议增加{food_name}摄入,当前{intake}g,距离推荐最小值还差{gap}g"
                if is_partial_entry:
                    suggestion = f"{food_name}摄入较少({intake}g),建议适当增加"
        elif intake > max_rec:
            status = "超标" if language == 'zh-CN' else "Excessive"
            gap = intake - max_rec
            if language == 'en-US':
                suggestion = f"Recommend reducing {food_name} intake, current {intake}g, exceeds maximum recommendation by {gap}g"
                if is_partial_entry:
                    suggestion = f"{food_name} intake is slightly high ({intake}g), recommend controlling in subsequent meals"
            else:
                suggestion = f"建议减少{food_name}摄入,当前{intake}g,已超过推荐最大值{gap}g"
                if is_partial_entry:
                    suggestion = f"{food_name}摄入略多({intake}g),建议后续餐次适当控制"
        else:
            status = "达标" if language == 'zh-CN' else "Meets Standard"
            gap = 0
            if language == 'en-US':
                suggestion = f"{food_name} intake is sufficient ({intake}g), please keep it up"
            else:
                suggestion = f"{food_name}摄入充足({intake}g),请继续保持"
        
        assessment[food_type] = {
            'intake': intake,
            'status': status,
            'gap': gap,
            'chinese_name': food_names[food_type],
            'suggestion': suggestion
        }
    
    return assessment

def generate_personalized_plan(user_intake, population_group, fridge_items=None, language='zh-CN'):
    """分人群差异化饮食方案生成"""
    assessment = nutrition_assessment(user_intake, population_group, language)
    
    population_info = {
        'adults': '成年人,需要均衡营养以维持身体机能',
        'children': '儿童,处于生长发育期,需要充足的蛋白质和钙质',
        'elderly': '老年人,消化吸收能力下降,需要易消化、高钙的食物'
    }
    
    population_info_en = {
        'adults': 'Adults, need balanced nutrition to maintain body functions',
        'children': 'Children, in growth and development stage, need sufficient protein and calcium',
        'elderly': 'Elderly, decreased digestive capacity, need easily digestible and high-calcium foods'
    }
    
    insufficient = [k for k, v in assessment.items() if v['status'] == '不足']
    excessive = [k for k, v in assessment.items() if v['status'] == '超标']
    
    if language == 'en-US':
        prompt = f"""You are a professional nutritionist. Please generate a personalized diet plan for TOMORROW based on today's intake.

【User Information】
- Population Group: {population_group} ({population_info_en.get(population_group, '')})
- Today's intake (compared with the configured WHO/food-based dietary reference framework): Vegetables {user_intake.get('vegetables', 0)}g, Fruits {user_intake.get('fruits', 0)}g, Meat {user_intake.get('meat', 0)}g, Eggs {user_intake.get('eggs', 0)}g

【Nutrition Assessment Results】
- Insufficient Intake: {', '.join(insufficient) if insufficient else 'None'}
- Excessive Intake: {', '.join(excessive) if excessive else 'None'}

【Task Requirements】
1. Analyze the special nutritional needs of this population group
2. Provide supplementation suggestions for insufficient intake items
3. Provide control suggestions for excessive intake items
4. Generate TOMORROW's diet recommendations (specific dishes + ingredient amounts) to fill today's gaps
5. Consider the digestive characteristics of this group (elderly: soft food, children: fun food, adults: balanced food)

【Output Format】
## Nutrition Assessment Summary
## Improvement Suggestions (at least 3)
## Tomorrow's Recipe Recommendations (2-3 dishes)

【Reply Requirements】
- Concise and clear, focus on key points
- Use structured headings and lists
- Avoid lengthy explanations
- Keep each suggestion under 50 words

Please respond entirely in English."""
    else:
        prompt = f"""你是一位专业营养师,请根据今日摄入情况生成**明日**个性化饮食方案:

【用户信息】
- 人群标签:{population_group}({population_info.get(population_group, '')})
- 今日摄入（对比 WHO 健康饮食原则与食物膳食指南参考框架）:蔬菜{user_intake.get('vegetables', 0)}g、水果{user_intake.get('fruits', 0)}g、肉类{user_intake.get('meat', 0)}g、蛋类{user_intake.get('eggs', 0)}g

【营养评估结果】
- 摄入不足:{', '.join(insufficient) if insufficient else '无'}
- 摄入超标:{', '.join(excessive) if excessive else '无'}

【任务要求】
1. 分析该人群的特殊营养需求
2. 针对摄入不足项给出补充建议
3. 针对摄入超标项给出控制建议
4. 生成**明日**饮食建议(具体菜品 + 食材用量)，以弥补今日缺口
5. 考虑该人群的消化特点(老年人软烂、儿童趣味、成年人均衡)

【输出格式】
## 营养评估总结
## 改善建议(至少 3 条)
## 明日食谱推荐(2-3 道菜)

【回复要求】
- 简洁明了，重点突出
- 使用结构化标题和列表
- 避免冗长解释
- 每条建议控制在50字以内"""
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        if api_result['success']:
            return api_result['content']
        else:
            return f"AI 生成失败:{api_result.get('error', '未知错误')}"
    except Exception as e:
        return f"生成方案时出错:{str(e)}"

def generate_daily_recommendation(user_intake, population_group, fridge_items, language='zh-CN'):
    """基于今日营养摄入缺口 + 现有食材，生成明日饮食推荐（优先补充不足）"""
    assessment = nutrition_assessment(user_intake, population_group, language)
    standard = get_nutrition_standard(population_group)

    # 收集摄入不足的食材类别
    deficient_foods = []
    for food_type, data in assessment.items():
        if data['status'] in ('不足', 'Insufficient'):
            deficient_foods.append({
                'name': data['chinese_name'],
                'intake': data['intake'],
                'gap': data['gap']
            })

    # 冰箱食材列表
    if fridge_items:
        ingredients_str = ", ".join([f"{item['name']}{item.get('quantity', '')}g" for item in fridge_items[:5]])
    else:
        ingredients_str = ''

    # 构建营养标准参考
    if standard:
        recs = standard.get('daily_recommendations', {})
        if language == 'en-US':
            food_names = {'vegetables': 'Vegetables', 'fruits': 'Fruits', 'meat': 'Meat', 'eggs': 'Eggs'}
            standard_lines = '\n'.join([
                f"  - {food_names.get(ft, ft)}: {recs.get(ft, {}).get('min', '?')}-{recs.get(ft, {}).get('max', '?')}g/day"
                for ft in ['vegetables', 'fruits', 'meat', 'eggs']
            ])
        else:
            food_names = {'vegetables': '蔬菜', 'fruits': '水果', 'meat': '肉类', 'eggs': '蛋类'}
            standard_lines = '\n'.join([
                f"  - {food_names.get(ft, ft)}: {recs.get(ft, {}).get('min', '?')}-{recs.get(ft, {}).get('max', '?')}g/天"
                for ft in ['vegetables', 'fruits', 'meat', 'eggs']
            ])
    else:
        standard_lines = ''

    if language == 'en-US':
        deficient_desc = '\n'.join([f"  - ⬇️ {d['name']}: current {d['intake']}g, need {d['gap']}g more to reach minimum" for d in deficient_foods]) if deficient_foods else '  - ✅ All food categories meet standards'

        prompt = f"""You are a professional nutritionist. Based on the user's TODAY intake, generate dietary recommendations for TOMORROW to fill nutrition gaps.

【Today's Intake vs UN/WHO Recommended Standards】
Daily reference ranges for {population_group} (WHO healthy-diet principles plus food-based dietary guidelines):
{standard_lines}

Actual TODAY intake:
  - Vegetables: {user_intake.get('vegetables', 0)}g
  - Fruits: {user_intake.get('fruits', 0)}g
  - Meat: {user_intake.get('meat', 0)}g
  - Eggs: {user_intake.get('eggs', 0)}g

【Nutrition Gaps — PRIORITIZE supplementing these TOMORROW】
{deficient_desc}

【Available Ingredients (Fridge)】
{ingredients_str if ingredients_str else 'Common household ingredients'}

【User Group】{population_group}

【⚠️ CORE TASK — Recommend TOMORROW's meals】
1. **Primary Goal**: Recommend TOMORROW's recipes that best supplement the DEFICIENT food categories above
2. **Secondary Goal**: Try to use available fridge ingredients when possible
3. If no fridge ingredients match the deficient category, suggest common ingredients from that category
4. Consider the digestion characteristics of {population_group}

【Output Format】
## Today's Nutrition Status Summary (one sentence)
## Tomorrow's Recommended Dishes (2-3, prioritize dishes that supplement deficiencies)
## Required Ingredients (with amounts)
## Brief Steps
## Nutritional Benefits (explain how each dish addresses the deficiency)

【Reply Requirements】
- Concise and focused on addressing nutrition gaps
- Use structured headings and lists
- ⚠️ IMPORTANT: For "Tomorrow's Recommended Dishes", MUST use numbered list format (1. 2. 3.)
- Avoid lengthy explanations
- Keep each dish suggestion under 60 words

Please respond entirely in English."""
    else:
        deficient_desc = '\n'.join([f"  - ⬇️ {d['name']}: 当前{d['intake']}g, 还差{d['gap']}g 达到最低推荐量" for d in deficient_foods]) if deficient_foods else '  - ✅ 所有食物类别均达标'

        prompt = f"""你是一位专业营养师。请根据用户**今日**的营养摄入情况，生成**明日**的饮食推荐，以弥补营养缺口。

【今日摄入 vs 饮食参考框架】
{population_group}的每日参考范围（WHO 健康饮食原则 + 食物膳食指南）:
{standard_lines}

今日实际摄入:
  - 蔬菜: {user_intake.get('vegetables', 0)}g
  - 水果: {user_intake.get('fruits', 0)}g
  - 肉类: {user_intake.get('meat', 0)}g
  - 蛋类: {user_intake.get('eggs', 0)}g

【营养缺口 — 明日优先补充以下类别】
{deficient_desc}

【冰箱可用食材】
{ingredients_str if ingredients_str else '家常常见食材'}

【用户人群】{population_group}

【⚠️ 核心任务 — 推荐明日食谱】
1. **首要目标**: 推荐最能补充上述"不足"类别的**明日**食谱
2. **次要目标**: 尽量使用冰箱已有的食材
3. 如果冰箱食材无法覆盖不足类别，请推荐该类别中的常见食材
4. 考虑{population_group}的消化特点

【输出格式】
## 今日营养状况总结（一句话）
## 明日推荐菜品（2-3个，优先补充不足类别）
## 所需食材及用量
## 简要步骤
## 营养功效（说明每个菜品如何弥补今日营养缺口）

【回复要求】
- 简洁明了，围绕补充营养缺口
- 使用结构化标题和列表
- ⚠️ 重要：在"明日推荐菜品"部分，必须使用有序数字列表格式（1. 2. 3.）
- 避免冗长解释
- 每条建议控制在60字以内"""
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        if api_result['success']:
            return api_result['content']
        else:
            return f"AI 生成失败:{api_result.get('error', '未知错误')}"
    except Exception as e:
        return f"生成推荐时出错:{str(e)}"

def get_smart_portion(ingredient_name):
    """智能获取食材份量：先查数据库，未知食材调用AI识别并缓存"""
    # 1. 先查本地数据库
    ing_en = INGREDIENT_MAP.get(ingredient_name, ingredient_name.lower())
    if ing_en in BASE_PORTIONS:
        return BASE_PORTIONS[ing_en]
    
    # 2. 本地没有，调用AI估算
    try:
        prompt = f"""请估算以下食材的标准份量（克/人）：
食材：{ingredient_name}
只需返回数字，不要其他文字。"""
        
        api_result = call_ai_api(prompt, api_type="auto")
        if api_result['success']:
            import re
            match = re.search(r'(\d+)', api_result['content'])
            if match:
                portion = int(match.group(1))
                # 缓存到内存中（本次运行有效）
                BASE_PORTIONS[ing_en] = portion
                INGREDIENT_MAP[ingredient_name] = ing_en
                print(f"✅ AI识别新食材: {ingredient_name} -> {ing_en} ({portion}g)")
                return portion
    except Exception as e:
        print(f"⚠️ AI识别食材失败: {e}，使用默认值")
    
    # 3. 失败则使用默认值
    return 100

def calculate_impact(ingredients, people_num=3, portion_coefficient=1.0, meal_type='home'):
    """计算环保影响"""
    total_portion = 0
    for ing in ingredients:
        # 🔑 关键改进：使用智能份量获取（数据库 + AI识别）
        base = get_smart_portion(ing)
        multiplier = MEAL_MULTIPLIERS.get(meal_type, 1.0) * portion_coefficient
        total_portion += base * people_num * multiplier

    traditional_portion = total_portion * (1 + WASTE_RATIO)
    waste_reduced = traditional_portion - total_portion
    water_saved = waste_reduced * ENV_FACTORS['water_per_g']
    co2_reduced = waste_reduced * ENV_FACTORS['co2_per_g']

    return {
        'food_waste': round(waste_reduced, 2),
        'water': round(water_saved, 2),
        'carbon': round(co2_reduced, 2)
    }

# ====================== 多语言支持 ======================
def get_language_from_request():
    """从请求中获取语言设置，默认为中文"""
    try:
        data = request.get_json(silent=True)
        if data and 'language' in data:
            return data['language']
    except:
        pass
    return 'zh-CN'

def build_recipe_prompt(ingredients, people_num, meal_type, appetite, use_fridge, language='zh-CN'):
    """根据语言构建食谱生成 Prompt"""
    
    # 根据餐型设置风格描述
    meal_style_map = {
        'home': {'zh': '家常菜（温馨实用、简单易做）', 'en': 'Home-style cooking (warm, practical, easy to make)'},
        'healthy': {'zh': '健康餐（低脂低糖、营养均衡）', 'en': 'Healthy meal (low-fat, low-sugar, nutritionally balanced)'},
        'vegetarian': {'zh': '素食（纯植物食材、营养丰富）', 'en': 'Vegetarian (plant-based ingredients, nutritionally rich)'},
        'banquet': {'zh': '宴客菜（精致美观、适合招待客人）', 'en': 'Banquet dish (elegant presentation, suitable for entertaining guests)'}
    }
    meal_style = meal_style_map.get(meal_type, meal_style_map['home'])
    
    if language == 'en-US':
        # 英文 Prompt
        ingredients_str = ', '.join(ingredients)
        fridge_data = load_data().get('fridge_inventory', [])
        fridge_item_names = [item['name'] for item in fridge_data[:5]]
        fridge_str = ', '.join(fridge_item_names) if fridge_item_names else 'None'
        
        prompt = f"""Please generate a family-friendly eco-friendly recipe based on the following ingredients:
【Basic Information】
- Main ingredients: {ingredients_str}
- Fridge ingredients: {fridge_str}
- Number of people: {people_num}
- Appetite level: {appetite}
- Meal type: {meal_style['en']}

【️ IMPORTANT PRINCIPLE: Reasonable combination, do not force mismatched ingredients!】
**This is the most important rule, please follow strictly:**
1. **If ingredients are not suitable to be mixed together, absolutely DO NOT force them into one dish!**
   - ❌ Wrong example: User inputs "milk, apple, egg" → Make "Milk Apple Scrambled Eggs" (disgusting!)
   - ✅ Correct example: User inputs "milk, apple, egg" → 
     * Breakfast Option 1: Boiled eggs with milk + fresh apple after meal
     * Breakfast Option 2: Steamed egg custard + warm milk + sliced apple
     * Breakfast Option 3: Apple milkshake + boiled egg
   
2. **Smart judgment of ingredient compatibility:**
   - 🥛 Beverages/Dairy (milk, soy milk, yogurt, etc.): Usually consumed separately or as drinks
   - 🍎 Fruits (apple, banana, orange, etc.): Usually eaten raw, in salads, or juiced, rarely stir-fried with meat
   - 🥚 Eggs: Can be scrambled, steamed, or boiled, but do not mix with fruits
   - 🥩 Meat + 🥬 Vegetables: Classic combination, can be cooked together
   - 🐟 Seafood + 🥬 Vegetables: Common combination
   - 🧀 Soy products + 🥬 Vegetables: Healthy combination
   
3. **Flexible dish organization:**
   - If ingredients are better consumed separately, design them as multiple independent dishes/drinks
   - For example: "milk, apple, egg" can be designed as:
     * Main dish: Steamed egg custard
     * Drink: Warm milk
     * Fruit: Sliced apple (after meal)
   
4. **Consider dining scenarios and time:**
   - Breakfast: Can be "main dish + drink + fruit" combination
   - Lunch/Dinner: Can be "main course + side dish + soup" combination
   - Snack: Can be individual fruit or drink

【Smart Dish Generation Rules】
1. **Prioritize user-input ingredients**:
   - ⭐ User-input ingredients ({ingredients_str}) must be the main ingredients
   - 🧊 Fridge ingredients ({fridge_str}) can be used as complementary or auxiliary ingredients
   - ✅ Each dish must clearly label which ingredients are 【User Input】 and which are 【Fridge Stock】

2. **Labeling format requirements**:
   In the 【Ingredients List】 of each dish, must label like this:
   - 【User Input】Main ingredient 1: xxx grams
   - 【Fridge Stock】Auxiliary: xxx grams
   
3. **If user inputs few ingredients**:
   - Can reasonably combine with common fridge ingredients
   - But must clearly label the source

4. **If user inputs many ingredients**:
   - Prioritize using user-input ingredients
   - Fridge ingredients as seasoning or side dishes

5. **Smartly decide number of dishes based on ingredient count**:
   - If user inputs ≤3 types of ingredients, can generate 1-2 dishes/drinks
   - If user inputs >3 types of ingredients, must generate multiple dishes (2-4), distribute ingredients reasonably across different dishes
   - **Key: Not all ingredients need to be mixed in one dish! Can handle separately based on ingredient characteristics**
   - Ensure all input ingredients are fully utilized to avoid waste

6. **Prioritize user-input ingredients as main ingredients**:
   - ⭐ **First priority**: User-input ingredients must be the **main ingredients** of each dish
   - ⭐ **Second priority**: Other auxiliary ingredients (onion, ginger, garlic, seasonings, side vegetables) are only supplements
   - ✅ Correct example: User inputs "potato, beef" → "Braised beef with potato" (both potato and beef are main ingredients)
   - ❌ Wrong example: User inputs "potato, beef" → "Stir-fried potato strips with green pepper" (green pepper is not user-input but becomes main ingredient)

7. **Reasonably combine ingredients, do not force same-type ingredients together**:
   - ❌ Wrong example: Stir-fry "potato, radish, winter melon, pumpkin" all in one dish (all vegetables, but unreasonable combination)
   - ✅ Correct example: "Braised beef with potato", "Shredded radish stir-fry", "Pumpkin scrambled eggs"
   - Each dish should contain different categories of ingredients (e.g., meat + vegetables, eggs + vegetables), nutritionally balanced

8. **Each dish must include the following complete structure**:
【Dish Name】xxx (should reflect "home-style" characteristic)
【Ingredient Category】xxx (e.g., Meat + Vegetables, Eggs + Soy Products, etc.)
【Ingredients List】
- Main ingredient 1: xxx grams (precise calculation, considering number of people and appetite level)
- Main ingredient 2: xxx grams
- Auxiliary: appropriate amount
【Cooking Steps】
Step 1: xxx
Step 2: xxx
Step 3: xxx
Step 4: xxx
Step 5: xxx
【Environmental Value】
- Estimated food waste reduced: xxx grams
- Estimated water saved: xxx liters
- Estimated carbon emissions reduced: xxx grams
- Environmental explanation: xxx

【General Requirements】
1. Identify the category of each ingredient (meat/vegetables/eggs/seafood/soy products, etc.) and provide specific cooking suggestions
2. Precisely calculate the amount (grams) of each ingredient, considering number of people and appetite level
3. Cooking steps should be detailed and clear (at least 5 steps)
4. **Important: Calculate environmental value data for each dish**
   - Food waste reduced (grams): Based on traditional practices would prepare 25% more food
   - Water saved (liters): Each gram of food consumes about 0.5 liters of water (China dietary weighted average)
   - Carbon emissions reduced (grams CO2e): Each gram of food emits about 3 grams CO2e (China dietary mixed average)

【Return Format Example】
If generating multiple dishes, list them sequentially in the following format:

=== Dish 1 ===
【Dish Name】xxx
【Ingredient Category】xxx
【Ingredients List】
- 【User Input】Main ingredient 1: xxx grams
- 【Fridge Stock】Auxiliary: xxx grams (if used)
【Cooking Steps】
Step 1: xxx
Step 2: xxx
Step 3: xxx
Step 4: xxx
Step 5: xxx
【Environmental Value】
- Estimated food waste reduced: xxx grams
- Estimated water saved: xxx liters
- Estimated carbon emissions reduced: xxx grams
- Environmental explanation: xxx

=== Dish 2 ===
...

Please respond entirely in English."""
    else:
        # 中文 Prompt (原有逻辑)
        if use_fridge and ingredients:
            fridge_data = load_data().get('fridge_inventory', [])
            fridge_item_names = [item['name'] for item in fridge_data[:5]]
            fridge_str = "、".join(fridge_item_names)
            
            prompt = f"""请根据以下食材生成家庭环保食谱：
【基本信息】
- 主要食材：{', '.join(ingredients)}
- 冰箱现有食材：{fridge_str}
- 就餐人数：{people_num}人
- 饭量系数：{appetite}
- 用餐类型：{meal_style['zh']}

【⚠️ 重要原则：合理搭配，不要硬凑！】
**这是最重要的规则，请务必遵守：**
1. **如果食材不适合混合在一起，绝对不要强行组合！**
   - ❌ 错误示例：用户输入“牛奶、苹果、鸡蛋”→ 做成“牛奶苹果炒鸡蛋”（非常恶心！）
   - ✅ 正确示例：用户输入“牛奶、苹果、鸡蛋”→ 
     * 早餐方案1：牛奶煮鸡蛋 + 餐后吃苹果
     * 早餐方案2：蒸鸡蛋羹 + 温牛奶 + 新鲜苹果切片
     * 早餐方案3：苹果牛奶昔 + 水煮蛋
   
2. **智能判断食材搭配的合理性：**
   - 🥛 饮品/乳制品类（牛奶、豆浆、酸奶等）：通常单独饮用或作为饮品搭配
   - 🍎 水果类（苹果、香蕉、橙子等）：通常生吃、做沙拉、榨汁，很少与肉类同炒
   - 🥚 蛋类：可以炒菜、蒸蛋、煮蛋，但不要与水果混炒
   - 🥩 肉类 + 🥬 蔬菜：经典搭配，可以一起烹饪
   - 🐟 水产 + 🥬 蔬菜：常见搭配
   - 🧀 豆制品 + 🥬 蔬菜：健康搭配
   
3. **灵活的菜品组织方式：**
   - 如果食材适合分开食用，就设计成多道独立的菜品/饮品
   - 例如：“牛奶、苹果、鸡蛋”可以设计为：
     * 主菜：蒸鸡蛋羹
     * 饮品：温牛奶
     * 水果：苹果切片（餐后食用）
   - 或者：“番茄、鸡蛋、面包”可以设计为：
     * 主菜：番茄炒蛋
     * 主食：烤面包片
   
4. **考虑用餐场景和时间：**
   - 早餐：可以是“主食 + 饮品 + 水果”的组合
   - 午餐/晚餐：可以是“主菜 + 配菜 + 汤”的组合
   - 加餐/零食：可以是单独的水果或饮品

【智能菜品生成规则】
1. **优先使用用户输入的食材**：
   - ⭐ 用户输入的食材（{', '.join(ingredients)}）必须作为主料
   - 🧊 冰箱食材（{fridge_str}）可以作为搭配或辅料
   - ✅ 每个菜品都必须标注哪些是【用户输入】的食材，哪些是【冰箱库存】的食材

2. **标注格式要求**：
   在每个菜品的【用料清单】中，必须这样标注：
   - 【用户输入】主料 1: xxx 克
   - 【冰箱库存】辅料：xxx 克
   
3. **如果用户输入的食材较少**：
   - 可以合理搭配冰箱中的常见食材
   - 但必须明确标注来源

4. **如果用户输入的食材较多**：
   - 优先使用用户输入的食材
   - 冰箱食材作为辅助调味或配菜

5. **根据食材数量智能决定菜品数量**：
   - 如果用户输入的食材种类≤3 种，可以只生成 1-2 个菜品/饮品
   - 如果用户输入的食材种类>3 种，必须生成多个菜品（2-4 个），合理分配食材到不同菜品中
   - **关键：不是所有食材都要混在一个菜里！可以根据食材特性分开处理**
   - 确保所有输入的食材都被充分利用，避免浪费

6. **优先使用用户输入的食材作为主料**：
   - ⭐ **第一优先级**：用户输入的食材必须作为每个菜品的**主料**（主要食材）
   - ⭐ **第二优先级**：其他辅料（葱姜蒜、调味料、配菜等）仅作为辅助，不要喧宾夺主
   - ✅ 正确示例：用户输入“土豆、牛肉”→ “土豆炖牛肉”（土豆和牛肉都是主料）
   - ❌ 错误示例：用户输入“土豆、牛肉”→ “青椒土豆丝”（青椒不是用户输入的，却成了主料）
   - 如果确实需要搭配其他食材，应该明确标注哪些是“主料”（用户输入的），哪些是“辅料”（额外搭配的）
   - 搭配的其他食材应该是常见的调味品或辅料（如葱姜蒜、酱油、盐等），而不是新的主菜食材

7. **合理搭配食材，不要硬凑同类型食材**：
   - ❌ 错误示例：把“土豆、萝卜、冬瓜、南瓜”全部炒在一个菜里（都是蔬菜，但搭配不合理）
   - ✅ 正确示例：“土豆炖牛肉”（土豆 + 肉类）、“清炒萝卜丝”（单独蔬菜）、“南瓜炒蛋”（南瓜 + 蛋类）
   - 每个菜品应该包含不同类别的食材（如：肉类 + 蔬菜、蛋类 + 蔬菜），营养均衡
   - 如果同类型食材过多（如 3 种蔬菜），应该分成不同的菜品，不要全部堆在一起

8. **每个菜品都必须包含以下完整结构**：
   【菜名】xxx（根据用餐类型调整风格：家常菜要温馨实用、健康餐要低脂低糖、素食要营养丰富、宴客菜要精致美观）
   【食材类别】xxx（如：肉类 + 蔬菜类、蛋类 + 豆制品等）
   【用料清单】
   - 主料 1: xxx 克（精准计算，考虑人数和饭量系数）
   - 主料 2: xxx 克
   - 辅料：适量
   【制作步骤】
   步骤 1: xxx
   步骤 2: xxx
   步骤 3: xxx
   步骤 4: xxx
   步骤 5: xxx
   【环保价值】
   - 预计减少食物浪费：xxx 克
   - 预计节约水资源：xxx 升
   - 预计减少碳排放：xxx 克
   - 环保说明：xxx

【通用要求】
1. 识别每种食材的类别（肉类/蔬菜/蛋类/水产/豆制品等）并给予专属烹饪建议
2. 精准计算每种食材的用量（克数），考虑人数和饭量系数
3. 制作步骤详细清晰（至少 5 步）
4. **重点：为每个菜品计算环保价值数据**
   - 减少食物浪费（克）：基于传统做法会多准备 25% 的食物
   - 节约水资源（升）：每克食物约消耗 0.5 升水（中国膳食加权平均）
   - 减少碳排放（克 CO2e）：每克食物约排放 3 克 CO2e（中国膳食混合平均）

【返回格式示例】
如果生成多个菜品，请按以下格式依次列出：

=== 菜品 1 ===
【菜名】xxx
【食材类别】xxx
【用料清单】
- 【用户输入】主料 1: xxx 克
- 【冰箱库存】辅料：xxx 克（如果有使用）
【制作步骤】
步骤 1: xxx
步骤 2: xxx
步骤 3: xxx
步骤 4: xxx
步骤 5: xxx
【环保价值】
- 预计减少食物浪费：xxx 克
- 预计节约水资源：xxx 升
- 预计减少碳排放：xxx 克
- 环保说明：xxx

=== 菜品 2 ===
...

请用中文回答。"""
        else:
            # 不使用冰箱食材的情况
            prompt = f"""请根据以下食材生成家庭环保食谱：
【基本信息】
- 主要食材：{', '.join(ingredients)}
- 就餐人数：{people_num}人
- 饭量系数：{appetite}
- 用餐类型：{meal_style['zh']}

【⚠️ 重要原则：合理搭配，不要硬凑！】
**这是最重要的规则，请务必遵守：**
1. **如果食材不适合混合在一起，绝对不要强行组合！**
   - ❌ 错误示例：用户输入“牛奶、苹果、鸡蛋”→ 做成“牛奶苹果炒鸡蛋”（非常恶心！）
   - ✅ 正确示例：用户输入“牛奶、苹果、鸡蛋”→ 
     * 早餐方案1：牛奶煮鸡蛋 + 餐后吃苹果
     * 早餐方案2：蒸鸡蛋羹 + 温牛奶 + 新鲜苹果切片
     * 早餐方案3：苹果牛奶昔 + 水煮蛋
   
2. **智能判断食材搭配的合理性：**
   - 🥛 饮品/乳制品类（牛奶、豆浆、酸奶等）：通常单独饮用或作为饮品搭配
   - 🍎 水果类（苹果、香蕉、橙子等）：通常生吃、做沙拉、榨汁，很少与肉类同炒
   - 🥚 蛋类：可以炒菜、蒸蛋、煮蛋，但不要与水果混炒
   - 🥩 肉类 + 🥬 蔬菜：经典搭配，可以一起烹饪
   - 🐟 水产 + 🥬 蔬菜：常见搭配
   - 🧀 豆制品 + 🥬 蔬菜：健康搭配
   
3. **灵活的菜品组织方式：**
   - 如果食材适合分开食用，就设计成多道独立的菜品/饮品
   - 例如：“牛奶、苹果、鸡蛋”可以设计为：
     * 主菜：蒸鸡蛋羹
     * 饮品：温牛奶
     * 水果：苹果切片（餐后食用）
   - 或者：“番茄、鸡蛋、面包”可以设计为：
     * 主菜：番茄炒蛋
     * 主食：烤面包片
   
4. **考虑用餐场景和时间：**
   - 早餐：可以是“主食 + 饮品 + 水果”的组合
   - 午餐/晚餐：可以是“主菜 + 配菜 + 汤”的组合
   - 加餐/零食：可以是单独的水果或饮品

【智能菜品生成规则】
1. **优先使用用户输入的食材**：
   - ⭐ 用户输入的食材（{', '.join(ingredients)}）必须作为主料
   - ✅ 每个菜品都必须以用户输入的食材为主料

2. **根据食材数量智能决定菜品数量**：
   - 如果用户输入的食材种类≤3 种，可以只生成 1-2 个菜品/饮品
   - 如果用户输入的食材种类>3 种，必须生成多个菜品（2-4 个），合理分配食材到不同菜品中
   - **关键：不是所有食材都要混在一个菜里！可以根据食材特性分开处理**
   - 确保所有输入的食材都被充分利用，避免浪费

3. **优先使用用户输入的食材作为主料**：
   - ⭐ **第一优先级**：用户输入的食材必须作为每个菜品的**主料**（主要食材）
   - ⭐ **第二优先级**：其他辅料（葱姜蒜、调味料、配菜等）仅作为辅助，不要喧宾夺主
   - ✅ 正确示例：用户输入“土豆、牛肉”→ “土豆炖牛肉”（土豆和牛肉都是主料）
   - ❌ 错误示例：用户输入“土豆、牛肉”→ “青椒土豆丝”（青椒不是用户输入的，却成了主料）

4. **合理搭配食材，不要硬凑同类型食材**：
   - ❌ 错误示例：把“土豆、萝卜、冬瓜、南瓜”全部炒在一个菜里（都是蔬菜，但搭配不合理）
   - ✅ 正确示例：“土豆炖牛肉”（土豆 + 肉类）、“清炒萝卜丝”（单独蔬菜）、“南瓜炒蛋”（南瓜 + 蛋类）
   - 每个菜品应该包含不同类别的食材（如：肉类 + 蔬菜、蛋类 + 蔬菜），营养均衡

5. **每个菜品都必须包含以下完整结构**：
   【菜名】xxx（根据用餐类型调整风格：家常菜要温馨实用、健康餐要低脂低糖、素食要营养丰富、宴客菜要精致美观）
   【食材类别】xxx（如：肉类 + 蔬菜类、蛋类 + 豆制品等）
   【用料清单】
   - 主料 1: xxx 克（精准计算，考虑人数和饭量系数）
   - 主料 2: xxx 克
   - 辅料：适量
   【制作步骤】
   步骤 1: xxx
   步骤 2: xxx
   步骤 3: xxx
   步骤 4: xxx
   步骤 5: xxx
   【环保价值】
   - 预计减少食物浪费：xxx 克
   - 预计节约水资源：xxx 升
   - 预计减少碳排放：xxx 克
   - 环保说明：xxx

【通用要求】
1. 识别每种食材的类别（肉类/蔬菜/蛋类/水产/豆制品等）并给予专属烹饪建议
2. 精准计算每种食材的用量（克数），考虑人数和饭量系数
3. 制作步骤详细清晰（至少 5 步）
4. **重点：为每个菜品计算环保价值数据**
   - 减少食物浪费（克）：基于传统做法会多准备 25% 的食物
   - 节约水资源（升）：每克食物约消耗 0.5 升水（中国膳食加权平均）
   - 减少碳排放（克 CO2e）：每克食物约排放 3 克 CO2e（中国膳食混合平均）

【返回格式示例】
如果生成多个菜品，请按以下格式依次列出：

=== 菜品 1 ===
【菜名】xxx
【食材类别】xxx
【用料清单】
- 主料 1: xxx 克
- 主料 2: xxx 克
【制作步骤】
步骤 1: xxx
步骤 2: xxx
步骤 3: xxx
步骤 4: xxx
步骤 5: xxx
【环保价值】
- 预计减少食物浪费：xxx 克
- 预计节约水资源：xxx 升
- 预计减少碳排放：xxx 克
- 环保说明：xxx

=== 菜品 2 ===
...

请用中文回答。"""
    
    return prompt

# ====================== Flask 路由 ======================
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/locales/<lang>.json')
def get_locale_file(lang):
    """提供语言文件"""
    from flask import send_from_directory
    try:
        return send_from_directory('locales', f'{lang}.json')
    except:
        # 降级到中文
        return send_from_directory('locales', 'zh-CN.json')

# ====================== 账号认证接口 ======================
USERNAME_RE = re.compile(r'^[\w\u4e00-\u9fff]{2,24}$')


def auth_attempt_key(username):
    return f"{request.remote_addr or 'local'}:{username.strip().lower()}"


def get_auth_lock_remaining(username):
    """返回账号当前剩余锁定秒数。"""
    key = auth_attempt_key(username)
    now = get_china_time()
    with _auth_failures_lock:
        state = _auth_failures.get(key)
        if not state:
            return 0
        locked_until = state.get('locked_until')
        if locked_until and locked_until > now:
            return max(1, int((locked_until - now).total_seconds()))
        if locked_until or now - state.get('first_at', now) > AUTH_FAILURE_WINDOW:
            _auth_failures.pop(key, None)
        return 0


def record_auth_failure(username):
    """记录失败尝试，15 分钟内 5 次失败后锁定 15 分钟。"""
    key = auth_attempt_key(username)
    now = get_china_time()
    with _auth_failures_lock:
        state = _auth_failures.get(key)
        if not state or now - state.get('first_at', now) > AUTH_FAILURE_WINDOW:
            state = {'count': 0, 'first_at': now, 'locked_until': None}
        state['count'] += 1
        if state['count'] >= AUTH_MAX_FAILURES:
            state['locked_until'] = now + AUTH_LOCK_DURATION
        _auth_failures[key] = state
        return state['count'], state.get('locked_until')


def clear_auth_failures(username):
    with _auth_failures_lock:
        _auth_failures.pop(auth_attempt_key(username), None)


def generate_recovery_code():
    """生成仅向用户展示一次的账号恢复码。"""
    return secrets.token_hex(6).upper()


def update_user_credentials(user, backend, password_hash=None, recovery_hash=None):
    if backend == 'local':
        return local_update_credentials(user['id'], password_hash, recovery_hash)
    update = {}
    if password_hash is not None:
        update['password_hash'] = password_hash
    if recovery_hash is not None:
        update['recovery_hash'] = recovery_hash
    if not update:
        return True
    return db_request('PATCH', 'users', params={'id': f"eq.{user['id']}"},
                      json_body=update) is not None

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    """注册新账号（成功后自动登录）"""
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''

    if not is_auth_enabled():
        return jsonify({'success': False, 'error': '服务器未配置数据库，暂不支持账号功能'})
    if not USERNAME_RE.match(username):
        return jsonify({'success': False, 'error': '用户名需为 2-24 位字母、数字、下划线或中文'})
    if len(password) < 6:
        return jsonify({'success': False, 'error': '密码长度至少 6 位'})

    recovery_code = generate_recovery_code()
    recovery_hash = generate_password_hash(recovery_code)
    user = None
    backend = None

    if is_db_configured():
        # 优先使用 Supabase；本地网络/权限导致失败时自动兜底到 SQLite。
        exists = db_request('GET', 'users', params={'username': f'eq.{username}', 'select': 'id'})
        if exists is not None:
            if len(exists) > 0:
                return jsonify({'success': False, 'error': '该用户名已被注册'})
            created = db_request('POST', 'users',
                                 json_body=[{'username': username,
                                             'password_hash': generate_password_hash(password),
                                             'recovery_hash': recovery_hash}],
                                 extra_headers={'Prefer': 'return=representation'})
            if not created:
                return jsonify({'success': False, 'error': '注册失败，请稍后重试'})
            user = created[0]
            backend = 'supabase'
        else:
            print('⚠️ [Auth] Supabase 不可用，注册自动切换到本地账号数据库')

    if user is None:
        existing_local = local_get_user_by_username(username)
        if existing_local:
            return jsonify({'success': False, 'error': '该用户名已被注册'})
        created_local = local_create_user(
            username, generate_password_hash(password), recovery_hash
        )
        if created_local and created_local.get('error') == 'exists':
            return jsonify({'success': False, 'error': '该用户名已被注册'})
        if not created_local:
            return jsonify({'success': False, 'error': '数据库连接失败，请稍后重试'})
        user = created_local
        backend = 'local'

    session.permanent = True
    session['user_id'] = user['id']
    session['username'] = username
    session['auth_backend'] = backend
    session['last_activity_at'] = get_china_time().isoformat()

    if backend == 'local':
        saved_ok = local_ensure_user_data_row(user['id'], username)
    else:
        # 初始化该账号的独立数据，不继承游客或其他账号记录。
        initial_data = build_initial_user_data(username)
        saved_ok = db_request('POST', 'user_data',
                              json_body=[{'user_id': user['id'], 'data': initial_data,
                                          'updated_at': get_china_time().isoformat()}],
                              extra_headers={'Prefer': 'resolution=merge-duplicates'}) is not None
    if not saved_ok:
        session.clear()
        return jsonify({'success': False, 'error': '数据库连接失败，请稍后重试'})

    clear_auth_failures(username)
    return jsonify({'success': True,
                    'user': {'id': user['id'], 'username': username},
                    'recovery_code': recovery_code})

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """登录"""
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''

    if not is_auth_enabled():
        return jsonify({'success': False, 'error': '服务器未配置数据库，暂不支持账号功能'})
    if not username or not password:
        return jsonify({'success': False, 'error': '请输入用户名和密码'})

    lock_remaining = get_auth_lock_remaining(username)
    if lock_remaining:
        return jsonify({
            'success': False,
            'error': '登录失败次数过多，请稍后重试',
            'retry_after': lock_remaining
        }), 429

    user = None
    backend = None
    if is_db_configured():
        rows = db_request('GET', 'users',
                          params={'username': f'eq.{username}',
                                  'select': 'id,username,password_hash,recovery_hash'})
        if rows is not None:
            if rows:
                user = rows[0]
                backend = 'supabase'
        else:
            print('⚠️ [Auth] Supabase 不可用，登录自动切换到本地账号数据库')

    if user is None:
        user = local_get_user_by_username(username)
        backend = 'local' if user else None

    if not user:
        record_auth_failure(username)
        return jsonify({'success': False, 'error': '没有该账号，请先注册'})

    if not check_password_hash(user['password_hash'], password):
        _, locked_until = record_auth_failure(username)
        if locked_until:
            return jsonify({
                'success': False,
                'error': '登录失败次数过多，账号已锁定 15 分钟',
                'retry_after': int(AUTH_LOCK_DURATION.total_seconds())
            }), 429
        return jsonify({'success': False, 'error': '密码错误，请重新输入'})

    clear_auth_failures(username)
    recovery_code = None
    if not user.get('recovery_hash'):
        recovery_code = generate_recovery_code()
        update_user_credentials(
            user, backend, recovery_hash=generate_password_hash(recovery_code)
        )

    session.permanent = True
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['auth_backend'] = backend
    session['last_activity_at'] = get_china_time().isoformat()
    if not ensure_user_data_row(user['id'], user['username']):
        session.clear()
        return jsonify({'success': False, 'error': '数据库连接失败，请稍后重试'})
    result = {'success': True,
              'user': {'id': user['id'], 'username': user['username']}}
    if recovery_code:
        result['recovery_code'] = recovery_code
    return jsonify(result)


@app.route('/api/auth/recover', methods=['POST'])
def auth_recover():
    """使用注册时发放的恢复码重设密码。"""
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    recovery_code = (body.get('recovery_code') or '').strip().upper()
    new_password = body.get('new_password') or ''
    if not username or not recovery_code:
        return jsonify({'success': False, 'error': '请输入用户名和恢复码'}), 400
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': '密码长度至少 6 位'}), 400
    lock_remaining = get_auth_lock_remaining(username)
    if lock_remaining:
        return jsonify({
            'success': False,
            'error': '尝试次数过多，请稍后重试',
            'retry_after': lock_remaining
        }), 429

    user, backend = None, None
    if is_db_configured():
        rows = db_request('GET', 'users', params={
            'username': f'eq.{username}',
            'select': 'id,username,password_hash,recovery_hash'
        })
        if rows:
            user, backend = rows[0], 'supabase'
    if user is None:
        user = local_get_user_by_username(username)
        backend = 'local' if user else None
    if not user or not user.get('recovery_hash') or not check_password_hash(
            user['recovery_hash'], recovery_code):
        record_auth_failure(username)
        return jsonify({'success': False, 'error': '账号或恢复码不正确'}), 400

    new_recovery_code = generate_recovery_code()
    if not update_user_credentials(
        user, backend,
        password_hash=generate_password_hash(new_password),
        recovery_hash=generate_password_hash(new_recovery_code)
    ):
        return jsonify({'success': False, 'error': '数据库连接失败，请稍后重试'}), 503
    clear_auth_failures(username)
    return jsonify({'success': True, 'recovery_code': new_recovery_code})

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """退出登录"""
    compact_user_storage(session.get('user_id'), get_current_auth_backend())
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    """查询当前登录状态"""
    return jsonify({'success': True, 'user': get_current_user(),
                    'auth_enabled': is_auth_enabled(),
                    'session_expired': bool(getattr(g, 'auth_session_expired', False))})

@app.route('/api/data', methods=['GET'])
def get_data():
    """获取用户数据"""
    raw_data = load_data()
    data = sanitize_persisted_user_data(raw_data)

    # 🔑 关键修复：确保旧数据文件也包含新字段
    need_save = data != raw_data
    if 'generation_count' not in data:
        data['generation_count'] = 0
        need_save = True
        print('🔧 [数据迁移] 已为旧数据添加 generation_count 字段')

    if need_save:
        save_data(data)  # 立即清理旧聊天记录/过期摄入记录，避免下次再出现

    # auth_enabled: 服务器是否启用了账号系统（前端据此决定是否强制登录）
    return jsonify({'success': True, 'data': data, 'user': get_current_user(),
                    'auth_enabled': is_auth_enabled(),
                    'session_expired': bool(getattr(g, 'auth_session_expired', False))})

@app.route('/api/data', methods=['POST'])
def update_data():
    """更新用户数据"""
    new_data = request.json
    current_data = load_data()
    current_data.update(new_data)
    current_data = sanitize_persisted_user_data(current_data)
    save_data(current_data)
    return jsonify({'success': True, 'data': current_data})

@app.route('/api/generate_recipe', methods=['POST'])
def generate_recipe():
    """生成智能食谱"""
    data = request.json
    custom_ingredients = data.get('custom_ingredients', '')
    people_num = data.get('people_num', 3)
    meal_type = data.get('meal_type', 'home')
    appetite = data.get('appetite', 1.0)
    use_fridge = data.get('use_fridge', False)
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    # 解析食材
    ingredients = [i.strip() for i in custom_ingredients.split(',') if i.strip()]
    
    if use_fridge:
        fridge_data = load_data().get('fridge_inventory', [])
        fridge_ingredients = [item['name'] for item in fridge_data[:5]]
        ingredients.extend(fridge_ingredients)
    
    if not ingredients:
        error_msg = '请至少输入一种食材' if language == 'zh-CN' else 'Please enter at least one ingredient'
        return jsonify({'success': False, 'error': error_msg})
    
    # 🌐 使用多语言 Prompt 构建函数
    prompt = build_recipe_prompt(ingredients, people_num, meal_type, appetite, use_fridge, language)
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            # 计算环保影响
            impact = calculate_impact(ingredients, people_num, appetite, meal_type)
            
            return jsonify({
                'success': True,
                'recipe': api_result['content'],
                'impact': impact
            })
        else:
            return jsonify({
                'success': False,
                'error': f"AI 生成失败:{api_result.get('error', '未知错误')}"
            })
    except Exception as e:
        return jsonify({'success': False, 'error': f'服务器错误:{str(e)}'})

@app.route('/api/calculate_impact', methods=['POST'])
def calculate_impact_api():
    """仅计算环保影响，不生成食谱（用于实时更新）"""
    data = request.json
    custom_ingredients = data.get('custom_ingredients', '')
    people_num = data.get('people_num', 3)
    appetite = data.get('appetite', 1.0)
    meal_type = data.get('meal_type', 'home')  # 🔑 新增：接收用餐类型
    
    # 解析食材
    ingredients = [i.strip() for i in custom_ingredients.split(',') if i.strip()]
    
    if not ingredients:
        return jsonify({'success': False, 'error': '请至少输入一种食材'})
    
    # 使用本地公式快速计算
    impact = calculate_impact(ingredients, people_num, appetite, meal_type)
    
    return jsonify({
        'success': True,
        'impact': impact
    })

@app.route('/api/nutrition_assess', methods=['POST'])
def nutrition_assess():
    """营养评估 - 返回格式化报告"""
    data = request.json
    user_intake = data.get('user_intake', {})
    population_group = data.get('population_group', 'adults')
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    try:
        # 检查是否为"以上皆是"模式
        if population_group == 'all':
            # 生成多人群对比报告
            report = generate_multi_group_nutrition_report(user_intake, language)
        else:
            # 生成单人群报告
            report = generate_nutrition_report(user_intake, population_group, language)
        
        return jsonify({'success': True, 'report': report})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/daily_recommendation', methods=['POST'])
def daily_recommendation():
    """明日饮食推荐（基于今日摄入缺口）"""
    data = request.json
    user_intake = data.get('user_intake', {})
    population_group = data.get('population_group', 'adults')
    fridge_items = data.get('fridge_items', [])
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    try:
        recommendation = generate_daily_recommendation(user_intake, population_group, fridge_items, language)
        return jsonify({'success': True, 'recommendation': recommendation})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/personalized_plan', methods=['POST'])
def personalized_plan():
    """个性化饮食方案"""
    data = request.json
    user_intake = data.get('user_intake', {})
    population_group = data.get('population_group', 'adults')
    fridge_items = data.get('fridge_items', [])
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    try:
        plan = generate_personalized_plan(user_intake, population_group, fridge_items, language)
        return jsonify({'success': True, 'plan': plan})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/save_intake', methods=['POST'])
def save_intake():
    """保存摄入数据"""
    data = request.get_json(silent=True) or {}

    def parse_intake_value(field):
        value = data.get(field, 0)
        if isinstance(value, bool):
            raise ValueError
        number = float(value)
        if not 0 <= number <= 100000:
            raise ValueError
        return round(number, 1)

    try:
        validated = {
            field: parse_intake_value(field)
            for field in ('vegetables', 'fruits', 'meat', 'eggs')
        }
    except (TypeError, ValueError):
        return jsonify({
            'success': False,
            'error': '摄入量必须是 0 到 100000 克之间的数字'
        }), 400

    meal_type = str(data.get('meal_type') or '').strip().lower()
    current_time = get_china_time().strftime('%H:%M')
    if meal_type not in VALID_MEAL_TYPES:
        meal_type = infer_meal_type(current_time)
    source = str(data.get('source') or 'manual').strip().lower()[:24]
    intake_record = {
        'id': str(uuid.uuid4()),
        'date': get_china_time().strftime('%Y-%m-%d'),
        'time': current_time,
        'meal_type': meal_type,
        'source': source,
        **validated
    }
    
    current_data = load_data()
    if 'daily_intake_records' not in current_data:
        current_data['daily_intake_records'] = []
    
    current_data['daily_intake_records'].append(intake_record)

    # 🔐 真实数据保存：今日记录不限条数（三餐 + 加餐/零食），全部真实保留到该账号的数据库
    save_data(current_data)
    
    # 检查是否需要预警
    population_group = current_data.get('population_group', 'adults')
    today_records = [r for r in current_data['daily_intake_records'] if r['date'] == intake_record['date']]
    
    print(f"\n📊 [save_intake] 今日记录数: {len(today_records)}")
    for i, r in enumerate(today_records):
        print(f"   记录{i+1}: 蔬菜{r.get('vegetables', 0)}g, 水果{r.get('fruits', 0)}g, 肉类{r.get('meat', 0)}g, 蛋类{r.get('eggs', 0)}g")
    
    # 汇总今日全部真实记录进行营养评估
    total_intake = {
        'vegetables': sum(r.get('vegetables', 0) for r in today_records),
        'fruits': sum(r.get('fruits', 0) for r in today_records),
        'meat': sum(r.get('meat', 0) for r in today_records),
        'eggs': sum(r.get('eggs', 0) for r in today_records)
    }
    
    print(f"📊 [save_intake] 今日总摄入: 蔬菜{total_intake['vegetables']}g, 水果{total_intake['fruits']}g, 肉类{total_intake['meat']}g, 蛋类{total_intake['eggs']}g")
    print(f"   📝 记录数: {len(today_records)}条 (全部真实保留)\n")
    
    # 🆕 关键改进：基于联合国标准的智能预警（针对三餐总和）
    warnings = []
    standard = get_nutrition_standard(population_group)
    
    if standard:
        daily_recs = standard['daily_recommendations']
        
        # 检查蔬菜
        veg_rec = daily_recs.get('vegetables', {})
        veg_min = veg_rec.get('min', 400)
        veg_max = veg_rec.get('max', 800)
        if total_intake['vegetables'] < veg_min * 0.5:  # 低于50%推荐最小值
            warnings.append(f"🥬 蔬菜摄入严重不足（当前{total_intake['vegetables']}g，推荐{veg_min}-{veg_max}g/天），建议增加至{veg_min}g以上")
        elif total_intake['vegetables'] < veg_min:  # 低于推荐最小值
            warnings.append(f"🥬 蔬菜摄入略少（当前{total_intake['vegetables']}g，推荐{veg_min}-{veg_max}g/天），建议适当增加")
        elif total_intake['vegetables'] > veg_max:  # 超过推荐最大值
            warnings.append(f"⚠️ 蔬菜摄入超标（当前{total_intake['vegetables']}g，推荐{veg_min}-{veg_max}g/天），建议后续餐次控制")
        
        # 检查水果
        fruit_rec = daily_recs.get('fruits', {})
        fruit_min = fruit_rec.get('min', 200)
        fruit_max = fruit_rec.get('max', 400)
        if total_intake['fruits'] < fruit_min * 0.5:
            warnings.append(f"🍎 水果摄入严重不足（当前{total_intake['fruits']}g，推荐{fruit_min}-{fruit_max}g/天），建议补充")
        elif total_intake['fruits'] < fruit_min:
            warnings.append(f"🍎 水果摄入略少（当前{total_intake['fruits']}g，推荐{fruit_min}-{fruit_max}g/天），建议适当增加")
        elif total_intake['fruits'] > fruit_max:
            warnings.append(f"⚠️ 水果摄入超标（当前{total_intake['fruits']}g，推荐{fruit_min}-{fruit_max}g/天），建议控制")
        
        # 检查肉类
        meat_rec = daily_recs.get('meat', {})
        meat_min = meat_rec.get('min', 50)
        meat_max = meat_rec.get('max', 150)
        if total_intake['meat'] < meat_min * 0.5:
            warnings.append(f"🥩 肉类摄入严重不足（当前{total_intake['meat']}g，推荐{meat_min}-{meat_max}g/天），建议增加蛋白质")
        elif total_intake['meat'] < meat_min:
            warnings.append(f"🥩 肉类摄入略少（当前{total_intake['meat']}g，推荐{meat_min}-{meat_max}g/天），建议适当增加")
        elif total_intake['meat'] > meat_max:
            warnings.append(f"⚠️ 肉类摄入超标（当前{total_intake['meat']}g，推荐{meat_min}-{meat_max}g/天），建议减少红肉，增加鱼类")
        
        # 检查蛋类
        egg_rec = daily_recs.get('eggs', {})
        egg_min = egg_rec.get('min', 30)
        egg_max = egg_rec.get('max', 70)
        if total_intake['eggs'] < egg_min * 0.5:
            warnings.append(f"🥚 蛋类摄入严重不足（当前{total_intake['eggs']}g，推荐{egg_min}-{egg_max}g/天），建议补充")
        elif total_intake['eggs'] < egg_min:
            warnings.append(f"🥚 蛋类摄入略少（当前{total_intake['eggs']}g，推荐{egg_min}-{egg_max}g/天），建议适当增加")
        elif total_intake['eggs'] > egg_max:
            warnings.append(f"⚠️ 蛋类摄入超标（当前{total_intake['eggs']}g，推荐{egg_min}-{egg_max}g/天），建议控制")
    else:
        # 降级方案：使用简化的预警逻辑
        for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
            amount = total_intake.get(food_type, 0)  # 🔑 修复：使用今日总和而非单条记录
            if amount > 0:
                if food_type == 'meat' and total_intake['meat'] > 300:
                    warnings.append(f"⚠️ 肉类摄入偏高,建议减少红肉,增加鱼类")
                elif food_type == 'vegetables' and total_intake['vegetables'] < 100:
                    warnings.append(f"🥬 蔬菜摄入严重不足,建议增加至300g以上")
    
    return jsonify({
        'success': True,
        'record': intake_record,
        'warnings': warnings,
        'total_intake': total_intake
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """AI 对话助手"""
    data = request.json
    message = data.get('message', '')
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    # 🌐 根据语言构建Prompt
    if language == 'en-US':
        prompt = f"""You are a professional smart recipe assistant.

[Response Requirements]
- Be concise and clear, focus on key points only
- Avoid lengthy explanations and background introductions
- Use bullet points instead of long paragraphs
- Keep responses under 200 words
- Provide practical advice directly

User question: {message}

Please respond in a friendly and professional tone in English."""
    else:
        prompt = f"""你是一个专业的智能食谱助手。

【回复要求】
- 简洁明了，只回答重点内容
- 避免冗长的解释和背景介绍
- 使用要点列表而非长段落
- 控制在200字以内
- 直接给出实用建议

用户问题:{message}

请用友好、专业的语气回答。"""
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            return jsonify({'success': True, 'reply': api_result['content']})
        else:
            return jsonify({'success': False, 'error': f"AI 回复失败:{api_result.get('error', '未知错误')}"})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ====================== SSE 流式输出 API ======================

def _sse_response(generator, done_data=None):
    """将生成器包装为 SSE Response"""
    def sse_generator():
        for chunk in generator:
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        if done_data:
            yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(sse_generator()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@app.route('/api/generate_recipe_stream', methods=['POST'])
def generate_recipe_stream():
    """生成智能食谱 - SSE流式输出"""
    data = request.json
    custom_ingredients = data.get('custom_ingredients', '')
    people_num = data.get('people_num', 3)
    meal_type = data.get('meal_type', 'home')
    appetite = data.get('appetite', 1.0)
    use_fridge = data.get('use_fridge', False)
    language = data.get('language', 'zh-CN')

    ingredients = [i.strip() for i in custom_ingredients.split(',') if i.strip()]

    if use_fridge:
        fridge_data = load_data().get('fridge_inventory', [])
        fridge_ingredients = [item['name'] for item in fridge_data[:5]]
        ingredients.extend(fridge_ingredients)

    if not ingredients:
        def error_gen():
            msg = '请至少输入一种食材' if language == 'zh-CN' else 'Please enter at least one ingredient'
            yield f"data: {json.dumps({'error': msg}, ensure_ascii=False)}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    prompt = build_recipe_prompt(ingredients, people_num, meal_type, appetite, use_fridge, language)
    impact = calculate_impact(ingredients, people_num, appetite, meal_type)

    def generate():
        full_content = ""
        for chunk in call_ai_api_stream(prompt):
            stream_error = extract_ai_stream_error(chunk)
            if stream_error:
                yield f"data: {json.dumps({'error': stream_error}, ensure_ascii=False)}\n\n"
                return
            full_content += chunk
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True, 'impact': impact, 'full_content': full_content}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@app.route('/api/chat_stream', methods=['POST'])
def chat_stream():
    """AI 对话助手 - SSE流式输出"""
    data = request.json
    message = data.get('message', '')
    language = data.get('language', 'zh-CN')

    if language == 'en-US':
        prompt = f"""You are a professional smart recipe assistant.

[Response Requirements]
- Be concise and clear, focus on key points only
- Avoid lengthy explanations and background introductions
- Use bullet points instead of long paragraphs
- Keep responses under 200 words
- Provide practical advice directly

User question: {message}

Please respond in a friendly and professional tone in English."""
    else:
        prompt = f"""你是一个专业的智能食谱助手。

【回复要求】
- 简洁明了，只回答重点内容
- 避免冗长的解释和背景介绍
- 使用要点列表而非长段落
- 控制在200字以内
- 直接给出实用建议

用户问题:{message}

请用友好、专业的语气回答。"""

    def generate():
        full_content = ""
        for chunk in call_ai_api_stream(prompt):
            stream_error = extract_ai_stream_error(chunk)
            if stream_error:
                yield f"data: {json.dumps({'error': stream_error}, ensure_ascii=False)}\n\n"
                return
            full_content += chunk
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True, 'full_content': full_content}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


def shopping_price_context(preferences, region, language='zh-CN'):
    """汇总同地区历史实际价格，作为 AI 预算校准信号。"""
    samples = (preferences or {}).get('price_samples') or []
    matched = [s for s in samples if s.get('region') == region][-5:]
    if not matched:
        return ''
    average = round(sum(float(s.get('actual_total', 0)) for s in matched) / len(matched), 2)
    if language == 'en-US':
        return (f"\n- User price feedback for this region: {len(matched)} recent purchase(s), "
                f"average actual total RMB {average}. Use it only as a calibration reference "
                "and still account for dish contents and serving count.")
    return (f"\n- 用户在该地区有 {len(matched)} 条近期实付样本，平均总价约 {average} 元。"
            "仅作为校准参考，仍需按本次菜品和人数调整。")


@app.route('/api/shopping/preferences', methods=['GET', 'POST'])
def shopping_preferences():
    """读写常用采购地区，不保存 AI 对话内容。"""
    current_data = load_data()
    preferences = current_data.get('shopping_preferences') or {}
    if request.method == 'GET':
        return jsonify({'success': True, 'preferences': preferences})
    body = request.get_json(silent=True) or {}
    preferences['province'] = str(body.get('province') or '')[:30]
    preferences['city'] = str(body.get('city') or '')[:30]
    preferences.setdefault('price_samples', [])
    current_data['shopping_preferences'] = preferences
    save_data(current_data)
    return jsonify({'success': True, 'preferences': preferences})


@app.route('/api/shopping/price-feedback', methods=['POST'])
def shopping_price_feedback():
    """保存用户输入的实际采购总价，最多保留 20 条样本。"""
    body = request.get_json(silent=True) or {}
    try:
        actual_total = round(float(body.get('actual_total')), 2)
        people_num = max(1, min(int(body.get('people_num', 1)), 20))
        if not 0 < actual_total <= 1000000:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': '请输入有效的实际总价'}), 400
    region = re.sub(r'[\r\n\t]+', ' ', str(body.get('region') or '')).strip()[:60]
    dishes = re.sub(r'[\r\n\t]+', ' ', str(body.get('dishes') or '')).strip()[:120]
    if not region:
        return jsonify({'success': False, 'error': '请先选择采购地区'}), 400
    current_data = load_data()
    preferences = current_data.get('shopping_preferences') or {}
    samples = preferences.get('price_samples') or []
    samples.append({
        'region': region, 'dishes': dishes, 'people_num': people_num,
        'actual_total': actual_total, 'date': get_china_time().date().isoformat()
    })
    preferences['price_samples'] = samples[-20:]
    current_data['shopping_preferences'] = preferences
    save_data(current_data)
    return jsonify({'success': True, 'sample_count': len(preferences['price_samples'])})


@app.route('/api/generate_shopping_list_stream', methods=['POST'])
def generate_shopping_list_stream():
    """生成智能采购清单 - SSE流式输出"""
    data = request.json
    dishes = data.get('dishes', '')
    people_num = data.get('people_num', 3)
    include_budget = data.get('include_budget', True)
    language = data.get('language', 'zh-CN')
    shopping_region = re.sub(r'[\r\n\t]+', ' ', str(data.get('shopping_region', ''))).strip()[:60]
    if not shopping_region:
        shopping_region = '中国大陆平均市场'
    current_data = load_data()
    preferences = current_data.get('shopping_preferences') or {}
    province = str(data.get('shopping_province') or '')[:30]
    city = str(data.get('shopping_city') or '')[:30]
    if province or city:
        preferences['province'] = province
        preferences['city'] = city
        current_data['shopping_preferences'] = preferences
        save_data(current_data)
    price_context = shopping_price_context(preferences, shopping_region, language)

    if not dishes:
        def error_gen():
            msg = '请输入想吃的菜品' if language == 'zh-CN' else 'Please enter dish names'
            yield f"data: {json.dumps({'error': msg}, ensure_ascii=False)}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    if language == 'en-US':
        budget_instruction = f"""
6. **Budget Estimate for {shopping_region}**
- Estimate using typical recent retail prices at local supermarkets and wet markets in {shopping_region}
- Show the reference unit price, item subtotal, and total in RMB
- Give a reasonable price range and clearly state that actual prices vary by store, season, and brand{price_context}""" if include_budget else ""
        prompt = f"""Please generate a detailed shopping list for the following dishes for [{people_num} servings]:

[Dishes to Cook] {dishes}

Please generate a complete shopping list including:

1️⃣ **Categorized by Supermarket Sections**
- 🥬 Vegetables Section: xxx
- 🥩 Meat Section: xxx
- 🐟 Seafood Section: xxx
- 🍞 Grains & Oils Section: xxx
- 🧂 Condiments Section: xxx
- 🥛 Dairy Section: xxx
- ❄️ Frozen Foods Section: xxx

2️⃣ **Precise Quantities** (considering {people_num} servings)
- Label specific quantities for each ingredient (grams/pieces/ml)
- Provide suggested amounts for seasonings

3️⃣ **Selection Tips**
- How to choose fresh ingredients
- Precautions

4️⃣ **Storage Recommendations**
- Which ingredients need refrigeration
- Shelf life reminders

5️⃣ **Alternatives**
- What are the substitutes if certain ingredients are unavailable{budget_instruction}

Please present in a clear table or list format for easy use while shopping.

Please respond entirely in English."""
    else:
        budget_instruction = f"""
6. **{shopping_region}预算估算**
- 参考{shopping_region}近期普通超市及菜市场的常见零售价格
- 标出每种食材的参考单价、小计和人民币总价
- 给出合理价格区间，并明确提示实际价格会因门店、季节和品牌而变化{price_context}""" if include_budget else ""
        prompt = f"""请为以下【{people_num}人份】的菜品生成详细的采购清单：

【想吃的菜品】{dishes}

请生成完整的购物清单，包含以下内容：

1️⃣ **按超市区域分类**
- 🥬 蔬菜区：xxx
- 🥩 肉类区：xxx
- 🐟 水产区：xxx
- 🍞 粮油副食区：xxx
- 🧂 调味品区：xxx
- 🥛 乳制品区：xxx
- ❄️ 冷冻食品区：xxx

2️⃣ **精确用量**（考虑{people_num}人份）
- 每种食材标注具体用量（克/个/毫升）
- 适量调味料也要给出建议用量

3️⃣ **挑选建议**
- 如何挑选新鲜食材
- 注意事项

4️⃣ **储存建议**
- 哪些食材需要冷藏
- 保质期提醒

5️⃣ **替代方案**
- 如果某些食材买不到，有什么替代品{budget_instruction}

请用清晰的表格或列表格式呈现，方便用户在超市购物时使用。"""

    def generate():
        full_content = ""
        for chunk in call_ai_api_stream(prompt):
            stream_error = extract_ai_stream_error(chunk)
            if stream_error:
                yield f"data: {json.dumps({'error': stream_error}, ensure_ascii=False)}\n\n"
                return
            full_content += chunk
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True, 'full_content': full_content}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@app.route('/api/generate_daily_recommendation_stream', methods=['POST'])
def generate_daily_recommendation_stream():
    """生成明日饮食推荐 - SSE流式输出（基于今日摄入缺口）"""
    current_data = load_data()
    population_group = current_data.get('population_group', 'adults')
    fridge_items = current_data.get('fridge_inventory', [])

    language = request.json.get('language', 'zh-CN') if request.is_json else 'zh-CN'

    today = get_china_time().strftime('%Y-%m-%d')
    all_records = current_data.get('daily_intake_records', [])
    today_records = [r for r in all_records if r.get('date') == today]

    if today_records:
        # 🔐 真实数据：汇总今日全部摄入记录（不限条数）
        user_intake = {
            'vegetables': sum(r.get('vegetables', 0) for r in today_records),
            'fruits': sum(r.get('fruits', 0) for r in today_records),
            'meat': sum(r.get('meat', 0) for r in today_records),
            'eggs': sum(r.get('eggs', 0) for r in today_records)
        }
    else:
        user_intake = {'vegetables': 0, 'fruits': 0, 'meat': 0, 'eggs': 0}

    try:
        if population_group == 'all':
            groups = ['adults', 'teens', 'children', 'elderly']
            if language == 'en-US':
                group_names = {'adults': 'Adults (18-60)', 'teens': 'Teens (13-17)', 'children': 'Children (6-12)', 'elderly': 'Elderly (60+)'}
            else:
                group_names = {'adults': '成年人 (18-60岁)', 'teens': '青少年 (13-17岁)', 'children': '儿童 (6-12岁)', 'elderly': '老年人 (60岁以上)'}

            # 为每个人群做营养评估，找出各自的缺口
            group_assessments = {}
            for group in groups:
                assessment = nutrition_assessment(user_intake, group, language)
                group_assessments[group] = assessment

            # 构建包含营养标准对比的详细 prompt
            if language == 'en-US':
                intake_summary = f"""Today's total intake:
  - Vegetables: {user_intake.get('vegetables', 0)}g
  - Fruits: {user_intake.get('fruits', 0)}g
  - Meat: {user_intake.get('meat', 0)}g
  - Eggs: {user_intake.get('eggs', 0)}g"""

                group_details = []
                for group in groups:
                    assessment = group_assessments[group]
                    standard = get_nutrition_standard(group)
                    recs = standard.get('daily_recommendations', {}) if standard else {}
                    group_detail = f"""
### {group_names[group]}
- Daily standard: Vegetables {recs.get('vegetables',{}).get('min','?')}-{recs.get('vegetables',{}).get('max','?')}g, Fruits {recs.get('fruits',{}).get('min','?')}-{recs.get('fruits',{}).get('max','?')}g, Meat {recs.get('meat',{}).get('min','?')}-{recs.get('meat',{}).get('max','?')}g, Eggs {recs.get('eggs',{}).get('min','?')}-{recs.get('eggs',{}).get('max','?')}g
- Deficiencies: {', '.join([assessment[k]['chinese_name'] + f" (gap: {assessment[k]['gap']}g)" for k, v in assessment.items() if v['status'] in ('不足', 'Insufficient')]) if any(v['status'] in ('不足', 'Insufficient') for v in assessment.values()) else '✅ All categories meet standards'}"""
                    group_details.append(group_detail)

                prompt = f"""You are a professional nutritionist. Based on TODAY's intake, generate TOMORROW's dietary recommendations for ALL population groups in one household.

{intake_summary}

【Nutrition assessment by group (WHO/food-based dietary reference framework)】
The SAME intake data may be sufficient for one group but deficient for another:
{"".join(group_details)}

【⚠️ CORE TASK — Recommend TOMORROW's meals for each group】
1. For EACH group, recommend 1-2 TOMORROW dishes that specifically address THEIR deficiencies
2. Prioritize foods from the deficient categories for each group
3. Consider each group's digestion characteristics (elderly: soft food, children: fun/bite-sized, etc.)
4. If you can recommend dishes that work for multiple groups, note that

【Output Format】
## Today's Overall Assessment (one sentence)
## Tomorrow's Recommendations by Group
### Adults
### Teens
### Children
### Elderly
## Shopping List (combined)

【Requirements】
- Focus on addressing each group's specific nutrition gaps
- Use numbered lists for dishes
- Keep each group's section under 120 words
- Be specific about ingredient amounts

Please respond entirely in English."""
            else:
                intake_summary = f"""今日总摄入:
  - 蔬菜: {user_intake.get('vegetables', 0)}g
  - 水果: {user_intake.get('fruits', 0)}g
  - 肉类: {user_intake.get('meat', 0)}g
  - 蛋类: {user_intake.get('eggs', 0)}g"""

                group_details = []
                for group in groups:
                    assessment = group_assessments[group]
                    standard = get_nutrition_standard(group)
                    recs = standard.get('daily_recommendations', {}) if standard else {}
                    group_detail = f"""
### {group_names[group]}
- 每日标准: 蔬菜{recs.get('vegetables',{}).get('min','?')}-{recs.get('vegetables',{}).get('max','?')}g, 水果{recs.get('fruits',{}).get('min','?')}-{recs.get('fruits',{}).get('max','?')}g, 肉类{recs.get('meat',{}).get('min','?')}-{recs.get('meat',{}).get('max','?')}g, 蛋类{recs.get('eggs',{}).get('min','?')}-{recs.get('eggs',{}).get('max','?')}g
- 摄入缺口: {', '.join([assessment[k]['chinese_name'] + f" (差{assessment[k]['gap']}g)" for k, v in assessment.items() if v['status'] in ('不足', 'Insufficient')]) if any(v['status'] in ('不足', 'Insufficient') for v in assessment.values()) else '✅ 所有类别均达标'}"""
                    group_details.append(group_detail)

                prompt = f"""你是一位专业营养师。请根据**今日**的摄入数据，为一个家庭中的所有人群生成**明日**饮食推荐。

{intake_summary}

【各人群营养评估（WHO 健康饮食原则 + 食物膳食指南参考框架）】
同样的摄入量，对不同人群意味着不同的缺口：
{"".join(group_details)}

【⚠️ 核心任务 — 推荐明日食谱】
1. 针对每个人群的具体营养缺口，各推荐 1-2 道**明日**补充菜品
2. 优先推荐缺口类别中的食材
3. 考虑各人群的消化特点（老年人：软烂易消化，儿童：趣味小份，青少年：营养丰富）
4. 如果有适合多个人群的菜品，可以标注出来

【输出格式】
## 今日总体评估（一句话）
## 明日各人群推荐
### 成年人
### 青少年
### 儿童
### 老年人
## 综合采购清单

【要求】
- 围绕补充各人群的营养缺口
- 菜品用有序数字列表
- 每个人群控制在 120 字以内
- 标注食材具体用量"""

            def generate():
                full_content = ""
                for chunk in call_ai_api_stream(prompt):
                    stream_error = extract_ai_stream_error(chunk)
                    if stream_error:
                        yield f"data: {json.dumps({'error': stream_error}, ensure_ascii=False)}\n\n"
                        return
                    full_content += chunk
                    yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True, 'full_content': full_content, 'is_multi_group': True}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(
                stream_with_context(generate()),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'keep-alive'
                }
            )

        else:
            recommendation = generate_daily_recommendation(user_intake, population_group, fridge_items, language)

            def generate():
                yield f"data: {json.dumps({'content': recommendation, 'full_content': recommendation, 'done': True}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(
                stream_with_context(generate()),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'keep-alive'
                }
            )

    except Exception as e:
        def error_gen():
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')


@app.route('/api/fridge/add', methods=['POST'])
def add_fridge_item():
    """添加冰箱食材"""
    data = request.json
    item = {
        'name': data.get('name', ''),
        'quantity': data.get('quantity', 0),
        'unit': data.get('unit', 'g'),
        'expiry_date': data.get('expiry_date', ''),
        'added_date': get_china_time().strftime('%Y-%m-%d')
    }
    
    current_data = load_data()
    if 'fridge_inventory' not in current_data:
        current_data['fridge_inventory'] = []
    
    current_data['fridge_inventory'].append(item)
    save_data(current_data)
    
    return jsonify({'success': True, 'inventory': current_data['fridge_inventory']})

@app.route('/api/fridge/list', methods=['GET'])
def list_fridge_items():
    """列出冰箱食材"""
    current_data = load_data()
    inventory = current_data.get('fridge_inventory', [])
    return jsonify({'success': True, 'inventory': inventory})

@app.route('/api/fridge/delete/<int:index>', methods=['DELETE'])
def delete_fridge_item(index):
    """删除冰箱食材"""
    current_data = load_data()
    inventory = current_data.get('fridge_inventory', [])
    
    if 0 <= index < len(inventory):
        inventory.pop(index)
        current_data['fridge_inventory'] = inventory
        save_data(current_data)
        return jsonify({'success': True, 'inventory': inventory})
    else:
        return jsonify({'success': False, 'error': '索引无效'})

@app.route('/api/intake/edit/<int:index>', methods=['PUT'])
def edit_intake_record(index):
    """编辑摄入记录"""
    data = request.json
    current_data = load_data()
    records = current_data.get('daily_intake_records', [])
    
    # 筛选今日记录
    today = get_china_time().strftime('%Y-%m-%d')
    today_records = [r for r in records if r.get('date') == today]
    
    if 0 <= index < len(today_records):
        # 找到原始记录在总列表中的位置
        original_index = records.index(today_records[index])
        
        # 更新数据
        records[original_index]['vegetables'] = data.get('vegetables', records[original_index].get('vegetables', 0))
        records[original_index]['fruits'] = data.get('fruits', records[original_index].get('fruits', 0))
        records[original_index]['meat'] = data.get('meat', records[original_index].get('meat', 0))
        records[original_index]['eggs'] = data.get('eggs', records[original_index].get('eggs', 0))
        meal_type = str(data.get('meal_type') or records[original_index].get('meal_type') or '')
        if meal_type in VALID_MEAL_TYPES:
            records[original_index]['meal_type'] = meal_type
        
        current_data['daily_intake_records'] = records
        save_data(current_data)
        
        return jsonify({'success': True, 'records': records})
    else:
        return jsonify({'success': False, 'error': '索引无效'})

@app.route('/api/intake/delete/<int:index>', methods=['DELETE'])
def delete_intake_record(index):
    """删除摄入记录"""
    current_data = load_data()
    records = current_data.get('daily_intake_records', [])
    
    # 筛选今日记录
    today = get_china_time().strftime('%Y-%m-%d')
    today_records = [r for r in records if r.get('date') == today]
    
    if 0 <= index < len(today_records):
        # 找到原始记录在总列表中的位置
        original_index = records.index(today_records[index])
        records.pop(original_index)
        
        current_data['daily_intake_records'] = records
        save_data(current_data)
        
        return jsonify({'success': True, 'records': records})
    else:
        return jsonify({'success': False, 'error': '索引无效'})

@app.route('/api/intake/update/<int:index>', methods=['PUT'])
def update_intake_record(index):
    """🆕 更新摄入记录 - 允许用户手动修改摄入量"""
    data = request.json
    current_data = load_data()
    records = current_data.get('daily_intake_records', [])
    
    # 筛选今日记录
    today = get_china_time().strftime('%Y-%m-%d')
    today_records = [r for r in records if r.get('date') == today]
    
    if 0 <= index < len(today_records):
        # 找到原始记录在总列表中的位置
        original_index = records.index(today_records[index])
        
        # 更新数据
        records[original_index]['vegetables'] = data.get('vegetables', 0)
        records[original_index]['fruits'] = data.get('fruits', 0)
        records[original_index]['meat'] = data.get('meat', 0)
        records[original_index]['eggs'] = data.get('eggs', 0)
        meal_type = str(data.get('meal_type') or records[original_index].get('meal_type') or '')
        if meal_type in VALID_MEAL_TYPES:
            records[original_index]['meal_type'] = meal_type
        
        print(f"\n✏️ [update_intake] 更新记录 {index}:")
        print(f"   蔬菜: {records[original_index]['vegetables']}g")
        print(f"   水果: {records[original_index]['fruits']}g")
        print(f"   肉类: {records[original_index]['meat']}g")
        print(f"   蛋类: {records[original_index]['eggs']}g")
        
        current_data['daily_intake_records'] = records
        save_data(current_data)
        
        return jsonify({'success': True, 'record': records[original_index]})
    else:
        return jsonify({'success': False, 'error': '索引无效'})

@app.route('/api/intake/history/7days', methods=['GET'])
def get_7days_history():
    """获取滚动近 7 天摄入历史"""
    current_data = load_data()
    records = current_data.get('daily_intake_records', [])
    
    # 从今天倒序获取 7 天；第 8 天及更早记录已由持久化清理逻辑删除。
    today = get_china_time().date()
    dates = [
        (today - timedelta(days=i)).isoformat()
        for i in range(7)
    ]
    
    # 按日期分组统计
    history = []
    for date in dates:
        day_records = [r for r in records if r.get('date') == date]
        if day_records:
            total = {
                'date': date,
                'vegetables': sum(r.get('vegetables', 0) for r in day_records),
                'fruits': sum(r.get('fruits', 0) for r in day_records),
                'meat': sum(r.get('meat', 0) for r in day_records),
                'eggs': sum(r.get('eggs', 0) for r in day_records),
                'record_count': len(day_records)
            }
            history.append(total)
    
    return jsonify({'success': True, 'history': history})

@app.route('/api/food_weight/query', methods=['POST'])
def query_food_weight():
    """查询食材重量 - 优先使用本地数据库，未收录的调用AI"""
    data = request.json
    food_name = data.get('food_name', '').strip()
    
    if not food_name:
        return jsonify({'success': False, 'error': '请输入食材名称'})
    
    try:
        # 1. 优先从本地数据库查找
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'food_weight_database.json')
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as f:
                weight_db = json.load(f)
            
            # 在所有类别中搜索
            for category in ['vegetables', 'fruits', 'meat', 'eggs', 'grains', 'dairy']:
                if food_name in weight_db.get(category, {}):
                    item = weight_db[category][food_name]
                    return jsonify({
                        'success': True,
                        'source': 'database',
                        'food_name': food_name,
                        'unit': item['unit'],
                        'weight_per_unit': item['weight_per_unit'],
                        'note': item['note'],
                        'estimated_weight': item['weight_per_unit']  # 默认按1个单位计算
                    })
        
        # 2. 数据库中未找到，调用AI估算
        prompt = f"""请提供以下常见食物的近似重量参考（帮助用户估算摄入量）：

食材名称：{food_name}

请以简洁的格式返回，例如：
- 1个中等大小的苹果 ≈ 200g
- 1碗米饭（标准碗）≈ 150g
- 1个鸡蛋 ≈ 50g
- 1片面包 ≈ 30g

如果是不常见的食材，请给出合理的估算。只返回重量信息，不要其他解释。"""
        
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            # 解析AI返回的结果，提取重量数值
            result_text = api_result['content']
            # 尝试提取数字（克数）
            import re
            numbers = re.findall(r'(\d+)\s*g', result_text)
            estimated_weight = int(numbers[0]) if numbers else 100  # 默认100g
            
            return jsonify({
                'success': True,
                'source': 'ai',
                'food_name': food_name,
                'ai_response': result_text,
                'estimated_weight': estimated_weight
            })
        else:
            return jsonify({'success': False, 'error': f"AI 查询失败:{api_result.get('error', '未知错误')}"})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/food_weight/batch_estimate', methods=['POST'])
def batch_estimate_food_weight():
    """批量估算食材重量 - 用于自动录入时调用
    
    ⚠️ 重要改进：让AI直接返回分类汇总后的总重量，而不是单个食材重量
    这样可以避免前端汇总时的误差，提高数据准确性
    """
    data = request.json
    ingredients = data.get('ingredients', [])  # 食材列表
    people_num = data.get('people_num', 1)  # 人数
    
    if not ingredients:
        return jsonify({'success': False, 'error': '请提供食材列表'})
    
    try:
        # 加载本地数据库（用于调试和回退）
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'food_weight_database.json')
        weight_db = {}
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as f:
                weight_db = json.load(f)
        
        print(f"\n📊 [batch_estimate] 开始处理 {len(ingredients)} 种食材，{people_num}人份")
        print(f"   食材列表: {', '.join(ingredients)}")
        
        # 构建Prompt，让AI直接返回分类汇总结果
        prompt = f"""你是一个专业的营养师和食材分析师。请分析以下食材清单，并计算每类食物的总重量。

【基本信息】
- 食材清单：{', '.join(ingredients)}
- 就餐人数：{people_num}人

【任务要求】
请将这些食材按以下6个类别进行分类，并计算每类的总重量（单位：克）：

1. vegetables（蔬菜类）：包括所有蔬菜（叶菜、根茎、瓜果类蔬菜）、菌菇、豆制品（豆腐、豆干等）
2. fruits（水果类）：包括所有新鲜水果（苹果、香蕉、橙子等）
3. meat（肉类）：包括猪牛羊肉、禽类（鸡鸭鹅）、水产海鲜（鱼虾蟹贝）、加工肉制品（香肠、腊肉等）
4. eggs（蛋类）：包括鸡蛋、鸭蛋、鹌鹑蛋等
5. grains（主食类）：包括米饭、面条、面包、馒头、粥等
6. dairy（乳制品）：包括牛奶、酸奶、奶酪、黄油等

【⚠️ 重要规则 - 必须严格遵守】
1. **肉类包含范围（非常重要）**：
   - ✅ 猪肉、牛肉、羊肉、鸡肉、鸭肉、鹅肉 → meat
   - ✅ 鱼肉、虾、蟹、贝类、鱿鱼、章鱼等海鲜 → meat
   - ✅ 香肠、腊肉、火腿、培根等加工肉 → meat
   - ❌ 豆制品（豆腐、豆干）不属于meat，属于vegetables
   
2. **蔬菜类包含范围**：
   - ✅ 叶菜类：白菜、菠菜、生菜、油麦菜等
   - ✅ 根茎类：土豆、胡萝卜、白萝卜、洋葱等
   - ✅ 瓜果类：番茄、黄瓜、茄子、青椒等
   - ✅ 菌菇类：香菇、金针菇、木耳等
   - ✅ 豆制品：豆腐、豆干、腐竹、豆浆等
   - ✅ 香菜、葱、姜、蒜等调味蔬菜
   
3. **水果类**：
   - ✅ 香蕉、苹果、橙子、葡萄、西瓜等所有新鲜水果
   - ❌ 番茄虽然是果实，但在营养学上归类为蔬菜
   
4. **重量计算原则**：
   - 参考常见食材的标准份量
   - 考虑{people_num}人份的总量
   - 例如：如果1人份羊肉约100g，那么{people_num}人份就是{people_num * 100}g
   - 例如：如果1人份香蕉约150g，那么{people_num}人份就是{people_num * 150}g
   
5. **只返回JSON格式**，不要其他解释

【输出格式】
请严格按以下JSON格式返回：
{{
  "vegetables": 数字（总克数）,
  "fruits": 数字（总克数）,
  "meat": 数字（总克数）,
  "eggs": 数字（总克数）,
  "grains": 数字（总克数）,
  "dairy": 数字（总克数）
}}

【示例1 - 含肉类和蔬菜】
输入：羊排 200g, 香菜 50g, 白菜 150g
输出：{{"vegetables": 200, "fruits": 0, "meat": 200, "eggs": 0, "grains": 0, "dairy": 0}}
说明：羊排→meat 200g, 香菜+白菜→vegetables 200g

【示例2 - 含水果】
输入：香蕉 2根, 苹果 1个
输出：{{"vegetables": 0, "fruits": 350, "meat": 0, "eggs": 0, "grains": 0, "dairy": 0}}
说明：香蕉+苹果→fruits 350g（假设1根香蕉150g，1个苹果200g）

【示例3 - 混合食材】
输入：牛肉 150g, 番茄 200g, 土豆 150g, 米饭 2碗
输出：{{"vegetables": 350, "fruits": 0, "meat": 150, "eggs": 0, "grains": 300, "dairy": 0}}
说明：番茄+土豆→vegetables 350g, 牛肉→meat 150g, 米饭→grains 300g

现在请分析以下食材：{', '.join(ingredients)}（{people_num}人份）
只返回JSON，不要其他内容。"""
        
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            import re
            import json as json_module
            
            print(f"   🤖 AI响应: {api_result['content'][:200]}...")
            
            # 尝试解析JSON
            try:
                # 提取JSON部分
                json_match = re.search(r'\{.*\}', api_result['content'], re.DOTALL)
                if json_match:
                    ai_result = json_module.loads(json_match.group())
                    
                    # 验证返回的数据结构
                    required_keys = ['vegetables', 'fruits', 'meat', 'eggs', 'grains', 'dairy']
                    if all(key in ai_result for key in required_keys):
                        print(f"   ✅ AI返回的分类汇总数据:")
                        print(f"      蔬菜: {ai_result['vegetables']}g")
                        print(f"      水果: {ai_result['fruits']}g")
                        print(f"      肉类: {ai_result['meat']}g")
                        print(f"      蛋类: {ai_result['eggs']}g")
                        print(f"      主食: {ai_result['grains']}g")
                        print(f"      乳制品: {ai_result['dairy']}g")
                        
                        # 构造详细的食材明细（用于调试）
                        detailed_results = []
                        for ingredient in ingredients:
                            ingredient = ingredient.strip()
                            if not ingredient:
                                continue
                            
                            # 尝试从数据库或INGREDIENT_MAP找到类别
                            category = 'unknown'
                            weight = 0
                            
                            # 检查数据库
                            for cat in ['vegetables', 'fruits', 'meat', 'eggs', 'grains', 'dairy']:
                                if ingredient in weight_db.get(cat, {}):
                                    category = cat
                                    weight = weight_db[cat][ingredient]['weight_per_unit']
                                    break
                            
                            # 检查INGREDIENT_MAP
                            if category == 'unknown' and ingredient in INGREDIENT_MAP:
                                mapped = INGREDIENT_MAP[ingredient]
                                if mapped in ['tomato', 'potato', 'tofu', 'bean_sprout']:
                                    category = 'vegetables'
                                elif mapped in ['fish', 'chicken', 'beef']:
                                    category = 'meat'
                                elif mapped == 'egg':
                                    category = 'eggs'
                            
                            detailed_results.append({
                                'ingredient': ingredient,
                                'source': 'database' if weight > 0 else 'ai_estimated',
                                'category': category,
                                'estimated_weight': weight if weight > 0 else 100
                            })
                        
                        return jsonify({
                            'success': True,
                            'results': detailed_results,  # 保留详细列表用于调试
                            'total_count': len(detailed_results),
                            'db_count': sum(1 for r in detailed_results if r['source'] == 'database'),
                            'ai_count': sum(1 for r in detailed_results if r['source'] == 'ai_estimated'),
                            # 关键：返回分类汇总的总重量
                            'category_totals': {
                                'vegetables': ai_result['vegetables'],
                                'fruits': ai_result['fruits'],
                                'meat': ai_result['meat'],
                                'eggs': ai_result['eggs'],
                                'grains': ai_result['grains'],
                                'dairy': ai_result['dairy']
                            }
                        })
                    else:
                        print(f"   ❌ AI返回的JSON缺少必要字段")
                        raise ValueError("JSON格式不完整")
                else:
                    print(f"   ❌ 未找到JSON格式")
                    raise ValueError("无法解析JSON")
            except Exception as e:
                print(f"   ❌ JSON解析失败: {e}")
                # 降级到旧方法
                return _fallback_batch_estimate(ingredients, people_num, weight_db)
        else:
            print(f"   ❌ AI调用失败: {api_result.get('error')}")
            return _fallback_batch_estimate(ingredients, people_num, weight_db)
        
    except Exception as e:
        print(f"   ❌ 批量估算异常: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


def _fallback_batch_estimate(ingredients, people_num, weight_db):
    """降级方案：使用数据库+INGREDIENT_MAP进行估算"""
    print(f"   🔄 使用降级方案估算食材重量")
    
    results = []
    category_totals = {
        'vegetables': 0,
        'fruits': 0,
        'meat': 0,
        'eggs': 0,
        'grains': 0,
        'dairy': 0
    }
    
    for ingredient in ingredients:
        ingredient = ingredient.strip()
        if not ingredient:
            continue
        
        found = False
        # 检查数据库
        for category in ['vegetables', 'fruits', 'meat', 'eggs', 'grains', 'dairy']:
            if ingredient in weight_db.get(category, {}):
                item = weight_db[category][ingredient]
                weight = item['weight_per_unit'] * people_num  # 乘以人数
                category_totals[category] += weight
                results.append({
                    'ingredient': ingredient,
                    'source': 'database',
                    'category': category,
                    'estimated_weight': weight
                })
                print(f"      📊 {ingredient} → {category}: {weight}g (数据库)")
                found = True
                break
        
        # 检查INGREDIENT_MAP
        if not found and ingredient in INGREDIENT_MAP:
            mapped = INGREDIENT_MAP[ingredient]
            if mapped in ['tomato', 'potato', 'tofu', 'bean_sprout']:
                category = 'vegetables'
                weight = 150 * people_num
            elif mapped in ['fish', 'chicken', 'beef']:
                category = 'meat'
                weight = 120 * people_num
            elif mapped == 'egg':
                category = 'eggs'
                weight = 50 * people_num
            else:
                category = 'vegetables'
                weight = 100 * people_num
            
            category_totals[category] += weight
            results.append({
                'ingredient': ingredient,
                'source': 'map_fallback',
                'category': category,
                'estimated_weight': weight
            })
            print(f"      📊 {ingredient} → {category}: {weight}g (映射表)")
            found = True
        
        # 默认值
        if not found:
            # 根据关键词猜测类别
            if any(kw in ingredient for kw in ['菜', '瓜', '菇', '豆', '萝卜']):
                category = 'vegetables'
                weight = 150 * people_num
            elif any(kw in ingredient for kw in ['苹果', '香蕉', '梨', '桃', '葡萄']):
                category = 'fruits'
                weight = 150 * people_num
            elif any(kw in ingredient for kw in ['猪', '牛', '羊', '鸡', '鸭', '鱼', '肉']):
                category = 'meat'
                weight = 120 * people_num
            elif '蛋' in ingredient:
                category = 'eggs'
                weight = 50 * people_num
            else:
                category = 'vegetables'
                weight = 100 * people_num
            
            category_totals[category] += weight
            results.append({
                'ingredient': ingredient,
                'source': 'keyword_guess',
                'category': category,
                'estimated_weight': weight
            })
            print(f"      📊 {ingredient} → {category}: {weight}g (关键词猜测)")
    
    print(f"   ✅ 降级方案完成，分类汇总:")
    print(f"      蔬菜: {category_totals['vegetables']}g")
    print(f"      水果: {category_totals['fruits']}g")
    print(f"      肉类: {category_totals['meat']}g")
    print(f"      蛋类: {category_totals['eggs']}g")
    
    return jsonify({
        'success': True,
        'results': results,
        'total_count': len(results),
        'db_count': sum(1 for r in results if r['source'] == 'database'),
        'ai_count': sum(1 for r in results if r['source'] != 'database'),
        'category_totals': category_totals
    })

@app.route('/api/generate_shopping_list', methods=['POST'])
def generate_shopping_list():
    """生成智能采购清单"""
    data = request.json
    dishes = data.get('dishes', '')
    people_num = data.get('people_num', 3)
    include_budget = data.get('include_budget', True)
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    shopping_region = re.sub(r'[\r\n\t]+', ' ', str(data.get('shopping_region', ''))).strip()[:60]
    if not shopping_region:
        shopping_region = '中国大陆平均市场'
    current_data = load_data()
    preferences = current_data.get('shopping_preferences') or {}
    province = str(data.get('shopping_province') or '')[:30]
    city = str(data.get('shopping_city') or '')[:30]
    if province or city:
        preferences['province'] = province
        preferences['city'] = city
        current_data['shopping_preferences'] = preferences
        save_data(current_data)
    price_context = shopping_price_context(preferences, shopping_region, language)
    
    if not dishes:
        error_msg = '请输入想吃的菜品' if language == 'zh-CN' else 'Please enter dish names'
        return jsonify({'success': False, 'error': error_msg})
    
    # 🌐 根据语言构建Prompt
    if language == 'en-US':
        budget_instruction = f"""
6. **Budget Estimate for {shopping_region}**
- Estimate using typical recent retail prices at local supermarkets and wet markets in {shopping_region}
- Show the reference unit price, item subtotal, and total in RMB
- Give a reasonable price range and clearly state that actual prices vary by store, season, and brand{price_context}""" if include_budget else ""
        
        prompt = f"""Please generate a detailed shopping list for the following dishes for [{people_num} servings]:

[Dishes to Cook] {dishes}

Please generate a complete shopping list including:

1️⃣ **Categorized by Supermarket Sections**
- 🥬 Vegetables Section: xxx
- 🥩 Meat Section: xxx
- 🐟 Seafood Section: xxx
- 🍞 Grains & Oils Section: xxx
- 🧂 Condiments Section: xxx
- 🥛 Dairy Section: xxx
- ❄️ Frozen Foods Section: xxx

2️⃣ **Precise Quantities** (considering {people_num} servings)
- Label specific quantities for each ingredient (grams/pieces/ml)
- Provide suggested amounts for seasonings

3️⃣ **Selection Tips**
- How to choose fresh ingredients
- Precautions

4️⃣ **Storage Recommendations**
- Which ingredients need refrigeration
- Shelf life reminders

5️⃣ **Alternatives**
- What are the substitutes if certain ingredients are unavailable{budget_instruction}

Please present in a clear table or list format for easy use while shopping.

Please respond entirely in English."""
    else:
        budget_instruction = f"""
6. **{shopping_region}预算估算**
- 参考{shopping_region}近期普通超市及菜市场的常见零售价格
- 标出每种食材的参考单价、小计和人民币总价
- 给出合理价格区间，并明确提示实际价格会因门店、季节和品牌而变化{price_context}""" if include_budget else ""
        
        prompt = f"""请为以下【{people_num}人份】的菜品生成详细的采购清单：

【想吃的菜品】{dishes}

请生成完整的购物清单，包含以下内容：

1️⃣ **按超市区域分类**
- 🥬 蔬菜区：xxx
- 🥩 肉类区：xxx
- 🐟 水产区：xxx
- 🍞 粮油副食区：xxx
- 🧂 调味品区：xxx
- 🥛 乳制品区：xxx
- ❄️ 冷冻食品区：xxx

2️⃣ **精确用量**（考虑{people_num}人份）
- 每种食材标注具体用量（克/个/毫升）
- 适量调味料也要给出建议用量

3️⃣ **挑选建议**
- 如何挑选新鲜食材
- 注意事项

4️⃣ **储存建议**
- 哪些食材需要冷藏
- 保质期提醒

5️⃣ **替代方案**
- 如果某些食材买不到，有什么替代品{budget_instruction}

请用清晰的表格或列表格式呈现，方便用户在超市购物时使用。"""
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            return jsonify({'success': True, 'shopping_list': api_result['content']})
        else:
            return jsonify({'success': False, 'error': f"AI 生成失败:{api_result.get('error', '未知错误')}"})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/generate_daily_recommendation', methods=['POST'])
def generate_daily_recommendation_route():
    """生成明日饮食推荐（基于今日摄入缺口）"""
    current_data = load_data()
    population_group = current_data.get('population_group', 'adults')
    fridge_items = current_data.get('fridge_inventory', [])
    
    # 🌐 从请求中获取语言设置
    language = request.json.get('language', 'zh-CN') if request.is_json else 'zh-CN'
    
    # 获取用户今日总摄入数据
    today = get_china_time().strftime('%Y-%m-%d')
    all_records = current_data.get('daily_intake_records', [])
    today_records = [r for r in all_records if r.get('date') == today]
    
    if today_records:
        # 🔐 真实数据：汇总今日全部摄入记录（不限条数）
        user_intake = {
            'vegetables': sum(r.get('vegetables', 0) for r in today_records),
            'fruits': sum(r.get('fruits', 0) for r in today_records),
            'meat': sum(r.get('meat', 0) for r in today_records),
            'eggs': sum(r.get('eggs', 0) for r in today_records)
        }
    else:
        user_intake = {'vegetables': 0, 'fruits': 0, 'meat': 0, 'eggs': 0}
    
    try:
        # 检查是否为"以上皆是"模式
        if population_group == 'all':
            # 为所有人群生成推荐
            groups = ['adults', 'teens', 'children', 'elderly']
                    
            # 🌐 根据语言设置人群名称
            if language == 'en-US':
                group_names = {
                    'adults': 'Adults',
                    'teens': 'Teens',
                    'children': 'Children',
                    'elderly': 'Elderly'
                }
            else:
                group_names = {
                    'adults': '成年人',
                    'teens': '青少年',
                    'children': '儿童',
                    'elderly': '老年人'
                }
                        
            recommendations = {}
            for group in groups:
                rec = generate_daily_recommendation(user_intake, group, fridge_items, language)
                recommendations[group_names[group]] = rec
                
            return jsonify({
                'success': True, 
                'recommendation': recommendations,
                'is_multi_group': True,
                'user_intake': user_intake
            })
        else:
            recommendation = generate_daily_recommendation(user_intake, population_group, fridge_items, language)
            return jsonify({'success': True, 'recommendation': recommendation, 'is_multi_group': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/image_recognize', methods=['POST'])
def image_recognize():
    """拍照识菜 - 图像识别食材"""
    data = request.json
    image_base64 = data.get('image_base64', '')
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    if not image_base64:
        return jsonify({'success': False, 'error': '请上传图片'})
    
    try:
        import base64
        from PIL import Image
        import io
        
        # 解码 base64 图片
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        
        # 压缩图片（减少网络传输）
        max_size = 800
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # 转换为 JPEG 并重新编码为 base64
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='JPEG', quality=85, optimize=True)
        image_bytes.seek(0)
        compressed_base64 = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
        
        # 调用智谱 AI GLM-4V-Flash 视觉模型
        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 🌐 根据语言设置 AI 提示词
        if language == 'en-US':
            prompt_text = """Please identify the food ingredients in this image.

【Important Requirements】
1. Only list specific ingredient names (e.g., tomato, egg, bell pepper, beef)
2. Separate with English commas (,)
3. No descriptive language, don't say 'I see', 'the image contains', etc.
4. If it's a dish, list main ingredients, not dish name
5. When uncertain, give the most likely ingredient name
6. List each ingredient separately, don't combine (e.g., 'potato,beef' not 'potato beef stew')
7. If no obvious ingredients in image, return 'Cannot identify'

【Common Ingredient Examples】
- Vegetables: cabbage, spinach, lettuce, tomato, cucumber, eggplant, bell pepper, onion, potato, carrot
- Meat: pork, beef, lamb, chicken, duck, fish, shrimp, crab
- Eggs: chicken egg, duck egg
- Fruits: apple, banana, orange, grape
- Others: tofu, dried tofu, mushroom, wood ear mushroom

Please return the ingredient list directly, for example:
tomato,egg,bell pepper"""
        else:  # zh-CN
            prompt_text = """请识别这张图片中的食材。

【重要要求】
1. 只列出具体的食材名称（如：西红柿、鸡蛋、青椒、牛肉）
2. 用英文逗号分隔（,）
3. 不要描述性语言，不要说'我看到'、'图片中有'等
4. 如果是菜品，列出主要食材而不是菜名
5. 不确定时给出最可能的食材名称
6. 每个食材单独列出，不要组合（例如：'土豆,牛肉'而不是'土豆炖牛肉'）
7. 如果图片中没有明显食材，返回'无法识别'

【常见食材示例】
- 蔬菜类：白菜、菠菜、生菜、番茄、黄瓜、茄子、青椒、洋葱、土豆、胡萝卜
- 肉类：猪肉、牛肉、羊肉、鸡肉、鸭肉、鱼肉、虾、蟹
- 蛋类：鸡蛋、鸭蛋
- 水果类：苹果、香蕉、橙子、葡萄
- 其他：豆腐、豆干、蘑菇、木耳

请直接返回食材列表，例如：
西红柿,鸡蛋,青椒"""
        
        payload = {
            "model": "glm-4v-flash",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{compressed_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt_text
                        }
                    ]
                }
            ],
            "max_tokens": 200,
            "temperature": 0.3
        }
        
        response = requests.post(ZHIPU_API_URL, headers=headers, json=payload, timeout=90)
        
        if response.status_code == 200:
            result = response.json()
            ingredients_text = result['choices'][0]['message']['content']
            
            print(f"\n📸 [image_recognize] AI识别结果:")
            print(f"   原始文本: {ingredients_text}")
            print(f"   长度: {len(ingredients_text)} 字符\n")
            
            return jsonify({
                'success': True,
                'ingredients': ingredients_text
            })
        else:
            error_msg = f"API 调用失败：{response.status_code}"
            if response.status_code == 401:
                error_msg += "\n智谱 AI API 密钥无效或已过期"
            elif response.status_code == 429:
                error_msg += "\n请求过于频繁，请稍后再试"
            
            return jsonify({'success': False, 'error': error_msg})
            
    except Exception as e:
        if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            return jsonify({'success': False, 'error': get_user_facing_ai_error(e)})
        return jsonify({'success': False, 'error': '图像识别暂时不可用，请稍后重试'})

@app.route('/api/analyze_nutrition', methods=['POST'])
def analyze_nutrition():
    """AI 营养分析 - 分析食材/食谱的营养成分"""
    data = request.json
    food_input = data.get('food_input', '').strip()
    people = data.get('people', 3)
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    if not food_input:
        error_msg = '请输入食材或食谱名称' if language == 'zh-CN' else 'Please enter food or recipe name'
        return jsonify({'success': False, 'error': error_msg})
    
    # 🌐 根据语言构建Prompt
    if language == 'en-US':
        prompt = f"""Please provide a professional nutritional analysis for the following ingredients/recipe for [{people} servings]:

[Food/Recipe] {food_input}

[⚠️ IMPORTANT PRINCIPLE: Smart Recognition of Ingredient Combinations]
**Before analyzing, please determine how to interpret the user's input:**

1. **If the user inputs multiple independent dishes** (separated by commas):
   - Example: "Braised Beef with Potato, Tomato Scrambled Eggs, Rice"
   - Approach: Analyze each dish separately, then provide overall nutritional assessment
   
2. **If the user inputs multiple ingredients without specifying preparation**:
   - Example: "Milk, Apple, Egg"
   - ❌ Wrong approach: Assume these ingredients are made into one dish (like "Milk Apple Scrambled Eggs")
   - ✅ Correct approach:
     * Option A: Assume this is a breakfast combination → Analyze "Warm Milk", "Fresh Apple", "Boiled Egg" separately
     * Option B: Ask the user about the specific preparation method
     * Option C: Provide several reasonable consumption methods with their nutritional analysis
   
3. **If the user inputs a single dish**:
   - Example: "Braised Beef with Potato"
   - Approach: Directly analyze the nutritional composition of this dish

[Analysis Requirements]
Please analyze in detail (per serving) according to the following structure:

📋 **Step 1: Ingredient Combination Interpretation**
- Explain how you understand the user's input ingredients/dishes
- If multiple ingredients, explain their reasonable consumption methods
- If ambiguous, provide 2-3 possible interpretations

1️⃣ **Basic Nutritional Data** (Precise Calculation)
- Total Calories: XXX kcal
- Protein: XX g
- Fat: XX g
- Carbohydrates: XX g
- Dietary Fiber: XX g

2️⃣ **Micronutrients** (Estimate)
- Vitamin A: XX μg
- Vitamin C: XX mg
- Calcium: XX mg
- Iron: XX mg
- Potassium: XX mg

3️⃣ **Nutritional Balance Assessment**
- Protein Source: High Quality/Average/Insufficient
- Fat Type: Saturated/Unsaturated Ratio
- Carbohydrate Type: Simple/Complex Carbs
- Overall Evaluation: Excellent/Good/Needs Improvement

4️⃣ **Health Recommendations**
- Suitable for: xxx
- Consumption Advice: xxx
- Pairing Suggestions: xxx
- Precautions: xxx

5️⃣ **Special Labels** (if applicable)
- High Protein: ✅ / ❌ (Mark ✅ only if protein content is actually high)
- Low Fat: ✅ / ❌ (Mark ✅ only if fat content is below normal level)
- Low Carb: ✅ / ❌ (Mark ✅ only if carb content is below normal level)
- High Fiber: ✅ / ❌ (Mark ✅ only if fiber content is above normal level)
- Rich in Vitamins: ✅ / ❌ (Mark ✅ only if vitamin content is actually high)

Please present in a clear format with scientifically sound data. **If the ingredient combination is unreasonable, please point it out clearly and provide improvement suggestions!

⚠️ IMPORTANT: Special labels must be objectively marked based on actual nutritional content. Only use ✅ or ❌, do not use [ ] or other symbols!**

Please respond entirely in English."""
    else:
        # 中文 Prompt (原有逻辑)
        prompt = f"""请对以下【{people}人份】的食材/食谱进行专业营养分析：

【食材/食谱】{food_input}

【⚠️ 重要原则：智能识别食材组合方式】
**在分析前，请先判断用户输入的食材应该如何理解：**

1. **如果用户输入的是多道独立的菜品**（用顿号、逗号分隔）：
   - 示例：“土豆炖牛肉、西红柿炒鸡蛋、米饭”
   - 处理方式：分别分析每道菜，然后给出整体营养评估
   
2. **如果用户输入的是多种食材但未说明做法**：
   - 示例：“牛奶、苹果、鸡蛋”
   - ❌ 错误做法：假设这些食材被做成一道菜（如“牛奶苹果炒鸡蛋”）
   - ✅ 正确做法：
     * 方案A：假设这是早餐组合 → 分别分析“温牛奶”、“新鲜苹果”、“水煮蛋”
     * 方案B：询问用户这些食材的具体做法
     * 方案C：给出几种合理的食用方式及其营养分析
   
3. **如果用户输入的是单一菜品**：
   - 示例：“土豆炖牛肉”
   - 处理方式：直接分析这道菜的营养成分

【分析要求】
请按以下结构详细分析（每人份）：

📋 **第一步：食材组合解读**
- 说明你如何理解用户输入的食材/菜品
- 如果是多种食材，说明它们的合理食用方式
- 如果有歧义，给出2-3种可能的解读

1️⃣ **基础营养数据**（精确计算）
- 总热量：XXX 大卡
- 蛋白质：XX 克
- 脂肪：XX 克
- 碳水化合物：XX 克
- 膳食纤维：XX 克

2️⃣ **微量营养素**（估算）
- 维生素 A：XX 微克
- 维生素 C：XX 毫克
- 钙：XX 毫克
- 铁：XX 毫克
- 钾：XX 毫克

3️⃣ **营养均衡评估**
- 蛋白质来源：优质/一般/不足
- 脂肪类型：饱和/不饱和比例
- 碳水类型：简单/复杂碳水
- 总体评价：优秀/良好/需改进

4️⃣ **健康建议**
- 适合人群：xxx
- 食用建议：xxx
- 搭配建议：xxx
- 注意事项：xxx

5️⃣ **特殊标签**（如有）
- 高蛋白：✅ / ❌ （根据实际营养成分标注，只有符合才算）
- 低脂肪：✅ / ❌ （脂肪含量低于正常水平标✅，否则标❌）
- 低碳水：✅ / ❌ （碳水含量低于正常水平标✅，否则标❌）
- 高纤维：✅ / ❌ （纤维含量高于正常水平标✅，否则标❌）
- 富含维生素：✅ / ❌ （维生素含量高标✅，否则标❌）

请用清晰格式呈现，数据要科学合理。**如果食材组合不合理，请明确指出并给出改进建议！

⚠️ 重要：特殊标签必须根据实际情况客观标注，只能使用✅或❌，不要使用[ ]或其他符号！**"""
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            return jsonify({
                'success': True,
                'analysis': api_result['content']
            })
        else:
            return jsonify({
                'success': False,
                'error': f"AI 分析失败：{api_result.get('error', '未知错误')}"
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/analyze_nutrition_stream', methods=['POST'])
def analyze_nutrition_stream():
    """AI 营养分析 - SSE流式输出"""
    data = request.json
    food_input = data.get('food_input', '').strip()
    people = data.get('people', 3)
    language = data.get('language', 'zh-CN')

    if not food_input:
        def error_gen():
            msg = '请输入食材或食谱名称' if language == 'zh-CN' else 'Please enter food or recipe name'
            yield f"data: {json.dumps({'error': msg}, ensure_ascii=False)}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    # 复用analyze_nutrition的prompt构建逻辑
    if language == 'en-US':
        prompt = f"""Please provide a professional nutritional analysis for the following ingredients/recipe for [{people} servings]:

[Food/Recipe] {food_input}

Please analyze in detail (per serving) according to the following structure:

📋 **Step 1: Ingredient Combination Interpretation**
- Explain how you understand the user's input ingredients/dishes

1️⃣ **Basic Nutritional Data** (Precise Calculation)
- Total Calories: XXX kcal
- Protein: XX g
- Fat: XX g
- Carbohydrates: XX g
- Dietary Fiber: XX g

2️⃣ **Micronutrients** (Estimate)
- Vitamin A: XX μg
- Vitamin C: XX mg
- Calcium: XX mg
- Iron: XX mg
- Potassium: XX mg

3️⃣ **Nutritional Balance Assessment**
- Overall Evaluation: Excellent/Good/Needs Improvement

4️⃣ **Health Recommendations**
- Suitable for: xxx
- Consumption Advice: xxx
- Pairing Suggestions: xxx

5️⃣ **Special Labels** (if applicable)
- High Protein / Low Fat / Low Carb / High Fiber / Rich in Vitamins: ✅ / ❌

Please respond entirely in English."""
    else:
        prompt = f"""请对以下【{people}人份】的食材/食谱进行专业营养分析：

【食材/食谱】{food_input}

请按以下结构详细分析（每人份）：

1️⃣ **基础营养数据**（精确计算）
- 总热量：XXX 大卡
- 蛋白质：XX 克
- 脂肪：XX 克
- 碳水化合物：XX 克
- 膳食纤维：XX 克

2️⃣ **微量营养素**（估算）
- 维生素 A：XX 微克
- 维生素 C：XX 毫克
- 钙：XX 毫克
- 铁：XX 毫克

3️⃣ **营养均衡评估**
- 总体评价：优秀/良好/需改进

4️⃣ **健康建议**
- 适合人群：xxx
- 食用建议：xxx
- 搭配建议：xxx

5️⃣ **特殊标签**（如有）
- 高蛋白 / 低脂肪 / 低碳水 / 高纤维 / 富含维生素：✅ / ❌"""

    def generate():
        full_content = ""
        for chunk in call_ai_api_stream(prompt):
            stream_error = extract_ai_stream_error(chunk)
            if stream_error:
                yield f"data: {json.dumps({'error': stream_error}, ensure_ascii=False)}\n\n"
                return
            full_content += chunk
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True, 'full_content': full_content}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@app.route('/api/voice_recognize', methods=['POST'])
def voice_recognize():
    """语音识别 - 将音频转换为文字（使用智谱GLM-ASR API）"""
    if 'audio' not in request.files:
        return jsonify({'success': False, 'error': '未找到音频文件'})
    
    audio_file = request.files['audio']
    
    try:
        # 读取音频文件
        audio_data = audio_file.read()
        
        # 检查文件大小（限制25MB）
        if len(audio_data) > 25 * 1024 * 1024:
            return jsonify({'success': False, 'error': '音频文件过大，请录制不超过25MB的音频'})
        
        # 调用智谱语音识别API（使用multipart/form-data方式）
        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}"
        }
        
        # 构建multipart/form-data请求
        files = {
            'file': ('recording.wav', audio_data, 'audio/wav')
        }
        
        # 🌐 从请求中获取语言设置（默认为auto自动检测）
        language = request.form.get('language', 'auto')
        
        data = {
            'model': 'glm-asr-2512',
            'stream': 'false'
        }
        
        # 如果指定了语言，添加到请求中
        if language in ['zh', 'en']:
            data['language'] = language
        
        response = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions",
            headers=headers,
            files=files,
            data=data,
            timeout=90
        )

        if response.status_code == 200:
            result = response.json()
            text = result.get('text', '')
            
            return jsonify({
                'success': True,
                'text': text
            })
        else:
            error_msg = f"API调用失败：{response.status_code}"
            if response.status_code == 401:
                error_msg += "\n智谱AI API密钥无效"
            elif response.status_code == 400:
                error_msg += "\n请求参数错误，请检查音频格式"
            elif response.status_code == 429:
                error_msg += "\n请求过于频繁，请稍后再试"
            
            # 尝试获取详细错误信息
            try:
                error_detail = response.json()
                if 'error' in error_detail:
                    error_msg += f"\n详细信息：{error_detail['error']}"
            except:
                pass
            
            return jsonify({'success': False, 'error': error_msg})
            
    except Exception as e:
        if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            return jsonify({'success': False, 'error': get_user_facing_ai_error(e)})
        return jsonify({'success': False, 'error': '语音识别暂时不可用，请稍后重试'})

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🍽️  FoodGuardian AI v2.0 - 智能食谱助手 (Web版)")
    print("="*70)
    print("\n✨ 功能特性:")
    print("   • 智能食谱生成 - 基于AI的个性化菜谱推荐")
    print("   • 营养分析评估 - WHO/FAO 膳食参考框架")
    print("   • 冰箱库存管理 - 智能食材搭配建议")
    print("   • 环保价值计算 - 量化食物浪费减少")
    print("   • 拍照识菜功能 - 图像识别食材")
    print("   • 语音交互支持 - 语音输入与识别（智谱免费GLM-ASR）")
    print("   • 采购清单生成 - 智能购物建议")
    print("\n🎨 UI设计:")
    print("   • 温暖棕色系配色方案")
    print("   • iOS风格毛玻璃效果")
    print("   • 流畅动画过渡")
    print("   • 响应式布局设计")
    print("\n📱 正在启动服务器...")
    print("🌐 访问地址: http://localhost:5000")
    print("💡 按 Ctrl+C 停止服务器\n")
    print("="*70 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
