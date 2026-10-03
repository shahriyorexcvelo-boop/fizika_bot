import os
"""
SQLite → PostgreSQL (Neon.tech) Migration Script v2
Avval jadvallar yaratadi, keyin barcha ma'lumotlarni ko'chiradi.
"""
import sqlite3
import sys

SQLITE_FILE = "test_system.db"
PG_URL = os.getenv("DATABASE_URL", "")

def migrate():
    print("📂 SQLite bazasidan ma'lumotlar o'qilmoqda...")
    sq = sqlite3.connect(SQLITE_FILE)
    sq.row_factory = sqlite3.Row
    sq_cur = sq.cursor()

    print("🔗 PostgreSQL (Neon.tech) ga ulanilmoqda...")
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        pg = psycopg2.connect(PG_URL, cursor_factory=RealDictCursor)
        pg.autocommit = False
        pg_cur = pg.cursor()
        print("✅ PostgreSQL ulanish muvaffaqiyatli!\n")
    except Exception as e:
        print(f"❌ PostgreSQL ulanishda xatolik: {e}")
        sys.exit(1)

    # ── 0. JADVALLARNI YARATISH ────────────────────────────
    print("🏗  Jadvallar yaratilmoqda (agar mavjud bo'lmasa)...")
    pg_cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        tg_id BIGINT UNIQUE NOT NULL,
        fullname TEXT NOT NULL,
        phone TEXT NOT NULL,
        username TEXT,
        status TEXT DEFAULT 'pending',
        pin_code TEXT,
        registered_at BIGINT NOT NULL
    )""")

    pg_cur.execute("""
    CREATE TABLE IF NOT EXISTS tests (
        id SERIAL PRIMARY KEY,
        test_code TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        subject TEXT DEFAULT 'Matematika',
        pdf_file_id TEXT,
        pdf_file_name TEXT,
        answers_json TEXT NOT NULL,
        total_questions INTEGER DEFAULT 45,
        time_limit_min INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        key_access_code TEXT,
        results_published INTEGER DEFAULT 0,
        created_at BIGINT NOT NULL
    )""")

    pg_cur.execute("""
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
        submitted_at BIGINT NOT NULL
    )""")

    pg_cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        tg_id BIGINT PRIMARY KEY,
        fullname TEXT,
        username TEXT,
        added_by BIGINT,
        created_at BIGINT NOT NULL
    )""")

    pg.commit()
    print("  ✅ Jadvallar tayyor!\n")

    # ── 1. ADMINS ──────────────────────────────────────────
    print("👑 Adminlar ko'chirilmoqda...")
    sq_cur.execute("SELECT * FROM admins")
    admins = [dict(r) for r in sq_cur.fetchall()]
    admin_ok = 0
    for a in admins:
        try:
            pg_cur.execute("""
                INSERT INTO admins (tg_id, fullname, username, added_by, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (tg_id) DO UPDATE SET
                    fullname = EXCLUDED.fullname,
                    username = EXCLUDED.username
            """, (a["tg_id"], a.get("fullname"), a.get("username"),
                  a.get("added_by", 0), a["created_at"]))
            admin_ok += 1
            print(f"  ✅ Admin: {a.get('fullname', a['tg_id'])}")
        except Exception as e:
            pg.rollback()
            print(f"  ⚠️ Admin {a['tg_id']} xatolik: {e}")
    pg.commit()
    print(f"  → Jami: {admin_ok}/{len(admins)} admin\n")

    # ── 2. USERS ───────────────────────────────────────────
    print("👥 Foydalanuvchilar ko'chirilmoqda...")
    sq_cur.execute("SELECT * FROM users")
    users = [dict(r) for r in sq_cur.fetchall()]
    user_ok = 0
    for u in users:
        try:
            pg_cur.execute("""
                INSERT INTO users (tg_id, fullname, phone, username, status, pin_code, registered_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tg_id) DO UPDATE SET
                    fullname = EXCLUDED.fullname,
                    phone = EXCLUDED.phone,
                    username = EXCLUDED.username,
                    status = EXCLUDED.status,
                    pin_code = EXCLUDED.pin_code
            """, (
                u["tg_id"], u["fullname"], u["phone"],
                u.get("username"), u.get("status", "approved"),
                u.get("pin_code"), u["registered_at"]
            ))
            user_ok += 1
            print(f"  ✅ {u['fullname']} ({u.get('status', '?')})")
        except Exception as e:
            pg.rollback()
            print(f"  ⚠️ {u.get('fullname', u['tg_id'])}: {e}")
    pg.commit()
    print(f"  → Jami: {user_ok}/{len(users)} foydalanuvchi\n")

    # ── 3. TESTS ───────────────────────────────────────────
    print("📋 Testlar ko'chirilmoqda...")
    sq_cur.execute("SELECT * FROM tests")
    tests = [dict(r) for r in sq_cur.fetchall()]
    test_id_map = {}
    test_ok = 0
    for t in tests:
        try:
            pg_cur.execute("""
                INSERT INTO tests (test_code, title, subject, pdf_file_id, pdf_file_name,
                                   answers_json, total_questions, time_limit_min, is_active,
                                   key_access_code, results_published, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (test_code) DO UPDATE SET
                    title = EXCLUDED.title,
                    answers_json = EXCLUDED.answers_json,
                    results_published = EXCLUDED.results_published
                RETURNING id
            """, (
                t["test_code"], t["title"], t.get("subject", "Matematika"),
                t.get("pdf_file_id"), t.get("pdf_file_name"),
                t["answers_json"], t.get("total_questions", 45),
                t.get("time_limit_min", 0), t.get("is_active", 1),
                t.get("key_access_code", ""), t.get("results_published", 0),
                t["created_at"]
            ))
            row = pg_cur.fetchone()
            if row:
                test_id_map[t["id"]] = row["id"]
            test_ok += 1
            print(f"  ✅ Test: {t['test_code']} — {t['title']}")
        except Exception as e:
            pg.rollback()
            print(f"  ⚠️ Test {t['test_code']}: {e}")
    pg.commit()
    print(f"  → Jami: {test_ok}/{len(tests)} test\n")

    # ── 4. SUBMISSIONS ─────────────────────────────────────
    print("📊 Javoblar ko'chirilmoqda...")
    sq_cur.execute("SELECT * FROM submissions")
    submissions = [dict(r) for r in sq_cur.fetchall()]
    sub_ok = 0
    sub_skip = 0
    for s in submissions:
        old_test_id = s["test_id"]
        new_test_id = test_id_map.get(old_test_id)

        # test_id yo'q bo'lsa, test_code orqali qidir
        if not new_test_id:
            try:
                pg_cur.execute("SELECT id FROM tests WHERE test_code=%s", (s["test_code"],))
                row = pg_cur.fetchone()
                if row:
                    new_test_id = row["id"]
            except Exception:
                pass

        if not new_test_id:
            sub_skip += 1
            print(f"  ⚠️ Submission skip: {s.get('fullname')} — test topilmadi")
            continue

        try:
            pg_cur.execute(
                "SELECT id FROM submissions WHERE test_id=%s AND user_tg_id=%s",
                (new_test_id, s["user_tg_id"])
            )
            if pg_cur.fetchone():
                sub_skip += 1
                continue

            pg_cur.execute("""
                INSERT INTO submissions (test_id, test_code, user_tg_id, fullname, phone,
                                        answers_json, score, max_score, correct_count,
                                        total_count, details_json, submitted_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                new_test_id, s["test_code"], s["user_tg_id"],
                s["fullname"], s["phone"],
                s["answers_json"], s["score"],
                s.get("max_score", 100.0), s["correct_count"],
                s.get("total_count", 55), s["details_json"],
                s["submitted_at"]
            ))
            sub_ok += 1
            print(f"  ✅ Javob: {s['fullname']} — {s['score']} ball")
        except Exception as e:
            pg.rollback()
            print(f"  ⚠️ Submission {s.get('fullname')}: {e}")

    pg.commit()
    print(f"  → Jami: {sub_ok}/{len(submissions)} javob ({sub_skip} o'tkazib yuborildi)\n")

    print("=" * 55)
    print("🎉 MIGRATION MUVAFFAQIYATLI YAKUNLANDI!")
    print(f"   👑 Adminlar:         {admin_ok}")
    print(f"   👥 Foydalanuvchilar: {user_ok}")
    print(f"   📋 Testlar:          {test_ok}")
    print(f"   📊 Javoblar:         {sub_ok}")
    print("=" * 55)

    sq.close()
    pg.close()

if __name__ == "__main__":
    migrate()
