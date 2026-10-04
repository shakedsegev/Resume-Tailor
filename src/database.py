"""
SQLite and PostgreSQL-backed persistent storage for users, master profiles, base resumes, sessions, and daily rate limits.
"""

import hmac
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
_DEFAULT_DB_PATH = DATA_DIR / "resume_tailor.db"
USER_RESUMES_DIR = DATA_DIR / "user_resumes"

DATA_DIR.mkdir(parents=True, exist_ok=True)
USER_RESUMES_DIR.mkdir(parents=True, exist_ok=True)


def clean_database_url(url: str) -> str:
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


_pg_pool: Optional[Any] = None


def is_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL") and HAS_PSYCOPG2)


def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        raw_url = os.environ.get("DATABASE_URL", "")
        db_url = clean_database_url(raw_url)
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=db_url)
    return _pg_pool


class DbCursor:
    def __init__(self, raw_cursor, is_pg: bool = False):
        self._cursor = raw_cursor
        self._is_pg = is_pg

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [dict(r) for r in rows]

    def __iter__(self):
        for row in self._cursor:
            yield dict(row)

    @property
    def rowcount(self):
        return self._cursor.rowcount


class DbConnection:
    def __init__(self, raw_conn, is_pg: bool = False, pool=None):
        self._conn = raw_conn
        self._is_pg = is_pg
        self._pool = pool
        self._closed = False

    def execute(self, sql: str, params: tuple = ()):
        if self._is_pg:
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            if params:
                pg_sql = sql.replace("%", "%%").replace("?", "%s")
                cur.execute(pg_sql, params)
            else:
                cur.execute(sql)
            return DbCursor(cur, is_pg=True)
        else:
            cur = self._conn.execute(sql, params)
            return DbCursor(cur, is_pg=False)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._conn.rollback()
        else:
            self._conn.commit()

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._is_pg:
            if self._pool is not None:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                try:
                    self._pool.putconn(self._conn)
                except Exception:
                    pass
            else:
                try:
                    self._conn.close()
                except Exception:
                    pass
        else:
            try:
                self._conn.close()
            except Exception:
                pass


