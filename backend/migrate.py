"""DB migration: adds risk management columns to existing analysts table."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "trading.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print("[migrate] No DB yet - will be created fresh on startup")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("PRAGMA table_info(trades)")
    trades_cols = {row[1] for row in c.fetchall()}
    if "mode" not in trades_cols:
        c.execute("ALTER TABLE trades ADD COLUMN mode VARCHAR(10) DEFAULT 'paper'")
        print("[migrate] trades.mode column added")

    # walk_forward_runs table (created fresh if missing)
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='walk_forward_runs'")
    if not c.fetchone():
        c.execute("""
            CREATE TABLE walk_forward_runs (
                id INTEGER PRIMARY KEY,
                strategy VARCHAR(100),
                primary_symbol VARCHAR(20),
                total_days INTEGER DEFAULT 365,
                train_days INTEGER DEFAULT 120,
                test_days INTEGER DEFAULT 60,
                status VARCHAR(20) DEFAULT 'pending',
                started_at DATETIME,
                completed_at DATETIME,
                n_windows INTEGER DEFAULT 0,
                avg_consistency FLOAT DEFAULT 0.0,
                results_json TEXT,
                error_msg TEXT
            )
        """)
        print("[migrate] walk_forward_runs table created")

    c.execute("PRAGMA table_info(analysts)")
    existing = {row[1] for row in c.fetchall()}

    to_apply = []
    if "paused_until" not in existing:
        to_apply.append("ALTER TABLE analysts ADD COLUMN paused_until DATETIME")
    if "pause_reason" not in existing:
        to_apply.append("ALTER TABLE analysts ADD COLUMN pause_reason VARCHAR(200)")
    if "consecutive_losses" not in existing:
        to_apply.append(
            "ALTER TABLE analysts ADD COLUMN consecutive_losses INTEGER DEFAULT 0"
        )
    if "peak_balance" not in existing:
        to_apply.append("ALTER TABLE analysts ADD COLUMN peak_balance FLOAT")
    if "force_trade_until" not in existing:
        to_apply.append("ALTER TABLE analysts ADD COLUMN force_trade_until DATETIME")

    for sql in to_apply:
        c.execute(sql)
        print(f"[migrate] {sql}")

    conn.commit()
    conn.close()

    if to_apply:
        print(f"[migrate] Applied {len(to_apply)} migration(s)")
    else:
        print("[migrate] Schema up to date")

    # On every startup, reset any runs/validations left stuck in running/pending
    # (happens when the backend process is killed mid-run)
    conn2 = sqlite3.connect(DB_PATH)
    c2 = conn2.cursor()
    bt_fixed = c2.execute(
        "UPDATE backtest_runs SET status='failed', error_msg='Interrupted: backend restart' "
        "WHERE status IN ('running','pending')"
    ).rowcount
    wf_fixed = c2.execute(
        "UPDATE walk_forward_runs SET status='failed', error_msg='Interrupted: backend restart' "
        "WHERE status IN ('running','pending')"
    ).rowcount
    conn2.commit()
    conn2.close()
    if bt_fixed or wf_fixed:
        print(f"[migrate] Cleared {bt_fixed} stuck backtest(s), {wf_fixed} stuck WF run(s)")


if __name__ == "__main__":
    migrate()
