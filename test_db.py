from __future__ import annotations
"""
Test Tekshirish Tizimi — PostgreSQL Database moduli (psycopg2)
Neon.tech PostgreSQL bilan ishlash uchun to'liq refaktoring qilingan.
SQLite fallback lokal sinov uchun saqlab qolindi.
"""
import json
import os
import re
import time
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

UZB_TZ = timezone(timedelta(hours=5))
ADMIN_ID = int(os.getenv("ADMIN_ID", "8039427064"))

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Agar Render da hali ham eski Matematika Neon DB (ep-sparkling-bread) qolgan bo'lsa, avtomatik yangi Fizika bazasiga yo'naltirish
if "ep-sparkling-bread" in DATABASE_URL or not DATABASE_URL:
    DATABASE_URL = "postgresql://neondb_owner:npg_sCxRJyj3Ob8c@ep-plain-mountain-b2554mwk-pooler.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Neon.tech uchun: agar URL da '-pooler' bo'lmasa, uni avtomatik '-pooler' (PgBouncer) rejimiga o'tkazish
# Bu 'Max connections' (ulanuvchilar soni chegarasi) xatoligini to'liq bartaraf qiladi.
if DATABASE_URL and "neon.tech" in DATABASE_URL and "-pooler" not in DATABASE_URL:
    DATABASE_URL = re.sub(r'(@[a-zA-Z0-9_\-]+)(?<!\-pooler)(\.[a-zA-Z0-9_\.\-]*neon\.tech)', r'\1-pooler\2', DATABASE_URL)
    print("ℹ️ DATABASE_URL avtomatik Neon PgBouncer (-pooler) rejimiga ulandi.")

# PostgreSQL yoki SQLite ni avtomatik aniqlash
USE_POSTGRES = bool(DATABASE_URL and ("postgresql" in DATABASE_URL or "postgres" in DATABASE_URL))

# ── PostgreSQL Connection Pool (Yuqori yuklama uchun optimallashtirilgan) ──
_pg_pool = None
_pool_connections = set()
_conn_last_used = {}
PG_POOL_MINCONN = int(os.getenv("PG_POOL_MINCONN", "4"))
PG_POOL_MAXCONN = int(os.getenv("PG_POOL_MAXCONN", "50"))

def _get_pg_pool():
    """PostgreSQL connection pool — bir marta yaratiladi, qayta ishlatiladi.
    minconn=4, maxconn=50: Neon PgBouncer pooler orqali bir vaqtda 50+ parallel so'rovlarni qabul qiladi.
    """
    global _pg_pool
    if _pg_pool is None and USE_POSTGRES:
        try:
            import psycopg2.pool
            _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=PG_POOL_MINCONN,
                maxconn=PG_POOL_MAXCONN,
                dsn=DATABASE_URL,
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
        except Exception as e:
            print(f"Connection pool xatolik: {e}")
            _pg_pool = None
    return _pg_pool

def _close_conn(conn):
    """Ulanishni pool ga qaytarish yoki yopish (Connection Leak va Abort tranzaksiyalarning oldini oladi)."""
    if conn is None:
        return
    conn_id = id(conn)
    if USE_POSTGRES and conn_id in _pool_connections:
        _pool_connections.discard(conn_id)
        _conn_last_used[conn_id] = time.time()
        pool = _get_pg_pool()
        if pool:
            try:
                # Agar tranzaksiya ochiq yoki xatolik bilan to'xtab qolgan bo'lsa, rollback qilib tozalash
                if hasattr(conn, "closed") and not conn.closed:
                    if not getattr(conn, "autocommit", False):
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                pool.putconn(conn)
                return
            except Exception:
                pass
    try:
        if hasattr(conn, "closed"):
            if not conn.closed:
                conn.close()
        else:
            conn.close()
    except Exception:
        pass

if not USE_POSTGRES:
    import sqlite3
    data_dir = os.getenv("DATA_DIR")
    if data_dir:
        try:
            os.makedirs(data_dir, exist_ok=True)
        except Exception:
            pass
        DB_FILE = os.path.join(data_dir, "test_system.db")
    else:
        DB_FILE = os.getenv("DB_PATH", "test_system.db")


