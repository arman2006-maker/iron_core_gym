# IronCore Gym — Gym Management & Membership Analytics System

**Course:** Database Management Systems (`ETCCMS304`) | **B.Tech. CSE – Semester III**

## Run the Website
```powershell
cd "d:\Dbms capstone\ironcore-gym"
python app.py
```
Then open: **http://127.0.0.1:8080**

## PPT Deliverables Implemented Live
1. **Overview & Views (Slides 1, 3, 6, 8):** 15 tables / 375 seed rows, KPIs, monthly revenue CTE + `SUM() OVER` chart, `v_class_load`, `v_dues_pending`, `audit_log`, and live `trg_auto_expire_subscription` test.
2. **Member & Operations App (Slides 3, 8, 11):** Live `gym_app.py` experience (`Reyansh Khan`, active plan days left, dues payment, class booking with full-class/overlap/expiry triggers, waitlist promotion on cancel, equipment maintenance lock).
3. **Interactive ER/EER Diagram & BCNF (Slides 4, 5, 6):** Clickable 15-table SVG ER diagram + live table browser + 0NF to BCNF breakdown and key functional dependencies.
4. **Complex SQL Query Lab & Indexes (Slides 7, 8):** All 6 capstone queries + custom read-only SQL editor + `EXPLAIN QUERY PLAN` before/after `idx_att_in`.
5. **Transactions, Concurrency & Security Labs (Slides 9, 10):** Live 2-thread `FOR UPDATE` race on Zumba #99, `SAVEPOINT sp_pay` rollback demo, RBAC `GRANT/REVOKE` tester, and SQL Injection simulator (`sqli_demo.py`).
6. **Star Schema ETL & NoSQL (Slide 11):** Live OLTP `gym` -> `gym_dw` (`dim_member`, `dim_plan`, `dim_date`, `fact_attendance`) ETL + MongoDB-style JSON workout logs & aggregation.
