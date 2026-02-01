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

CREATE TABLE IF NOT EXISTS cluster_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id INTEGER NOT NULL,
    cluster_id INTEGER,
    cluster_label TEXT,
    similarity_threshold REAL,
    FOREIGN KEY (step_id) REFERENCES test_steps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cluster_info (
    cluster_id INTEGER PRIMARY KEY,
    label TEXT,
    step_count INTEGER,
    case_count INTEGER,
    threshold REAL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_test_steps_case_id ON test_steps(case_id);
CREATE INDEX IF NOT EXISTS idx_cluster_results_step_id ON cluster_results(step_id);
CREATE INDEX IF NOT EXISTS idx_cluster_results_cluster_id ON cluster_results(cluster_id);
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
        db.commit()
        logger.info("Database initialized at %s", db_path)
    app.teardown_appcontext(close_db)


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
