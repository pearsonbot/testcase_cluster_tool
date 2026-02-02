import os
import sqlite3
import logging

from flask import g, current_app

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS test_cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    extra_fields TEXT,
    source_file TEXT,
    import_time TEXT
);

CREATE TABLE IF NOT EXISTS test_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    step_no INTEGER NOT NULL,
    operation TEXT NOT NULL,
    extra_fields TEXT,
    FOREIGN KEY (case_id) REFERENCES test_cases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cluster_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_time TEXT NOT NULL,
    model_type TEXT,
    model_name TEXT,
    similarity_threshold REAL,
    total_steps INTEGER,
    total_clusters INTEGER,
    noise_count INTEGER,
    elapsed_seconds REAL,
    is_current INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cluster_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id INTEGER NOT NULL,
    cluster_id INTEGER,
    cluster_label TEXT,
    similarity_threshold REAL,
    history_id INTEGER REFERENCES cluster_history(id),
    FOREIGN KEY (step_id) REFERENCES test_steps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cluster_info (
    cluster_id INTEGER NOT NULL,
    label TEXT,
    step_count INTEGER,
    case_count INTEGER,
    threshold REAL,
    history_id INTEGER REFERENCES cluster_history(id),
    PRIMARY KEY (cluster_id, history_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_test_steps_case_id ON test_steps(case_id);
CREATE INDEX IF NOT EXISTS idx_cluster_results_step_id ON cluster_results(step_id);
CREATE INDEX IF NOT EXISTS idx_cluster_results_cluster_id ON cluster_results(cluster_id);
CREATE INDEX IF NOT EXISTS idx_cluster_results_history ON cluster_results(history_id);
CREATE INDEX IF NOT EXISTS idx_cluster_info_history ON cluster_info(history_id);
CREATE INDEX IF NOT EXISTS idx_cluster_history_current ON cluster_history(is_current);
"""

MIGRATION_SQL = """
-- Add history_id to cluster_results if not exists
ALTER TABLE cluster_results ADD COLUMN history_id INTEGER REFERENCES cluster_history(id);
-- Add history_id to cluster_info if not exists
ALTER TABLE cluster_info ADD COLUMN history_id INTEGER REFERENCES cluster_history(id);
"""


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE_PATH'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    db_path = app.config['DATABASE_PATH']
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA_SQL)
        # Run migrations for existing databases
        _run_migrations(db)
        db.commit()
        logger.info("Database initialized at %s", db_path)
    app.teardown_appcontext(close_db)


def _run_migrations(db):
    """Apply schema migrations for existing databases."""
    # Check if cluster_history table exists
    table_check = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cluster_history'"
    ).fetchone()
    if not table_check:
        db.execute("""CREATE TABLE IF NOT EXISTS cluster_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_time TEXT NOT NULL,
            model_type TEXT,
            model_name TEXT,
            similarity_threshold REAL,
            total_steps INTEGER,
            total_clusters INTEGER,
            noise_count INTEGER,
            elapsed_seconds REAL,
            is_current INTEGER DEFAULT 0
        )""")

    # Check if history_id column exists in cluster_results
    cols = [row[1] for row in db.execute("PRAGMA table_info(cluster_results)").fetchall()]
    if 'history_id' not in cols:
        try:
            db.execute("ALTER TABLE cluster_results ADD COLUMN history_id INTEGER REFERENCES cluster_history(id)")
        except Exception:
            pass

    # Check if history_id column exists in cluster_info
    cols = [row[1] for row in db.execute("PRAGMA table_info(cluster_info)").fetchall()]
    if 'history_id' not in cols:
        try:
            db.execute("ALTER TABLE cluster_info ADD COLUMN history_id INTEGER REFERENCES cluster_history(id)")
        except Exception:
            pass


def get_setting(key, default=None):
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row['value']
    return default


def set_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value)
    )
    db.commit()
