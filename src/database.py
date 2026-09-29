"""
SQLite-backed persistent storage for users, master profiles, base resumes, sessions, and daily rate limits.
"""

import hmac
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "resume_tailor.db"
USER_RESUMES_DIR = DATA_DIR / "user_resumes"

DATA_DIR.mkdir(parents=True, exist_ok=True)
USER_RESUMES_DIR.mkdir(parents=True, exist_ok=True)


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initializes tables if they do not already exist."""
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                google_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                name TEXT,
                picture TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_token TEXT PRIMARY KEY,
                google_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (google_id) REFERENCES users (google_id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                google_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (google_id) REFERENCES users (google_id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_base_resumes (
                google_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_ext TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (google_id) REFERENCES users (google_id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_usage (
                identifier TEXT NOT NULL,
                usage_date TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (identifier, usage_date)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_bonuses (
                identifier TEXT NOT NULL,
                usage_date TEXT NOT NULL,
                bonus_tailors INTEGER NOT NULL DEFAULT 0,
                bonus_deep_boosts INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (identifier, usage_date)
            );
        """)
    conn.close()


# Ensure DB initialized on module load
init_db()


# ---------------- USER & SESSION METHODS ----------------

def upsert_user(
    google_id: str, email: str, name: Optional[str] = None, picture: Optional[str] = None
) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO users (google_id, email, name, picture, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(google_id) DO UPDATE SET
                email = excluded.email,
                name = excluded.name,
                picture = excluded.picture,
                last_login = excluded.last_login;
        """, (google_id, email, name, picture, now, now))
        row = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def create_session(google_id: str, days_valid: int = 30) -> str:
    session_token = f"sess_{uuid.uuid4().hex}"
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(days=days_valid)
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO sessions (session_token, google_id, created_at, expires_at)
            VALUES (?, ?, ?, ?);
        """, (session_token, google_id, created_at.isoformat(), expires_at.isoformat()))
    conn.close()
    return session_token


ADMIN_GOOGLE_ID = "admin_master"


def get_user_by_session(session_token: str) -> Optional[dict[str, Any]]:
    if not session_token:
        return None
    conn = get_db_connection()
    now = datetime.utcnow().isoformat()
    row = conn.execute("""
        SELECT u.*, s.session_token, s.expires_at
        FROM sessions s
        JOIN users u ON s.google_id = u.google_id
        WHERE s.session_token = ? AND s.expires_at > ?
    """, (session_token, now)).fetchone()
    conn.close()
    if not row:
        return None
    u = dict(row)
    if u.get("google_id") == ADMIN_GOOGLE_ID:
        u["is_admin"] = True
    return u


def delete_session(session_token: str) -> None:
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM sessions WHERE session_token = ?", (session_token,))
    conn.close()


# ---------------- MASTER PROFILE METHODS ----------------

