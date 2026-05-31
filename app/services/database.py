import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "data/testsuitedb.sqlite")

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS environments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        base_url TEXT NOT NULL,
        env_type TEXT NOT NULL DEFAULT 'dev',
        headers TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS test_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        test_type TEXT NOT NULL DEFAULT 'functional',
        method TEXT NOT NULL DEFAULT 'GET',
        path TEXT NOT NULL,
        headers TEXT DEFAULT '{}',
        body TEXT DEFAULT '',
        expected_status INTEGER DEFAULT 200,
        expected_body TEXT DEFAULT '',
        assertions TEXT DEFAULT '[]',
        vus INTEGER DEFAULT 10,
        duration INTEGER DEFAULT 30,
        ramp_up INTEGER DEFAULT 5,
        tags TEXT DEFAULT '[]',
        url_type TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")
    try:
        c.execute("ALTER TABLE test_cases ADD COLUMN url_type TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass

    c.execute("""
    CREATE TABLE IF NOT EXISTS test_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_name TEXT,
        env_name TEXT,
        status TEXT DEFAULT 'pending',
        test_type TEXT DEFAULT 'functional',
        started_at TEXT,
        finished_at TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    try:
        c.execute("ALTER TABLE test_runs ADD COLUMN env_name TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE test_runs ADD COLUMN mapping_name TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE test_runs ADD COLUMN mapping_file TEXT")
        conn.commit()
    except Exception:
        pass

    c.execute("""
    CREATE TABLE IF NOT EXISTS run_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        test_case_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        duration_ms REAL,
        status_code INTEGER,
        response_body TEXT,
        error TEXT,
        assertions_passed INTEGER DEFAULT 0,
        assertions_failed INTEGER DEFAULT 0,
        p50_ms REAL,
        p95_ms REAL,
        p99_ms REAL,
        rps REAL,
        error_rate REAL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (run_id) REFERENCES test_runs(id),
        FOREIGN KEY (test_case_id) REFERENCES test_cases(id)
    )""")

    conn.commit()
    conn.close()


def sync_test_cases_from_file():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("testcases", "testcases.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cases = getattr(mod, "TEST_CASES", [])
    except Exception:
        return

    conn = get_conn()
    for tc in cases:
        name = tc.get("name", "").strip()
        if not name:
            continue
        existing = conn.execute("SELECT id FROM test_cases WHERE name=?", (name,)).fetchone()
        fields = (
            tc.get("description", ""),
            tc.get("test_type", "functional"),
            tc.get("method", "GET"),
            tc.get("path", "/"),
            tc.get("headers", "{}"),
            tc.get("body", ""),
            tc.get("expected_status", 200),
            tc.get("expected_body", ""),
            tc.get("assertions", "[]"),
            tc.get("vus", 10),
            tc.get("duration", 30),
            tc.get("ramp_up", 5),
            tc.get("tags", "[]"),
            tc.get("url_type", ""),
        )
        if existing:
            conn.execute("""
                UPDATE test_cases SET description=?, test_type=?, method=?, path=?,
                headers=?, body=?, expected_status=?, expected_body=?, assertions=?,
                vus=?, duration=?, ramp_up=?, tags=?, url_type=?, updated_at=datetime('now')
                WHERE name=?
            """, (*fields, name))
        else:
            conn.execute("""
                INSERT INTO test_cases
                (name, description, test_type, method, path, headers, body,
                 expected_status, expected_body, assertions, vus, duration, ramp_up, tags, url_type)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (name, *fields))
    conn.commit()
    conn.close()
