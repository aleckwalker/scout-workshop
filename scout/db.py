"""SQLite database for Scout state management."""
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "scout.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS voices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    platform TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    handle TEXT,
    topic TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, approved, rejected, skipped
    approved_at TEXT,
    rejected_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    bio TEXT,
    feed_url TEXT,
    feed_failures INTEGER NOT NULL DEFAULT 0,
    UNIQUE(profile_url, topic)
);

CREATE TABLE IF NOT EXISTS voice_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id INTEGER NOT NULL REFERENCES voices(id),
    title TEXT,
    url TEXT NOT NULL,
    snippet TEXT,
    discovered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id INTEGER NOT NULL REFERENCES voices(id),
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    published_at TEXT,
    summary TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS discovery_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    platform TEXT,
    results_count INTEGER NOT NULL DEFAULT 0,
    run_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    content_count INTEGER NOT NULL DEFAULT 0,
    has_ai_themes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_db(db_path=None):
    """Get a database connection, creating schema if needed."""
    path = db_path or DEFAULT_DB
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """Add columns that may not exist in older databases."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(voices)").fetchall()}
    if "bio" not in cols:
        conn.execute("ALTER TABLE voices ADD COLUMN bio TEXT")
        conn.commit()


def get_pending_voices(conn, topic=None):
    """Get voices awaiting approval."""
    if topic:
        return conn.execute(
            "SELECT * FROM voices WHERE status='pending' AND topic=? ORDER BY created_at",
            (topic,),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM voices WHERE status='pending' ORDER BY topic, created_at"
    ).fetchall()


def get_approved_voices(conn, topic=None):
    """Get approved voices for monitoring."""
    if topic:
        return conn.execute(
            "SELECT * FROM voices WHERE status='approved' AND topic=? ORDER BY name",
            (topic,),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM voices WHERE status='approved' ORDER BY topic, name"
    ).fetchall()


def get_voice_evidence(conn, voice_id):
    """Get evidence links for a voice."""
    return conn.execute(
        "SELECT * FROM voice_evidence WHERE voice_id=? ORDER BY discovered_at",
        (voice_id,),
    ).fetchall()


def upsert_voice(conn, name, platform, profile_url, handle, topic):
    """Insert or get existing voice. Returns (voice_id, is_new)."""
    existing = conn.execute(
        "SELECT id FROM voices WHERE profile_url=? AND topic=?",
        (profile_url, topic),
    ).fetchone()
    if existing:
        return existing["id"], False
    cur = conn.execute(
        "INSERT INTO voices (name, platform, profile_url, handle, topic) VALUES (?, ?, ?, ?, ?)",
        (name, platform, profile_url, handle, topic),
    )
    conn.commit()
    return cur.lastrowid, True


def update_voice_bio(conn, voice_id, bio):
    """Update the bio for a voice."""
    conn.execute("UPDATE voices SET bio=? WHERE id=?", (bio, voice_id))
    conn.commit()


def add_evidence(conn, voice_id, title, url, snippet):
    """Add an evidence link for a voice."""
    conn.execute(
        "INSERT OR IGNORE INTO voice_evidence (voice_id, title, url, snippet) VALUES (?, ?, ?, ?)",
        (voice_id, title, url, snippet),
    )
    conn.commit()


def approve_voice(conn, voice_id, feed_url=None):
    """Mark a voice as approved."""
    conn.execute(
        "UPDATE voices SET status='approved', approved_at=datetime('now'), feed_url=? WHERE id=?",
        (feed_url, voice_id),
    )
    conn.commit()


def reject_voice(conn, voice_id):
    """Mark a voice as rejected."""
    conn.execute(
        "UPDATE voices SET status='rejected', rejected_at=datetime('now') WHERE id=?",
        (voice_id,),
    )
    conn.commit()


def skip_voice(conn, voice_id):
    """Mark a voice as skipped (can resurface later)."""
    conn.execute("UPDATE voices SET status='skipped' WHERE id=?", (voice_id,))
    conn.commit()


def add_content(conn, voice_id, title, url, published_at, summary):
    """Store new content. Returns True if new, False if duplicate."""
    try:
        conn.execute(
            "INSERT INTO content (voice_id, title, url, published_at, summary) VALUES (?, ?, ?, ?, ?)",
            (voice_id, title, url, published_at, summary),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_recent_content(conn, days=7, since=None, until=None):
    """Get content from the last N days, or within a date range."""
    if since and until:
        return conn.execute(
            """SELECT c.*, v.name as voice_name, v.platform, v.profile_url
               FROM content c JOIN voices v ON c.voice_id=v.id
               WHERE c.published_at BETWEEN ? AND ?
               ORDER BY v.name, c.published_at DESC""",
            (since, until),
        ).fetchall()
    return conn.execute(
        """SELECT c.*, v.name as voice_name, v.platform, v.profile_url
           FROM content c JOIN voices v ON c.voice_id=v.id
           WHERE c.fetched_at >= datetime('now', ?)
           ORDER BY v.name, c.published_at DESC""",
        (f"-{days} days",),
    ).fetchall()


def increment_feed_failure(conn, voice_id):
    """Increment failure counter for a voice's feed."""
    conn.execute(
        "UPDATE voices SET feed_failures = feed_failures + 1 WHERE id=?",
        (voice_id,),
    )
    conn.commit()


def reset_feed_failure(conn, voice_id):
    """Reset failure counter after successful poll."""
    conn.execute(
        "UPDATE voices SET feed_failures = 0 WHERE id=?", (voice_id,)
    )
    conn.commit()


def log_discovery_run(conn, topic, platform, results_count):
    """Log a discovery run."""
    conn.execute(
        "INSERT INTO discovery_runs (topic, platform, results_count) VALUES (?, ?, ?)",
        (topic, platform, results_count),
    )
    conn.commit()


def log_digest(conn, file_path, content_count, has_ai_themes):
    """Log a generated digest."""
    conn.execute(
        "INSERT INTO digests (file_path, content_count, has_ai_themes) VALUES (?, ?, ?)",
        (str(file_path), content_count, int(has_ai_themes)),
    )
    conn.commit()


def get_past_digests(conn):
    """List all past digests."""
    return conn.execute(
        "SELECT * FROM digests ORDER BY created_at DESC"
    ).fetchall()