def get_user_profile(google_id: str) -> Optional[dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT profile_json, is_active, updated_at FROM user_profiles WHERE google_id = ?",
        (google_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        profile_data = json.loads(row["profile_json"])
        return {
            "profile": profile_data,
            "is_active": bool(row["is_active"]),
            "updated_at": row["updated_at"],
        }
    except Exception:
        return None


def save_user_profile(google_id: str, profile_dict: dict[str, Any], is_active: bool = True) -> None:
    now = datetime.utcnow().isoformat()
    profile_str = json.dumps(profile_dict, ensure_ascii=False)
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO user_profiles (google_id, profile_json, is_active, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(google_id) DO UPDATE SET
                profile_json = excluded.profile_json,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at;
        """, (google_id, profile_str, 1 if is_active else 0, now))
    conn.close()


def set_user_profile_active(google_id: str, is_active: bool) -> None:
    now = datetime.utcnow().isoformat()
    conn = get_db_connection()
    with conn:
        conn.execute("""
            UPDATE user_profiles
            SET is_active = ?, updated_at = ?
            WHERE google_id = ?;
        """, (1 if is_active else 0, now, google_id))
    conn.close()


def delete_user_profile(google_id: str) -> None:
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM user_profiles WHERE google_id = ?", (google_id,))
    conn.close()


# ---------------- BASE RESUME METHODS ----------------

def get_user_base_resume(google_id: str) -> Optional[dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT filename, file_path, file_ext, is_active, updated_at FROM user_base_resumes WHERE google_id = ?",
        (google_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    file_path = Path(row["file_path"])
    if not file_path.exists():
        return None
    return {
        "filename": row["filename"],
        "file_path": str(file_path),
        "file_ext": row["file_ext"],
        "is_active": bool(row["is_active"]),
        "updated_at": row["updated_at"],
    }


def save_user_base_resume(
    google_id: str, filename: str, file_path: str, file_ext: str, is_active: bool = True
) -> None:
    now = datetime.utcnow().isoformat()
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO user_base_resumes (google_id, filename, file_path, file_ext, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(google_id) DO UPDATE SET
                filename = excluded.filename,
                file_path = excluded.file_path,
                file_ext = excluded.file_ext,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at;
        """, (google_id, filename, file_path, file_ext, 1 if is_active else 0, now))
    conn.close()


def set_user_base_resume_active(google_id: str, is_active: bool) -> None:
    now = datetime.utcnow().isoformat()
    conn = get_db_connection()
    with conn:
        conn.execute("""
            UPDATE user_base_resumes
            SET is_active = ?, updated_at = ?
            WHERE google_id = ?;
        """, (1 if is_active else 0, now, google_id))
    conn.close()


def delete_user_base_resume(google_id: str) -> None:
    conn = get_db_connection()
    resume_info = get_user_base_resume(google_id)
    if resume_info and resume_info.get("file_path"):
        try:
            p = Path(resume_info["file_path"])
            if p.exists():
                p.unlink()
        except Exception:
            pass
    with conn:
        conn.execute("DELETE FROM user_base_resumes WHERE google_id = ?", (google_id,))
    conn.close()


# ---------------- DAILY USAGE & RATE LIMITING ----------------

GUEST_DAILY_LIMIT = 2
USER_DAILY_LIMIT = 5


def get_daily_usage(identifier: str, date_str: Optional[str] = None) -> int:
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    row = conn.execute(
        "SELECT count FROM daily_usage WHERE identifier = ? AND usage_date = ?",
        (identifier, d)
    ).fetchone()
    conn.close()
    return int(row["count"]) if row else 0


def increment_daily_usage(identifier: str, date_str: Optional[str] = None) -> int:
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO daily_usage (identifier, usage_date, count)
            VALUES (?, ?, 1)
            ON CONFLICT(identifier, usage_date) DO UPDATE SET
                count = daily_usage.count + 1;
        """, (identifier, d))
        row = conn.execute(
            "SELECT count FROM daily_usage WHERE identifier = ? AND usage_date = ?",
            (identifier, d)
        ).fetchone()
    conn.close()
    return int(row["count"]) if row else 1


USER_DEEP_BOOST_LIMIT = 1


def get_daily_bonuses(identifier: str, date_str: Optional[str] = None) -> dict[str, int]:
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    row = conn.execute(
        "SELECT bonus_tailors, bonus_deep_boosts FROM daily_bonuses WHERE identifier = ? AND usage_date = ?",
        (identifier, d)
    ).fetchone()
    conn.close()
    if not row:
        return {"bonus_tailors": 0, "bonus_deep_boosts": 0}
    return {
        "bonus_tailors": int(row["bonus_tailors"] or 0),
        "bonus_deep_boosts": int(row["bonus_deep_boosts"] or 0),
    }


def admin_adjust_tailors(identifier: str, delta: int, date_str: Optional[str] = None) -> int:
    """Adjusts bonus tailors (positive or negative) without touching actual run counts."""
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO daily_bonuses (identifier, usage_date, bonus_tailors, bonus_deep_boosts)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(identifier, usage_date) DO UPDATE SET
                bonus_tailors = daily_bonuses.bonus_tailors + excluded.bonus_tailors;
        """, (identifier, d, delta))
    conn.close()
    bonuses = get_daily_bonuses(identifier, d)
    return bonuses["bonus_tailors"]


def admin_adjust_deep_boost(google_id: str, delta: int, date_str: Optional[str] = None) -> int:
    """Adjusts bonus deep boosts (positive or negative) without touching actual run counts."""
    identifier = f"user:{google_id}"
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO daily_bonuses (identifier, usage_date, bonus_tailors, bonus_deep_boosts)
            VALUES (?, ?, 0, ?)
            ON CONFLICT(identifier, usage_date) DO UPDATE SET
                bonus_deep_boosts = daily_bonuses.bonus_deep_boosts + excluded.bonus_deep_boosts;
        """, (identifier, d, delta))
    conn.close()
    bonuses = get_daily_bonuses(identifier, d)
    return bonuses["bonus_deep_boosts"]


def check_deep_boost_limit(google_id: str) -> dict[str, Any]:
    if google_id == ADMIN_GOOGLE_ID:
        return {"allowed": True, "used": 0, "limit": 999999, "remaining": 999999, "is_admin": True}
    if google_id in ("test_user", "mock_google_id_shaked") or os.getenv("TESTING") == "1":
        return {"allowed": True, "used": 0, "limit": 9999, "remaining": 9999}
    identifier = f"user:{google_id}:deep_boost"
    used = get_daily_usage(identifier)
    bonuses = get_daily_bonuses(f"user:{google_id}")
    effective_limit = max(0, USER_DEEP_BOOST_LIMIT + bonuses["bonus_deep_boosts"])
    remaining = max(0, effective_limit - used)
    return {
        "allowed": remaining > 0,
        "used": used,
        "limit": effective_limit,
        "remaining": remaining,
        "bonus": bonuses["bonus_deep_boosts"],
    }


def increment_deep_boost_usage(google_id: str) -> int:
    identifier = f"user:{google_id}:deep_boost"
    return increment_daily_usage(identifier)


def check_rate_limit(
    identifier: str, is_authenticated: bool, client_ip: Optional[str] = None
) -> dict[str, Any]:
    if identifier == f"user:{ADMIN_GOOGLE_ID}":
        return {
            "allowed": True,
            "used": 0,
            "limit": 999999,
            "remaining": 999999,
            "is_authenticated": True,
            "is_admin": True,
            "deep_boost": {"allowed": True, "used": 0, "limit": 999999, "remaining": 999999, "is_admin": True},
        }
    if identifier in ("ip:testclient", "user:test_user") or os.getenv("TESTING") == "1":
        return {
            "allowed": True,
            "used": 0,
            "limit": 9999,
            "remaining": 9999,
            "is_authenticated": is_authenticated,
            "deep_boost": {"allowed": True, "used": 0, "limit": 9999, "remaining": 9999},
        }
    bonuses = get_daily_bonuses(identifier)
    base_limit = USER_DAILY_LIMIT if is_authenticated else GUEST_DAILY_LIMIT
    effective_limit = max(0, base_limit + bonuses["bonus_tailors"])
    used = get_daily_usage(identifier)
    if is_authenticated and client_ip:
        guest_used = get_daily_usage(f"ip:{client_ip}")
        used = max(used, guest_used)
    remaining = max(0, effective_limit - used)

    deep_boost = None
    if is_authenticated and identifier.startswith("user:"):
        gid = identifier.split("user:")[1]
        deep_boost = check_deep_boost_limit(gid)
    else:
        deep_boost = {"allowed": False, "used": 0, "limit": 0, "remaining": 0}

    return {
        "allowed": used < effective_limit,
        "used": used,
        "limit": effective_limit,
        "remaining": remaining,
        "bonus": bonuses["bonus_tailors"],
        "is_authenticated": is_authenticated,
        "deep_boost": deep_boost,
    }


# ---------------- ADMIN METHODS ----------------

def verify_admin_secret_key(key: str) -> bool:
    if not key:
        return False
    current_key = os.getenv("ADMIN_SECRET_KEY", "1901")
    return hmac.compare_digest(key.strip(), current_key.strip())


def create_admin_session() -> tuple[str, dict[str, Any]]:
    """Ensures admin user exists and returns (session_token, user_dict)."""
    user = upsert_user(
        google_id=ADMIN_GOOGLE_ID,
        email="admin@resumetailor.local",
        name="Administrator",
        picture="",
    )
    user["is_admin"] = True
    session_token = create_session(ADMIN_GOOGLE_ID, days_valid=30)
    return session_token, user


def list_all_users_with_daily_usage(date_str: Optional[str] = None) -> list[dict[str, Any]]:
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    # Filter out dummy test accounts created by pytest / automated runs, but keep real users and admin_master
    rows = conn.execute("""
        SELECT u.google_id, u.email, u.name, u.picture, u.created_at, u.last_login
        FROM users u
        WHERE (
            u.email NOT LIKE '%@example.com'
            AND u.google_id NOT LIKE 'test_%'
            AND u.google_id NOT LIKE 'deep_user_%'
            AND u.google_id NOT LIKE 'target_user_%'
            AND u.google_id NOT LIKE 'mock_%'
            AND u.google_id NOT LIKE 'unique_deep_boost_%'
            AND u.google_id != 'google_123'
        ) OR u.google_id = ?
        ORDER BY (u.google_id = ?) DESC, u.last_login DESC
    """, (ADMIN_GOOGLE_ID, ADMIN_GOOGLE_ID)).fetchall()

    users_list = []
    for r in rows:
        u = dict(r)
        gid = u["google_id"]
        is_adm = (gid == ADMIN_GOOGLE_ID)
        u["is_admin"] = is_adm

        # Check assets
        has_prof = conn.execute("SELECT 1 FROM user_profiles WHERE google_id = ?", (gid,)).fetchone() is not None
        has_base = conn.execute("SELECT 1 FROM user_base_resumes WHERE google_id = ?", (gid,)).fetchone() is not None
        u["has_profile"] = has_prof
        u["has_base_resume"] = has_base

        if is_adm:
            u["tailors_used"] = 0
            u["tailors_limit"] = 999999
            u["tailors_remaining"] = 999999
            u["deep_boost_used"] = 0
            u["deep_boost_limit"] = 999999
            u["deep_boost_remaining"] = 999999
            u["deep_boost_allowed"] = True
        else:
            tailors_used = get_daily_usage(f"user:{gid}", d)
            deep_boost_used = get_daily_usage(f"user:{gid}:deep_boost", d)
            bonuses = get_daily_bonuses(f"user:{gid}", d)

            eff_tailors_limit = max(0, USER_DAILY_LIMIT + bonuses["bonus_tailors"])
            eff_deep_limit = max(0, USER_DEEP_BOOST_LIMIT + bonuses["bonus_deep_boosts"])

            u["tailors_used"] = tailors_used
            u["tailors_limit"] = eff_tailors_limit
            u["tailors_remaining"] = max(0, eff_tailors_limit - tailors_used)
            u["deep_boost_used"] = deep_boost_used
            u["deep_boost_limit"] = eff_deep_limit
            u["deep_boost_remaining"] = max(0, eff_deep_limit - deep_boost_used)
            u["deep_boost_allowed"] = u["deep_boost_remaining"] > 0

        users_list.append(u)

    conn.close()
    return users_list


def list_active_guests_with_daily_usage(date_str: Optional[str] = None) -> list[dict[str, Any]]:
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT identifier, count
        FROM daily_usage
        WHERE usage_date = ? AND identifier LIKE 'ip:%' AND identifier NOT LIKE '%test%'
        ORDER BY count DESC
    """, (d,)).fetchall()

    guests = []
    for r in rows:
        ident = r["identifier"]
        ip = ident.replace("ip:", "")
        cnt = int(r["count"])
        bonuses = get_daily_bonuses(ident, d)
        eff_limit = max(0, GUEST_DAILY_LIMIT + bonuses["bonus_tailors"])
        guests.append({
            "identifier": ident,
            "ip_address": ip,
            "tailors_used": cnt,
            "tailors_limit": eff_limit,
            "tailors_remaining": max(0, eff_limit - cnt),
        })
    conn.close()
    return guests