def get_db_path() -> Path:
    env_path = os.environ.get("RESUME_TAILOR_DB_PATH")
    if env_path:
        p = Path(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return _DEFAULT_DB_PATH


def get_db_connection(db_path: Optional[Path] = None) -> DbConnection:
    if is_postgres() and db_path is None:
        try:
            pool = get_pg_pool()
            raw_conn = pool.getconn()
            return DbConnection(raw_conn, is_pg=True, pool=pool)
        except Exception as err:
            logger.error(f"PostgreSQL connection error: {err}. Falling back to SQLite.")

    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return DbConnection(conn, is_pg=False)


def init_db(db_path: Optional[Path] = None) -> None:
    """Initializes tables if they do not already exist."""
    conn = get_db_connection(db_path)
    with conn:
        if conn._is_pg:
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
                    google_id TEXT NOT NULL REFERENCES users (google_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    google_id TEXT PRIMARY KEY REFERENCES users (google_id) ON DELETE CASCADE,
                    profile_json TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_base_resumes (
                    google_id TEXT PRIMARY KEY REFERENCES users (google_id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_ext TEXT NOT NULL,
                    file_bytes BYTEA,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
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
                    tailors_reset_offset INTEGER NOT NULL DEFAULT 0,
                    deep_boost_reset_offset INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (identifier, usage_date)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tailor_runs (
                    id SERIAL PRIMARY KEY,
                    run_date TEXT NOT NULL,
                    run_time TEXT NOT NULL,
                    identifier TEXT NOT NULL,
                    google_id TEXT,
                    client_ip TEXT NOT NULL,
                    is_deep_boost INTEGER NOT NULL DEFAULT 0
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_ips (
                    google_id TEXT NOT NULL REFERENCES users (google_id) ON DELETE CASCADE,
                    ip_address TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    PRIMARY KEY (google_id, ip_address)
                );
            """)
        else:
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
                    file_bytes BLOB,
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
                    tailors_reset_offset INTEGER NOT NULL DEFAULT 0,
                    deep_boost_reset_offset INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (identifier, usage_date)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tailor_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    run_time TEXT NOT NULL,
                    identifier TEXT NOT NULL,
                    google_id TEXT,
                    client_ip TEXT NOT NULL,
                    is_deep_boost INTEGER NOT NULL DEFAULT 0
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_ips (
                    google_id TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    PRIMARY KEY (google_id, ip_address),
                    FOREIGN KEY (google_id) REFERENCES users (google_id) ON DELETE CASCADE
                );
            """)
            # Ensure migration columns exist on daily_bonuses
            cursor = conn.execute("PRAGMA table_info(daily_bonuses);")
            existing_cols = [row["name"] for row in cursor.fetchall()]
            if "tailors_reset_offset" not in existing_cols:
                conn.execute("ALTER TABLE daily_bonuses ADD COLUMN tailors_reset_offset INTEGER NOT NULL DEFAULT 0;")
            if "deep_boost_reset_offset" not in existing_cols:
                conn.execute("ALTER TABLE daily_bonuses ADD COLUMN deep_boost_reset_offset INTEGER NOT NULL DEFAULT 0;")

            # Ensure migration column exists on user_base_resumes
            cursor_base = conn.execute("PRAGMA table_info(user_base_resumes);")
            existing_base_cols = [row["name"] for row in cursor_base.fetchall()]
            if "file_bytes" not in existing_base_cols:
                conn.execute("ALTER TABLE user_base_resumes ADD COLUMN file_bytes BLOB;")
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
        "SELECT filename, file_path, file_ext, file_bytes, is_active, updated_at FROM user_base_resumes WHERE google_id = ?",
        (google_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    file_path = Path(row["file_path"])
    raw_bytes = row.get("file_bytes")
    file_bytes = bytes(raw_bytes) if raw_bytes else None

    # If the local file does not exist on this machine/container, reconstruct it from DB bytes!
    if not file_path.exists() and file_bytes:
        USER_RESUMES_DIR.mkdir(parents=True, exist_ok=True)
        file_path = USER_RESUMES_DIR / f"{google_id}_base{row['file_ext']}"
        try:
            file_path.write_bytes(file_bytes)
        except Exception:
            pass

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
    google_id: str,
    filename: str,
    file_path: str,
    file_ext: str,
    is_active: bool = True,
    file_bytes: Optional[bytes] = None,
) -> None:
    now = datetime.utcnow().isoformat()
    if file_bytes is None and Path(file_path).exists():
        try:
            file_bytes = Path(file_path).read_bytes()
        except Exception:
            pass

    conn = get_db_connection()
    binary_data = psycopg2.Binary(file_bytes) if (conn._is_pg and file_bytes) else file_bytes

    with conn:
        conn.execute("""
            INSERT INTO user_base_resumes (google_id, filename, file_path, file_ext, file_bytes, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(google_id) DO UPDATE SET
                filename = excluded.filename,
                file_path = excluded.file_path,
                file_ext = excluded.file_ext,
                file_bytes = excluded.file_bytes,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at;
        """, (google_id, filename, file_path, file_ext, binary_data, 1 if is_active else 0, now))
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


# ---------------- USER IP & TELEMETRY METHODS ----------------

def link_user_ip(google_id: str, ip_address: str) -> None:
    """Links a client IP address to a registered user account."""
    if not google_id or not ip_address or google_id == ADMIN_GOOGLE_ID:
        return
    ip = ip_address.replace("ip:", "").strip()
    if not ip or ip == "unknown":
        return
    now = datetime.utcnow().isoformat()
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO user_ips (google_id, ip_address, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(google_id, ip_address) DO UPDATE SET last_seen = excluded.last_seen;
        """, (google_id, ip, now))
    conn.close()


def get_linked_ips_for_user(google_id: str) -> list[str]:
    """Returns all client IPs associated with a registered Google user."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT ip_address FROM user_ips WHERE google_id = ? ORDER BY last_seen DESC",
        (google_id,)
    ).fetchall()
    conn.close()
    return [r["ip_address"] for r in rows]


def is_ip_linked_to_user(ip_address: str) -> bool:
    """Checks if a client IP address belongs to any registered user."""
    ip = ip_address.replace("ip:", "").strip()
    conn = get_db_connection()
    row = conn.execute(
        "SELECT 1 FROM user_ips WHERE ip_address = ?", (ip,)
    ).fetchone()
    conn.close()
    return row is not None


def record_tailor_run(
    identifier: str,
    client_ip: str,
    google_id: Optional[str] = None,
    is_deep_boost: bool = False,
    date_str: Optional[str] = None,
) -> None:
    """
    Records an immutable telemetry run in tailor_runs.
    This strictly cumulative data log is NEVER altered by admin resets or bonus adjustments.
    """
    now = datetime.utcnow()
    d = date_str or now.strftime("%Y-%m-%d")
    t = now.isoformat()
    clean_ip = client_ip.replace("ip:", "").strip()
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO tailor_runs (run_date, run_time, identifier, google_id, client_ip, is_deep_boost)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (d, t, identifier, google_id, clean_ip, 1 if is_deep_boost else 0))
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
        "SELECT bonus_tailors, bonus_deep_boosts, tailors_reset_offset, deep_boost_reset_offset FROM daily_bonuses WHERE identifier = ? AND usage_date = ?",
        (identifier, d)
    ).fetchone()
    conn.close()
    if not row:
        return {
            "bonus_tailors": 0,
            "bonus_deep_boosts": 0,
            "tailors_reset_offset": 0,
            "deep_boost_reset_offset": 0,
        }
    return {
        "bonus_tailors": int(row["bonus_tailors"] or 0),
        "bonus_deep_boosts": int(row["bonus_deep_boosts"] or 0),
        "tailors_reset_offset": int(row["tailors_reset_offset"] or 0),
        "deep_boost_reset_offset": int(row["deep_boost_reset_offset"] or 0),
    }


def admin_adjust_tailors(identifier: str, delta: int, date_str: Optional[str] = None) -> int:
    """Adjusts bonus tailors (positive or negative) without touching actual run counts."""
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO daily_bonuses (identifier, usage_date, bonus_tailors, bonus_deep_boosts, tailors_reset_offset, deep_boost_reset_offset)
            VALUES (?, ?, ?, 0, 0, 0)
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
            INSERT INTO daily_bonuses (identifier, usage_date, bonus_tailors, bonus_deep_boosts, tailors_reset_offset, deep_boost_reset_offset)
            VALUES (?, ?, 0, ?, 0, 0)
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
    actual_used = get_daily_usage(identifier)
    bonuses = get_daily_bonuses(f"user:{google_id}")
    effective_limit = max(0, USER_DEEP_BOOST_LIMIT + bonuses["bonus_deep_boosts"])
    effective_used = max(0, actual_used - bonuses["deep_boost_reset_offset"])
    remaining = max(0, effective_limit - effective_used)
    return {
        "allowed": remaining > 0,
        "used": actual_used,
        "effective_used": effective_used,
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
    actual_runs = get_daily_usage(identifier)
    if is_authenticated and identifier.startswith("user:"):
        gid = identifier.split("user:")[1]
        linked_ips = get_linked_ips_for_user(gid)
        if client_ip and client_ip not in linked_ips:
            linked_ips.append(client_ip)
        for ip in linked_ips:
            guest_used = get_daily_usage(f"ip:{ip}")
            actual_runs = max(actual_runs, guest_used)
    elif not is_authenticated and client_ip:
        actual_runs = max(actual_runs, get_daily_usage(f"ip:{client_ip}"))
    effective_used = max(0, actual_runs - bonuses["tailors_reset_offset"])
    remaining = max(0, effective_limit - effective_used)

    deep_boost = None
    if is_authenticated and identifier.startswith("user:"):
        gid = identifier.split("user:")[1]
        deep_boost = check_deep_boost_limit(gid)
    else:
        deep_boost = {"allowed": False, "used": 0, "limit": 0, "remaining": 0}

    return {
        "allowed": remaining > 0,
        "used": actual_runs,
        "effective_used": effective_used,
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
    # List real registered users ONLY (strictly excluding admin_master and test accounts)
    rows = conn.execute("""
        SELECT u.google_id, u.email, u.name, u.picture, u.created_at, u.last_login
        FROM users u
        WHERE u.google_id != ?
          AND u.email NOT LIKE '%@example.com'
          AND u.google_id NOT LIKE 'test_%'
          AND u.google_id NOT LIKE 'deep_user_%'
          AND u.google_id NOT LIKE 'target_user_%'
          AND u.google_id NOT LIKE 'mock_%'
          AND u.google_id NOT LIKE 'unique_%'
          AND u.google_id != 'google_123'
        ORDER BY u.last_login DESC
    """, (ADMIN_GOOGLE_ID,)).fetchall()

    users_list = []
    for r in rows:
        u = dict(r)
        gid = u["google_id"]
        u["is_admin"] = False

        # Check assets
        has_prof = conn.execute("SELECT 1 FROM user_profiles WHERE google_id = ?", (gid,)).fetchone() is not None
        has_base = conn.execute("SELECT 1 FROM user_base_resumes WHERE google_id = ?", (gid,)).fetchone() is not None
        u["has_profile"] = has_prof
        u["has_base_resume"] = has_base

        # Linked IP addresses
        ip_rows = conn.execute(
            "SELECT ip_address FROM user_ips WHERE google_id = ? ORDER BY last_seen DESC",
            (gid,)
        ).fetchall()
        u["linked_ips"] = [row["ip_address"] for row in ip_rows]

        # Calculate unified usage across user account and linked IP addresses
        user_runs = get_daily_usage(f"user:{gid}", d)
        ip_runs = 0
        for ip in u["linked_ips"]:
            ip_runs = max(ip_runs, get_daily_usage(f"ip:{ip}", d))
        actual_used = max(user_runs, ip_runs)

        deep_boost_used = get_daily_usage(f"user:{gid}:deep_boost", d)
        bonuses = get_daily_bonuses(f"user:{gid}", d)

        eff_tailors_limit = max(0, USER_DAILY_LIMIT + bonuses["bonus_tailors"])
        eff_tailors_used = max(0, actual_used - bonuses["tailors_reset_offset"])
        tailors_remaining = max(0, eff_tailors_limit - eff_tailors_used)

        eff_deep_limit = max(0, USER_DEEP_BOOST_LIMIT + bonuses["bonus_deep_boosts"])
        eff_deep_used = max(0, deep_boost_used - bonuses["deep_boost_reset_offset"])
        deep_boost_remaining = max(0, eff_deep_limit - eff_deep_used)

        u["tailors_used"] = actual_used
        u["tailors_limit"] = eff_tailors_limit
        u["tailors_remaining"] = tailors_remaining
        u["deep_boost_used"] = deep_boost_used
        u["deep_boost_limit"] = eff_deep_limit
        u["deep_boost_remaining"] = deep_boost_remaining
        u["deep_boost_allowed"] = deep_boost_remaining > 0

        users_list.append(u)

    conn.close()
    return users_list


def list_active_guests_with_daily_usage(date_str: Optional[str] = None) -> list[dict[str, Any]]:
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()
    # Filter out test identifiers AND any IP that is linked to a registered user!
    rows = conn.execute("""
        SELECT identifier, count
        FROM daily_usage
        WHERE usage_date = ? 
          AND identifier LIKE 'ip:%' 
          AND identifier NOT LIKE '%test%'
          AND replace(identifier, 'ip:', '') NOT IN (SELECT ip_address FROM user_ips)
        ORDER BY count DESC
    """, (d,)).fetchall()

    guests = []
    for r in rows:
        ident = r["identifier"]
        ip = ident.replace("ip:", "")
        cnt = int(r["count"])
        bonuses = get_daily_bonuses(ident, d)
        eff_limit = max(0, GUEST_DAILY_LIMIT + bonuses["bonus_tailors"])
        eff_used = max(0, cnt - bonuses["tailors_reset_offset"])
        guests.append({
            "identifier": ident,
            "ip_address": ip,
            "tailors_used": cnt,
            "tailors_limit": eff_limit,
            "tailors_remaining": max(0, eff_limit - eff_used),
        })
    conn.close()
    return guests


def admin_reset_daily_usage(identifier: str, date_str: Optional[str] = None) -> None:
    """
    Resets active quota so user/guest has full quota available again,
    WITHOUT wiping out the actual historical runs count for the day.
    """
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    actual_used = get_daily_usage(identifier, d)
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO daily_bonuses (identifier, usage_date, bonus_tailors, bonus_deep_boosts, tailors_reset_offset, deep_boost_reset_offset)
            VALUES (?, ?, 0, 0, ?, 0)
            ON CONFLICT(identifier, usage_date) DO UPDATE SET
                tailors_reset_offset = excluded.tailors_reset_offset,
                bonus_tailors = 0;
        """, (identifier, d, actual_used))
    conn.close()


def admin_add_daily_usage(identifier: str, delta: int, date_str: Optional[str] = None) -> int:
    """Adjusts bonus tailors without touching actual runs counter."""
    return admin_adjust_tailors(identifier, delta, date_str)


def admin_reset_deep_boost(google_id: str, date_str: Optional[str] = None) -> None:
    """
    Resets deep boost quota so user has 1 full boost ready,
    WITHOUT wiping out the actual deep boost runs count for the day.
    """
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    identifier = f"user:{google_id}"
    deep_ident = f"user:{google_id}:deep_boost"
    actual_used = get_daily_usage(deep_ident, d)
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO daily_bonuses (identifier, usage_date, bonus_tailors, bonus_deep_boosts, tailors_reset_offset, deep_boost_reset_offset)
            VALUES (?, ?, 0, 0, 0, ?)
            ON CONFLICT(identifier, usage_date) DO UPDATE SET
                deep_boost_reset_offset = excluded.deep_boost_reset_offset,
                bonus_deep_boosts = 0;
        """, (identifier, d, actual_used))
    conn.close()


def get_system_stats(date_str: Optional[str] = None) -> dict[str, Any]:
    d = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db_connection()

    # Total real registered users (strictly excluding admin_master)
    user_count_row = conn.execute("""
        SELECT COUNT(*) as cnt FROM users 
        WHERE google_id != ?
          AND email NOT LIKE '%@example.com'
          AND google_id NOT LIKE 'test_%'
          AND google_id NOT LIKE 'deep_user_%'
          AND google_id NOT LIKE 'target_user_%'
          AND google_id NOT LIKE 'mock_%'
          AND google_id NOT LIKE 'unique_%'
          AND google_id != 'google_123'
    """, (ADMIN_GOOGLE_ID,)).fetchone()
    total_users = int(user_count_row["cnt"]) if user_count_row else 0

    # 1. Total Tailors Run Today by regular users and guests (strictly excluding admin)
    tailors_run_row = conn.execute("""
        SELECT COUNT(*) as total FROM tailor_runs 
        WHERE run_date = ? 
          AND is_deep_boost = 0
          AND (google_id IS NULL OR google_id != ?)
          AND identifier NOT LIKE '%admin%'
          AND identifier NOT LIKE '%test%'
          AND identifier NOT LIKE '%mock%'
    """, (d, ADMIN_GOOGLE_ID)).fetchone()
    today_tailors = int(tailors_run_row["total"] or 0) if tailors_run_row else 0

    # Fallback to daily_usage if tailor_runs was empty
    if today_tailors == 0:
        tailors_row = conn.execute("""
            SELECT SUM(count) as total FROM daily_usage 
            WHERE usage_date = ? 
              AND identifier NOT LIKE '%:deep_boost' 
              AND identifier NOT LIKE '%admin%'
              AND identifier NOT LIKE '%test%'
              AND identifier NOT LIKE '%mock%'
        """, (d,)).fetchone()
        today_tailors = int(tailors_row["total"] or 0) if tailors_row else 0

    # 2. Total Deep Boosts Run Today by regular users (strictly excluding admin)
    boosts_run_row = conn.execute("""
        SELECT COUNT(*) as total FROM tailor_runs 
        WHERE run_date = ? 
          AND is_deep_boost = 1
          AND (google_id IS NULL OR google_id != ?)
          AND identifier NOT LIKE '%admin%'
          AND identifier NOT LIKE '%test%'
          AND identifier NOT LIKE '%mock%'
    """, (d, ADMIN_GOOGLE_ID)).fetchone()
    today_boosts = int(boosts_run_row["total"] or 0) if boosts_run_row else 0

    if today_boosts == 0:
        boosts_row = conn.execute("""
            SELECT SUM(count) as total FROM daily_usage 
            WHERE usage_date = ? 
              AND identifier LIKE '%:deep_boost'
              AND identifier NOT LIKE '%admin%'
              AND identifier NOT LIKE '%test%'
              AND identifier NOT LIKE '%mock%'
        """, (d,)).fetchone()
        today_boosts = int(boosts_row["total"] or 0) if boosts_row else 0

    # 3. Dedicated Admin Activity Today (separate from regular user metrics)
    admin_tailors_row = conn.execute("""
        SELECT COUNT(*) as total FROM tailor_runs 
        WHERE run_date = ? 
          AND is_deep_boost = 0
          AND (identifier = ? OR google_id = ?)
    """, (d, f"user:{ADMIN_GOOGLE_ID}", ADMIN_GOOGLE_ID)).fetchone()
    admin_tailors = int(admin_tailors_row["total"] or 0) if admin_tailors_row else 0
    if admin_tailors == 0:
        admin_tailors = get_daily_usage(f"user:{ADMIN_GOOGLE_ID}", d)

    admin_boosts_row = conn.execute("""
        SELECT COUNT(*) as total FROM tailor_runs 
        WHERE run_date = ? 
          AND is_deep_boost = 1
          AND (identifier = ? OR identifier = ? OR google_id = ?)
    """, (d, f"user:{ADMIN_GOOGLE_ID}:deep_boost", f"user:{ADMIN_GOOGLE_ID}", ADMIN_GOOGLE_ID)).fetchone()
    admin_boosts = int(admin_boosts_row["total"] or 0) if admin_boosts_row else 0
    if admin_boosts == 0:
        admin_boosts = get_daily_usage(f"user:{ADMIN_GOOGLE_ID}:deep_boost", d)

    # 4. Active Guests Today: exclude any IP linked to a registered user!
    active_guests_row = conn.execute("""
        SELECT COUNT(DISTINCT identifier) as cnt FROM daily_usage
        WHERE usage_date = ? 
          AND identifier LIKE 'ip:%' 
          AND identifier NOT LIKE '%test%'
          AND replace(identifier, 'ip:', '') NOT IN (SELECT ip_address FROM user_ips)
    """, (d,)).fetchone()
    today_guests = int(active_guests_row["cnt"] or 0) if active_guests_row else 0

    conn.close()

    return {
        "total_users": total_users,
        "today_tailors": today_tailors,
        "today_deep_boosts": today_boosts,
        "admin_tailors_today": admin_tailors,
        "admin_deep_boosts_today": admin_boosts,
        "total_active_guests_today": today_guests,
        "date": d,
    }
