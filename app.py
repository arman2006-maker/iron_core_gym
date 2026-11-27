"""
IronCore Gym Management & Membership Analytics System
Backend REST API + Static Web Server (Python Standard Library + SQLite3)
Database Management Systems (ETCCMS304) | B.Tech. CSE - Semester III
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from seed_data import (
    BASE_DIR,
    DB_PATH,
    DW_DB_PATH,
    NOSQL_PATH,
    REF_DATE,
    get_connection,
    init_database,
)

STATIC_DIR = os.path.join(BASE_DIR, "static")

VALID_TABLES = [
    "attendance",
    "audit_log",
    "booking",
    "branch",
    "class_session",
    "equipment",
    "gym_class",
    "maintenance",
    "member",
    "membership_plan",
    "payment",
    "subscription",
    "trainer",
    "waitlist",
    "workout_plan",
]

# Live RBAC privilege store (matches Slide 10 GRANT / REVOKE demo)
RBAC_STATE = {
    "member": {
        "user": "member_user@localhost",
        "description": "View own bookings, browse classes, book class, pay own dues",
        "permissions": {
            "select_gym_class": True,
            "select_booking": True,
            "insert_booking": True,
            "select_payment": False,
            "insert_payment": True,
            "delete_member": False,
            "mark_attendance": False,
            "manage_equipment": False,
            "run_etl": False,
            "run_sql_lab": False,
        },
    },
    "trainer": {
        "user": "trainer_user@localhost",
        "description": "Mark attendance, view assigned sessions & workout plans, add workout logs",
        "permissions": {
            "select_gym_class": True,
            "select_booking": True,
            "insert_booking": False,
            "select_payment": False,
            "insert_payment": False,
            "delete_member": False,
            "mark_attendance": True,
            "manage_equipment": False,
            "run_etl": False,
            "run_sql_lab": False,
        },
    },
    "front_desk": {
        "user": "front_desk_user@localhost",
        "description": "Add bookings and record payments; cannot delete member records",
        "permissions": {
            "select_gym_class": True,
            "select_booking": True,
            "insert_booking": True,
            "select_payment": True,
            "insert_payment": True,
            "delete_member": False,
            "mark_attendance": True,
            "manage_equipment": True,
            "run_etl": False,
            "run_sql_lab": False,
        },
    },
    "manager": {
        "user": "manager_user@localhost",
        "description": "Read all tables, run analytics reports, ETL star schema & equipment logs",
        "permissions": {
            "select_gym_class": True,
            "select_booking": True,
            "insert_booking": True,
            "select_payment": True,
            "insert_payment": True,
            "delete_member": False,
            "mark_attendance": True,
            "manage_equipment": True,
            "run_etl": True,
            "run_sql_lab": True,
        },
    },
    "admin": {
        "user": "root@localhost",
        "description": "Full privileges including GRANT/REVOKE, triggers, DDL & SQL console",
        "permissions": {
            "select_gym_class": True,
            "select_booking": True,
            "insert_booking": True,
            "select_payment": True,
            "insert_payment": True,
            "delete_member": True,
            "mark_attendance": True,
            "manage_equipment": True,
            "run_etl": True,
            "run_sql_lab": True,
        },
    },
}

RBAC_LOCK = threading.Lock()


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


def check_perm(role: str, perm: str):
    with RBAC_LOCK:
        role_cfg = RBAC_STATE.get(role, RBAC_STATE["admin"])
        return role_cfg["permissions"].get(perm, False), role_cfg["user"]


def build_overview(conn: sqlite3.Connection):
    table_counts = []
    total_rows = 0
    for tbl in VALID_TABLES:
        cnt = conn.execute(f"SELECT COUNT(*) AS c FROM {tbl}").fetchone()["c"]
        table_counts.append({"table": tbl, "rows": cnt})
        total_rows += cnt

    active_members = conn.execute(
        "SELECT COUNT(*) AS c FROM subscription WHERE status = 'ACTIVE'"
    ).fetchone()["c"]
    total_members = conn.execute("SELECT COUNT(*) AS c FROM member").fetchone()["c"]
    total_revenue = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM payment"
    ).fetchone()["s"]
    pending_dues = conn.execute(
        "SELECT COALESCE(SUM(dues_left), 0) AS s FROM v_dues_pending"
    ).fetchone()["s"]
    maint_count = conn.execute(
        "SELECT COUNT(*) AS c FROM equipment WHERE status = 'MAINTENANCE'"
    ).fetchone()["c"]
    occ_row = conn.execute(
        "SELECT SUM(seats_booked) AS b, SUM(capacity) AS cap FROM class_session"
    ).fetchone()
    occupancy_pct = round((occ_row["b"] * 100.0) / occ_row["cap"], 1) if occ_row["cap"] else 0.0

    views = {
        "v_active_members": rows_to_dicts(
            conn.execute("SELECT * FROM v_active_members ORDER BY member_id LIMIT 15").fetchall()
        ),
        "v_dues_pending": rows_to_dicts(
            conn.execute("SELECT * FROM v_dues_pending ORDER BY dues_left DESC").fetchall()
        ),
        "v_class_load": rows_to_dicts(
            conn.execute("SELECT * FROM v_class_load ORDER BY load_pct DESC, session_id").fetchall()
        ),
        "v_trainer_workload": rows_to_dicts(
            conn.execute(
                "SELECT name, speciality, sessions, total_bookings, "
                "RANK() OVER (ORDER BY sessions DESC) AS rnk, "
                "DENSE_RANK() OVER (ORDER BY sessions DESC) AS drnk "
                "FROM v_trainer_workload ORDER BY rnk, name"
            ).fetchall()
        ),
    }

    audit_log = rows_to_dicts(
        conn.execute("SELECT * FROM audit_log ORDER BY log_id DESC LIMIT 15").fetchall()
    )

    monthly_revenue = rows_to_dicts(
        conn.execute(
            "WITH m AS ("
            "  SELECT strftime('%Y-%m', paid_on) AS ym, SUM(amount) AS rev "
            "  FROM payment GROUP BY ym"
            ") "
            "SELECT ym, rev, SUM(rev) OVER (ORDER BY ym) AS run_total "
            "FROM m ORDER BY ym ASC"
        ).fetchall()
    )

    return {
        "project": "IronCore Gym Management & Membership Analytics System",
        "course": "Database Management Systems (ETCCMS304) | B.Tech. CSE - Semester III",
        "reference_date": REF_DATE,
        "table_counts": table_counts,
        "total_tables": len(VALID_TABLES),
        "total_rows": total_rows,
        "kpis": {
            "active_members": active_members,
            "total_members": total_members,
            "total_revenue": total_revenue,
            "pending_dues": pending_dues,
            "occupancy_pct": occupancy_pct,
            "maintenance_equipment": maint_count,
        },
        "views": views,
        "monthly_revenue": monthly_revenue,
        "audit_log": audit_log,
    }


def get_member_portal(conn: sqlite3.Connection, member_id: int):
    member = conn.execute(
        "SELECT m.*, b.branch_name FROM member m JOIN branch b ON m.branch_id = b.branch_id WHERE m.member_id = ?",
        (member_id,),
    ).fetchone()
    if not member:
        return None

    sub = conn.execute(
        "SELECT s.*, p.plan_name, p.fee, "
        "CAST(julianday(s.end_date) - julianday(?) AS INTEGER) AS days_left "
        "FROM subscription s JOIN membership_plan p ON s.plan_id = p.plan_id "
        "WHERE s.member_id = ? ORDER BY s.sub_id DESC LIMIT 1",
        (REF_DATE, member_id),
    ).fetchone()

    dues_left = 0.0
    paid_total = 0.0
    if sub:
        paid_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS paid FROM payment WHERE sub_id = ?",
            (sub["sub_id"],),
        ).fetchone()
        paid_total = paid_row["paid"]
        dues_left = max(0.0, round(sub["fee"] - paid_total, 2))

    free_classes = rows_to_dicts(
        conn.execute(
            "SELECT cs.session_id, gc.class_name, t.name AS trainer_name, cs.room, "
            "cs.session_start, cs.capacity, cs.seats_booked, (cs.capacity - cs.seats_booked) AS free_seats "
            "FROM class_session cs "
            "JOIN gym_class gc ON cs.class_id = gc.class_id "
            "JOIN trainer t ON cs.trainer_id = t.trainer_id "
            "ORDER BY cs.session_start ASC"
        ).fetchall()
    )

    upcoming_bookings = rows_to_dicts(
        conn.execute(
            "SELECT b.booking_id, b.status, b.booked_at, cs.session_id, gc.class_name, "
            "t.name AS trainer_name, cs.room, cs.session_start "
            "FROM booking b "
            "JOIN class_session cs ON b.session_id = cs.session_id "
            "JOIN gym_class gc ON cs.class_id = gc.class_id "
            "JOIN trainer t ON cs.trainer_id = t.trainer_id "
            "WHERE b.member_id = ? AND b.status = 'CONFIRMED' "
            "ORDER BY cs.session_start ASC",
            (member_id,),
        ).fetchall()
    )

    waitlist_entries = rows_to_dicts(
        conn.execute(
            "SELECT w.wait_id, w.session_id, w.requested_at, gc.class_name, cs.session_start "
            "FROM waitlist w "
            "JOIN class_session cs ON w.session_id = cs.session_id "
            "JOIN gym_class gc ON cs.class_id = gc.class_id "
            "WHERE w.member_id = ? ORDER BY w.wait_id DESC",
            (member_id,),
        ).fetchall()
    )

    payments = []
    if sub:
        payments = rows_to_dicts(
            conn.execute(
                "SELECT * FROM payment WHERE sub_id = ? ORDER BY payment_id DESC",
                (sub["sub_id"],),
            ).fetchall()
        )

    return {
        "member": dict(member),
        "subscription": dict(sub) if sub else None,
        "paid_total": paid_total,
        "dues_left": dues_left,
        "free_classes": free_classes,
        "upcoming_bookings": upcoming_bookings,
        "waitlist": waitlist_entries,
        "payments": payments,
    }


def run_preset_queries(conn: sqlite3.Connection):
    presets = [
        {
            "id": "expiring_memberships",
            "title": "1. Expiring Memberships (INNER JOIN)",
            "technique": "INNER JOIN + date window filter",
            "sql": (
                "SELECT m.member_id, m.name, p.plan_name, s.end_date, "
                "CAST(julianday(s.end_date) - julianday('2026-11-27') AS INTEGER) AS days_left "
                "FROM member m "
                "INNER JOIN subscription s ON m.member_id = s.member_id "
                "INNER JOIN membership_plan p ON s.plan_id = p.plan_id "
                "WHERE s.status = 'ACTIVE' AND s.end_date <= date('2026-11-27', '+40 day') "
                "ORDER BY s.end_date ASC;"
            ),
        },
        {
            "id": "free_seats",
            "title": "2. Classes with Free Seats (Subquery)",
            "technique": "Scalar / IN Subquery",
            "sql": (
                "SELECT cs.session_id, gc.class_name, cs.session_start, "
                "(cs.capacity - cs.seats_booked) AS free_seats "
                "FROM class_session cs "
                "JOIN gym_class gc ON cs.class_id = gc.class_id "
                "WHERE cs.session_id IN ("
                "  SELECT session_id FROM class_session WHERE seats_booked < capacity"
                ") "
                "ORDER BY free_seats ASC, cs.session_id LIMIT 8;"
            ),
        },
        {
            "id": "top_trainers",
            "title": "3. Top Trainers (RANK / DENSE_RANK)",
            "technique": "Window Ranking Functions",
            "sql": (
                "SELECT name, speciality, sessions, "
                "RANK() OVER (ORDER BY sessions DESC) AS rnk, "
                "DENSE_RANK() OVER (ORDER BY sessions DESC) AS drnk "
                "FROM v_trainer_workload "
                "ORDER BY rnk, name;"
            ),
        },
        {
            "id": "monthly_revenue",
            "title": "4. Monthly Revenue (CTE + SUM() OVER)",
            "technique": "CTE + Running Total Window",
            "sql": (
                "WITH m AS ("
                "  SELECT strftime('%Y-%m', paid_on) AS ym, SUM(amount) AS rev "
                "  FROM payment GROUP BY ym"
                ") "
                "SELECT ym, rev, SUM(rev) OVER (ORDER BY ym) AS run_total "
                "FROM m ORDER BY ym DESC;"
            ),
        },
        {
            "id": "absent_30_days",
            "title": "5. Active Members Absent 30+ Days (EXCEPT)",
            "technique": "Set Operation (EXCEPT)",
            "sql": (
                "SELECT member_id FROM subscription WHERE status = 'ACTIVE' "
                "EXCEPT "
                "SELECT member_id FROM attendance WHERE check_in >= date('2026-11-27', '-30 day') "
                "ORDER BY 1;"
            ),
        },
        {
            "id": "above_avg_plans",
            "title": "6. Members on Above-Average Plans (Correlated/Scalar Subquery)",
            "technique": "JOIN + Aggregate Subquery",
            "sql": (
                "SELECT m.member_id, m.name, p.plan_name, p.fee "
                "FROM member m "
                "JOIN subscription s USING(member_id) "
                "JOIN membership_plan p USING(plan_id) "
                "WHERE p.fee > (SELECT AVG(fee) FROM membership_plan) "
                "ORDER BY m.member_id LIMIT 10;"
            ),
        },
    ]

    out = []
    for item in presets:
        cur = conn.execute(item["sql"])
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [dict(r) for r in cur.fetchall()]
        out.append(
            {
                "id": item["id"],
                "title": item["title"],
                "technique": item["technique"],
                "sql": item["sql"],
                "columns": cols,
                "rows": rows,
            }
        )
    return out


def run_etl_star_schema():
    """
    Replicates `etl_star.py` from Slide 11:
    [EXTRACT] from OLTP `gym.db` -> [TRANSFORM] date keys & joins -> [LOAD] `gym_dw.db` star schema.
    """
    if os.path.exists(DW_DB_PATH):
        os.remove(DW_DB_PATH)

    oltp = get_connection(DB_PATH)
    dw = sqlite3.connect(DW_DB_PATH)
    dw.row_factory = sqlite3.Row

    dw.executescript(
        """
        CREATE TABLE dim_member (
            member_key INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            plan_name TEXT NOT NULL
        );
        CREATE TABLE dim_plan (
            plan_key INTEGER PRIMARY KEY,
            plan_name TEXT NOT NULL,
            duration_days INTEGER NOT NULL,
            fee REAL NOT NULL
        );
        CREATE TABLE dim_date (
            date_key TEXT PRIMARY KEY,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            day INTEGER NOT NULL,
            day_name TEXT NOT NULL
        );
        CREATE TABLE fact_attendance (
            fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_key INTEGER NOT NULL,
            plan_key INTEGER NOT NULL,
            date_key TEXT NOT NULL,
            duration_min INTEGER NOT NULL,
            FOREIGN KEY (member_key) REFERENCES dim_member(member_key),
            FOREIGN KEY (plan_key) REFERENCES dim_plan(plan_key),
            FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
        );
        """
    )

    members = oltp.execute(
        "SELECT m.member_id, m.name, b.branch_name, p.plan_name, p.plan_id "
        "FROM member m "
        "JOIN branch b ON m.branch_id = b.branch_id "
        "JOIN subscription s ON m.member_id = s.member_id "
        "JOIN membership_plan p ON s.plan_id = p.plan_id"
    ).fetchall()

    plans = oltp.execute("SELECT * FROM membership_plan").fetchall()
    atts = oltp.execute(
        "SELECT a.att_id, a.member_id, a.check_in, a.check_out, s.plan_id "
        "FROM attendance a JOIN subscription s ON a.member_id = s.member_id"
    ).fetchall()

    dw.executemany(
        "INSERT INTO dim_member(member_key, name, branch_name, plan_name) VALUES (?, ?, ?, ?)",
        [(m["member_id"], m["name"], m["branch_name"], m["plan_name"]) for m in members],
    )
    dw.executemany(
        "INSERT INTO dim_plan(plan_key, plan_name, duration_days, fee) VALUES (?, ?, ?, ?)",
        [(p["plan_id"], p["plan_name"], p["duration_days"], p["fee"]) for p in plans],
    )

    seen_dates = set()
    date_rows = []
    fact_rows = []
    for a in atts:
        cin = datetime.strptime(a["check_in"], "%Y-%m-%d %H:%M:%S")
        cout = (
            datetime.strptime(a["check_out"], "%Y-%m-%d %H:%M:%S")
            if a["check_out"]
            else cin
        )
        dur = max(15, int((cout - cin).total_seconds() // 60))
        dkey = cin.strftime("%Y-%m-%d")
        if dkey not in seen_dates:
            seen_dates.add(dkey)
            date_rows.append((dkey, cin.year, cin.month, cin.day, cin.strftime("%A")))
        fact_rows.append((a["member_id"], a["plan_id"], dkey, dur))

    dw.executemany(
        "INSERT INTO dim_date(date_key, year, month, day, day_name) VALUES (?, ?, ?, ?, ?)",
        date_rows,
    )
    dw.executemany(
        "INSERT INTO fact_attendance(member_key, plan_key, date_key, duration_min) VALUES (?, ?, ?, ?)",
        fact_rows,
    )
    dw.commit()

    report = rows_to_dicts(
        dw.execute(
            "SELECT p.plan_name AS plan, COUNT(*) AS visits, ROUND(AVG(f.duration_min), 0) AS avg_min "
            "FROM fact_attendance f JOIN dim_plan p ON f.plan_key = p.plan_key "
            "GROUP BY p.plan_name ORDER BY visits DESC"
        ).fetchall()
    )
    counts = {
        "dim_member": dw.execute("SELECT COUNT(*) FROM dim_member").fetchone()[0],
        "dim_plan": dw.execute("SELECT COUNT(*) FROM dim_plan").fetchone()[0],
        "dim_date": dw.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0],
        "fact_attendance": dw.execute("SELECT COUNT(*) FROM fact_attendance").fetchone()[0],
    }
    sample_facts = rows_to_dicts(
        dw.execute(
            "SELECT f.fact_id, m.name, p.plan_name, d.date_key, d.day_name, f.duration_min "
            "FROM fact_attendance f "
            "JOIN dim_member m ON f.member_key = m.member_key "
            "JOIN dim_plan p ON f.plan_key = p.plan_key "
            "JOIN dim_date d ON f.date_key = d.date_key "
            "ORDER BY f.fact_id DESC LIMIT 8"
        ).fetchall()
    )

    dw.close()
    oltp.close()

    return {
        "extracted": {
            "attendance": len(atts),
            "member": len(members),
            "plans": len(plans),
        },
        "loaded": counts,
        "report": report,
        "sample_facts": sample_facts,
    }


def run_concurrency_demo():
    """
    Runs a live two-thread SQLite transaction race on Zumba #99 (capacity 20, 19 booked).
    Session A (member 30) acquires an exclusive write lock, holds it briefly, books the 20th seat, and commits.
    Session B (member 31) requests the lock, blocks until A commits, observes 20/20, and joins the waitlist.
    """
    # Prepare clean state on session 99 (19/20, members 30 & 31 unbooked and not waitlisted)
    prep = get_connection(DB_PATH)
    prep.execute("DELETE FROM booking WHERE session_id = 99 AND member_id IN (30, 31)")
    prep.execute("DELETE FROM waitlist WHERE session_id = 99 AND member_id IN (30, 31)")
    booked_cnt = prep.execute(
        "SELECT COUNT(*) FROM booking WHERE session_id = 99 AND status = 'CONFIRMED'"
    ).fetchone()[0]
    prep.execute(
        "UPDATE class_session SET seats_booked = ? WHERE session_id = 99", (booked_cnt,)
    )
    prep.commit()
    prep.close()

    timeline = []
    lock_acquired_a = threading.Event()
    t0 = time.perf_counter()

    def ts():
        return f"+{(time.perf_counter() - t0):.3f}s"

    def session_a():
        conn_a = sqlite3.connect(DB_PATH, timeout=15.0, isolation_level=None)
        conn_a.row_factory = sqlite3.Row
        conn_a.execute("PRAGMA foreign_keys = ON;")
        conn_a.execute("BEGIN IMMEDIATE")
        row = conn_a.execute(
            "SELECT session_id, capacity, seats_booked FROM class_session WHERE session_id = 99"
        ).fetchone()
        timeline.append(
            {
                "session": "A",
                "time": ts(),
                "sql": "BEGIN IMMEDIATE; SELECT session_id, capacity, seats_booked FROM class_session WHERE session_id=99 FOR UPDATE;",
                "output": f"Lock acquired -> session 99: {row['seats_booked']}/{row['capacity']} seats booked",
            }
        )
        lock_acquired_a.set()
        time.sleep(1.2)
        conn_a.execute(
            "INSERT INTO booking(member_id, session_id) VALUES (30, 99)"
        )
        conn_a.execute("COMMIT")
        row_after = conn_a.execute(
            "SELECT capacity, seats_booked FROM class_session WHERE session_id = 99"
        ).fetchone()
        timeline.append(
            {
                "session": "A",
                "time": ts(),
                "sql": "INSERT INTO booking(member_id, session_id) VALUES (30, 99); COMMIT;",
                "output": f"Committed! Member 30 got seat #20 ({row_after['seats_booked']}/{row_after['capacity']})",
            }
        )
        conn_a.close()

    def session_b():
        lock_acquired_a.wait()
        time.sleep(0.15)
        conn_b = sqlite3.connect(DB_PATH, timeout=15.0, isolation_level=None)
        conn_b.row_factory = sqlite3.Row
        conn_b.execute("PRAGMA foreign_keys = ON;")
        timeline.append(
            {
                "session": "B",
                "time": ts(),
                "sql": "BEGIN IMMEDIATE; SELECT session_id, capacity, seats_booked FROM class_session WHERE session_id=99 FOR UPDATE;",
                "output": "Waiting for Session A lock to release...",
            }
        )
        conn_b.execute("BEGIN IMMEDIATE")
        row = conn_b.execute(
            "SELECT session_id, capacity, seats_booked FROM class_session WHERE session_id = 99"
        ).fetchone()
        timeline.append(
            {
                "session": "B",
                "time": ts(),
                "sql": "-- Lock granted after A committed",
                "output": f"Read seats {row['seats_booked']}/{row['capacity']} -> Class is FULL! Routing member 31 to waitlist.",
            }
        )
        conn_b.execute(
            "INSERT OR IGNORE INTO waitlist(member_id, session_id) VALUES (31, 99)"
        )
        conn_b.execute("COMMIT")
        timeline.append(
            {
                "session": "B",
                "time": ts(),
                "sql": "INSERT INTO waitlist(member_id, session_id) VALUES (31, 99); COMMIT;",
                "output": "Committed! Member 31 added to waitlist (zero overbooking).",
            }
        )
        conn_b.close()

    ta = threading.Thread(target=session_a)
    tb = threading.Thread(target=session_b)
    ta.start()
    tb.start()
    ta.join()
    tb.join()

    # Check final state
    verify = get_connection(DB_PATH)
    final_s99 = dict(
        verify.execute("SELECT * FROM v_class_load WHERE session_id = 99").fetchone()
    )
    wl = rows_to_dicts(
        verify.execute(
            "SELECT w.*, m.name FROM waitlist w JOIN member m ON w.member_id = m.member_id WHERE w.session_id = 99"
        ).fetchall()
    )
    verify.close()
    return {"timeline": timeline, "session_99": final_s99, "waitlist": wl}


def run_savepoint_demo():
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    steps = []
    try:
        conn.execute("BEGIN")
        steps.append({"step": "START TRANSACTION", "status": "OK", "detail": "Transaction opened"})

        conn.execute(
            "INSERT INTO payment(sub_id, amount, mode, paid_on) VALUES (25, 500.0, 'UPI', ?)",
            (REF_DATE,),
        )
        steps.append(
            {
                "step": "INSERT INTO payment(sub_id, amount, mode) VALUES (25, 500, 'UPI')",
                "status": "OK",
                "detail": "1 row inserted (valid payment)",
            }
        )

        conn.execute("SAVEPOINT sp_pay")
        steps.append(
            {
                "step": "SAVEPOINT sp_pay",
                "status": "OK",
                "detail": "Savepoint created before second payment step",
            }
        )

        try:
            conn.execute(
                "INSERT INTO payment(sub_id, amount, mode, paid_on) VALUES (25, -50.0, 'UPI', ?)",
                (REF_DATE,),
            )
        except sqlite3.IntegrityError as e:
            steps.append(
                {
                    "step": "INSERT INTO payment(sub_id, amount, mode) VALUES (25, -50, 'UPI')",
                    "status": "ERROR",
                    "detail": f"CHECK constraint failed: {e}",
                }
            )
            conn.execute("ROLLBACK TO sp_pay")
            steps.append(
                {
                    "step": "ROLLBACK TO sp_pay",
                    "status": "OK",
                    "detail": "Undid only the failed step; 500.00 UPI payment preserved",
                }
            )

        conn.execute("COMMIT")
        steps.append({"step": "COMMIT", "status": "OK", "detail": "Transaction committed cleanly"})
        rows = rows_to_dicts(
            conn.execute(
                "SELECT payment_id, sub_id, amount, mode, paid_on FROM payment WHERE sub_id = 25 ORDER BY payment_id DESC LIMIT 3"
            ).fetchall()
        )
    finally:
        conn.close()
    return {"steps": steps, "payments_for_sub_25": rows}


def run_sqli_demo(user_input: str):
    conn = get_connection(DB_PATH)
    # 1. Unsafe string concatenation (executed on read-only copy or strictly read-only SELECT)
    ro_conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    ro_conn.row_factory = sqlite3.Row

    unsafe_sql = f"SELECT member_id, name, phone FROM member WHERE name = '{user_input}'"
    unsafe_rows = []
    unsafe_error = None
    try:
        unsafe_rows = rows_to_dicts(ro_conn.execute(unsafe_sql).fetchall())
    except Exception as e:
        unsafe_error = str(e)

    safe_sql = "SELECT member_id, name, phone FROM member WHERE name = ?"
    safe_rows = rows_to_dicts(ro_conn.execute(safe_sql, (user_input,)).fetchall())

    ro_conn.close()
    conn.close()
    return {
        "input": user_input,
        "unsafe": {
            "query": unsafe_sql,
            "rows_leaked": len(unsafe_rows),
            "sample": unsafe_rows[:6],
            "error": unsafe_error,
        },
        "safe": {
            "query": 'cur.execute("SELECT member_id, name, phone FROM member WHERE name = ?", (inp,))',
            "rows_returned": len(safe_rows),
            "sample": safe_rows[:6],
        },
    }


def read_nosql_logs():
    with open(NOSQL_PATH, "r", encoding="utf-8") as f:
        docs = json.load(f)
    # Aggregation pipeline equivalent
    by_type = {}
    for d in docs:
        wt = d.get("workout_type", "Other")
        bucket = by_type.setdefault(wt, {"workout_type": wt, "logs": 0, "total_calories": 0, "rpe_sum": 0.0})
        bucket["logs"] += 1
        bucket["total_calories"] += int(d.get("calories_burned", 0))
        bucket["rpe_sum"] += float(d.get("rpe", 0))
    aggregation = [
        {
            "workout_type": v["workout_type"],
            "logs": v["logs"],
            "total_calories": v["total_calories"],
            "avg_rpe": round(v["rpe_sum"] / v["logs"], 2),
        }
        for v in by_type.values()
    ]
    return {"documents": docs, "aggregation": aggregation}


class GymHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # Keep server output clean

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _role(self):
        return self.headers.get("X-Role", "admin").strip().lower() or "admin"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/overview":
            conn = get_connection(DB_PATH)
            data = build_overview(conn)
            conn.close()
            return self._send_json(data)

        if path.startswith("/api/tables/"):
            tbl = path.split("/api/tables/")[1].strip()
            if tbl not in VALID_TABLES:
                return self._send_json({"error": f"Unknown table: {tbl}"}, HTTPStatus.NOT_FOUND)
            role = self._role()
            if tbl == "payment":
                allowed, user = check_perm(role, "select_payment")
                if not allowed:
                    return self._send_json(
                        {"error": f"ERROR 1142: SELECT command denied to user '{user}' for table 'gym.payment'"},
                        HTTPStatus.FORBIDDEN,
                    )
            conn = get_connection(DB_PATH)
            rows = rows_to_dicts(conn.execute(f"SELECT * FROM {tbl} LIMIT 100").fetchall())
            cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
            conn.close()
            return self._send_json({"table": tbl, "columns": cols, "rows": rows})

        if path == "/api/member-portal":
            member_id = int(qs.get("member_id", ["5"])[0])
            conn = get_connection(DB_PATH)
            portal = get_member_portal(conn, member_id)
            all_members = rows_to_dicts(
                conn.execute("SELECT member_id, name FROM member ORDER BY member_id").fetchall()
            )
            conn.close()
            if not portal:
                return self._send_json({"error": "Member not found"}, HTTPStatus.NOT_FOUND)
            portal["members_list"] = all_members
            return self._send_json(portal)

        if path == "/api/queries/presets":
            conn = get_connection(DB_PATH)
            res = run_preset_queries(conn)
            conn.close()
            return self._send_json({"presets": res})

        if path == "/api/explain-demo":
            conn = get_connection(DB_PATH)
            # Without index (temp drop then recreate so before/after is authentic)
            conn.execute("DROP INDEX IF EXISTS idx_att_in")
            before_plan = rows_to_dicts(
                conn.execute(
                    "EXPLAIN QUERY PLAN SELECT * FROM attendance WHERE check_in = '2026-11-19 17:00:00'"
                ).fetchall()
            )
            conn.execute("CREATE INDEX idx_att_in ON attendance(check_in)")
            after_plan = rows_to_dicts(
                conn.execute(
                    "EXPLAIN QUERY PLAN SELECT * FROM attendance WHERE check_in = '2026-11-19 17:00:00'"
                ).fetchall()
            )
            conn.commit()
            conn.close()
            return self._send_json({"before": before_plan, "after": after_plan})

        if path == "/api/rbac/status":
            with RBAC_LOCK:
                return self._send_json({"roles": RBAC_STATE})

        if path == "/api/nosql/logs":
            return self._send_json(read_nosql_logs())

        if path == "/api/etl/dw":
            if not os.path.exists(DW_DB_PATH):
                return self._send_json(run_etl_star_schema())
            return self._send_json(run_etl_star_schema())

        # Serve SPA fallback
        if path == "/" or not os.path.exists(os.path.join(STATIC_DIR, path.lstrip("/"))):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        role = self._role()
        body = self._read_json()

        if path == "/api/bookings":
            allowed, user = check_perm(role, "insert_booking")
            if not allowed:
                return self._send_json(
                    {"error": f"ERROR 1142: INSERT command denied to user '{user}' for table 'gym.booking'"},
                    HTTPStatus.FORBIDDEN,
                )
            member_id = int(body["member_id"])
            session_id = int(body["session_id"])
            join_waitlist_if_full = bool(body.get("join_waitlist_if_full", False))

            conn = get_connection(DB_PATH)
            try:
                conn.execute(
                    "INSERT INTO booking(member_id, session_id) VALUES (?, ?)",
                    (member_id, session_id),
                )
                conn.commit()
                conn.close()
                return self._send_json({"status": "BOOKED", "message": f"book_class({member_id}, {session_id}) -> BOOKED"})
            except sqlite3.IntegrityError as e:
                err_msg = str(e)
                if "Class is full" in err_msg and join_waitlist_if_full:
                    try:
                        conn.execute(
                            "INSERT INTO waitlist(member_id, session_id) VALUES (?, ?)",
                            (member_id, session_id),
                        )
                        conn.commit()
                        conn.close()
                        return self._send_json(
                            {"status": "WAITLISTED", "message": "Class was full; added to waitlist cleanly."}
                        )
                    except sqlite3.IntegrityError as we:
                        conn.close()
                        return self._send_json({"error": str(we)}, HTTPStatus.BAD_REQUEST)
                conn.close()
                return self._send_json({"error": err_msg}, HTTPStatus.BAD_REQUEST)

        if path == "/api/payments":
            allowed, user = check_perm(role, "insert_payment")
            if not allowed:
                return self._send_json(
                    {"error": f"ERROR 1142: INSERT command denied to user '{user}' for table 'gym.payment'"},
                    HTTPStatus.FORBIDDEN,
                )
            sub_id = int(body["sub_id"])
            amount = float(body["amount"])
            mode = str(body.get("mode", "UPI")).upper()
            conn = get_connection(DB_PATH)
            try:
                conn.execute(
                    "INSERT INTO payment(sub_id, amount, mode, paid_on) VALUES (?, ?, ?, ?)",
                    (sub_id, amount, mode, REF_DATE),
                )
                conn.execute(
                    "INSERT INTO audit_log(table_name, action, details) VALUES ('payment', 'INSERT', ?)",
                    (f"sub_id {sub_id} paid {amount:.2f} via {mode}",),
                )
                conn.commit()
                conn.close()
                return self._send_json({"status": "PAID", "message": f"Paid {amount:.2f} via {mode}"})
            except sqlite3.IntegrityError as e:
                conn.close()
                return self._send_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

        if path == "/api/subscriptions/expire-test":
            sub_id = int(body.get("sub_id", 21))
            conn = get_connection(DB_PATH)
            conn.execute(
                "UPDATE subscription SET end_date = date(?, '-1 day') WHERE sub_id = ?",
                (REF_DATE, sub_id),
            )
            conn.commit()
            row = dict(
                conn.execute(
                    "SELECT sub_id, member_id, end_date, status FROM subscription WHERE sub_id = ?",
                    (sub_id,),
                ).fetchone()
            )
            conn.close()
            return self._send_json({"subscription": row, "message": f"Trigger auto-expired sub_id={sub_id}"})

        if path == "/api/subscriptions/renew":
            member_id = int(body["member_id"])
            plan_id = int(body["plan_id"])
            conn = get_connection(DB_PATH)
            plan = conn.execute("SELECT * FROM membership_plan WHERE plan_id = ?", (plan_id,)).fetchone()
            if not plan:
                conn.close()
                return self._send_json({"error": "Invalid plan_id"}, HTTPStatus.BAD_REQUEST)
            conn.execute(
                "UPDATE subscription SET plan_id = ?, start_date = ?, end_date = date(?, '+' || ? || ' day'), status = 'ACTIVE' "
                "WHERE member_id = ?",
                (plan_id, REF_DATE, REF_DATE, plan["duration_days"], member_id),
            )
            conn.execute(
                "INSERT INTO audit_log(table_name, action, details) VALUES ('subscription', 'RENEW', ?)",
                (f"member {member_id} renewed -> {plan['plan_name']}",),
            )
            conn.commit()
            conn.close()
            return self._send_json({"status": "RENEWED", "plan": plan["plan_name"]})

        if path == "/api/attendance":
            allowed, user = check_perm(role, "mark_attendance")
            if not allowed:
                return self._send_json(
                    {"error": f"ERROR 1142: INSERT command denied to user '{user}' for table 'gym.attendance'"},
                    HTTPStatus.FORBIDDEN,
                )
            member_id = int(body["member_id"])
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_connection(DB_PATH)
            conn.execute(
                "INSERT INTO attendance(member_id, check_in, check_out) VALUES (?, ?, datetime(?, '+75 minutes'))",
                (member_id, now_str, now_str),
            )
            conn.commit()
            conn.close()
            return self._send_json({"status": "CHECKED_IN", "check_in": now_str})

        if path == "/api/equipment/issue":
            allowed, user = check_perm(role, "manage_equipment")
            if not allowed:
                return self._send_json(
                    {"error": f"ERROR 1142: UPDATE command denied to user '{user}' for table 'gym.equipment'"},
                    HTTPStatus.FORBIDDEN,
                )
            equip_id = int(body["equip_id"])
            member_id = int(body.get("member_id", 5))
            conn = get_connection(DB_PATH)
            try:
                conn.execute(
                    "UPDATE equipment SET status = 'ISSUED', issued_to_member_id = ? WHERE equip_id = ?",
                    (member_id, equip_id),
                )
                conn.commit()
                conn.close()
                return self._send_json({"status": "ISSUED", "message": f"Equipment #{equip_id} issued to member #{member_id}"})
            except sqlite3.IntegrityError as e:
                conn.close()
                return self._send_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

        if path == "/api/equipment/return":
            allowed, user = check_perm(role, "manage_equipment")
            if not allowed:
                return self._send_json(
                    {"error": f"ERROR 1142: UPDATE command denied to user '{user}' for table 'gym.equipment'"},
                    HTTPStatus.FORBIDDEN,
                )
            equip_id = int(body["equip_id"])
            conn = get_connection(DB_PATH)
            conn.execute(
                "UPDATE equipment SET status = 'AVAILABLE', issued_to_member_id = NULL WHERE equip_id = ?",
                (equip_id,),
            )
            conn.commit()
            conn.close()
            return self._send_json({"status": "AVAILABLE"})

        if path == "/api/queries/run":
            allowed, user = check_perm(role, "run_sql_lab")
            if not allowed:
                return self._send_json(
                    {"error": f"ERROR 1142: SQL Console restricted for '{user}'. Switch to Manager or Admin."},
                    HTTPStatus.FORBIDDEN,
                )
            sql = str(body.get("sql", "")).strip()
            low = sql.lower()
            if not (low.startswith("select") or low.startswith("with") or low.startswith("explain")):
                return self._send_json(
                    {"error": "SQL Console only executes read-only SELECT, WITH, or EXPLAIN statements."},
                    HTTPStatus.BAD_REQUEST,
                )
            ro_conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            ro_conn.row_factory = sqlite3.Row
            try:
                cur = ro_conn.execute(sql)
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = [dict(r) for r in cur.fetchall()]
                ro_conn.close()
                return self._send_json({"columns": cols, "rows": rows[:200]})
            except Exception as e:
                ro_conn.close()
                return self._send_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

        if path == "/api/labs/concurrency":
            return self._send_json(run_concurrency_demo())

        if path == "/api/labs/savepoint":
            return self._send_json(run_savepoint_demo())

        if path == "/api/labs/sqli":
            inp = str(body.get("input", "x' OR '1'='1"))
            return self._send_json(run_sqli_demo(inp))

        if path == "/api/rbac/toggle":
            target_role = str(body.get("role", "front_desk"))
            perm = str(body.get("permission", "insert_payment"))
            grant = bool(body.get("grant", True))
            with RBAC_LOCK:
                if target_role in RBAC_STATE and perm in RBAC_STATE[target_role]["permissions"]:
                    RBAC_STATE[target_role]["permissions"][perm] = grant
            return self._send_json({"roles": RBAC_STATE})

        if path == "/api/rbac/test":
            test_role = str(body.get("role", "member"))
            action = str(body.get("action", "select_payment"))
            allowed, user = check_perm(test_role, action)
            if action == "select_payment":
                sql = "SELECT * FROM payment LIMIT 1"
                msg = (
                    "Query OK: returned payment_id=1, amount=8000.00, mode='CARD'"
                    if allowed
                    else f"ERROR 1142: SELECT command denied to user '{user}' for table `gym`.`payment`"
                )
            elif action == "insert_payment":
                sql = "INSERT INTO payment(sub_id, amount, mode, paid_on) VALUES (25, 300, 'CASH', CURDATE())"
                msg = (
                    "Query OK, 1 row affected"
                    if allowed
                    else f"ERROR 1142: INSERT command denied to user '{user}' for table `gym`.`payment`"
                )
            elif action == "delete_member":
                sql = "DELETE FROM member WHERE member_id = 40"
                msg = (
                    "Query OK, 1 row affected (only admin permitted)"
                    if allowed
                    else f"ERROR 1142: DELETE command denied to user '{user}' for table `gym`.`member`"
                )
            else:
                sql = "SELECT class_name FROM gym_class LIMIT 2"
                msg = "CrossFit, HIIT"
            return self._send_json({"allowed": allowed, "user": user, "sql": sql, "output": msg})

        if path == "/api/etl/run":
            allowed, user = check_perm(role, "run_etl")
            if not allowed:
                return self._send_json(
                    {"error": f"ETL pipeline requires Manager or Admin role (current: {user})"},
                    HTTPStatus.FORBIDDEN,
                )
            return self._send_json(run_etl_star_schema())

        if path == "/api/nosql/logs":
            with open(NOSQL_PATH, "r", encoding="utf-8") as f:
                docs = json.load(f)
            member_id = int(body.get("member_id", 5))
            conn = get_connection(DB_PATH)
            m_row = conn.execute("SELECT name FROM member WHERE member_id = ?", (member_id,)).fetchone()
            t_id = int(body.get("trainer_id", 1))
            t_row = conn.execute("SELECT name FROM trainer WHERE trainer_id = ?", (t_id,)).fetchone()
            conn.close()
            new_doc = {
                "_id": f"wl_{int(time.time())}",
                "member_id": member_id,
                "member_name": m_row["name"] if m_row else f"Member #{member_id}",
                "trainer_id": t_id,
                "trainer_name": t_row["name"] if t_row else f"Trainer #{t_id}",
                "date": REF_DATE,
                "workout_type": body.get("workout_type", "Strength & Conditioning"),
                "exercises": body.get(
                    "exercises",
                    [{"name": body.get("exercise", "Barbell Squat"), "sets": 4, "reps": 8, "weight_kg": 80}],
                ),
                "rpe": float(body.get("rpe", 8.0)),
                "calories_burned": int(body.get("calories_burned", 420)),
                "trainer_note": body.get("trainer_note", "Logged via IronCore NoSQL Trainer Console."),
            }
            docs.insert(0, new_doc)
            with open(NOSQL_PATH, "w", encoding="utf-8") as f:
                json.dump(docs, f, indent=2)
            return self._send_json(read_nosql_logs())

        if path == "/api/reset":
            init_database(force_reset=True)
            conn = get_connection(DB_PATH)
            data = build_overview(conn)
            conn.close()
            return self._send_json({"status": "RESET_OK", "overview": data})

        return self._send_json({"error": "Endpoint not found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/bookings/"):
            booking_id = int(path.split("/api/bookings/")[1])
            conn = get_connection(DB_PATH)
            b = conn.execute("SELECT * FROM booking WHERE booking_id = ?", (booking_id,)).fetchone()
            if not b:
                conn.close()
                return self._send_json({"error": "Booking not found"}, HTTPStatus.NOT_FOUND)
            session_id = b["session_id"]
            conn.execute("DELETE FROM booking WHERE booking_id = ?", (booking_id,))
            conn.execute(
                "UPDATE class_session SET seats_booked = MAX(0, seats_booked - 1) WHERE session_id = ?",
                (session_id,),
            )
            # Auto-promote first waitlisted member if available
            wl = conn.execute(
                "SELECT * FROM waitlist WHERE session_id = ? ORDER BY wait_id ASC LIMIT 1",
                (session_id,),
            ).fetchone()
            promoted_msg = None
            if wl:
                try:
                    conn.execute(
                        "INSERT INTO booking(member_id, session_id) VALUES (?, ?)",
                        (wl["member_id"], session_id),
                    )
                    conn.execute("DELETE FROM waitlist WHERE wait_id = ?", (wl["wait_id"],))
                    promoted_msg = f"Promoted member #{wl['member_id']} from waitlist"
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
            conn.close()
            return self._send_json({"status": "CANCELLED", "promoted": promoted_msg})
        return self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)


def main():
    init_database(force_reset=False)
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("127.0.0.1", port), GymHandler)
    print(f"IronCore Gym DBMS Web App running at http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