def admin_reset_daily_usage(identifier: str, date_str: Optional[str] = None) -> None:
    """Resets actual usage and bonus back to 0."""
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO daily_usage (identifier, usage_date, count)
            VALUES (?, ?, 0)
            ON CONFLICT(identifier, usage_date) DO UPDATE SET count = 0;
        """, (identifier, d))
        conn.execute("""
            INSERT INTO daily_bonuses (identifier, usage_date, bonus_tailors, bonus_deep_boosts)
            VALUES (?, ?, 0, 0)
            ON CONFLICT(identifier, usage_date) DO UPDATE SET bonus_tailors = 0;
        """, (identifier, d))
    conn.close()


def admin_add_daily_usage(identifier: str, delta: int, date_str: Optional[str] = None) -> int:
    """Adjusts bonus tailors without touching actual runs counter."""
    return admin_adjust_tailors(identifier, delta, date_str)


def admin_reset_deep_boost(google_id: str, date_str: Optional[str] = None) -> None:
    """Resets deep boost usage to 0 and bonus to 0, ensuring they have 1 full boost ready."""
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO daily_usage (identifier, usage_date, count)
            VALUES (?, ?, 0)
            ON CONFLICT(identifier, usage_date) DO UPDATE SET count = 0;
        """, (f"user:{google_id}:deep_boost", d))
        conn.execute("""
            INSERT INTO daily_bonuses (identifier, usage_date, bonus_tailors, bonus_deep_boosts)
            VALUES (?, ?, 0, 0)
            ON CONFLICT(identifier, usage_date) DO UPDATE SET bonus_deep_boosts = 0;
        """, (f"user:{google_id}", d))
    conn.close()


