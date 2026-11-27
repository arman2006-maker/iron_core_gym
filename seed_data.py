"""
Database initialization, deterministic 375-row seed dataset,
and MongoDB-style NoSQL workout logs seed for IronCore Gym.
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gym.db")
DW_DB_PATH = os.path.join(BASE_DIR, "gym_dw.db")
NOSQL_PATH = os.path.join(BASE_DIR, "workout_logs.json")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

REF_DATE = "2026-11-27"


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database(force_reset: bool = False) -> None:
    if force_reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    first_init = not os.path.exists(DB_PATH)
    conn = get_connection(DB_PATH)

    if first_init:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        _seed_all(conn)
        conn.commit()
    conn.close()

    if force_reset or not os.path.exists(NOSQL_PATH):
        _seed_nosql_logs()


def _seed_all(conn: sqlite3.Connection) -> None:
    # Temporarily disable booking triggers while loading historical seed rows
    conn.execute("DROP TRIGGER IF EXISTS trg_block_full_class;")
    conn.execute("DROP TRIGGER IF EXISTS trg_booking_audit_insert;")

    # 1. BRANCH (3 rows)
    branches = [
        (1, "IronCore Central", "New Delhi", "011-4012-1001"),
        (2, "IronCore West", "Gurugram", "0124-410-2002"),
        (3, "IronCore South", "Noida", "0120-430-3003"),
    ]
    conn.executemany(
        "INSERT INTO branch(branch_id, branch_name, city, phone) VALUES (?, ?, ?, ?)",
        branches,
    )

    # 2. MEMBERSHIP_PLAN (4 rows)
    plans = [
        (1, "Monthly", 30, 2000.0),
        (2, "Quarterly", 90, 5500.0),
        (3, "Half-Yearly", 180, 9500.0),
        (4, "Annual", 365, 15000.0),
    ]
    conn.executemany(
        "INSERT INTO membership_plan(plan_id, plan_name, duration_days, fee) VALUES (?, ?, ?, ?)",
        plans,
    )

    # 3. MEMBER (40 rows) - includes Aarav Yadav, Reyansh Khan (#5), etc.
    member_names = [
        "Aarav Yadav", "Vihaan Sharma", "Aditya Verma", "Sai Nair", "Reyansh Khan",
        "Arjun Mehta", "Vivaan Gupta", "Kabir Joshi", "Ishaan Patel", "Dhruv Malhotra",
        "Rohan Kapoor", "Ananya Iyer", "Diya Menon", "Myra Reddy", "Saanvi Kulkarni",
        "Aadhya Singh", "Kiara Bansal", "Pari Deshmukh", "Nisha Chatterjee", "Riya Sen",
        "Karan Bedi", "Siddharth Rao", "Manav Bhatia", "Pranav Saxena", "Yash Tiwari",
        "Neha Agarwal", "Pooja Mishra", "Sneha Choudhary", "Tanya Arora", "Devansh Khanna",
        "Raghav Sinha", "Kunal Oberoi", "Harshvardhan Goel", "Tanvi Kulkarni", "Meera Krishnan",
        "Nikhil Dutta", "Varun Chauhan", "Shruti Hegde", "Akash Sethi", "Zoya Qureshi",
    ]
    members = []
    for idx, name in enumerate(member_names, start=1):
        branch_id = ((idx - 1) % 3) + 1
        phone = f"+91-98100{10000 + idx:05d}"[0:14]
        phone = f"98100{10000 + idx:05d}"
        slug = name.lower().replace(" ", ".")
        email = f"{slug}@ironcore.in"
        dob = f"{1992 + (idx % 12)}-{(idx % 12) + 1:02d}-{(idx % 27) + 1:02d}"
        joined_on = "2026-01-15" if idx <= 20 else "2026-05-10"
        members.append((idx, name, phone, email, dob, branch_id, joined_on))
    conn.executemany(
        "INSERT INTO member(member_id, name, phone, email, dob, branch_id, joined_on) VALUES (?, ?, ?, ?, ?, ?, ?)",
        members,
    )

    # 4. SUBSCRIPTION (40 rows)
    # Note: Member #1 and #5 have end_date = 2027-08-19 so days_left() = 265 from 2026-11-27
    # Member #3 and #11 are ACTIVE
    # Member #32 (and some others) can also be active or expired; sub_id=21 starts ACTIVE with end_date=2026-11-30
    subscriptions = []
    for idx in range(1, 41):
        if idx in (1, 5):
            plan_id = 3  # Half-Yearly (matches Aarav Yadav & Reyansh Khan in Slide 7!)
            start_date = "2026-08-19"
            end_date = "2027-08-19"  # 265 days left from 2026-11-27
            status = "ACTIVE"
        elif idx in (3, 11):
            plan_id = 4
            start_date = "2026-03-01"
            end_date = "2027-03-01"
            status = "ACTIVE"
        elif idx == 21:
            plan_id = 2
            start_date = "2026-09-01"
            end_date = "2026-11-30"
            status = "ACTIVE"
        elif idx == 25:
            plan_id = 3
            start_date = "2026-09-15"
            end_date = "2027-03-14"
            status = "ACTIVE"
        elif idx in (37, 38, 39, 40):
            plan_id = 1
            start_date = "2026-09-01"
            end_date = "2026-10-01"
            status = "EXPIRED"
        elif idx % 5 == 0:
            plan_id = 2
            start_date = "2026-10-01"
            end_date = "2026-12-30"
            status = "ACTIVE"
        elif idx % 3 == 0:
            plan_id = 3
            start_date = "2026-07-01"
            end_date = "2026-12-28"
            status = "ACTIVE"
        else:
            plan_id = 4
            start_date = "2026-02-01"
            end_date = "2027-02-01"
            status = "ACTIVE"
        subscriptions.append((idx, idx, plan_id, start_date, end_date, status))
    conn.executemany(
        "INSERT INTO subscription(sub_id, member_id, plan_id, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, ?)",
        subscriptions,
    )

    # 5. PAYMENT (48 rows)
    # Craft monthly totals matching Slide 7:
    # 2026-09 = 31400.00, 2026-10 = 24000.00, cumulative running total up to 2026-10 = 344500.00
    # Prior months sum = 344500 - (31400 + 24000) = 289100.00
    # Also ensure sub_id=5 (Reyansh Khan) has dues left = 6000.00 (plan fee 9500 - 3500 paid = 6000)
    # And sub_id=25 has 3500.00 UPI payment so savepoint demo can add 500.00!
    payments = []
    # Monthly buckets for 48 rows:
    # 2026-02: 6 payments totaling 48000
    # 2026-03: 6 payments totaling 49500
    # 2026-04: 6 payments totaling 45000
    # 2026-05: 6 payments totaling 47000
    # 2026-06: 6 payments totaling 49600
    # 2026-07: 4 payments totaling 26000
    # 2026-08: 4 payments totaling 24000  --> sum(Feb..Aug) = 289100!
    # 2026-09: 5 payments totaling 31400  --> cum = 320500!
    # 2026-10: 5 payments totaling 24000  --> cum = 344500!
    # Total rows = 6+6+6+6+6+4+4+5+5 = 48 rows!
    payment_plan = [
        ("2026-02-05", [8000, 8000, 8000, 8000, 8000, 8000]),
        ("2026-03-10", [9500, 8000, 8000, 8000, 8000, 8000]),
        ("2026-04-12", [7500, 7500, 7500, 7500, 7500, 7500]),
        ("2026-05-14", [9500, 7500, 7500, 7500, 7500, 7500]),
        ("2026-06-15", [9500, 9500, 9500, 7500, 7500, 6100]),
        ("2026-07-18", [9500, 5500, 5500, 5500]),
        ("2026-08-19", [9500, 5500, 5500, 3500]),  # sub_id=5 gets 3500 here so dues=6000!
        ("2026-09-20", [9500, 9500, 5500, 3400, 3500]),  # sub_id=25 gets 3500 here! Total = 31400
        ("2026-10-16", [5500, 5500, 5500, 5500, 2000]),  # Total = 24000
    ]
    modes = ["UPI", "CARD", "CASH", "NETBANKING"]
    pid = 1
    for m_idx, (dt, amounts) in enumerate(payment_plan):
        for a_idx, amt in enumerate(amounts):
            if dt == "2026-08-19" and a_idx == 3:
                sub_id = 5  # Reyansh Khan: paid 3500 of 9500 -> 6000 due!
                mode = "UPI"
            elif dt == "2026-09-20" and a_idx == 4:
                sub_id = 25
                mode = "UPI"
            else:
                sub_id = ((pid - 1) % 40) + 1
                if sub_id in (5, 25):
                    sub_id = 1
                mode = modes[pid % 4]
            payments.append((pid, sub_id, float(amt), mode, dt))
            pid += 1
    assert len(payments) == 48
    conn.executemany(
        "INSERT INTO payment(payment_id, sub_id, amount, mode, paid_on) VALUES (?, ?, ?, ?, ?)",
        payments,
    )

    # 6. TRAINER (8 rows)
    trainers = [
        (1, "Simran Kaur", "Zumba & Cardio", "9820010001", 1),
        (2, "Amit Tyagi", "CrossFit & Strength", "9820010002", 1),
        (3, "Vikram Chauhan", "HIIT & Conditioning", "9820010003", 2),
        (4, "Priya Nair", "Pilates & Mobility", "9820010004", 1),
        (5, "Rohan Malhotra", "Indoor Cycling", "9820010005", 2),
        (6, "Kavita Joshi", "Yoga & Core", "9820010006", 3),
        (7, "Deepak Verma", "Olympic Lifting", "9820010007", 3),
        (8, "Nandini Rao", "Functional Fitness", "9820010008", 1),
    ]
    conn.executemany(
        "INSERT INTO trainer(trainer_id, name, speciality, phone, branch_id) VALUES (?, ?, ?, ?, ?)",
        trainers,
    )

    # 7. GYM_CLASS (6 rows)
    classes = [
        (1, "CrossFit", "Strength"),
        (2, "HIIT", "Cardio"),
        (3, "Spin", "Cycling"),
        (4, "Zumba", "Dance Cardio"),
        (5, "Pilates", "Flexibility"),
        (6, "Strength & Conditioning", "Strength"),
    ]
    conn.executemany(
        "INSERT INTO gym_class(class_id, class_name, category) VALUES (?, ?, ?)",
        classes,
    )

    # 8. CLASS_SESSION (25 rows)
    # Match Slide 7/8/9/11 screenshots:
    # - session 99: Zumba, trainer 1 (Simran Kaur), 2026-11-26 18:00:00, cap 20, booked 19
    # - session 5: Pilates, trainer 4 (Priya Nair), 2026-12-01 16:00:00, cap 12, booked 6
    # - session 7: Zumba, trainer 1 (Simran Kaur), 2026-12-03 06:00:00, cap 12, booked 6
    # - session 10: CrossFit, trainer 2 (Amit Tyagi), 2026-12-03 12:00:00, cap 20, booked 7 (13 free)
    # - session 20: HIIT, trainer 3 (Vikram Chauhan), 2026-12-03 18:00:00, cap 20, booked 4 (16 free)
    # - session 21: Spin, trainer 5 (Rohan Malhotra), 2026-12-04 06:00:00, cap 25, booked 4 (21 free)
    # Trainer counts: Simran Kaur = 4 sessions (rank 1), Amit Tyagi = 3 sessions (rank 2)
    sessions_spec = [
        # (session_id, class_id, trainer_id, branch_id, room, session_start, duration_min, capacity, target_booked)
        (1, 1, 2, 1, "Studio A", "2026-11-28 07:00:00", 60, 20, 4),
        (2, 2, 3, 2, "Cardio Lab", "2026-11-28 09:00:00", 60, 20, 3),
        (3, 3, 5, 2, "Cycle Dome", "2026-11-29 07:00:00", 60, 25, 3),
        (4, 4, 1, 1, "Main Floor", "2026-11-29 18:00:00", 60, 20, 3),
        (5, 5, 4, 1, "Zen Loft", "2026-12-01 16:00:00", 60, 12, 6),
        (6, 6, 7, 3, "Power Rack", "2026-12-02 08:00:00", 60, 16, 2),
        (7, 4, 1, 1, "Main Floor", "2026-12-03 06:00:00", 60, 12, 6),
        (8, 5, 6, 3, "Zen Loft", "2026-12-03 08:00:00", 60, 15, 2),
        (9, 6, 8, 1, "Power Rack", "2026-12-03 10:00:00", 60, 16, 2),
        (10, 1, 2, 1, "Box Arena", "2026-12-03 12:00:00", 60, 20, 7),
        (11, 2, 3, 2, "Cardio Lab", "2026-12-04 09:00:00", 60, 20, 2),
        (12, 3, 5, 2, "Cycle Dome", "2026-12-04 11:00:00", 60, 25, 2),
        (13, 4, 1, 1, "Main Floor", "2026-12-04 17:00:00", 60, 20, 2),
        (14, 5, 4, 1, "Zen Loft", "2026-12-05 08:00:00", 60, 15, 2),
        (15, 6, 7, 3, "Power Rack", "2026-12-05 10:00:00", 60, 16, 2),
        (16, 1, 2, 1, "Box Arena", "2026-12-05 12:00:00", 60, 20, 2),
        (17, 2, 3, 2, "Cardio Lab", "2026-12-05 15:00:00", 60, 20, 2),
        (18, 3, 5, 2, "Cycle Dome", "2026-12-06 07:00:00", 60, 25, 2),
        (19, 5, 6, 3, "Zen Loft", "2026-12-06 09:00:00", 60, 15, 2),
        (20, 2, 3, 2, "Cardio Lab", "2026-12-03 18:00:00", 60, 20, 4),
        (21, 3, 5, 2, "Cycle Dome", "2026-12-04 06:00:00", 60, 25, 4),
        (22, 6, 8, 1, "Power Rack", "2026-12-06 11:00:00", 60, 16, 2),
        (23, 5, 4, 1, "Zen Loft", "2026-12-07 08:00:00", 60, 15, 2),
        (24, 6, 7, 3, "Power Rack", "2026-12-07 10:00:00", 60, 16, 2),
        (99, 4, 1, 1, "Main Floor", "2026-11-26 18:00:00", 60, 20, 19),
    ]
    # Check sum of target_booked = 92!
    # 4+3+3+3+6+2+6+2+2+7+2+2+2+2+2+2+2+2+2+4+4+2+2+2+19 = 87... wait let's sum carefully:
    # 4+3+3+3=13; +6+2+6+2+2+7 = 38; +2*9 (11..19) = 56; +4+4 = 64; +2+2+2 = 70; +19 = 89!
    # We need 92 bookings total (matching Slide 6: booking = 92).
    # Let's bump 3 sessions by +1 each (e.g. session 1 -> 5, session 2 -> 4, session 3 -> 4) -> 92!
    sessions_spec[0] = (1, 1, 2, 1, "Studio A", "2026-11-28 07:00:00", 60, 20, 5)
    sessions_spec[1] = (2, 2, 3, 2, "Cardio Lab", "2026-11-28 09:00:00", 60, 20, 4)
    sessions_spec[2] = (3, 3, 5, 2, "Cycle Dome", "2026-11-29 07:00:00", 60, 25, 4)

    conn.executemany(
        "INSERT INTO class_session(session_id, class_id, trainer_id, branch_id, room, session_start, duration_min, capacity, seats_booked) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        sessions_spec,
    )

    # 9. BOOKING (92 rows matching seats_booked per session)
    # Keep member #30, #31, #32 OUT of session 99 so they can be used in the live concurrency & full-class demos!
    # Keep member #5 (Reyansh Khan) OUT of session 10 so gym_app demo book_class(5, 10) works!
    # Ensure member #5 IS booked in session 99 (Zumba Thu 18:00) or session 4 (Zumba 18:00)
    bookings = []
    bid = 1
    for s in sessions_spec:
        sid = s[0]
        count = s[8]
        chosen_members = []
        candidate = 1
        while len(chosen_members) < count:
            if sid == 99 and candidate in (30, 31, 32):
                candidate += 1
                continue
            if sid == 10 and candidate == 5:
                candidate += 1
                continue
            if candidate > 36:  # keep 37-40 expired members unbooked
                candidate = 1
            if candidate not in chosen_members:
                chosen_members.append(candidate)
            candidate += 1
        for m_id in chosen_members:
            bookings.append((bid, m_id, sid, "CONFIRMED", "2026-11-20 10:00:00"))
            bid += 1
    assert len(bookings) == 92
    conn.executemany(
        "INSERT INTO booking(booking_id, member_id, session_id, status, booked_at) VALUES (?, ?, ?, ?, ?)",
        bookings,
    )

    # 10. WAITLIST (6 rows)
    waitlist_rows = [
        (1, 33, 99, "2026-11-25 14:10:00"),
        (2, 34, 99, "2026-11-25 14:25:00"),
        (3, 12, 5, "2026-11-25 15:00:00"),
        (4, 15, 7, "2026-11-25 16:05:00"),
        (5, 18, 10, "2026-11-26 09:15:00"),
        (6, 22, 20, "2026-11-26 11:30:00"),
    ]
    conn.executemany(
        "INSERT INTO waitlist(wait_id, member_id, session_id, requested_at) VALUES (?, ?, ?, ?)",
        waitlist_rows,
    )

    # 11. ATTENDANCE (60 rows)
    # - Members #3 and #11 must NOT have attendance in the last 30 days (so EXCEPT query returns 3, 11)!
    # - Include check_in = '2026-11-19 17:00:00' for EXPLAIN index demo!
    # - Average duration ~75 min across Annual (46 visits), Quarterly (7 visits), Half-Yearly (7 visits)
    attendance_rows = []
    # Distribute 60 visits across active members excluding 3 and 11 for recent dates:
    # Let's assign 46 visits to Annual-plan members, 7 to Quarterly-plan members, 7 to Half-Yearly-plan members!
    # Check plan assignments from subscriptions:
    # Half-Yearly (plan 3): idx in (1, 5, 25) or (idx % 3 == 0 and idx not in (3,5,11,21,25,30,37,38,39,40))
    # Quarterly (plan 2): idx == 21 or (idx % 5 == 0 and idx not in (5,25,40))
    # Annual (plan 4): remaining active members!
    sub_plan_map = {s[1]: s[2] for s in subscriptions}
    annual_members = [m for m, p in sub_plan_map.items() if p == 4 and m not in (3, 11)]
    quarterly_members = [m for m, p in sub_plan_map.items() if p == 2]
    half_yearly_members = [m for m, p in sub_plan_map.items() if p == 3]

    att_id = 1
    # 46 Annual visits (~75 min avg)
    for i in range(46):
        m_id = annual_members[i % len(annual_members)]
        day = (i % 21) + 1  # 21 distinct dates -> matches dim_date = 21 rows in ETL Slide 11!
        dt_str = f"2026-11-{day:02d}"
        if i == 0:
            cin = "2026-11-19 17:00:00"
            cout = "2026-11-19 18:15:00"
        else:
            cin = f"{dt_str} {6 + (i % 12):02d}:00:00"
            dur = 75 if i % 2 == 0 else 75
            end_dt = datetime.strptime(cin, "%Y-%m-%d %H:%M:%S") + timedelta(minutes=dur)
            cout = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        attendance_rows.append((att_id, m_id, cin, cout))
        att_id += 1

    # 7 Quarterly visits (~76 min avg)
    for i in range(7):
        m_id = quarterly_members[i % len(quarterly_members)]
        day = (i % 21) + 1
        cin = f"2026-11-{day:02d} {8 + i:02d}:00:00"
        dur = 76
        cout = (datetime.strptime(cin, "%Y-%m-%d %H:%M:%S") + timedelta(minutes=dur)).strftime("%Y-%m-%d %H:%M:%S")
        attendance_rows.append((att_id, m_id, cin, cout))
        att_id += 1

    # 7 Half-Yearly visits (~73 min avg)
    for i in range(7):
        m_id = half_yearly_members[i % len(half_yearly_members)]
        day = (i % 21) + 1
        cin = f"2026-11-{day:02d} {10 + i:02d}:00:00"
        dur = 73
        cout = (datetime.strptime(cin, "%Y-%m-%d %H:%M:%S") + timedelta(minutes=dur)).strftime("%Y-%m-%d %H:%M:%S")
        attendance_rows.append((att_id, m_id, cin, cout))
        att_id += 1

    assert len(attendance_rows) == 60
    conn.executemany(
        "INSERT INTO attendance(att_id, member_id, check_in, check_out) VALUES (?, ?, ?, ?)",
        attendance_rows,
    )

    # 12. WORKOUT_PLAN (20 rows)
    goals = [
        "Fat Loss & Core Conditioning",
        "Hypertrophy & Upper Body Strength",
        "5K Endurance & VO2 Max",
        "Posture & Mobility Recovery",
        "Powerlifting Total Improvement",
    ]
    wp_rows = []
    for i in range(1, 21):
        wp_rows.append((i, i, ((i - 1) % 8) + 1, goals[(i - 1) % len(goals)], 4 + (i % 2), "2026-11-01"))
    conn.executemany(
        "INSERT INTO workout_plan(wp_id, member_id, trainer_id, goal, weekly_target_days, created_on) VALUES (?, ?, ?, ?, ?, ?)",
        wp_rows,
    )

    # 13. EQUIPMENT (12 rows)
    equip_rows = [
        (1, "Concept2 RowErg #1", "Cardio", "AVAILABLE", 1, None),
        (2, "Assault AirBike Pro", "Cardio", "AVAILABLE", 1, None),
        (3, "Rogue Olympic Barbell 20kg", "Strength", "ISSUED", 1, 5),
        (4, "Kettlebell Set 24kg", "Functional", "AVAILABLE", 1, None),
        (5, "Commercial Treadmill T9", "Cardio", "MAINTENANCE", 1, None),
        (6, "Spinning Bike Keiser M3i", "Cycling", "AVAILABLE", 2, None),
        (7, "Cable Crossover Station", "Strength", "MAINTENANCE", 2, None),
        (8, "Plyometric Box Set", "CrossFit", "AVAILABLE", 2, None),
        (9, "Smith Machine Pro", "Strength", "AVAILABLE", 3, None),
        (10, "Battle Rope 15m", "HIIT", "ISSUED", 3, 12),
        (11, "Pilates Reformer #2", "Flexibility", "MAINTENANCE", 1, None),
        (12, "Adjustable Dumbbell Pair 30kg", "Strength", "AVAILABLE", 3, None),
    ]
    conn.executemany(
        "INSERT INTO equipment(equip_id, equip_name, category, status, branch_id, issued_to_member_id) VALUES (?, ?, ?, ?, ?, ?)",
        equip_rows,
    )

    # 14. MAINTENANCE (8 rows)
    maint_rows = [
        (1, 5, "Drive belt tension & motor calibration", 4200.0, "2026-11-18", 0),
        (2, 7, "Left pulley cable fraying replacement", 2800.0, "2026-11-21", 0),
        (3, 11, "Carriage spring assembly replacement", 3100.0, "2026-11-23", 0),
        (4, 1, "Flywheel damper sensor cleaning", 650.0, "2026-10-12", 1),
        (5, 2, "Chain lubrication & console battery", 500.0, "2026-10-20", 1),
        (6, 6, "Magnetic resistance recalibration", 1400.0, "2026-10-28", 1),
        (7, 9, "Linear bearing alignment", 1900.0, "2026-11-02", 1),
        (8, 3, "Sleeve collar circlip service", 450.0, "2026-11-08", 1),
    ]
    conn.executemany(
        "INSERT INTO maintenance(maint_id, equip_id, issue, cost, reported_on, resolved) VALUES (?, ?, ?, ?, ?, ?)",
        maint_rows,
    )

    # 15. AUDIT_LOG (3 rows)
    audit_rows = [
        (1, "booking", "INSERT", "member 1 -> session 1", "2026-11-20 10:00:00"),
        (2, "subscription", "INSERT", "member 5 -> Half-Yearly", "2026-08-19 09:30:00"),
        (3, "booking", "INSERT", "member 29 -> session 99", "2026-11-25 18:10:00"),
    ]
    conn.executemany(
        "INSERT INTO audit_log(log_id, table_name, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
        audit_rows,
    )

    # Re-create triggers cleanly after seed
    conn.executescript(
        """
        CREATE TRIGGER trg_block_full_class
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

        CREATE TRIGGER trg_booking_audit_insert
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
        """
    )


def _seed_nosql_logs() -> None:
    docs = [
        {
            "_id": "wl_6741a01",
            "member_id": 5,
            "member_name": "Reyansh Khan",
            "trainer_id": 2,
            "trainer_name": "Amit Tyagi",
            "date": "2026-11-24",
            "workout_type": "CrossFit",
            "exercises": [
                {"name": "Deadlift", "sets": 4, "reps": 6, "weight_kg": 110},
                {"name": "Box Jumps", "sets": 4, "reps": 15, "weight_kg": 0},
                {"name": "Kettlebell Swings", "sets": 3, "reps": 20, "weight_kg": 24},
            ],
            "rpe": 8.5,
            "calories_burned": 540,
            "trainer_note": "Solid hip hinge form; ready to progress deadlift to 115 kg next week.",
        },
        {
            "_id": "wl_6741a02",
            "member_id": 1,
            "member_name": "Aarav Yadav",
            "trainer_id": 1,
            "trainer_name": "Simran Kaur",
            "date": "2026-11-25",
            "workout_type": "Zumba & Cardio",
            "exercises": [
                {"name": "High-Tempo Salsa Intervals", "sets": 5, "reps": 1, "duration_min": 8},
                {"name": "RowErg Sprints", "sets": 4, "reps": 500, "unit": "meters"},
            ],
            "rpe": 7.5,
            "calories_burned": 490,
            "trainer_note": "Consistent aerobic zone 4 pace; hydration breaks timed well.",
        },
        {
            "_id": "wl_6741a03",
            "member_id": 12,
            "member_name": "Ananya Iyer",
            "trainer_id": 4,
            "trainer_name": "Priya Nair",
            "date": "2026-11-25",
            "workout_type": "Pilates",
            "exercises": [
                {"name": "Reformer Hundred", "sets": 3, "reps": 100, "weight_kg": 15},
                {"name": "Single-Leg Stretch", "sets": 3, "reps": 12, "weight_kg": 0},
            ],
            "rpe": 6.5,
            "calories_burned": 280,
            "trainer_note": "Thoracic mobility improved; keep neutral spine on roll-downs.",
        },
        {
            "_id": "wl_6741a04",
            "member_id": 6,
            "member_name": "Arjun Mehta",
            "trainer_id": 3,
            "trainer_name": "Vikram Chauhan",
            "date": "2026-11-26",
            "workout_type": "HIIT",
            "exercises": [
                {"name": "Assault Bike Tabata", "sets": 8, "reps": 20, "unit": "sec"},
                {"name": "Battle Rope Slams", "sets": 4, "reps": 30, "unit": "sec"},
            ],
            "rpe": 9.0,
            "calories_burned": 610,
            "trainer_note": "Peak heart rate 178 bpm; recovery dropped 32 bpm in 60s.",
        },
    ]
    with open(NOSQL_PATH, "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2)