def format_uzb_time(timestamp: Optional[float] = None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """O'zbekiston (Toshkent, UTC+5) vaqti bo'yicha formatlash"""
    if timestamp is None:
        dt = datetime.now(UZB_TZ)
    else:
        dt = datetime.fromtimestamp(timestamp, tz=UZB_TZ)
    return dt.strftime(fmt)


# ──────────────────────────────────────────────────────────
# ULANISH MENEJERI
# ──────────────────────────────────────────────────────────

def get_connection():
    """PostgreSQL yoki SQLite ulanishini qaytaradi (pool orqali)."""
    if USE_POSTGRES:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        pool = _get_pg_pool()
        if pool:
            # Yuqori yuklamada pool to'lib qolsa, kutib turmasdan darhol yangi connect ochish o'rniga
            # qisqa vaqt (30-50ms) kutib qayta urinish (Retry) orqali ulanish oladi
            for attempt in range(4):
                try:
                    conn = pool.getconn()
                    # O'lik / uzilgan ulanishni aniqlab yangilash
                    if hasattr(conn, "closed") and conn.closed:
                        try:
                            pool.putconn(conn, close=True)
                        except Exception:
                            pass
                        conn = pool.getconn()

                    conn_id = id(conn)
                    now_t = time.time()
                    last_used = _conn_last_used.get(conn_id, 0)
                    if now_t - last_used > 45:
                        try:
                            with conn.cursor() as cur_check:
                                cur_check.execute("SELECT 1")
                            conn.rollback()
                        except Exception:
                            try:
                                pool.putconn(conn, close=True)
                            except Exception:
                                pass
                            conn = pool.getconn()
                            conn_id = id(conn)

                    _conn_last_used[conn_id] = now_t
                    conn.cursor_factory = RealDictCursor
                    conn.autocommit = False
                    _pool_connections.add(conn_id)
                    return conn
                except Exception as pe:
                    import psycopg2.pool
                    if isinstance(pe, psycopg2.pool.PoolError) and attempt < 3:
                        time.sleep(0.04 * (attempt + 1))
                        continue
                    break

        # Fallback: Agar pool to'liq to'lgan va kutish muddati tugagan bo'lsagina yangi ulanish
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect(DB_FILE, timeout=20.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=20000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn


def _row_to_dict(row) -> Optional[Dict[str, Any]]:
    """psycopg2 RealDictRow yoki sqlite3.Row ni dict ga o'tkazish."""
    if row is None:
        return None
    return dict(row)


def _commit_and_close(conn):
    """Commit qilib, ulanishni pool ga qaytarish (yoki yopish)."""
    try:
        conn.commit()
    finally:
        _close_conn(conn)


def _placeholder(n: int = 1) -> str:
    """PostgreSQL uchun %s, SQLite uchun ? placeholder qaytaradi."""
    ph = "%s" if USE_POSTGRES else "?"
    if n == 1:
        return ph
    return ", ".join([ph] * n)


def _ph() -> str:
    """Bitta placeholder."""
    return "%s" if USE_POSTGRES else "?"


# ──────────────────────────────────────────────────────────
# JADVALLARNI YARATISH
# ──────────────────────────────────────────────────────────

def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()

        if USE_POSTGRES:
            # PostgreSQL jadvallar
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                tg_id BIGINT UNIQUE NOT NULL,
                fullname TEXT NOT NULL,
                phone TEXT NOT NULL,
                username TEXT,
                status TEXT DEFAULT 'approved',
                pin_code TEXT,
                registered_at BIGINT NOT NULL
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                id SERIAL PRIMARY KEY,
                test_code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                subject TEXT DEFAULT 'Fizika',
                pdf_file_id TEXT,
                pdf_file_name TEXT,
                answers_json TEXT NOT NULL,
                total_questions INTEGER DEFAULT 45,
                time_limit_min INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                key_access_code TEXT,
                results_published INTEGER DEFAULT 0,
                created_at BIGINT NOT NULL,
                created_by BIGINT DEFAULT 0,
                created_by_name TEXT DEFAULT ''
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id SERIAL PRIMARY KEY,
                test_id INTEGER NOT NULL REFERENCES tests(id),
                test_code TEXT NOT NULL,
                user_tg_id BIGINT NOT NULL,
                fullname TEXT NOT NULL,
                phone TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                score REAL NOT NULL,
                max_score REAL DEFAULT 100.0,
                correct_count INTEGER NOT NULL,
                total_count INTEGER DEFAULT 45,
                details_json TEXT NOT NULL,
                submitted_at BIGINT NOT NULL,
                is_late INTEGER DEFAULT 0
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                tg_id BIGINT PRIMARY KEY,
                fullname TEXT,
                username TEXT,
                added_by BIGINT,
                created_at BIGINT NOT NULL
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_history (
                id SERIAL PRIMARY KEY,
                batch_id TEXT UNIQUE NOT NULL,
                sender_tg_id BIGINT DEFAULT 0,
                message_text TEXT DEFAULT '',
                photo_id TEXT DEFAULT '',
                total_sent INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                created_at BIGINT NOT NULL
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_messages (
                id SERIAL PRIMARY KEY,
                batch_id TEXT NOT NULL,
                chat_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                status TEXT DEFAULT 'sent',
                created_at BIGINT NOT NULL
            )
            """)

            # Bosh adminni qo'shish (ON CONFLICT — PostgreSQL)
            cur.execute("""
            INSERT INTO admins (tg_id, fullname, username, added_by, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (tg_id) DO NOTHING
            """, (8039427064, 'Bosh Admin', 'admin', 0, 1789300000))

            # PostgreSQL indekslar (Tezkor qidiruv va yuklamaga chidamlilik)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_user_tg_id ON submissions(user_tg_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_test_id ON submissions(test_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tests_test_code ON tests(test_code)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tests_is_active ON tests(is_active)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bc_msg_batch ON broadcast_messages(batch_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bc_msg_chat ON broadcast_messages(chat_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bc_hist_created ON broadcast_history(created_at)")

            try:
                # Suhrob Olloyorovning (ID 106) brauzerdan topshirgan 25 ta to'g'ri javobini uning akkauntiga biriktirish
                cur.execute("""
                UPDATE submissions 
                SET user_tg_id = 7829748474, fullname = 'Suhrob Olloyorov', phone = '+998332072205'
                WHERE id = 106 AND (user_tg_id = 0 OR user_tg_id IS NULL)
                """)
                # Orphaned anonim test yozuvi 102 ni tozalash
                cur.execute("DELETE FROM submissions WHERE id = 102 AND (user_tg_id = 0 OR user_tg_id IS NULL)")
            except Exception:
                pass

        else:
            # SQLite jadvallar (fallback)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                fullname TEXT NOT NULL,
                phone TEXT NOT NULL,
                username TEXT,
                status TEXT DEFAULT 'approved',
                pin_code TEXT,
                registered_at INTEGER NOT NULL
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                subject TEXT DEFAULT 'Fizika',
                pdf_file_id TEXT,
                pdf_file_name TEXT,
                answers_json TEXT NOT NULL,
                total_questions INTEGER DEFAULT 45,
                time_limit_min INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                key_access_code TEXT,
                results_published INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                created_by INTEGER DEFAULT 0,
                created_by_name TEXT DEFAULT ''
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                test_code TEXT NOT NULL,
                user_tg_id INTEGER NOT NULL,
                fullname TEXT NOT NULL,
                phone TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                score REAL NOT NULL,
                max_score REAL DEFAULT 100.0,
                correct_count INTEGER NOT NULL,
                total_count INTEGER DEFAULT 45,
                details_json TEXT NOT NULL,
                submitted_at INTEGER NOT NULL,
                is_late INTEGER DEFAULT 0,
                FOREIGN KEY(test_id) REFERENCES tests(id)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                tg_id INTEGER PRIMARY KEY,
                fullname TEXT,
                username TEXT,
                added_by INTEGER,
                created_at INTEGER NOT NULL
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT UNIQUE NOT NULL,
                sender_tg_id INTEGER DEFAULT 0,
                message_text TEXT DEFAULT '',
                photo_id TEXT DEFAULT '',
                total_sent INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                status TEXT DEFAULT 'sent',
                created_at INTEGER NOT NULL
            )
            """)

            cur.execute("""
            INSERT OR IGNORE INTO admins (tg_id, fullname, username, added_by, created_at)
            VALUES (8039427064, 'Bosh Admin', 'admin', 0, 1789300000)
            """)

            # SQLite indekslar (Tezkor qidiruv va yuklamaga chidamlilik)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_user_tg_id ON submissions(user_tg_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_test_id ON submissions(test_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tests_test_code ON tests(test_code)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tests_is_active ON tests(is_active)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bc_msg_batch ON broadcast_messages(batch_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bc_msg_chat ON broadcast_messages(chat_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bc_hist_created ON broadcast_history(created_at)")

        # Jadval vaqt va qo'shimcha ustunlar migration (mavjud bo'lsa xato bermaydi)
        if USE_POSTGRES:
            for col, coltype in [
                ("scheduled_date", "TEXT"),
                ("scheduled_start", "TEXT"),
                ("scheduled_end", "TEXT"),
                ("created_by", "BIGINT"),
                ("created_by_name", "TEXT"),
                ("auto_notified", "TEXT"),
                ("youtube_url", "TEXT"),
                ("stopped_at", "BIGINT"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE tests ADD COLUMN IF NOT EXISTS {col} {coltype} DEFAULT NULL")
                    conn.commit()
                except Exception:
                    conn.rollback()
        else:
            for col, coltype in [
                ("scheduled_date", "TEXT"),
                ("scheduled_start", "TEXT"),
                ("scheduled_end", "TEXT"),
                ("created_by", "INTEGER"),
                ("created_by_name", "TEXT"),
                ("auto_notified", "TEXT"),
                ("youtube_url", "TEXT"),
                ("stopped_at", "INTEGER"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE tests ADD COLUMN {col} {coltype} DEFAULT NULL")
                    conn.commit()
                except Exception:
                    pass

        # submissions jadvaliga is_late, status va reject_reason ustunlarini qo'shish
        if USE_POSTGRES:
            try:
                cur.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS is_late INTEGER DEFAULT 0")
                cur.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'accepted'")
                cur.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS reject_reason TEXT DEFAULT ''")
                conn.commit()
            except Exception:
                conn.rollback()
        else:
            try:
                cur.execute("ALTER TABLE submissions ADD COLUMN is_late INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE submissions ADD COLUMN status TEXT DEFAULT 'accepted'")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE submissions ADD COLUMN reject_reason TEXT DEFAULT ''")
            except Exception:
                pass
            conn.commit()

        # Kutilmoqda (pending) bo'lgan mavjud barcha foydalanuvchilarni to'g'ridan-to'g'ri faol (approved) holatiga o'tkazish
        try:
            cur.execute("UPDATE users SET status = 'approved' WHERE status = 'pending'")
        except Exception:
            pass

        conn.commit()
    finally:
        _close_conn(conn)


# ──────────────────────────────────────────────────────────
# TEST JADVAL VAQT BOSHQARUVI (SCHEDULER)
# ──────────────────────────────────────────────────────────

def set_test_schedule(test_id: int, scheduled_date: str, start_time: str, end_time: str) -> bool:
    """Test uchun avtomatik boshlanish/tugash vaqtini o'rnatish.
    scheduled_date: "26.09.2026", start_time: "19:30", end_time: "22:00" (UZB vaqt)
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tests SET scheduled_date={_ph()}, scheduled_start={_ph()}, scheduled_end={_ph()}, auto_notified='' WHERE id={_ph()}",
            (scheduled_date, start_time, end_time, test_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error set_test_schedule: {e}")
        return False
    finally:
        _close_conn(conn)


def mark_test_auto_notified(test_id: int, stage: str) -> bool:
    """Belgilangan bosqich (30m, 10m, started, 15m) xabari yuborilganini belgilash."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT auto_notified FROM tests WHERE id = {_ph()}", (test_id,))
        row = cur.fetchone()
        cur_val = (row[0] if isinstance(row, (list, tuple)) else row.get('auto_notified')) if row else ""
        cur_val = cur_val or ""
        stages = set(s for s in cur_val.split(",") if s)
        stages.add(stage)
        new_val = ",".join(stages)
        cur.execute(f"UPDATE tests SET auto_notified = {_ph()} WHERE id = {_ph()}", (new_val, test_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error mark_test_auto_notified: {e}")
        return False
    finally:
        _close_conn(conn)


def clear_test_schedule(test_id: int) -> bool:
    """Test jadvalini tozalash (avtomatik boshlanish bekor qilish)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tests SET scheduled_date=NULL, scheduled_start=NULL, scheduled_end=NULL WHERE id={_ph()}",
            (test_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error clear_test_schedule: {e}")
        return False
    finally:
        _close_conn(conn)


def set_test_youtube_url(test_id: int, url: str) -> bool:
    """Test uchun YouTube video tahlil havolasini saqlash yoki o'chirish."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        val = url.strip() if url and url.strip() else None
        cur.execute(
            f"UPDATE tests SET youtube_url = {_ph()} WHERE id = {_ph()}",
            (val, test_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error set_test_youtube_url: {e}")
        return False
    finally:
        _close_conn(conn)


def get_test_youtube_url(test_id: int) -> Optional[str]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT youtube_url FROM tests WHERE id = {_ph()}", (test_id,))
        row = cur.fetchone()
        if row:
            d = _row_to_dict(row)
            return d.get("youtube_url")
        return None
    except Exception as e:
        print(f"Error get_test_youtube_url: {e}")
        return None
    finally:
        _close_conn(conn)


def get_next_test_code() -> str:
    """Mavjud testlar ketma-ketligiga qarab keyingi unikal test kodini avtomatik aniqlash."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT test_code FROM tests ORDER BY id ASC")
        rows = cur.fetchall()
        if not rows:
            return "1"

        codes = [str(r[0] if isinstance(r, (list, tuple)) else r['test_code']).strip() for r in rows if r]
        int_codes = [int(c) for c in codes if c.isdigit()]
        if int_codes:
            return str(max(int_codes) + 1)

        import re
        latest_code = codes[-1] if codes else ""
        match = re.match(r'^(.*?)(\d+)$', latest_code)
        if match:
            prefix, num_str = match.groups()
            next_num = int(num_str) + 1
            return f"{prefix}{next_num:0{len(num_str)}d}"

        return str(len(codes) + 1)
    finally:
        _close_conn(conn)


def get_scheduled_tests() -> List[Dict[str, Any]]:
    """Jadval vaqti belgilangan barcha testlarni qaytaradi."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM tests WHERE scheduled_start IS NOT NULL AND scheduled_end IS NOT NULL"
        )
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


# ──────────────────────────────────────────────────────────
# TIZIM SOZLAMALARI VA TEXNIK REJIM (MAINTENANCE MODE)
# ──────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    """Tizim sozlamasini olish."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT value FROM system_settings WHERE key = {_ph()}", (key,))
        row = cur.fetchone()
        if row:
            val = row["value"] if isinstance(row, dict) else row[0]
            return str(val)
        return default
    finally:
        _close_conn(conn)


def set_setting(key: str, value: str):
    """Tizim sozlamasini saqlash yoki yangilash."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
            INSERT INTO system_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (key, str(value)))
        else:
            cur.execute("""
            INSERT INTO system_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, str(value)))
        conn.commit()
    finally:
        _close_conn(conn)


def is_maintenance_mode() -> bool:
    """Texnik profilaktika rejimi yoqilganmi?"""
    return get_setting("maintenance_mode", "0") == "1"


def set_maintenance_mode(enabled: bool):
    """Texnik profilaktika rejimini yoqish yoki o'chirish."""
    set_setting("maintenance_mode", "1" if enabled else "0")


def get_broadcast_users() -> List[Dict[str, Any]]:
    """Xabar tarqatish uchun faol foydalanuvchilar ro'yxati (bloklanmaganlar)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT tg_id, fullname, status FROM users WHERE status NOT IN ('blocked', 'rejected')")
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


def create_broadcast_batch(batch_id: str, sender_tg_id: int = 0, message_text: str = "", photo_id: str = "") -> bool:
    """Yangi broadcast partiyasini yaratish."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = int(time.time())
        sql = f"""
        INSERT INTO broadcast_history (batch_id, sender_tg_id, message_text, photo_id, total_sent, is_deleted, created_at)
        VALUES ({_ph()}, {_ph()}, {_ph()}, {_ph()}, 0, 0, {_ph()})
        """
        cur.execute(sql, (batch_id, sender_tg_id, str(message_text)[:1000], str(photo_id or ''), now))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error create_broadcast_batch: {e}")
        return False
    finally:
        _close_conn(conn)


def record_broadcast_message(batch_id: str, chat_id: int, message_id: int) -> bool:
    """Har bir yuborilgan xabar ID sini saqlash (keyinchalik o'chirish uchun)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = int(time.time())
        sql = f"""
        INSERT INTO broadcast_messages (batch_id, chat_id, message_id, status, created_at)
        VALUES ({_ph()}, {_ph()}, {_ph()}, 'sent', {_ph()})
        """
        cur.execute(sql, (batch_id, chat_id, message_id, now))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error record_broadcast_message: {e}")
        return False
    finally:
        _close_conn(conn)


def update_broadcast_sent_count(batch_id: str, total_sent: int) -> bool:
    """Yuborilgan jami xabarlar sonini yangilash."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = f"UPDATE broadcast_history SET total_sent = {_ph()} WHERE batch_id = {_ph()}"
        cur.execute(sql, (total_sent, batch_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error update_broadcast_sent_count: {e}")
        return False
    finally:
        _close_conn(conn)


def get_broadcast_messages(batch_id: str) -> List[Dict[str, Any]]:
    """Partiyaga tegishli barcha yuborilgan xabar ID lari ro'yxati."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = f"SELECT chat_id, message_id FROM broadcast_messages WHERE batch_id = {_ph()} AND status = 'sent'"
        cur.execute(sql, (batch_id,))
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


def mark_broadcast_deleted(batch_id: str) -> bool:
    """Xabar barcha o'quvchilardan o'chirilganini belgilash."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE broadcast_history SET is_deleted = 1 WHERE batch_id = {_ph()}", (batch_id,))
        cur.execute(f"UPDATE broadcast_messages SET status = 'deleted' WHERE batch_id = {_ph()}", (batch_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error mark_broadcast_deleted: {e}")
        return False
    finally:
        _close_conn(conn)


def get_recent_broadcasts(limit: int = 10) -> List[Dict[str, Any]]:
    """Yaqinda yuborilgan broadcast xabarlari ro'yxati."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = f"SELECT * FROM broadcast_history ORDER BY id DESC LIMIT {_ph()}"
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


def get_broadcast_by_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    """Partiyani kodi orqali olish."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = f"SELECT * FROM broadcast_history WHERE batch_id = {_ph()} LIMIT 1"
        cur.execute(sql, (batch_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        _close_conn(conn)


# ──────────────────────────────────────────────────────────
# USERS & ACCESS
# ──────────────────────────────────────────────────────────

def add_or_update_user(tg_id: int, fullname: str, phone: str,
                       username: Optional[str] = None, status: str = "approved") -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = int(time.time())
        if USE_POSTGRES:
            cur.execute("""
            INSERT INTO users (tg_id, fullname, phone, username, status, registered_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tg_id) DO UPDATE SET
                fullname = EXCLUDED.fullname,
                phone = EXCLUDED.phone,
                username = EXCLUDED.username,
                status = CASE WHEN users.status = 'blocked' THEN 'blocked' ELSE EXCLUDED.status END
            """, (tg_id, fullname, phone, username, status, now))
        else:
            cur.execute("""
            INSERT INTO users (tg_id, fullname, phone, username, status, registered_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                fullname=excluded.fullname,
                phone=excluded.phone,
                username=excluded.username,
                status=CASE WHEN users.status = 'blocked' THEN 'blocked' ELSE excluded.status END
            """, (tg_id, fullname, phone, username, status, now))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving user: {e}")
        return False
    finally:
        _close_conn(conn)


def update_user_profile(tg_id: int, fullname: Optional[str] = None, phone: Optional[str] = None) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        updates = []
        params = []
        if fullname is not None:
            updates.append(f"fullname = {_ph()}")
            params.append(fullname.strip())
        if phone is not None:
            updates.append(f"phone = {_ph()}")
            params.append(phone.strip())
        if not updates:
            return True
        params.append(tg_id)
        sql = f"UPDATE users SET {', '.join(updates)} WHERE tg_id = {_ph()}"
        cur.execute(sql, tuple(params))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating user profile: {e}")
        return False
    finally:
        _close_conn(conn)


def get_user(tg_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM users WHERE tg_id = {_ph()}", (tg_id,))
        row = cur.fetchone()
        return _row_to_dict(row)
    finally:
        _close_conn(conn)


def find_user(query: Any) -> Optional[Dict[str, Any]]:
    """
    Foydalanuvchini turli parametrlar bo'yicha qidiradi:
    - tg_id (masalan: 8039427064)
    - username (masalan: @username yoki username yoki https://t.me/username)
    - telefon raqami (masalan: +998901234567 yoki 998901234567)
    - id (baza ichki id si)
    - fullname (ism-familiya bo'yicha)
    Natija sifatida foydalanuvchi ma'lumotlari, testlar soni va oxirgi topshirgan vaqti qaytariladi.
    """
    if not query:
        return None
    raw_q = str(query).strip()
    if not raw_q:
        return None

    clean_q = raw_q
    for prefix in ["https://t.me/", "http://t.me/", "t.me/"]:
        if clean_q.lower().startswith(prefix):
            clean_q = clean_q[len(prefix):].split("/")[0].split("?")[0]
            break

    clean_uname = clean_q.lstrip("@").strip()
    digits_only = re.sub(r"\D", "", raw_q)

    conn = get_connection()
    try:
        cur = conn.cursor()
        ph = _ph()

        # 1. Telegram ID (aniq moslik)
        if digits_only and len(digits_only) >= 5:
            num_val = int(digits_only)
            cur.execute(f"""
                SELECT u.*, COUNT(s.id) as tests_count, MAX(s.submitted_at) as last_test_at
                FROM users u
                LEFT JOIN submissions s ON u.tg_id = s.user_tg_id
                WHERE u.tg_id = {ph}
                GROUP BY u.id, u.tg_id, u.fullname, u.phone, u.username, u.status, u.pin_code, u.registered_at
            """, (num_val,))
            row = cur.fetchone()
            if row:
                return _row_to_dict(row)

        # 2. Username bo'yicha
        if clean_uname:
            cur.execute(f"""
                SELECT u.*, COUNT(s.id) as tests_count, MAX(s.submitted_at) as last_test_at
                FROM users u
                LEFT JOIN submissions s ON u.tg_id = s.user_tg_id
                WHERE LOWER(u.username) = LOWER({ph})
                GROUP BY u.id, u.tg_id, u.fullname, u.phone, u.username, u.status, u.pin_code, u.registered_at
            """, (clean_uname,))
            row = cur.fetchone()
            if row:
                return _row_to_dict(row)

        # 3. Telefon raqami bo'yicha
        if digits_only and len(digits_only) >= 7:
            cur.execute(f"""
                SELECT u.*, COUNT(s.id) as tests_count, MAX(s.submitted_at) as last_test_at
                FROM users u
                LEFT JOIN submissions s ON u.tg_id = s.user_tg_id
                WHERE u.phone LIKE {ph}
                GROUP BY u.id, u.tg_id, u.fullname, u.phone, u.username, u.status, u.pin_code, u.registered_at
            """, (f"%{digits_only[-9:]}%",))
            row = cur.fetchone()
            if row:
                return _row_to_dict(row)

        # 4. Ichki baza ID raqami bo'yicha (users.id)
        if digits_only:
            try:
                db_id = int(digits_only)
                cur.execute(f"""
                    SELECT u.*, COUNT(s.id) as tests_count, MAX(s.submitted_at) as last_test_at
                    FROM users u
                    LEFT JOIN submissions s ON u.tg_id = s.user_tg_id
                    WHERE u.id = {ph}
                    GROUP BY u.id, u.tg_id, u.fullname, u.phone, u.username, u.status, u.pin_code, u.registered_at
                """, (db_id,))
                row = cur.fetchone()
                if row:
                    return _row_to_dict(row)
            except Exception:
                pass

        # 5. Ism bo'yicha (LOWER LIKE)
        if len(raw_q) >= 3:
            cur.execute(f"""
                SELECT u.*, COUNT(s.id) as tests_count, MAX(s.submitted_at) as last_test_at
                FROM users u
                LEFT JOIN submissions s ON u.tg_id = s.user_tg_id
                WHERE LOWER(u.fullname) LIKE LOWER({ph})
                GROUP BY u.id, u.tg_id, u.fullname, u.phone, u.username, u.status, u.pin_code, u.registered_at
                LIMIT 1
            """, (f"%{raw_q}%",))
            row = cur.fetchone()
            if row:
                return _row_to_dict(row)

        return None
    except Exception as e:
        print(f"Error in find_user: {e}")
        return None
    finally:
        _close_conn(conn)


def is_user_approved(tg_id: int, admin_id: int = 8039427064) -> bool:
    user = get_user(tg_id)
    if not user:
        return True
    return user.get("status") != "blocked"


def approve_user(tg_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE users SET status = 'approved' WHERE tg_id = {_ph()}", (tg_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error approving user: {e}")
        return False
    finally:
        _close_conn(conn)


def reject_user(tg_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE users SET status = 'rejected' WHERE tg_id = {_ph()}", (tg_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error rejecting user: {e}")
        return False
    finally:
        _close_conn(conn)


def set_user_pin(tg_id: int, pin: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE users SET pin_code = {_ph()} WHERE tg_id = {_ph()}", (pin, tg_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting PIN: {e}")
        return False
    finally:
        _close_conn(conn)


def get_user_pin(tg_id: int) -> Optional[str]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT pin_code FROM users WHERE tg_id = {_ph()}", (tg_id,))
        row = cur.fetchone()
        if row:
            d = _row_to_dict(row)
            return d.get("pin_code") if d else None
        return None
    except Exception as e:
        print(f"Error getting PIN: {e}")
        return None
    finally:
        _close_conn(conn)


def block_user(tg_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE users SET status = 'blocked' WHERE tg_id = {_ph()}", (tg_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error blocking user: {e}")
        return False
    finally:
        _close_conn(conn)


def set_user_pending(tg_id: int) -> bool:
    """Foydalanuvchi maqomini 'pending' (kutilmoqda) ga o'tkazadi."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE users SET status = 'pending' WHERE tg_id = {_ph()}", (tg_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting user pending: {e}")
        return False
    finally:
        _close_conn(conn)


def restrict_all_users(super_admin_id: int = 8039427064) -> int:
    """
    Barcha oddiy foydalanuvchilarning maqomini 'pending' (kutilmoqda) ga o'tkazadi.
    Adminlar daxlsiz qoladi.
    Qaytaradi: cheklangan foydalanuvchilar soni.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT tg_id FROM admins")
        admin_rows = cur.fetchall()
        admin_ids = set()
        for r in admin_rows:
            d = _row_to_dict(r)
            if d and d.get("tg_id"):
                admin_ids.add(int(d["tg_id"]))
        admin_ids.add(int(super_admin_id))
        admin_list = list(admin_ids)

        if USE_POSTGRES:
            cur.execute("""
                UPDATE users 
                SET status = 'pending' 
                WHERE NOT (tg_id = ANY(%s)) AND status != 'pending'
            """, (admin_list,))
        else:
            placeholders = ",".join("?" for _ in admin_list)
            cur.execute(f"""
                UPDATE users 
                SET status = 'pending' 
                WHERE tg_id NOT IN ({placeholders}) AND status != 'pending'
            """, admin_list)
        count = cur.rowcount
        conn.commit()
        return count
    except Exception as e:
        print(f"Error restricting all users: {e}")
        return 0
    finally:
        _close_conn(conn)


def delete_user(tg_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM users WHERE tg_id = {_ph()} OR id = {_ph()}", (tg_id, tg_id))
        user_row = _row_to_dict(cur.fetchone())
        actual_tg_id = user_row.get("tg_id") if user_row else tg_id

        # 1. broadcast_messages (chat_id ustuni)
        try:
            cur.execute(f"DELETE FROM broadcast_messages WHERE chat_id = {_ph()}", (actual_tg_id,))
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        # 2. submissions (user_tg_id ustuni)
        try:
            cur.execute(f"DELETE FROM submissions WHERE user_tg_id = {_ph()}", (actual_tg_id,))
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        # 3. users (tg_id va id bo'yicha to'liq o'chirish)
        try:
            cur.execute(f"DELETE FROM users WHERE tg_id = {_ph()} OR id = {_ph()}", (actual_tg_id, tg_id))
            conn.commit()
        except Exception as e3:
            try:
                conn.rollback()
            except Exception:
                pass
            raise e3

        return user_row or {"tg_id": tg_id, "fullname": "Noma'lum", "phone": "—", "username": ""}
    except Exception as e:
        print(f"Error deleting user {tg_id}: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return None
    finally:
        _close_conn(conn)


def delete_all_blocked_users() -> List[Dict[str, Any]]:
    """Bazada status = 'blocked' bo'lgan barcha foydalanuvchilarni butunlay o'chirib tashlash."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE status = 'blocked'")
        rows = cur.fetchall()
        blocked_users = [_row_to_dict(r) for r in rows if r]

        for u in blocked_users:
            uid = u.get("tg_id")
            if uid:
                try:
                    cur.execute(f"DELETE FROM broadcast_messages WHERE chat_id = {_ph()}", (uid,))
                except Exception:
                    pass
                try:
                    cur.execute(f"DELETE FROM submissions WHERE user_tg_id = {_ph()}", (uid,))
                except Exception:
                    pass

        cur.execute("DELETE FROM users WHERE status = 'blocked'")
        conn.commit()
        return blocked_users
    except Exception as e:
        print(f"Error deleting blocked users: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return []
    finally:
        _close_conn(conn)


def get_users_count() -> Dict[str, int]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM users")
        total = (_row_to_dict(cur.fetchone()) or {}).get("total", 0)
        cur.execute("SELECT COUNT(*) as approved FROM users WHERE status = 'approved'")
        approved = (_row_to_dict(cur.fetchone()) or {}).get("approved", 0)
        cur.execute("SELECT COUNT(*) as pending FROM users WHERE status = 'pending'")
        pending = (_row_to_dict(cur.fetchone()) or {}).get("pending", 0)
        cur.execute("SELECT COUNT(*) as blocked FROM users WHERE status = 'blocked'")
        blocked = (_row_to_dict(cur.fetchone()) or {}).get("blocked", 0)
        return {
            "total": total,
            "approved": approved,
            "pending": pending,
            "blocked": blocked
        }
    finally:
        _close_conn(conn)


# ──────────────────────────────────────────────────────────
# TESTS
# ──────────────────────────────────────────────────────────

def create_test(test_code: str, title: str, subject: str, answers: Dict[str, Any],
                pdf_file_id: Optional[str] = None, pdf_file_name: Optional[str] = None,
                time_limit_min: int = 0, key_access_code: str = "",
                created_by: int = 0, created_by_name: str = "",
                youtube_url: str = "") -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = int(time.time())
        if USE_POSTGRES:
            cur.execute("""
            INSERT INTO tests (test_code, title, subject, pdf_file_id, pdf_file_name,
                               answers_json, total_questions, time_limit_min, is_active,
                               key_access_code, results_published, created_at, created_by, created_by_name, youtube_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, 0, %s, %s, %s, %s)
            ON CONFLICT (test_code) DO UPDATE SET
                title = EXCLUDED.title,
                subject = EXCLUDED.subject,
                pdf_file_id = COALESCE(EXCLUDED.pdf_file_id, tests.pdf_file_id),
                pdf_file_name = COALESCE(EXCLUDED.pdf_file_name, tests.pdf_file_name),
                answers_json = EXCLUDED.answers_json,
                time_limit_min = EXCLUDED.time_limit_min,
                key_access_code = EXCLUDED.key_access_code,
                is_active = 1,
                results_published = 0,
                created_by = COALESCE(EXCLUDED.created_by, tests.created_by),
                created_by_name = COALESCE(EXCLUDED.created_by_name, tests.created_by_name),
                youtube_url = COALESCE(NULLIF(EXCLUDED.youtube_url, ''), tests.youtube_url)
            """, (test_code, title, subject, pdf_file_id, pdf_file_name,
                  json.dumps(answers, ensure_ascii=False), 45, time_limit_min,
                  key_access_code, now, created_by, created_by_name, youtube_url or None))
        else:
            cur.execute("""
            INSERT INTO tests (test_code, title, subject, pdf_file_id, pdf_file_name,
                               answers_json, total_questions, time_limit_min, is_active,
                               key_access_code, results_published, created_at, created_by, created_by_name, youtube_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0, ?, ?, ?, ?)
            ON CONFLICT(test_code) DO UPDATE SET
                title=excluded.title,
                subject=excluded.subject,
                pdf_file_id=COALESCE(excluded.pdf_file_id, tests.pdf_file_id),
                pdf_file_name=COALESCE(excluded.pdf_file_name, tests.pdf_file_name),
                answers_json=excluded.answers_json,
                time_limit_min=excluded.time_limit_min,
                key_access_code=excluded.key_access_code,
                is_active=1,
                results_published=0,
                created_by=COALESCE(excluded.created_by, tests.created_by),
                created_by_name=COALESCE(excluded.created_by_name, tests.created_by_name),
                youtube_url=COALESCE(NULLIF(excluded.youtube_url, ''), tests.youtube_url)
            """, (test_code, title, subject, pdf_file_id, pdf_file_name,
                  json.dumps(answers, ensure_ascii=False), 45, time_limit_min,
                  key_access_code, now, created_by, created_by_name, youtube_url or None))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating/updating test: {e}")
        return False
    finally:
        _close_conn(conn)


def update_test_pdf(test_id: int, pdf_file_id: str, pdf_file_name: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tests SET pdf_file_id = {_ph()}, pdf_file_name = {_ph()} WHERE id = {_ph()}",
            (pdf_file_id, pdf_file_name, test_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating test pdf: {e}")
        return False
    finally:
        _close_conn(conn)


def get_active_tests() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tests WHERE is_active = 1 ORDER BY id DESC")
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


def get_test_by_code(test_code: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM tests WHERE test_code = {_ph()}", (test_code,))
        row = cur.fetchone()
        return _row_to_dict(row)
    finally:
        _close_conn(conn)


def get_test_by_id(test_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM tests WHERE id = {_ph()}", (test_id,))
        row = cur.fetchone()
        return _row_to_dict(row)
    finally:
        _close_conn(conn)


get_test = get_test_by_id


def get_all_tests() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tests ORDER BY id DESC")
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


def toggle_test_status(test_id: int) -> Optional[int]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT is_active FROM tests WHERE id = {_ph()}", (test_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = _row_to_dict(row)
        new_status = 0 if d["is_active"] == 1 else 1
        cur.execute(f"UPDATE tests SET is_active = {_ph()} WHERE id = {_ph()}", (new_status, test_id))
        conn.commit()
        return new_status
    except Exception as e:
        print(f"Error toggling test: {e}")
        return None
    finally:
        _close_conn(conn)


def set_test_active_status(test_id: int, status: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        now_ts = int(time.time())
        if not status:
            cur.execute(
                f"UPDATE tests SET is_active = 0, stopped_at = {_ph()} WHERE id = {_ph()}",
                (now_ts, test_id)
            )
        else:
            cur.execute(
                f"UPDATE tests SET is_active = 1 WHERE id = {_ph()}",
                (test_id,)
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting test active status: {e}")
        return False
    finally:
        _close_conn(conn)


def get_test_submission_bounds(test_id: int) -> Dict[str, Any]:
    """Test uchun birinchi va oxirgi topshirilgan vaqtlarni qaytaradi."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT MIN(submitted_at), MAX(submitted_at), COUNT(*) FROM submissions WHERE test_id = {_ph()}",
            (test_id,)
        )
        row = cur.fetchone()
        if row:
            if isinstance(row, dict):
                return {
                    "first_submitted_at": row.get("min") or row.get("MIN(submitted_at)"),
                    "last_submitted_at": row.get("max") or row.get("MAX(submitted_at)"),
                    "count": row.get("count") or 0
                }
            min_ts = row[0]
            max_ts = row[1]
            count = row[2]
            return {
                "first_submitted_at": min_ts,
                "last_submitted_at": max_ts,
                "count": count or 0
            }
        return {"first_submitted_at": None, "last_submitted_at": None, "count": 0}
    except Exception as e:
        print(f"Error getting submission bounds: {e}")
        return {"first_submitted_at": None, "last_submitted_at": None, "count": 0}
    finally:
        _close_conn(conn)


def get_all_tests_submission_bounds() -> Dict[int, Dict[str, Any]]:
    """Barcha testlar uchun birinchi va oxirgi topshirilgan vaqtlarni bitta so'rovda qaytaradi."""
    conn = get_connection()
    res = {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT test_id, MIN(submitted_at) as min_ts, MAX(submitted_at) as max_ts, COUNT(*) as cnt FROM submissions GROUP BY test_id")
        rows = cur.fetchall()
        for row in rows:
            if isinstance(row, dict):
                tid = row.get("test_id")
                if tid:
                    res[int(tid)] = {
                        "first_submitted_at": row.get("min_ts") or row.get("min"),
                        "last_submitted_at": row.get("max_ts") or row.get("max"),
                        "count": row.get("cnt") or row.get("count") or 0
                    }
            else:
                tid = row[0]
                if tid:
                    res[int(tid)] = {
                        "first_submitted_at": row[1],
                        "last_submitted_at": row[2],
                        "count": row[3] or 0
                    }
        return res
    except Exception as e:
        print(f"Error getting all submission bounds: {e}")
        return res
    finally:
        _close_conn(conn)


def update_test_time_limit(test_id: int, time_limit_min: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tests SET time_limit_min = {_ph()} WHERE id = {_ph()}",
            (time_limit_min, test_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating test time limit: {e}")
        return False
    finally:
        _close_conn(conn)


def set_test_results_published(test_id: int, published: bool = True) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tests SET results_published = {_ph()} WHERE id = {_ph()}",
            (1 if published else 0, test_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error publishing results: {e}")
        return False
    finally:
        _close_conn(conn)


def is_test_results_published(test_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT results_published FROM tests WHERE id = {_ph()}", (test_id,))
        row = cur.fetchone()
        if row:
            d = _row_to_dict(row)
            return bool(d.get("results_published", 0))
        return False
    except Exception:
        return False
    finally:
        _close_conn(conn)


def get_test_submissions_with_users(test_id: int, include_late: bool = False) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        late_cond = "" if include_late else "AND (s.is_late = 0 OR s.is_late IS NULL)"
        cur.execute(f"""
        SELECT s.*, t.title as test_title, t.test_code, t.results_published, t.youtube_url
        FROM submissions s
        JOIN tests t ON s.test_id = t.id
        WHERE s.test_id = {_ph()} {late_cond}
        ORDER BY s.score DESC, s.submitted_at ASC
        """, (test_id,))
        rows = cur.fetchall()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            if d:
                d["grade"] = calculate_grade(d.get("score", 0.0))
                out.append(d)
        return out
    finally:
        _close_conn(conn)


def delete_test(test_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM submissions WHERE test_id = {_ph()}", (test_id,))
        cur.execute(f"DELETE FROM tests WHERE id = {_ph()}", (test_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        _close_conn(conn)


# ──────────────────────────────────────────────────────────
# ADMINS
# ──────────────────────────────────────────────────────────

def is_admin(tg_id: int, super_admin_id: int = 8039427064) -> bool:
    if tg_id == super_admin_id:
        return True
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT tg_id FROM admins WHERE tg_id = {_ph()}", (tg_id,))
        row = cur.fetchone()
        return bool(row)
    finally:
        _close_conn(conn)


def add_admin(tg_id: int, fullname: str = "Admin", username: Optional[str] = None, added_by: int = 0) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = int(time.time())
        if USE_POSTGRES:
            cur.execute("""
            INSERT INTO admins (tg_id, fullname, username, added_by, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (tg_id) DO UPDATE SET
                fullname = EXCLUDED.fullname,
                username = EXCLUDED.username
            """, (tg_id, fullname, username, added_by, now))
        else:
            cur.execute("""
            INSERT INTO admins (tg_id, fullname, username, added_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                fullname=excluded.fullname,
                username=excluded.username
            """, (tg_id, fullname, username, added_by, now))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding admin: {e}")
        return False
    finally:
        _close_conn(conn)


def remove_admin(tg_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM admins WHERE tg_id = {_ph()}", (tg_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        _close_conn(conn)


def get_all_admins() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM admins ORDER BY created_at ASC")
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


def get_all_users() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT u.*, COUNT(s.id) as tests_count, MAX(s.submitted_at) as last_test_at
        FROM users u
        LEFT JOIN submissions s ON u.tg_id = s.user_tg_id
        GROUP BY u.id, u.tg_id, u.fullname, u.phone, u.username, u.status, u.pin_code, u.registered_at
        ORDER BY u.registered_at DESC
        """)
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


# ──────────────────────────────────────────────────────────
# SUBMISSIONS / RESULTS
# ──────────────────────────────────────────────────────────

def parse_answers_json(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


DASHES_PATTERN = r"[\u2212\u2013\u2014\u2012\u2015\uFE63\uFF0D\u00ad]"
MULT_SYMS_PATTERN = r"[\u00d7\u00b7\u2022\u2219\u22c5\u2715\u2716]"


def normalize_answer(ans: Any) -> str:
    if ans is None:
        return ""
    s = str(ans).strip()

    # 1. Bo'shliqlar, ko'rinmas belgilar va dollar belgilarini olib tashlash
    s = re.sub(r"[\s\u200b\u200c\u200d\u00a0\uFEFF\$]", "", s)

    # 2. Barcha klaviaturalardagi minus/chiziqchalarni bitta standart '-' belgisiga keltirish
    s = re.sub(DASHES_PATTERN, "-", s)

    # 3. Barcha ko'paytirish belgilarini '*' ga keltirish
    s = re.sub(MULT_SYMS_PATTERN, "*", s)
    s = re.sub(r"\\+(?:cdot|times)\b", "*", s)

    # 4. Bo'lish belgilarini '/' ga keltirish
    s = re.sub(r"[\u00f7]", "/", s)

    # 5. O'nlik kasrlardagi vergul: 2,5 -> 2.5
    s = re.sub(r"(\d+),(\d+)", r"\g<1>.\g<2>", s)

    # 6. Plus-minus belgisi
    s = re.sub(r"(\+\/\-|\+\s*\-|\+\-)", "±", s)

    # 7. Pi soni: \pi, pi, PI -> π
    s = re.sub(r"(^|[^a-zA-Z])\\*pi(?![a-zA-Z])", r"\g<1>π", s, flags=re.IGNORECASE)

    # 7b. Cheksizlik (Infinity): \infty, infty, infinity, inf, cheksiz, cheksizlik -> ∞
    s = s.replace(r"\\infty", "∞").replace(r"\infty", "∞").replace(r"\inf", "∞")
    s = re.sub(r"(?:infinity|infty|inf|cheksiz(?:lik)?)\b", "∞", s, flags=re.IGNORECASE)
    # Musbat cheksizlik: +∞ -> ∞
    s = re.sub(r"(?<![0-9a-zA-Z])\+∞", "∞", s)

    # Oraliqlardagi vergul: [0, ∞) -> [0;∞), (-∞, 5) -> (-∞;5)
    s = re.sub(r"([0-9a-zA-Z∞\.\-\+]+),([0-9a-zA-Z∞\.\-\+]+)", r"\1;\2", s)

    # 8. Darajalarni standart ^ shakliga keltirish
    for sup, norm in [("⁰", "^0"), ("¹", "^1"), ("²", "^2"), ("³", "^3"), ("⁴", "^4"),
                      ("⁵", "^5"), ("⁶", "^6"), ("⁷", "^7"), ("⁸", "^8"), ("⁹", "^9"), ("ⁿ", "^n")]:
        s = s.replace(sup, norm)

    # 9. LaTeX residuallari: \frac, \sqrt, \sqrt[n]
    while re.search(r"\\+sqrt\[([^\]]+)\]\{([^{}]+)\}", s):
        s = re.sub(r"\\+sqrt\[([^\]]+)\]\{([^{}]+)\}", r"\1√\2", s)
    while re.search(r"\\+d?frac\{([^{}]+)\}\{([^{}]+)\}", s):
        s = re.sub(r"\\+d?frac\{([^{}]+)\}\{([^{}]+)\}", r"\1/\2", s)
    while "sqrt{" in s:
        s = re.sub(r"\\+sqrt\{([^{}]+)\}", r"√\1", s)
    s = re.sub(r"\\+sqrt([0-9a-zA-Z]+)", r"√\1", s)
    s = re.sub(r"sqrt\(", "√(", s)
    s = s.replace("sqrt", "√")

    # Ildizlar va darajalar
    s = s.replace("cbrt", "∛")

    # Ildiz qavslari: "√(29)" -> "√29", "5√(32)" -> "5√32"
    while re.search(r"([0-9a-zA-Z]*√)\(([0-9a-zA-Z]+)\)", s):
        s = re.sub(r"([0-9a-zA-Z]*√)\(([0-9a-zA-Z]+)\)", r"\1\2", s)
    while re.search(r"^\(([0-9a-zA-Z]*√[0-9a-zA-Z]+)\)$", s):
        s = re.sub(r"^\(([0-9a-zA-Z]*√[0-9a-zA-Z]+)\)$", r"\1", s)

    # Raqam va qavsli ildiz: "8(√58)" -> "8√58" (lekin 32(√2+1) emas!)
    s = re.sub(r"(\d)\((√[0-9a-zA-Z]+)\)", r"\1\2", s)

    # Tashqi ortiqcha qavslar: (-3π/2) -> -3π/2
    while s.startswith("(") and s.endswith(")") and s.count("(") == 1:
        s = s[1:-1]

    # "x = ", "x1 = ", "javob:" kabi prefikslarni tozalash
    s = re.sub(r"^(?:[a-zA-Z]|x\d*|y\d*|k\d*)\s*=\s*", "", s)
    s = re.sub(r"^(?:javob|ans)\s*:\s*", "", s, flags=re.IGNORECASE)

    # Ortiqcha figurali qavslar va sleshlar
    s = re.sub(r"\{([^{}]+)\}", r"\1", s)
    s = s.replace("\\", "")

    return s.strip().lower()


def eval_numeric_val(expr: str) -> Optional[float]:
    """Matematik ifodaning sonli qiymatini xavfsiz hisoblash (π, √, kasrlar va darajalar bilan)."""
    s = normalize_answer(expr)
    if not s or "±" in s:
        return None

    # Agar x, y, a kabi algebraik noma'lumlar bo'lsa, sonli hisoblab bo'lmaydi
    clean_for_vars = re.sub(r"(math|sqrt|pi|abs|exp)", "", s)
    if re.search(r"[a-df-oq-z]", clean_for_vars):
        return None

    # 1. LaTeX va maxsus n-darajali ildizlar
    s = re.sub(r"\\+sqrt\[([^\]]+)\]\{([^{}]+)\}", r"((\2)**(1/(\1)))", s)
    s = re.sub(r"∛\(([^()]+)\)", r"((\1)**(1/3))", s)
    s = re.sub(r"∛(\d+(?:\.\d+)?)", r"((\1)**(1/3))", s)
    s = re.sub(r"∜\(([^()]+)\)", r"((\1)**(1/4))", s)
    s = re.sub(r"∜(\d+(?:\.\d+)?)", r"((\1)**(1/4))", s)

    # 2. Kvadrat ildiz: avval √(...) va √son larni math.sqrt(...) ga aylantiramiz
    s = re.sub(r"√\(([^()]+)\)", r"math.sqrt(\1)", s)
    s = re.sub(r"√(\d+(?:\.\d+)?)", r"math.sqrt(\1)", s)
    s = s.replace("√", "math.sqrt")

    # 3. math.sqrt oldidagi ko'paytirish (masalan: 32math.sqrt(2) -> 32*math.sqrt(2))
    s = re.sub(r"(\d)math\.sqrt", r"\1*math.sqrt", s)
    s = re.sub(r"(\))math\.sqrt", r"\1*math.sqrt", s)

    # 4. Pi va ko'paytirish
    s = re.sub(r"(\d)π", r"\1*math.pi", s)
    s = re.sub(r"(\))π", r"\1*math.pi", s)
    s = re.sub(r"π(\d)", r"math.pi*\1", s)
    s = re.sub(r"(\))\s*\(", r"\1*(", s)
    s = re.sub(r"(\d)\s*\(", r"\1*(", s)
    s = re.sub(r"(\))\s*(\d)", r"\1*\2", s)
    s = s.replace("π", "math.pi")
    s = s.replace("^", "**")

    allowed = set("0123456789.+-*/()math.sqrtpi ")
    if not set(s).issubset(allowed):
        return None
    try:
        val = eval(s, {"__builtins__": None, "math": math})
        return float(val)
    except Exception:
        return None


def count_binary_plus_minus(s: str) -> int:
    """
    Ifodadagi binar qo'shish va ayirish amallarini sanash.
    Masalan:
      '133+5/13' -> 1 ('+')
      '140-5/13' -> 1 ('-')
      '-133-5/13' -> 1 (birinchi '-' unar, ikkinchi '-' binar)
      '1734/13'  -> 0
      '-1734/13' -> 0
      '85/√13'   -> 0
      '(85√13)/13' -> 0
    """
    if not s:
        return 0
    cnt = 0
    for i, ch in enumerate(s):
        if ch == "+":
            cnt += 1
        elif ch == "-":
            if i > 0 and s[i - 1] not in ("(", "*", "/", "^", "±", "[", "{"):
                cnt += 1
    return cnt




# ── FIZIKA JAVOBLARINI SOLISHTIRISH (SI birliklar va prefikslar bilan) ──────────
_SUPERSCRIPT_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_SI_PREFIXES = {
    "p": 1e-12, "n": 1e-9, "μ": 1e-6, "µ": 1e-6, "u": 1e-6, "mk": 1e-6, "mc": 1e-6,
    "m": 1e-3, "c": 1e-2, "s": 1e-2, "d": 1e-1, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12,
}
# Asosiy birliklar (uzunroqlari birinchi tekshiriladi)
_BASE_UNITS = {
    "eV": ("eV", 1.0), "Hz": ("Hz", 1.0), "Pa": ("Pa", 1.0), "Wb": ("Wb", 1.0),
    "mol": ("mol", 1.0), "ohm": ("Ω", 1.0), "Om": ("Ω", 1.0), "Ω": ("Ω", 1.0),
    "min": ("s", 60.0), "J": ("J", 1.0), "N": ("N", 1.0), "W": ("W", 1.0),
    "V": ("V", 1.0), "A": ("A", 1.0), "C": ("C", 1.0), "F": ("F", 1.0),
    "H": ("H", 1.0), "T": ("T", 1.0), "K": ("K", 1.0), "L": ("L", 1.0),
    "l": ("L", 1.0), "g": ("g", 1.0), "m": ("m", 1.0), "s": ("s", 1.0),
}
_BASE_ORDER = sorted(_BASE_UNITS.keys(), key=len, reverse=True)
_PHYS_WORDS_RE = re.compile(r"\b(?:ga|marta|ga\s+teng|teng)\b", re.IGNORECASE)


def clean_physics_str(s: str) -> str:
    """Fizika javobini normallashtirish (registr saqlanadi: M=mega, m=milli)."""
    if not s:
        return ""
    s = str(s).strip()
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    s = s.replace("≈", "").replace("~", "").replace("`", "'").replace("’", "'").replace("'", "'")
    s = s.replace("×", "*").replace("·", "*").replace("⋅", "*")
    s = s.replace("²", "^2").replace("³", "^3")
    s = s.translate(_SUPERSCRIPT_MAP)
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_unit_factor(tok: str):
    """'kV' -> ({'V':1}, 1e3); 'cm^2' -> ({'m':2}, 1e-4). Tanilmasa None."""
    m = re.fullmatch(r"([A-Za-zμµΩ]+)(?:\^?(-?\d+))?", tok)
    if not m:
        return None
    name, exp = m.group(1), int(m.group(2) or 1)
    if name in ("sm", "cm"):  # santimetr
        return {"m": exp}, (1e-2) ** exp
    if name in ("kg",):
        return {"g": exp}, (1e3) ** exp
    for attempt in (name, name.lower()):
        bases = _BASE_ORDER if attempt == name else [b for b in _BASE_ORDER if b == b.lower()] + ["j", "n", "w", "v", "a", "hz", "pa", "ev"]
        for base in bases:
            if not attempt.endswith(base):
                continue
            prefix = attempt[: -len(base)]
            key = base if base in _BASE_UNITS else {"j": "J", "n": "N", "w": "W", "v": "V", "a": "A", "hz": "Hz", "pa": "Pa", "ev": "eV"}[base]
            dim, mult = _BASE_UNITS[key]
            if prefix == "":
                scale = mult
            elif prefix in _SI_PREFIXES:
                scale = _SI_PREFIXES[prefix] * mult
            else:
                continue
            return {dim: exp}, scale ** exp
    return None


def parse_physics_unit(unit: str):
    """'kV/m' -> ({'V':1,'m':-1}, 1000.0). Bo'sh -> ({}, 1.0). Tanilmasa None."""
    unit = (unit or "").strip().strip(".")
    if not unit:
        return {}, 1.0
    unit = unit.replace(" ", "")
    dims, scale = {}, 1.0
    parts = re.split(r"(/|\*)", unit)
    sign = 1
    for p in parts:
        if p == "/":
            sign = -1
            continue
        if p == "*":
            continue
        if not p:
            continue
        r = _parse_unit_factor(p)
        if r is None:
            return None
        d, sc = r
        for k, v in d.items():
            dims[k] = dims.get(k, 0) + sign * v
        scale *= sc ** sign
    dims = {k: v for k, v in dims.items() if v != 0}
    return dims, scale


def extract_physics_number_and_unit(s: str):
    """'1.45*10^-6 J ga kamaydi' -> (-1.45e-6, 'J', clean). Son bo'lmasa (None, '', clean)."""
    clean = clean_physics_str(s)
    work = clean
    negative_word = bool(re.search(r"kamay", work, re.IGNORECASE))
    work = re.sub(r"\b(?:ga\s+)?(?:kamaydi|kamayadi|ortdi|ortadi|oshdi|oshadi)\b", " ", work, flags=re.IGNORECASE)
    work = _PHYS_WORDS_RE.sub(" ", work)
    m = re.search(r"([-+]?\d+(?:\.\d+)?)(?:\s*(?:\*|x)\s*10\s*\^?\s*\(?\s*([-+]?\d+)\s*\)?|\s*e([-+]?\d+))?", work)
    if not m:
        return None, "", clean
    try:
        num_val = float(m.group(1))
        exp = m.group(2) or m.group(3)
        if exp:
            num_val *= 10 ** int(exp)
    except Exception:
        return None, "", clean
    if negative_word and num_val > 0:
        num_val = -num_val
    unit_part = (work[: m.start()] + " " + work[m.end():]).strip()
    unit_part = re.sub(r"\s+", "", unit_part)
    return num_val, unit_part, clean


def _num_close(a: float, b: float, approx: bool) -> bool:
    tol = 0.035 if approx else 1e-3
    return abs(a - b) <= max(1e-9, tol * max(abs(a), abs(b)))


def check_physics_match(u_raw: Any, c_raw: Any) -> bool:
    """Fizika javoblari: SI prefikslar (nJ = 1e-9 J), birliklar, vergul/nuqta,
    taqribiy (≈) qiymatlar, 'kamaydi' = manfiy, 'N-nur' va matnli javoblar."""
    if u_raw is None or c_raw is None:
        return False
    c_full = str(c_raw)
    u_full = str(u_raw)
    u = clean_physics_str(u_full)
    c = clean_physics_str(c_full)
    if not u or not c:
        return False
    approx = ("≈" in c_full) or ("~" in c_full) or ("≈" in u_full) or ("~" in u_full)

    if u.lower().replace(" ", "") == c.lower().replace(" ", ""):
        return True

    # Matnli maxsus javoblar (masalan: "hech qaysi nur" vs "hech qaysi" vs "hech biri")
    if any(h in c.lower() for h in ["hech", "yo'q", "mavjud emas"]):
        if any(h in u.lower() for h in ["hech", "yo'q", "mavjud emas"]):
            return True

    # Qavs ichidagi muqobil javob: "2-nur (1,89 eV)" -> "2-nur" yoki "1,89 eV"
    paren = re.match(r"^(.*?)\s*\((.+)\)\s*$", c)
    if paren:
        return check_physics_match(u_raw, paren.group(1)) or check_physics_match(u_raw, paren.group(2))

    # Faqat maxsus "N-nur", "N-holat" kabi tartib raqamlar
    ord_m = re.fullmatch(r"(\d+)\s*-?\s*(nur|holat|qism|daraja)\b.*", c, re.IGNORECASE)
    if ord_m:
        u_ord = re.fullmatch(r"(\d+)\s*-?\s*([A-Za-z'ʻ]*)", u)
        if u_ord and u_ord.group(1) == ord_m.group(1):
            return True

    c_num, c_unit, _ = extract_physics_number_and_unit(c)
    u_num, u_unit, _ = extract_physics_number_and_unit(u)

    if c_num is None:
        # Matnli javob (masalan: "hech qaysi nur")
        cw = set(re.findall(r"[a-zA-Z'ʻ]+", c.lower())) - {"nur"}
        uw = set(re.findall(r"[a-zA-Z'ʻ]+", u.lower())) - {"nur"}
        return bool(cw) and cw == uw
    if u_num is None:
        return False

    # Birlik yozilmagan bo'lsa: faqat son bo'yicha (kalitdagi birlikda deb hisoblanadi)
    if not u_unit or not c_unit:
        return _num_close(u_num, c_num, approx)

    pu, pc = parse_physics_unit(u_unit), parse_physics_unit(c_unit)
    if pu is None or pc is None:
        # Noma'lum birlik — matn bo'yicha qat'iy solishtirish
        same_unit = u_unit.replace("^", "").lower() == c_unit.replace("^", "").lower()
        return same_unit and _num_close(u_num, c_num, approx)
    (du, su), (dc, sc) = pu, pc
    if du != dc:
        return False
    return _num_close(u_num * su, c_num * sc, approx)


def check_answer_match(user_ans: Any, correct_ans: Any) -> Tuple[bool, float, str]:
    """
    Foydalanuvchi javobini to'g'ri kalitga solishtirish va moslik koeffitsientini hisoblash:
    Returns:
        (is_matched, ratio, status)
        - is_matched: bool (True agar qabul qilinsa)
        - ratio: float (1.0 = 100% to'liq to'g'ri, 0.3 = 30% oxirgacha hisoblanmagan, 0.0 = noto'g'ri)
        - status: str ("correct", "partial", "incorrect")
    """
    if user_ans is None or correct_ans is None:
        return (False, 0.0, "incorrect")
    u_str = str(user_ans).strip()
    c_str = str(correct_ans).strip()
    if not u_str or not c_str:
        return (False, 0.0, "incorrect")

    # Kalitda bir nechta to'g'ri variant berilgan bo'lsa (masalan: "2; 5" yoki "-3π/2 | 3π/2")
    if any(sep in c_str for sep in [";", "|", "yoki", "or"]):
        parts = [p.strip() for p in re.split(r";|\||\byoki\b|\bor\b", c_str) if p.strip()]
        best_res = (False, 0.0, "incorrect")
        for p in parts:
            res = check_answer_match(user_ans, p)
            if res[1] > best_res[1]:
                best_res = res
            if best_res[1] >= 1.0:
                return best_res
        return best_res

    # 0. Fizika maxsus mosligi (birliklar, vergulli sonlar, taqribiy qiymatlar)
    if check_physics_match(u_str, c_str):
        return (True, 1.0, "correct")

    u = normalize_answer(u_str)
    c = normalize_answer(c_str)

    # 1. Aniq matnli moslik -> 100% to'g'ri
    if u == c:
        return (True, 1.0, "correct")

    # 2. Yulduzcha ko'paytirish belgisi farqi: 8*√58 == 8√58, 36*π == 36π -> 100% to'g'ri
    if u.replace("*", "") == c.replace("*", ""):
        return (True, 1.0, "correct")

    # 3. Yig'indi hadlarining o'rin almashuvi: 120 + 36π == 36π + 120, 6 + 2√2 == 2√2 + 6 -> 100% to'g'ri
    if "+" in u and "+" in c:
        u_terms = sorted([t.strip().replace("*", "") for t in u.split("+") if t.strip()])
        c_terms = sorted([t.strip().replace("*", "") for t in c.split("+") if t.strip()])
        if u_terms == c_terms:
            return (True, 1.0, "correct")

    # 4. Matematik ifoda sonli qiymatlarini solishtirish
    num_u = eval_numeric_val(u)
    num_c = eval_numeric_val(c)
    if num_u is not None and num_c is not None:
        # Ishoralari qat'iy bir xil bo'lishi shart (-3π/2 musbat 3π/2 ga teng bo'lolmaydi)
        if (num_u > 1e-6 and num_c < -1e-6) or (num_u < -1e-6 and num_c > 1e-6):
            return (False, 0.0, "incorrect")
        if abs(num_u - num_c) < 1e-4:
            # Agar foydalanuvchi javobida hisoblanmay qolib ketgan + yoki - bo'lsa (masalan: 133+5/13 vs 1734/13):
            # User talabi: "oxirgacha qisqartirilmagan... +,- bilan hisoblanib qolib ketgan misollarga 100% ball berilmasin, 30% berilsin"
            if count_binary_plus_minus(u) > count_binary_plus_minus(c):
                return (True, 0.3, "partial")
            return (True, 1.0, "correct")

    return (False, 0.0, "incorrect")


def is_answer_matching(user_ans: Any, correct_ans: Any) -> bool:
    """Oldingi kodlar bilan to'liq moslik uchun yordamchi funksiya."""
    matched, _, _ = check_answer_match(user_ans, correct_ans)
    return matched


def get_user_submission_for_test(test_id: int, user_tg_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM submissions WHERE test_id = {_ph()} AND user_tg_id = {_ph()}",
            (test_id, user_tg_id)
        )
        row = cur.fetchone()
        return _row_to_dict(row)
    finally:
        _close_conn(conn)


def get_user_submissions_map(user_tg_id: int) -> Dict[int, Dict[str, Any]]:
    """Foydalanuvchining barcha topshirgan testlarini {test_id: submission_dict} qilib qaytaradi."""
    if not user_tg_id:
        return {}
    conn = get_connection()
    res = {}
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM submissions WHERE user_tg_id = {_ph()}",
            (user_tg_id,)
        )
        rows = cur.fetchall()
        for r in rows:
            d = _row_to_dict(r)
            if d and d.get('test_id'):
                res[int(d['test_id'])] = d
        return res
    except Exception as e:
        print(f"Error get_user_submissions_map: {e}")
        return res
    finally:
        _close_conn(conn)


def get_submission_by_id(submission_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM submissions WHERE id = {_ph()}", (submission_id,))
        row = cur.fetchone()
        return _row_to_dict(row)
    finally:
        _close_conn(conn)


def set_submission_late_status(submission_id: int, is_late: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE submissions SET is_late = {_ph()} WHERE id = {_ph()}",
            (is_late, submission_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating late status: {e}")
        return False
    finally:
        _close_conn(conn)


def reject_submission(submission_id: int, reason: str = "") -> bool:
    """O'quvchining topshirgan javoblarini rad etadi / bekor qiladi (qabul qilmaydi)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE submissions SET status = 'rejected', reject_reason = {_ph()} WHERE id = {_ph()}",
            (reason, submission_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error rejecting submission: {e}")
        return False
    finally:
        _close_conn(conn)


def delete_submission(submission_id: int) -> bool:
    """O'quvchining topshirgan javoblarini o'chiradi (testni qayta topshirish imkonini beradi)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM submissions WHERE id = {_ph()}", (submission_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting submission: {e}")
        return False
    finally:
        _close_conn(conn)


def get_key_and_score(q_data: Any, default_score: float) -> tuple:
    if isinstance(q_data, dict):
        ans = str(q_data.get("ans", q_data.get("answer", "")))
        try:
            score = float(q_data.get("score", q_data.get("ball", default_score)))
        except (ValueError, TypeError):
            score = default_score
        return ans, score
    else:
        return str(q_data or ""), default_score


def calculate_grade(score: float, correct_count: Optional[int] = None) -> str:
    if correct_count is not None and correct_count == 0:
        return "—"
    if score <= 0.0:
        return "—"
    if score >= 70.0:
        return "A+"
    elif score >= 65.0:
        return "A"
    elif score >= 60.0:
        return "B+"
    elif score >= 55.0:
        return "B"
    elif score >= 50.0:
        return "C+"
    elif score >= 46.0:
        return "C"
    else:
        return "—"


def check_and_save_submission(test_id: int, user_tg_id: int, user_answers: Dict[str, str], is_late: int = 0) -> Dict[str, Any]:
    test = get_test_by_id(test_id)
    if not test:
        raise ValueError("Test topilmadi!")

    if not user_tg_id or int(user_tg_id) <= 0:
        raise ValueError("⚠️ Web orqali ishlash mumkin emas! Testni faqat rasmiy Telegram botimiz (@fizika_rash_testbot) va Mini ilova orqali topshirish mumkin.")

    existing = get_user_submission_for_test(test_id, user_tg_id)
    if existing:
        if is_admin(user_tg_id, ADMIN_ID):
            conn_del = get_connection()
            try:
                cur_del = conn_del.cursor()
                cur_del.execute(
                    f"DELETE FROM submissions WHERE id = {_ph()}", (existing["id"],)
                )
                conn_del.commit()
            finally:
                _close_conn(conn_del)
        else:
            raise ValueError("Siz ushbu testni allaqachon topshirgansiz! Qayta topshirish taqiqlanadi.")

    user = get_user(user_tg_id) if user_tg_id else None
    fullname = user["fullname"] if user else "Foydalanuvchi"
    phone = user["phone"] if user else "-"

    correct_answers_raw = json.loads(test["answers_json"])

    total_questions = 55
    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0
    details = {}
    earned_score = 0.0
    total_possible_score = 0.0

    # 1-32 savollar (4 variant, default 2.0 ball)
    for q in range(1, 33):
        key = str(q)
        q_raw = correct_answers_raw.get(key, "A")
        correct_ans, q_score = get_key_and_score(q_raw, default_score=2.0)
        total_possible_score += q_score
        user_val = user_answers.get(key, "")
        is_corr = False
        if not user_val or not str(user_val).strip():
            status = "unanswered"
            unanswered_count += 1
        elif is_answer_matching(user_val, correct_ans):
            is_corr = True
            status = "correct"
            correct_count += 1
            earned_score += q_score
        else:
            status = "incorrect"
            incorrect_count += 1
        details[key] = {
            "num": f"{q}-savol", "type": "choice_4",
            "user": user_val, "correct": correct_ans,
            "status": status,
            "score": q_score if is_corr else 0.0,
            "max_score": q_score
        }

    # 33, 34, 35 savollar (6 variant, default 2.0 ball)
    for q in [33, 34, 35]:
        key = str(q)
        q_raw = correct_answers_raw.get(key, "A")
        correct_ans, q_score = get_key_and_score(q_raw, default_score=2.0)
        total_possible_score += q_score
        user_val = user_answers.get(key, "")
        is_corr = False
        if not user_val or not str(user_val).strip():
            status = "unanswered"
            unanswered_count += 1
        elif is_answer_matching(user_val, correct_ans):
            is_corr = True
            status = "correct"
            correct_count += 1
            earned_score += q_score
        else:
            status = "incorrect"
            incorrect_count += 1
        details[key] = {
            "num": f"{q}-savol", "type": "choice_6",
            "user": user_val, "correct": correct_ans,
            "status": status,
            "score": q_score if is_corr else 0.0,
            "max_score": q_score
        }

    # 36a–45b ochiq savollar (default 1.5 ball)
    for q in range(36, 46):
        for sub in ["a", "b"]:
            key = f"{q}{sub}"
            q_raw = correct_answers_raw.get(key, "1")
            correct_ans, q_score = get_key_and_score(q_raw, default_score=1.5)
            total_possible_score += q_score
            user_val = user_answers.get(key, "")
            is_matched, ratio, match_status = check_answer_match(user_val, correct_ans)
            if not user_val or not str(user_val).strip():
                status = "unanswered"
                unanswered_count += 1
                item_score = 0.0
            elif is_matched:
                if ratio >= 1.0:
                    status = "correct"
                    correct_count += 1
                    item_score = q_score
                    earned_score += q_score
                else:
                    status = "partial"
                    item_score = round(q_score * 0.3, 2)
                    earned_score += item_score
            else:
                status = "incorrect"
                incorrect_count += 1
                item_score = 0.0

            details[key] = {
                "num": f"{key}-savol", "type": "open",
                "user": user_val, "correct": correct_ans,
                "status": status,
                "score": item_score,
                "max_score": q_score,
                "ratio": ratio
            }

    earned_score = round(earned_score, 1)
    if correct_count == 0:
        earned_score = 0.0
        grade = "—"
    elif correct_count == 55:
        earned_score = 100.0
        grade = "A+"
    else:
        grade = calculate_grade(earned_score, correct_count=correct_count)
    total_possible_score = 100.0
    percentage = round((earned_score / total_possible_score) * 100.0, 1)
    rasch_theta = 0.0

    now = int(time.time())
    conn = get_connection()
    try:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
            INSERT INTO submissions (
                test_id, test_code, user_tg_id, fullname, phone,
                answers_json, score, max_score, correct_count, total_count,
                details_json, submitted_at, is_late
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """, (
                test["id"], test["test_code"], user_tg_id, fullname, phone,
                json.dumps(user_answers, ensure_ascii=False), earned_score, total_possible_score,
                correct_count, 55,
                json.dumps(details, ensure_ascii=False), now, is_late
            ))
            sub_row = cur.fetchone()
            submission_id = _row_to_dict(sub_row).get("id") if sub_row else None
        else:
            cur.execute("""
            INSERT INTO submissions (
                test_id, test_code, user_tg_id, fullname, phone,
                answers_json, score, max_score, correct_count, total_count,
                details_json, submitted_at, is_late
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test["id"], test["test_code"], user_tg_id, fullname, phone,
                json.dumps(user_answers, ensure_ascii=False), earned_score, total_possible_score,
                correct_count, 55,
                json.dumps(details, ensure_ascii=False), now, is_late
            ))
            submission_id = cur.lastrowid
        conn.commit()
    finally:
        _close_conn(conn)

    return {
        "submission_id": submission_id,
        "is_late": is_late,
        "submitted_at": now,
        "test_title": test["title"],
        "test_code": test["test_code"],
        "fullname": fullname,
        "score": earned_score,
        "max_score": total_possible_score,
        "percentage": percentage,
        "grade": grade,
        "rasch_theta": rasch_theta,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unanswered_count": unanswered_count,
        "details": details,
        "submitted_at": now
    }


def get_user_submissions(user_tg_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
        SELECT s.*, t.title as test_title, t.results_published, t.is_active
        FROM submissions s
        JOIN tests t ON s.test_id = t.id
        WHERE s.user_tg_id = {_ph()} ORDER BY s.id DESC
        """, (user_tg_id,))
        rows = cur.fetchall()
    finally:
        _close_conn(conn)
    results = []
    for r in rows:
        d = _row_to_dict(r)
        if not d:
            continue
        is_pub = bool(d.get("results_published", 0))
        d["results_published"] = is_pub
        is_rejected = (str(d.get("status", "")).strip().lower() == "rejected")
        d["is_rejected"] = is_rejected
        if is_rejected:
            d["grade"] = "Bekor qilingan"
            d["score"] = 0
            d["correct_count"] = 0
            d["incorrect_count"] = 0
            d["status_text"] = "Bekor qilingan"
        elif is_pub:
            d["grade"] = calculate_grade(d.get("score", 0))
        else:
            d["grade"] = "Kutilmoqda"
            d["score"] = None
            d["correct_count"] = None
            d["total_count"] = None
            d["details_json"] = "{}"
        results.append(d)
    return results


def get_test_results_leaderboard(test_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
        SELECT fullname, phone, score, correct_count, submitted_at
        FROM submissions
        WHERE test_id = {_ph()} AND (is_late = 0 OR is_late IS NULL)
        ORDER BY score DESC, submitted_at ASC
        """, (test_id,))
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


def get_tests_with_stats() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT t.*, COUNT(s.id) as submissions_count,
               COALESCE(AVG(s.score), 0) as avg_score,
               COALESCE(MAX(s.score), 0) as max_score_achieved
        FROM tests t
        LEFT JOIN submissions s ON t.id = s.test_id AND (s.is_late = 0 OR s.is_late IS NULL)
        GROUP BY t.id, t.test_code, t.title, t.subject, t.pdf_file_id, t.pdf_file_name,
                 t.answers_json, t.total_questions, t.time_limit_min, t.is_active,
                 t.key_access_code, t.results_published, t.created_at, t.created_by, t.created_by_name
        ORDER BY t.id DESC
        """)
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


# ──────────────────────────────────────────────────────────
# RASCH MODEL INTEGRATION
# ──────────────────────────────────────────────────────────

def get_test_submissions_for_rasch(test_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
        SELECT user_tg_id, fullname, details_json, score, correct_count, submitted_at
        FROM submissions
        WHERE test_id = {_ph()} AND details_json IS NOT NULL AND details_json != ''
          AND (is_late = 0 OR is_late IS NULL)
        ORDER BY submitted_at ASC
        """, (test_id,))
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        _close_conn(conn)


def evaluate_test_rasch(test_id: int, auto_update_db: bool = False) -> Optional[Dict[str, Any]]:
    try:
        from rasch_engine import evaluate_single_test
        res = evaluate_single_test(test_id, get_test_submissions_for_rasch)
        if res and auto_update_db and res.get("students"):
            item_score_map = {
                it["item_label"].replace("Q", ""): it.get("item_score", 1.0)
                for it in res.get("items", [])
            }
            conn = get_connection()
            try:
                cur = conn.cursor()
                for s in res["students"]:
                    student_id = s.get("student_id")
                    final_score = s.get("final_score", 0.0)
                    cur.execute(f"""
                        SELECT id, details_json FROM submissions
                        WHERE test_id = {_ph()} AND (user_tg_id = {_ph()} OR id = {_ph()})
                    """, (test_id, student_id, student_id))
                    row = cur.fetchone()
                    if row:
                        d = _row_to_dict(row)
                        sub_id = d["id"]
                        det_raw = d["details_json"]
                        try:
                            det = json.loads(det_raw) if det_raw else {}
                            for k, v in det.items():
                                if k in item_score_map:
                                    is_c = (v.get("status") == "correct")
                                    sc = item_score_map[k]
                                    v["score"] = sc if is_c else 0.0
                                    v["max_score"] = sc
                            new_det = json.dumps(det, ensure_ascii=False)
                            cur.execute(f"""
                                UPDATE submissions
                                SET score = {_ph()}, details_json = {_ph()}
                                WHERE id = {_ph()}
                            """, (final_score, new_det, sub_id))
                        except Exception:
                            cur.execute(
                                f"UPDATE submissions SET score = {_ph()} WHERE id = {_ph()}",
                                (final_score, sub_id)
                            )
                conn.commit()
            finally:
                _close_conn(conn)
        return res
    except ImportError:
        print("[rasch] rasch_engine.py topilmadi — Rasch baholash o'tkazib yuborildi.")
        return None
    except Exception as e:
        print(f"[rasch] Xatolik: {e}")
        return None


# ──────────────────────────────────────────────────────────
# PDF GENERATION HELPERS
# ──────────────────────────────────────────────────────────

CYRILLIC_TO_LATIN = {
    'А': 'A', 'а': 'a', 'Б': 'B', 'б': 'b', 'В': 'V', 'в': 'v',
    'Г': 'G', 'г': 'g', 'Д': 'D', 'д': 'd', 'Е': 'E', 'е': 'e',
    'Ё': 'Yo', 'ё': 'yo', 'Ж': 'J', 'ж': 'j', 'З': 'Z', 'з': 'z',
    'И': 'I', 'и': 'i', 'Й': 'Y', 'й': 'y', 'К': 'K', 'к': 'k',
    'Л': 'L', 'л': 'l', 'М': 'M', 'м': 'm', 'Н': 'N', 'н': 'n',
    'О': 'O', 'о': 'o', 'П': 'P', 'п': 'p', 'Р': 'R', 'р': 'r',
    'С': 'S', 'с': 's', 'Т': 'T', 'т': 't', 'У': 'U', 'у': 'u',
    'Ф': 'F', 'ф': 'f', 'Х': 'X', 'х': 'x', 'Ц': 'Ts', 'ц': 'ts',
    'Ч': 'Ch', 'ч': 'ch', 'Ш': 'Sh', 'ш': 'sh', 'Щ': 'Sh', 'щ': 'sh',
    'Ъ': "'", 'ъ': "'", 'Ь': '', 'ь': '', 'Э': 'E', 'э': 'e',
    'Ю': 'Yu', 'ю': 'yu', 'Я': 'Ya', 'я': 'ya',
    'Ў': "O'", 'ў': "o'", 'Қ': 'Q', 'қ': 'q', 'Ғ': "G'", 'ғ': "g'",
    'Ҳ': 'H', 'ҳ': 'h'
}


def transliterate_cyrillic(text: str) -> str:
    if not text:
        return ""
    return "".join(CYRILLIC_TO_LATIN.get(ch, ch) for ch in text)


def _clean_pdf_text(text: Any) -> str:
    if text is None:
        return ""
    s = str(text).strip()
    s = re.sub(r'[\U00010000-\U0010ffff]', '', s)
    s = re.sub(r'[\u200B-\u200D\uFEFF]', '', s)
    s = s.replace("—", "-").replace("–", "-").replace("−", "-")
    for ch in ["ʻ", "ʼ", "'", "'", "′", "`", "´", "ʹ", "ʽ"]:
        s = s.replace(ch, "'")
    for q in [""", """, "„", "«", "»"]:
        s = s.replace(q, '"')
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.strip()


def generate_test_results_pdf(test_id: int) -> Optional[str]:
    """Test natijalari bo'yicha rasmiy PDF reyting jadvali generatsiya qiladi."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        test = get_test_by_id(test_id)
        if not test:
            return None

        results = get_test_results_leaderboard(test_id)

        pdf_filename = f"test_result_{test_id}_{int(time.time())}.pdf"
        pdf_path = os.path.join(os.path.dirname(__file__), pdf_filename)

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            leftMargin=30, rightMargin=30,
            topMargin=30, bottomMargin=30
        )

        font_name = 'Helvetica'
        font_bold = 'Helvetica-Bold'

        font_dir = os.path.join(os.path.dirname(__file__), 'fonts')
        possible_regular = [
            os.path.join(font_dir, 'Arial.ttf'),
            '/System/Library/Fonts/Supplemental/Arial.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/Library/Fonts/Arial.ttf'
        ]
        possible_bold = [
            os.path.join(font_dir, 'Arial-Bold.ttf'),
            '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/Library/Fonts/Arial Bold.ttf'
        ]

        reg_path = next((p for p in possible_regular if os.path.exists(p)), None)
        bld_path = next((p for p in possible_bold if os.path.exists(p)), None)

        if reg_path:
            try:
                pdfmetrics.registerFont(TTFont('UnicodeSans', reg_path))
                font_name = 'UnicodeSans'
            except Exception as fe:
                print(f"Font regular error: {fe}")

        if bld_path:
            try:
                pdfmetrics.registerFont(TTFont('UnicodeSansBold', bld_path))
                font_bold = 'UnicodeSansBold'
            except Exception as fe:
                print(f"Font bold error: {fe}")
        elif font_name == 'UnicodeSans':
            font_bold = 'UnicodeSans'

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'],
                                     fontName=font_bold, fontSize=15, leading=19,
                                     textColor=colors.HexColor("#1E3A8A"), alignment=1)
        subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'],
                                        fontName=font_name, fontSize=10, leading=14,
                                        textColor=colors.HexColor("#475569"), alignment=1)
        header_cell_style = ParagraphStyle('HeaderCellStyle', parent=styles['Normal'],
                                           fontName=font_bold, fontSize=9, leading=12,
                                           textColor=colors.HexColor("#1E3A8A"), alignment=1)
        cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'],
                                    fontName=font_name, fontSize=9, leading=12, alignment=1)
        cell_name_style = ParagraphStyle('CellNameStyle', parent=styles['Normal'],
                                         fontName=font_name, fontSize=9, leading=12, alignment=0)
        cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'],
                                   fontName=font_bold, fontSize=9, leading=12, alignment=1)

        elements = []
        elements.append(Paragraph("FIZIKA - MILLIY SERTIFIKAT", title_style))
        elements.append(Spacer(1, 6))

        test_title_clean = _clean_pdf_text(test['title'])
        test_subject_clean = _clean_pdf_text(test.get('subject', 'Fizika'))
        if font_name == 'Helvetica':
            test_title_clean = transliterate_cyrillic(test_title_clean)
            test_subject_clean = transliterate_cyrillic(test_subject_clean)

        elements.append(Paragraph(f"Test: <b>{test_title_clean}</b> | Fan: {test_subject_clean}", subtitle_style))
        elements.append(Paragraph(f"Jami ishtirokchilar soni: <b>{len(results)} nafar</b> | Sana: {format_uzb_time()}", subtitle_style))
        elements.append(Spacer(1, 14))

        table_data = [[
            Paragraph("<b>O'rin</b>", header_cell_style),
            Paragraph("<b>Ism va Familiya</b>", header_cell_style),
            Paragraph("<b>To'plangan Ball</b>", header_cell_style),
            Paragraph("<b>Daraja</b>", header_cell_style),
            Paragraph("<b>To'g'ri</b>", header_cell_style),
            Paragraph("<b>Topshirilgan Vaqt</b>", header_cell_style)
        ]]

        for rank, r in enumerate(results, 1):
            dt = format_uzb_time(r["submitted_at"], "%d.%m %H:%M")
            grade = calculate_grade(r["score"])
            fullname_clean = _clean_pdf_text(r["fullname"] or "Foydalanuvchi")
            if font_name == 'Helvetica':
                fullname_clean = transliterate_cyrillic(fullname_clean)
            grade_clean = _clean_pdf_text(grade)

            table_data.append([
                Paragraph(f"<b>#{rank}</b>", cell_bold),
                Paragraph(f"&nbsp;{fullname_clean}", cell_name_style),
                Paragraph(f"<b>{r['score']} ball</b>", cell_bold),
                Paragraph(f"<b>{grade_clean}</b>", cell_style),
                Paragraph(f"{r['correct_count']} ta", cell_style),
                Paragraph(dt, cell_style)
            ])

        col_widths = [45, 215, 80, 70, 55, 70]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(t)
        doc.build(elements)
        return pdf_path
    except Exception as e:
        import traceback
        print(f"PDF Generation Error: {e}")
        traceback.print_exc()
        return None



def update_test_keys(test_id: int, new_answers: Dict[str, Any],
                     title: Optional[str] = None,
                     time_limit_min: Optional[int] = None,
                     key_access_code: Optional[str] = None,
                     scheduled_date: Optional[str] = None,
                     scheduled_start: Optional[str] = None,
                     scheduled_end: Optional[str] = None,
                     youtube_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Test kalitlarini yangilaydi va shu testga topshirilgan barcha o'quvchilar javoblarini
    yangi kalitlar bo'yicha qayta tekshirib, Rasch modelini va PDF reytingni avtomatik yangilaydi.
    """
    test = get_test_by_id(test_id)
    if not test:
        raise ValueError(f"ID #{test_id} ga ega test topilmadi!")

    answers_json = json.dumps(new_answers, ensure_ascii=False)

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Testning yangilangan ma'lumotlarini saqlash
        update_fields = [f"answers_json = {_ph()}"]
        params: List[Any] = [answers_json]

        if title is not None and str(title).strip():
            update_fields.append(f"title = {_ph()}")
            params.append(str(title).strip())
        if time_limit_min is not None:
            update_fields.append(f"time_limit_min = {_ph()}")
            params.append(int(time_limit_min))
        if key_access_code is not None:
            update_fields.append(f"key_access_code = {_ph()}")
            params.append(str(key_access_code).strip())
        if scheduled_date is not None:
            update_fields.append(f"scheduled_date = {_ph()}")
            params.append(str(scheduled_date).strip())
        if scheduled_start is not None:
            update_fields.append(f"scheduled_start = {_ph()}")
            params.append(str(scheduled_start).strip())
        if scheduled_end is not None:
            update_fields.append(f"scheduled_end = {_ph()}")
            params.append(str(scheduled_end).strip())
        if youtube_url is not None:
            update_fields.append(f"youtube_url = {_ph()}")
            params.append(str(youtube_url).strip())

        params.append(test_id)
        sql = f"UPDATE tests SET {', '.join(update_fields)} WHERE id = {_ph()}"
        cur.execute(sql, tuple(params))

        # 2. Barcha topshirilgan javoblarni (submissions) yangi kalitlar bo'yicha qayta tekshirish
        cur.execute(f"SELECT id, answers_json, user_tg_id FROM submissions WHERE test_id = {_ph()}", (test_id,))
        subs = [_row_to_dict(r) for r in cur.fetchall()]

        updated_count = 0
        correct_answers_raw = new_answers

        for sub in subs:
            sub_id = sub["id"]
            ans_raw = sub.get("answers_json")
            if not ans_raw:
                continue
            try:
                user_answers = json.loads(ans_raw)
            except Exception:
                user_answers = {}

            correct_count = 0
            incorrect_count = 0
            unanswered_count = 0
            details = {}
            earned_score = 0.0
            total_possible_score = 0.0

            # 1-32 savollar (4 variant, default 2.0 ball)
            for q in range(1, 33):
                key = str(q)
                q_raw = correct_answers_raw.get(key, "A")
                correct_ans, q_score = get_key_and_score(q_raw, default_score=2.0)
                total_possible_score += q_score
                user_val = user_answers.get(key, "")
                is_corr = False
                if not user_val or not str(user_val).strip():
                    status = "unanswered"
                    unanswered_count += 1
                elif is_answer_matching(user_val, correct_ans):
                    is_corr = True
                    status = "correct"
                    correct_count += 1
                    earned_score += q_score
                else:
                    status = "incorrect"
                    incorrect_count += 1
                details[key] = {
                    "num": f"{q}-savol", "type": "choice_4",
                    "user": user_val, "correct": correct_ans,
                    "status": status,
                    "score": q_score if is_corr else 0.0,
                    "max_score": q_score
                }

            # 33, 34, 35 savollar (6 variant, default 2.0 ball)
            for q in [33, 34, 35]:
                key = str(q)
                q_raw = correct_answers_raw.get(key, "A")
                correct_ans, q_score = get_key_and_score(q_raw, default_score=2.0)
                total_possible_score += q_score
                user_val = user_answers.get(key, "")
                is_corr = False
                if not user_val or not str(user_val).strip():
                    status = "unanswered"
                    unanswered_count += 1
                elif is_answer_matching(user_val, correct_ans):
                    is_corr = True
                    status = "correct"
                    correct_count += 1
                    earned_score += q_score
                else:
                    status = "incorrect"
                    incorrect_count += 1
                details[key] = {
                    "num": f"{q}-savol", "type": "choice_6",
                    "user": user_val, "correct": correct_ans,
                    "status": status,
                    "score": q_score if is_corr else 0.0,
                    "max_score": q_score
                }

            # 36a–45b ochiq savollar (default 1.5 ball)
            for q in range(36, 46):
                for sub_part in ["a", "b"]:
                    key = f"{q}{sub_part}"
                    q_raw = correct_answers_raw.get(key, "1")
                    correct_ans, q_score = get_key_and_score(q_raw, default_score=1.5)
                    total_possible_score += q_score
                    user_val = user_answers.get(key, "")
                    is_matched, ratio, match_status = check_answer_match(user_val, correct_ans)
                    if not user_val or not str(user_val).strip():
                        status = "unanswered"
                        unanswered_count += 1
                        item_score = 0.0
                    elif is_matched:
                        if ratio >= 1.0:
                            status = "correct"
                            correct_count += 1
                            item_score = q_score
                            earned_score += q_score
                        else:
                            status = "partial"
                            item_score = round(q_score * 0.3, 2)
                            earned_score += item_score
                    else:
                        status = "incorrect"
                        incorrect_count += 1
                        item_score = 0.0

                    details[key] = {
                        "num": f"{key}-savol", "type": "open",
                        "user": user_val, "correct": correct_ans,
                        "status": status,
                        "score": item_score,
                        "max_score": q_score,
                        "ratio": ratio
                    }

            earned_score = round(earned_score, 1)
            cur.execute(f"""
                UPDATE submissions
                SET score = {_ph()}, correct_count = {_ph()}, details_json = {_ph()}
                WHERE id = {_ph()}
            """, (earned_score, correct_count, json.dumps(details, ensure_ascii=False), sub_id))
            updated_count += 1

        conn.commit()
    finally:
        _close_conn(conn)

    # 3. Rasch modelini yangilangan kalitlar va javoblar bo'yicha qayta hisoblash
    rasch_res = None
    try:
        rasch_res = evaluate_test_rasch(test_id, auto_update_db=True)
    except Exception as e:
        print(f"Rasch re-eval error: {e}")

    # 4. Yangilangan natijalar bo'yicha PDF reytingni qayta generatsiya qilish
    try:
        generate_test_results_pdf(test_id)
    except Exception as e:
        print(f"PDF regeneration error: {e}")

    return {
        "success": True,
        "test_id": test_id,
        "recalculated_count": updated_count,
        "rasch_updated": bool(rasch_res)
    }


# ──────────────────────────────────────────────────────────
# MACBOOK DASHBOARD / ADMIN APIS
# ──────────────────────────────────────────────────────────

def _fetch_scalar(row, key: str = "cnt") -> Any:
    if row is None:
        return 0
    if isinstance(row, dict):
        return row.get(key, list(row.values())[0]) if row else 0
    return row[0]


def get_dashboard_summary() -> Dict[str, Any]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        now_ts = int(time.time())
        today_midnight = now_ts - (now_ts % 86400) - (5 * 3600)
        if today_midnight > now_ts:
            today_midnight -= 86400

        cur.execute(f"""
        SELECT 
            (SELECT COUNT(*) FROM users) as total_users,
            (SELECT COUNT(*) FROM users WHERE status = 'approved') as approved_users,
            (SELECT COUNT(*) FROM users WHERE status = 'pending') as pending_users,
            (SELECT COUNT(*) FROM users WHERE status = 'blocked') as blocked_users,
            (SELECT COUNT(*) FROM tests) as total_tests,
            (SELECT COUNT(*) FROM tests WHERE is_active = 1) as active_tests,
            (SELECT COUNT(*) FROM submissions) as total_submissions,
            (SELECT COUNT(*) FROM submissions WHERE is_late = 1) as late_submissions,
            (SELECT COUNT(*) FROM submissions WHERE submitted_at >= {_ph()}) as today_submissions,
            (SELECT COALESCE(AVG(score), 0) FROM submissions WHERE score IS NOT NULL) as avg_score,
            (SELECT COALESCE(AVG(correct_count), 0) FROM submissions WHERE correct_count IS NOT NULL) as avg_correct
        """, (today_midnight,))
        row = cur.fetchone()
        d = _row_to_dict(row) or {}

        return {
            "total_users": int(d.get("total_users") or 0),
            "approved_users": int(d.get("approved_users") or 0),
            "pending_users": int(d.get("pending_users") or 0),
            "blocked_users": int(d.get("blocked_users") or 0),
            "total_tests": int(d.get("total_tests") or 0),
            "active_tests": int(d.get("active_tests") or 0),
            "total_submissions": int(d.get("total_submissions") or 0),
            "today_submissions": int(d.get("today_submissions") or 0),
            "late_submissions": int(d.get("late_submissions") or 0),
            "avg_score": round(float(d.get("avg_score") or 0.0), 1),
            "avg_correct": round(float(d.get("avg_correct") or 0.0), 1),
            "db_type": "PostgreSQL (Neon Cloud)" if USE_POSTGRES else "SQLite (Local)"
        }
    finally:
        _close_conn(conn)


def get_all_submissions_for_admin(limit: int = 1000) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
        SELECT s.id, s.test_id, s.test_code, s.user_tg_id, s.fullname, s.phone,
               s.score, s.max_score, s.correct_count, s.total_count,
               s.submitted_at, s.is_late, s.status, s.reject_reason,
               u.username, u.status as user_status,
               t.title as test_title, t.subject as test_subject,
               t.results_published, t.is_active as test_is_active
        FROM submissions s
        LEFT JOIN users u ON s.user_tg_id = u.tg_id
        LEFT JOIN tests t ON s.test_id = t.id
        ORDER BY s.submitted_at DESC
        LIMIT {int(limit)}
        """)
        rows = cur.fetchall()
        results = []
        for r in rows:
            d = _row_to_dict(r)
            if not d:
                continue
            d["grade"] = calculate_grade(d.get("score", 0), correct_count=d.get("correct_count", 0))
            results.append(d)
        return results
    finally:
        _close_conn(conn)


def get_user_submissions_for_admin(user_tg_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
        SELECT s.id, s.test_id, s.test_code, s.user_tg_id, s.fullname, s.phone,
               s.score, s.max_score, s.correct_count, s.total_count,
               s.submitted_at, s.is_late, s.status, s.reject_reason,
               u.username, u.status as user_status,
               t.title as test_title, t.subject as test_subject,
               t.results_published, t.is_active as test_is_active
        FROM submissions s
        LEFT JOIN users u ON s.user_tg_id = u.tg_id
        LEFT JOIN tests t ON s.test_id = t.id
        WHERE s.user_tg_id = {_ph()}
        ORDER BY s.submitted_at DESC
        """, (user_tg_id,))
        rows = cur.fetchall()
        results = []
        for r in rows:
            d = _row_to_dict(r)
            if not d:
                continue
            d["grade"] = calculate_grade(d.get("score", 0), correct_count=d.get("correct_count", 0))
            results.append(d)
        return results
    finally:
        _close_conn(conn)


get_user_results = get_user_submissions_for_admin


def get_submission_details_for_admin(sub_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
        SELECT s.*, u.username, u.status as user_status,
               t.title as test_title, t.subject as test_subject, t.answers_json as test_keys_json
        FROM submissions s
        LEFT JOIN users u ON s.user_tg_id = u.tg_id
        LEFT JOIN tests t ON s.test_id = t.id
        WHERE s.id = {_ph()}
        """, (sub_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = _row_to_dict(row)
        d["grade"] = calculate_grade(d.get("score", 0), correct_count=d.get("correct_count", 0))
        return d
    finally:
        _close_conn(conn)


def get_activity_logs(limit: int = 60) -> List[Dict[str, Any]]:
    """Tizimdagi so'nggi jarayonlar va voqealar xronologiyasi."""
    events = []
    conn = get_connection()
    try:
        cur = conn.cursor()
        # 1. So'nggi topshirilgan testlar
        cur.execute(f"""
        SELECT s.id, s.user_tg_id, s.fullname, s.submitted_at, s.score, s.correct_count, s.is_late,
               s.test_code, t.title as test_title, u.username
        FROM submissions s
        LEFT JOIN tests t ON s.test_id = t.id
        LEFT JOIN users u ON s.user_tg_id = u.tg_id
        ORDER BY s.submitted_at DESC
        LIMIT {int(limit)}
        """)
        for r in cur.fetchall():
            d = _row_to_dict(r)
            if d:
                events.append({
                    "type": "late_submission" if d.get("is_late") else "submission",
                    "time": d.get("submitted_at"),
                    "title": f"Test topshirildi: {d.get('test_title') or '#' + str(d.get('test_code'))}",
                    "user_name": d.get("fullname"),
                    "username": d.get("username"),
                    "user_id": d.get("user_tg_id"),
                    "badge": f"{d.get('correct_count', 0)} to'g'ri • {d.get('score', 0)} ball" + (" (Kech)" if d.get("is_late") else ""),
                    "badge_color": "warning" if d.get("is_late") else "success",
                    "data_id": d.get("id")
                })
        
        # 2. So'nggi ro'yxatdan o'tgan foydalanuvchilar
        cur.execute(f"""
        SELECT id, tg_id, fullname, username, phone, status, registered_at
        FROM users
        ORDER BY registered_at DESC
        LIMIT {int(limit // 2)}
        """)
        for r in cur.fetchall():
            d = _row_to_dict(r)
            if d:
                events.append({
                    "type": "registration",
                    "time": d.get("registered_at"),
                    "title": "Yangi foydalanuvchi qo'shildi",
                    "user_name": d.get("fullname"),
                    "username": d.get("username"),
                    "user_id": d.get("tg_id"),
                    "badge": d.get("status", "approved").capitalize(),
                    "badge_color": "danger" if d.get("status") == "blocked" else ("warning" if d.get("status") == "pending" else "info"),
                    "data_id": d.get("id")
                })

        # Vaqt bo'yicha kamayish tartibida saralash
        events.sort(key=lambda x: x.get("time") or 0, reverse=True)
        return events[:limit]
    finally:
        _close_conn(conn)


def execute_admin_safe_query(query: str, limit: int = 100) -> Dict[str, Any]:
    """Admin uchun xavfsiz SELECT so'rovlarini bajarish."""
    q = (query or "").strip()
    if not q.lower().startswith("select"):
        return {"success": False, "error": "Faqat SELECT so'rovlarini bajarish mumkin!"}
    
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(q)
        rows = cur.fetchmany(limit)
        results = [_row_to_dict(r) for r in rows if r]
        return {
            "success": True,
            "count": len(results),
            "rows": results
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        _close_conn(conn)


def recalculate_all_submissions_globally() -> int:
    """Barcha testlarning topshirilgan javoblarini yangi qoidalar (masalan, uncomputed +/- ga 30% ball) bo'yicha qayta hisoblash."""
    conn = get_connection()
    total_recalculated = 0
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, answers_json FROM tests")
        tests = [_row_to_dict(r) for r in cur.fetchall()]
        for t in tests:
            test_id = t["id"]
            raw_answers = t.get("answers_json")
            if not raw_answers:
                continue
            try:
                answers_dict = json.loads(raw_answers)
            except Exception:
                continue
            cur.execute(f"SELECT id, answers_json FROM submissions WHERE test_id = {_ph()}", (test_id,))
            subs = [_row_to_dict(r) for r in cur.fetchall()]
            for sub in subs:
                sub_id = sub["id"]
                sub_ans_raw = sub.get("answers_json")
                if not sub_ans_raw:
                    continue
                try:
                    user_answers = json.loads(sub_ans_raw)
                except Exception:
                    continue

                correct_count = 0
                incorrect_count = 0
                unanswered_count = 0
                details = {}
                earned_score = 0.0

                for q in range(1, 33):
                    key = str(q)
                    correct_ans, q_score = get_key_and_score(answers_dict.get(key, "A"), default_score=2.0)
                    user_val = user_answers.get(key, "")
                    is_matched, ratio, _ = check_answer_match(user_val, correct_ans)
                    if not user_val or not str(user_val).strip():
                        status = "unanswered"
                        unanswered_count += 1
                        score = 0.0
                    elif is_matched and ratio >= 1.0:
                        status = "correct"
                        correct_count += 1
                        score = q_score
                        earned_score += q_score
                    else:
                        status = "incorrect"
                        incorrect_count += 1
                        score = 0.0
                    details[key] = {
                        "num": f"{q}-savol", "type": "choice_4",
                        "user": user_val, "correct": correct_ans,
                        "status": status, "score": score, "max_score": q_score
                    }

                for q in [33, 34, 35]:
                    key = str(q)
                    correct_ans, q_score = get_key_and_score(answers_dict.get(key, "A"), default_score=2.0)
                    user_val = user_answers.get(key, "")
                    is_matched, ratio, _ = check_answer_match(user_val, correct_ans)
                    if not user_val or not str(user_val).strip():
                        status = "unanswered"
                        unanswered_count += 1
                        score = 0.0
                    elif is_matched and ratio >= 1.0:
                        status = "correct"
                        correct_count += 1
                        score = q_score
                        earned_score += q_score
                    else:
                        status = "incorrect"
                        incorrect_count += 1
                        score = 0.0
                    details[key] = {
                        "num": f"{q}-savol", "type": "choice_6",
                        "user": user_val, "correct": correct_ans,
                        "status": status, "score": score, "max_score": q_score
                    }

                for q in range(36, 46):
                    for sub_part in ["a", "b"]:
                        key = f"{q}{sub_part}"
                        correct_ans, q_score = get_key_and_score(answers_dict.get(key, "1"), default_score=1.5)
                        user_val = user_answers.get(key, "")
                        is_matched, ratio, _ = check_answer_match(user_val, correct_ans)
                        if not user_val or not str(user_val).strip():
                            status = "unanswered"
                            unanswered_count += 1
                            score = 0.0
                        elif is_matched:
                            if ratio >= 1.0:
                                status = "correct"
                                correct_count += 1
                                score = q_score
                                earned_score += q_score
                            else:
                                status = "partial"
                                score = round(q_score * 0.3, 2)
                                earned_score += score
                        else:
                            status = "incorrect"
                            incorrect_count += 1
                            score = 0.0
                        details[key] = {
                            "num": f"{key}-savol", "type": "open",
                            "user": user_val, "correct": correct_ans,
                            "status": status, "score": score, "max_score": q_score, "ratio": ratio
                        }

                earned_score = round(earned_score, 1)
                cur.execute(f"""
                    UPDATE submissions
                    SET score = {_ph()}, correct_count = {_ph()}, details_json = {_ph()}
                    WHERE id = {_ph()}
                """, (earned_score, correct_count, json.dumps(details, ensure_ascii=False), sub_id))
                total_recalculated += 1
        conn.commit()
        return total_recalculated
    except Exception as e:
        print(f"Global recalculate submissions xatolik: {e}")
        return total_recalculated
    finally:
        _close_conn(conn)


# Baza inicializatsiyasi
init_db()