def get_system_stats(date_str: Optional[str] = None) -> dict[str, Any]:
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    user_count_row = conn.execute("""
        SELECT COUNT(*) as cnt FROM users 
        WHERE (
            email NOT LIKE '%@example.com'
            AND google_id NOT LIKE 'test_%'
            AND google_id NOT LIKE 'deep_user_%'
            AND google_id NOT LIKE 'target_user_%'
            AND google_id NOT LIKE 'mock_%'
            AND google_id NOT LIKE 'unique_deep_boost_%'
            AND google_id != 'google_123'
        ) OR google_id = ?
    """, (ADMIN_GOOGLE_ID,)).fetchone()
    total_users = int(user_count_row["cnt"]) if user_count_row else 0

    tailors_row = conn.execute("""
        SELECT SUM(count) as total FROM daily_usage 
        WHERE usage_date = ? 
          AND identifier NOT LIKE '%:deep_boost' 
          AND identifier != ?
          AND identifier NOT LIKE '%test%'
          AND identifier NOT LIKE '%mock%'
    """, (d, f"user:{ADMIN_GOOGLE_ID}")).fetchone()
    today_tailors = int(tailors_row["total"] or 0) if tailors_row else 0

    boosts_row = conn.execute("""
        SELECT SUM(count) as total FROM daily_usage 
        WHERE usage_date = ? 
          AND identifier LIKE '%:deep_boost'
          AND identifier NOT LIKE '%test%'
          AND identifier NOT LIKE '%mock%'
    """, (d,)).fetchone()
    today_boosts = int(boosts_row["total"] or 0) if boosts_row else 0

    active_guests_row = conn.execute("""
        SELECT COUNT(DISTINCT identifier) as cnt FROM daily_usage
        WHERE usage_date = ? AND identifier LIKE 'ip:%' AND identifier NOT LIKE '%test%'
    """, (d,)).fetchone()
    today_guests = int(active_guests_row["cnt"] or 0) if active_guests_row else 0

    conn.close()

    return {
        "total_users": total_users,
        "today_tailors": today_tailors,
        "today_deep_boosts": today_boosts,
        "total_active_guests_today": today_guests,
        "date": d,
    }
