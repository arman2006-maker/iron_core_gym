-- IronCore Gym Management & Membership Analytics System
-- Database Management Systems (ETCCMS304) | B.Tech. CSE - Semester III
-- 15-Table Relational Schema (BCNF) + Views + Indexes + Triggers

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS branch (
    branch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_name TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    phone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS membership_plan (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name TEXT NOT NULL UNIQUE,
    duration_days INTEGER NOT NULL CHECK (duration_days > 0),
    fee REAL NOT NULL CHECK (fee > 0)
);

CREATE TABLE IF NOT EXISTS member (
    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    dob TEXT NOT NULL,
    branch_id INTEGER NOT NULL,
    joined_on TEXT NOT NULL DEFAULT (date('now')),
    FOREIGN KEY (branch_id) REFERENCES branch(branch_id)
);

CREATE TABLE IF NOT EXISTS subscription (
    sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'CANCELLED')),
    FOREIGN KEY (member_id) REFERENCES member(member_id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES membership_plan(plan_id)
);

CREATE TABLE IF NOT EXISTS payment (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_id INTEGER NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    mode TEXT NOT NULL CHECK (mode IN ('UPI', 'CARD', 'CASH', 'NETBANKING')),
    paid_on TEXT NOT NULL,
    FOREIGN KEY (sub_id) REFERENCES subscription(sub_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trainer (
    trainer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    speciality TEXT NOT NULL,
    phone TEXT NOT NULL,
    branch_id INTEGER NOT NULL,
    FOREIGN KEY (branch_id) REFERENCES branch(branch_id)
);

CREATE TABLE IF NOT EXISTS gym_class (
    class_id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS class_session (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    trainer_id INTEGER NOT NULL,
    branch_id INTEGER NOT NULL DEFAULT 1,
    room TEXT NOT NULL,
    session_start TEXT NOT NULL,
    duration_min INTEGER NOT NULL DEFAULT 60 CHECK (duration_min > 0),
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    seats_booked INTEGER NOT NULL DEFAULT 0 CHECK (seats_booked >= 0 AND seats_booked <= capacity),
    FOREIGN KEY (class_id) REFERENCES gym_class(class_id),
    FOREIGN KEY (trainer_id) REFERENCES trainer(trainer_id),
    FOREIGN KEY (branch_id) REFERENCES branch(branch_id),
    UNIQUE (room, session_start)
);

CREATE TABLE IF NOT EXISTS booking (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'CONFIRMED' CHECK (status IN ('CONFIRMED', 'CANCELLED')),
    booked_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (member_id) REFERENCES member(member_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES class_session(session_id) ON DELETE CASCADE,
    UNIQUE (member_id, session_id)
);

CREATE TABLE IF NOT EXISTS waitlist (
    wait_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    requested_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (member_id) REFERENCES member(member_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES class_session(session_id) ON DELETE CASCADE,
    UNIQUE (member_id, session_id)
);

CREATE TABLE IF NOT EXISTS attendance (
    att_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    check_in TEXT NOT NULL,
    check_out TEXT,
    FOREIGN KEY (member_id) REFERENCES member(member_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workout_plan (
    wp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    trainer_id INTEGER NOT NULL,
    goal TEXT NOT NULL,
    weekly_target_days INTEGER NOT NULL DEFAULT 4 CHECK (weekly_target_days BETWEEN 1 AND 7),
    created_on TEXT NOT NULL DEFAULT (date('now')),
    FOREIGN KEY (member_id) REFERENCES member(member_id) ON DELETE CASCADE,
    FOREIGN KEY (trainer_id) REFERENCES trainer(trainer_id)
);

CREATE TABLE IF NOT EXISTS equipment (
    equip_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equip_name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'ISSUED', 'MAINTENANCE')),
    branch_id INTEGER NOT NULL,
    issued_to_member_id INTEGER,
    FOREIGN KEY (branch_id) REFERENCES branch(branch_id),
    FOREIGN KEY (issued_to_member_id) REFERENCES member(member_id)
);

CREATE TABLE IF NOT EXISTS maintenance (
    maint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equip_id INTEGER NOT NULL,
    issue TEXT NOT NULL,
    cost REAL NOT NULL CHECK (cost >= 0),
    reported_on TEXT NOT NULL DEFAULT (date('now')),
    resolved INTEGER NOT NULL DEFAULT 0 CHECK (resolved IN (0, 1)),
    FOREIGN KEY (equip_id) REFERENCES equipment(equip_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- 4 INDEXES (matching Slide 8)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_att_in ON attendance(check_in);
CREATE INDEX IF NOT EXISTS idx_session_start ON class_session(session_start);
CREATE INDEX IF NOT EXISTS idx_sub_end_status ON subscription(end_date, status);
CREATE INDEX IF NOT EXISTS idx_booking_status ON booking(status);

-- ============================================================
-- 4 VIEWS (matching Slide 8)
-- ============================================================
CREATE VIEW IF NOT EXISTS v_active_members AS
SELECT m.member_id, m.name, m.phone, b.branch_name, p.plan_name,
       s.start_date, s.end_date,
       CAST(julianday(s.end_date) - julianday('2026-11-27') AS INTEGER) AS days_left
FROM member m
JOIN branch b ON m.branch_id = b.branch_id
JOIN subscription s ON m.member_id = s.member_id
JOIN membership_plan p ON s.plan_id = p.plan_id
WHERE s.status = 'ACTIVE';

CREATE VIEW IF NOT EXISTS v_dues_pending AS
SELECT s.sub_id, m.member_id, m.name, p.plan_name, p.fee,
       COALESCE(SUM(pay.amount), 0) AS paid_amount,
       ROUND(MAX(0, p.fee - COALESCE(SUM(pay.amount), 0)), 2) AS dues_left
FROM subscription s
JOIN member m ON s.member_id = m.member_id
JOIN membership_plan p ON s.plan_id = p.plan_id
LEFT JOIN payment pay ON s.sub_id = pay.sub_id
GROUP BY s.sub_id, m.member_id, m.name, p.plan_name, p.fee
HAVING dues_left > 0;

CREATE VIEW IF NOT EXISTS v_class_load AS
SELECT cs.session_id, gc.class_name, t.name AS trainer_name, cs.room,
       cs.session_start, cs.seats_booked, cs.capacity,
       ROUND((cs.seats_booked * 100.0) / cs.capacity, 0) AS load_pct
FROM class_session cs
JOIN gym_class gc ON cs.class_id = gc.class_id
JOIN trainer t ON cs.trainer_id = t.trainer_id;

CREATE VIEW IF NOT EXISTS v_trainer_workload AS
SELECT t.trainer_id, t.name, t.speciality,
       COUNT(cs.session_id) AS sessions,
       COALESCE(SUM(cs.seats_booked), 0) AS total_bookings
FROM trainer t
LEFT JOIN class_session cs ON t.trainer_id = cs.trainer_id
GROUP BY t.trainer_id, t.name, t.speciality;

-- ============================================================
-- 3 TRIGGERS (matching Slide 8 & Business Rules)
-- ============================================================
CREATE TRIGGER IF NOT EXISTS trg_block_full_class
BEFORE INSERT ON booking
FOR EACH ROW
WHEN NEW.status = 'CONFIRMED'
BEGIN
    SELECT CASE
        WHEN (SELECT seats_booked FROM class_session WHERE session_id = NEW.session_id)
          >= (SELECT capacity FROM class_session WHERE session_id = NEW.session_id)
        THEN RAISE(ABORT, 'ERROR 1644: Class is full - booking blocked')
    END;
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM subscription
            WHERE member_id = NEW.member_id AND status = 'ACTIVE' AND end_date >= '2026-11-27'
        )
        THEN RAISE(ABORT, 'Business Rule 1: Member can book only with an active subscription')
    END;
    SELECT CASE
        WHEN EXISTS (
            SELECT 1
            FROM booking b
            JOIN class_session cs_existing ON b.session_id = cs_existing.session_id
            JOIN class_session cs_new ON cs_new.session_id = NEW.session_id
            WHERE b.member_id = NEW.member_id
              AND b.status = 'CONFIRMED'
              AND cs_existing.session_start = cs_new.session_start
        )
        THEN RAISE(ABORT, 'Business Rule 3: One member cannot hold two overlapping bookings')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_booking_audit_insert
AFTER INSERT ON booking
FOR EACH ROW
WHEN NEW.status = 'CONFIRMED'
BEGIN
    UPDATE class_session
    SET seats_booked = seats_booked + 1
    WHERE session_id = NEW.session_id;

    INSERT INTO audit_log(table_name, action, details)
    VALUES ('booking', 'INSERT', 'member ' || NEW.member_id || ' -> session ' || NEW.session_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_auto_expire_subscription
AFTER UPDATE OF end_date ON subscription
FOR EACH ROW
WHEN NEW.end_date < '2026-11-27' AND NEW.status = 'ACTIVE'
BEGIN
    UPDATE subscription SET status = 'EXPIRED' WHERE sub_id = NEW.sub_id;
    INSERT INTO audit_log(table_name, action, details)
    VALUES ('subscription', 'AUTO_EXPIRE', 'sub_id ' || NEW.sub_id || ' marked EXPIRED');
END;

CREATE TRIGGER IF NOT EXISTS trg_block_maintenance_equipment_issue
BEFORE UPDATE OF status, issued_to_member_id ON equipment
FOR EACH ROW
WHEN OLD.status = 'MAINTENANCE' AND NEW.status = 'ISSUED'
BEGIN
    SELECT RAISE(ABORT, 'Business Rule 6: Equipment under maintenance cannot be issued');
END;
