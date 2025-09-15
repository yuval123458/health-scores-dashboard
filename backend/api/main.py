import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

app = FastAPI(title="Customer Health Score API", version="0.2.0 (events-based)")

# ---- CORS ----
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://production-frontend.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Config / weights (could be moved to a DB table later) ----
WEIGHTS = {
    "logins": 0.40,
    "adoption": 0.35,
    "tickets": 0.15,
    "invoice": 0.10,
}
TARGETS = {
    "logins_30d": 20,          # target for last 30 days logins
    "adoption_denominator": 5, # distinct features in 60d / denom
    "tickets_cap_30d": 5,      # penalty cap
}

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def compute_health_from_components(
    logins_30d: int,
    adoption_rate_60d: float,  # 0..1
    tickets_30d: int,
    last_invoice: Optional[str],  # 'invoice_paid' | 'invoice_late' | 'unknown'/None
) -> int:
    logins_norm = clamp01(logins_30d / max(1, TARGETS["logins_30d"]))
    adoption_norm = clamp01(adoption_rate_60d)
    tickets_penalty = clamp01(tickets_30d / max(1, TARGETS["tickets_cap_30d"]))
    invoice_factor = 1.0 if last_invoice == "invoice_paid" else (0.0 if last_invoice == "invoice_late" else 0.5)

    score01 = (
        WEIGHTS["logins"]   * logins_norm +
        WEIGHTS["adoption"] * adoption_norm +
        WEIGHTS["tickets"]  * (1 - tickets_penalty) +
        WEIGHTS["invoice"]  * invoice_factor
    )
    score = int(round(100 * clamp01(score01)))
    return score

def tier(score: int) -> str:
    return "Green" if score >= 80 else ("Yellow" if score >= 60 else "Red")

# ---- Startup: verify DB ----
@app.on_event("startup")
def test_db_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        import sys
        print("Database connection failed:", e)
        sys.exit(1)

# ---- Helper SQL snippets built on events ----
AGG_NOW_SQL = text("""
/* Per-customer current-window metrics from events only */
WITH
l30 AS (
  SELECT customer_id, COUNT(*) AS logins_30d
  FROM event
  WHERE type='login' AND occurred_at >= NOW() - INTERVAL 30 DAY
  GROUP BY customer_id
),
a60 AS (
  /* adoption = distinct features in 60d / denominator */
  SELECT
    e.customer_id,
    COUNT(DISTINCT JSON_UNQUOTE(JSON_EXTRACT(e.metadata_json,'$.feature'))) AS distinct_features_60d
  FROM event e
  WHERE e.type='feature_use'
    AND e.occurred_at >= NOW() - INTERVAL 60 DAY
  GROUP BY e.customer_id
),
t30 AS (
  SELECT customer_id, COUNT(*) AS tickets_30d
  FROM event
  WHERE type='ticket_opened' AND occurred_at >= NOW() - INTERVAL 30 DAY
  GROUP BY customer_id
),
inv AS (
  /* Latest invoice_paid per customer, interpreted via metadata_json.paid_on_time */
  SELECT customer_id,
         CASE
           WHEN JSON_EXTRACT(metadata_json,'$.paid_on_time') = true  THEN 'invoice_paid'
           WHEN JSON_EXTRACT(metadata_json,'$.paid_on_time') = false THEN 'invoice_late'
           ELSE 'unknown'
         END AS last_invoice_type,
         (JSON_EXTRACT(metadata_json,'$.paid_on_time') = true) AS last_paid_on_time,
         CAST(JSON_UNQUOTE(JSON_EXTRACT(metadata_json,'$.days_late')) AS UNSIGNED) AS last_days_late
  FROM (
    SELECT e.*,
           ROW_NUMBER() OVER (PARTITION BY e.customer_id ORDER BY e.occurred_at DESC) AS rn
    FROM event e
    WHERE e.type='invoice_paid'
  ) z
  WHERE rn = 1
),
last_evt AS (
  SELECT customer_id, MAX(occurred_at) AS last_activity_at
  FROM event
  GROUP BY customer_id
)
SELECT
  c.id,
  c.name,
  c.segment,
  c.plan,
  c.created_at,
  c.updated_at,
  COALESCE(l30.logins_30d, 0) AS logins_30d,
  COALESCE(a60.distinct_features_60d, 0) AS distinct_features_60d,
  COALESCE(t30.tickets_30d, 0) AS tickets_30d,
  COALESCE(inv.last_invoice_type, 'unknown') AS last_invoice_type,
  COALESCE(inv.last_paid_on_time, NULL)     AS last_paid_on_time,
  COALESCE(inv.last_days_late, NULL)        AS last_days_late,
  last_evt.last_activity_at
FROM customer c
LEFT JOIN l30      ON l30.customer_id = c.id
LEFT JOIN a60      ON a60.customer_id = c.id
LEFT JOIN t30      ON t30.customer_id = c.id
LEFT JOIN inv      ON inv.customer_id = c.id
LEFT JOIN last_evt ON last_evt.customer_id = c.id
ORDER BY c.name;
""")


@app.get("/api/customers")
def list_customers():
    with engine.connect() as conn:
        rows = conn.execute(AGG_NOW_SQL).mappings().all()

    out: List[Dict[str, Any]] = []
    denom = max(1, TARGETS["adoption_denominator"])
    for r in rows:
        adoption_rate = min(1.0, (r["distinct_features_60d"] or 0) / denom)
        score = compute_health_from_components(
            logins_30d=int(r["logins_30d"] or 0),
            adoption_rate_60d=float(adoption_rate),
            tickets_30d=int(r["tickets_30d"] or 0),
            last_invoice=str(r["last_invoice_type"] or "unknown"),
        )
        out.append({
            "id": r["id"],
            "name": r["name"],
            "segment": r["segment"],
            "plan": r["plan"],
            "created_at": r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else None,
            "updated_at": r["updated_at"].strftime("%Y-%m-%d") if r["updated_at"] else None,
            "health_score": score,
            "health_tier": tier(score),
            "metrics": {
                "logins_30d": r["logins_30d"],
                "adoption_distinct_features_60d": r["distinct_features_60d"],
                "adoption_rate_60d": round(adoption_rate, 3),
                "tickets_30d": r["tickets_30d"],
                "last_invoice": r["last_invoice_type"],  # 'invoice_paid' or 'invoice_late' or 'unknown'
                "last_invoice_paid_on_time": r["last_paid_on_time"],  # 1/0/None
                "last_invoice_days_late": r["last_days_late"],  # int/None
                "last_activity_at": r["last_activity_at"].strftime("%Y-%m-%d") if r["last_activity_at"] else None,
            }
        })
    return out

@app.get("/api/customers/{id}/health")
def customer_health_detail(id: int):
    with engine.connect() as conn:
        customer = conn.execute(
            text("SELECT id, name, segment, plan, created_at, updated_at FROM customer WHERE id=:id"),
            {"id": id}
        ).mappings().first()
        if not customer:
            raise HTTPException(404, "Customer not found")

        # Month-by-month metrics from events (last 12 months)
        history_sql = text("""
        WITH seq AS (
          SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL
          SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL
          SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11
        ),
        months AS (
          -- first day of each month as DATE
          SELECT DATE_SUB(DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL n MONTH) AS month_start
          FROM seq
        ),
        mwin AS (
          SELECT
            month_start,
            DATE_ADD(month_start, INTERVAL 1 MONTH) AS month_end
          FROM months
        ),
        l AS (
          SELECT
            mw.month_start,
            COUNT(e.id) AS login_count
          FROM mwin mw
          LEFT JOIN event e
            ON e.customer_id=:cid
           AND e.type='login'
           AND e.occurred_at >= mw.month_start
           AND e.occurred_at <  mw.month_end
          GROUP BY mw.month_start
        ),
        a AS (
          SELECT
            mw.month_start,
            COUNT(DISTINCT JSON_UNQUOTE(JSON_EXTRACT(e.metadata_json,'$.feature'))) AS feature_adoption
          FROM mwin mw
          LEFT JOIN event e
            ON e.customer_id=:cid
           AND e.type='feature_use'
           AND e.occurred_at >= mw.month_start
           AND e.occurred_at <  mw.month_end
          GROUP BY mw.month_start
        ),
        t AS (
          SELECT
            mw.month_start,
            COUNT(e.id) AS support_tickets
          FROM mwin mw
          LEFT JOIN event e
            ON e.customer_id=:cid
           AND e.type='ticket_opened'
           AND e.occurred_at >= mw.month_start
           AND e.occurred_at <  mw.month_end
          GROUP BY mw.month_start
        ),
            p AS (
  SELECT
    mw.month_start,
    SUBSTRING_INDEX(
      GROUP_CONCAT(
        CASE
          WHEN e.type='invoice_paid'
           AND e.occurred_at >= mw.month_start
           AND e.occurred_at <  mw.month_end
          THEN CASE
                 WHEN JSON_EXTRACT(e.metadata_json,'$.paid_on_time') = true  THEN 'invoice_paid'
                 WHEN JSON_EXTRACT(e.metadata_json,'$.paid_on_time') = false THEN 'invoice_late'
                 ELSE 'unknown'
               END
        END
        ORDER BY e.occurred_at DESC
      ), ',', 1
    ) AS payment_status
  FROM mwin mw
  LEFT JOIN event e
    ON e.customer_id=:cid
  GROUP BY mw.month_start
)

        SELECT
          DATE_FORMAT(month_start, '%Y-%m') AS month,
          COALESCE(l.login_count,0)            AS login_count,
          COALESCE(a.feature_adoption,0)       AS feature_adoption,
          COALESCE(t.support_tickets,0)        AS support_tickets,
          COALESCE(p.payment_status,'unknown') AS payment_status
        FROM mwin
        LEFT JOIN l USING (month_start)
        LEFT JOIN a USING (month_start)
        LEFT JOIN t USING (month_start)
        LEFT JOIN p USING (month_start)
        ORDER BY month_start DESC;
        """)
        hist_rows = conn.execute(history_sql, {"cid": id}).mappings().all()

    # compute scores per month (using per-month buckets as approximation)
    out_history: List[Dict[str, Any]] = []
    denom = max(1, TARGETS["adoption_denominator"])
    for h in hist_rows:
        adoption_rate = min(1.0, (h["feature_adoption"] or 0) / denom)
        score = compute_health_from_components(
            logins_30d=int(h["login_count"] or 0),
            adoption_rate_60d=float(adoption_rate),
            tickets_30d=int(h["support_tickets"] or 0),
            last_invoice=("invoice_paid" if h["payment_status"] == "invoice_paid"
                          else "invoice_late" if h["payment_status"] == "invoice_late"
                          else "unknown"),
        )
        out_history.append({
            "month": h["month"],
            "health_score": score,
            "health_tier": tier(score),
            "metrics": {
                "login_count": h["login_count"],
                "feature_adoption": h["feature_adoption"],
                "adoption_rate": round(adoption_rate, 3),
                "support_tickets": h["support_tickets"],
                "payment_status": h["payment_status"],
            }
        })

    return {
        "id": customer["id"],
        "name": customer["name"],
        "segment": customer["segment"],
        "plan": customer["plan"],
        "created_at": customer["created_at"].strftime("%Y-%m-%d") if customer["created_at"] else None,
        "updated_at": customer["updated_at"].strftime("%Y-%m-%d") if customer["updated_at"] else None,
        "history": out_history
    }

# ---- POST /api/customers/{id}/events : basic validator & accept ----
@app.post("/api/customers/{id}/events")
def record_event(id: int, payload: Dict[str, Any]):
    # Minimal validation; extend per event type
    evt_type = payload.get("type")
    occurred_at = payload.get("occurred_at")  # ISO string expected
    metadata = payload.get("metadata", {})

    if not evt_type or not occurred_at:
        raise HTTPException(400, "Fields 'type' and 'occurred_at' are required")

    # Parse timestamp
    try:
        # Allow 'YYYY-mm-dd' or ISO datetime
        if len(occurred_at) == 10:
            occurred = datetime.strptime(occurred_at, "%Y-%m-%d")
        else:
            # Best effort parse; you can switch to python-dateutil
            occurred = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(400, "Invalid occurred_at format")

    # Note: metadata expectations by event type (not enforced, but supported downstream):
    # login:         {"device": "...", "region": "..."}
    # feature_use:   {"feature": "..."}
    # ticket_opened: {"severity": "low|medium|high"}
    # invoice_paid:  {"days_late": 0, "paid_on_time": true}
    # invoice_late:  {"days_late": N>0, "paid_on_time": false}

    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM customer WHERE id=:id"), {"id": id}
        ).first()
        if not exists:
            raise HTTPException(404, "Customer not found")

        conn.execute(text("""
            INSERT INTO event (customer_id, type, occurred_at, metadata_json, created_at)
            VALUES (:cid, :type, :occurred_at, CAST(:metadata AS JSON), NOW())
        """), {
            "cid": id,
            "type": evt_type,
            "occurred_at": occurred.strftime("%Y-%m-%d %H:%M:%S"),
            "metadata": json.dumps(metadata, ensure_ascii=False),
        })

    return {"status": "stored", "customer_id": id, "type": evt_type}

# ---- (Optional) KPI cards endpoint built from events (fast & simple) ----
@app.get("/api/dashboard/summary")
def dashboard_summary():
    with engine.connect() as conn:
        rows = conn.execute(AGG_NOW_SQL).mappings().all()

    denom = max(1, TARGETS["adoption_denominator"])
    scores: List[int] = []
    tiers = {"Red": 0, "Yellow": 0, "Green": 0}
    improving = 0
    declining = 0
    late_count_30d = 0

    prev_sql = text("""
                    SELECT c.id,
                           COUNT(CASE
                                     WHEN e.type = 'login' AND e.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
                                         AND e.occurred_at < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                                         THEN 1 END)                                                                 AS logins_prev,
                           COUNT(CASE
                                     WHEN e.type = 'ticket_opened' AND
                                          e.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
                                         AND e.occurred_at < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                                         THEN 1 END)                                                                 AS tickets_prev,
                           COUNT(DISTINCT CASE
                                              WHEN e.type = 'feature_use' AND
                                                   e.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
                                                  AND e.occurred_at < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                                                  THEN JSON_UNQUOTE(JSON_EXTRACT(e.metadata_json, '$.feature')) END) AS features_prev,
                           SUBSTRING_INDEX(GROUP_CONCAT(
                                                   CASE
                                                       WHEN e.type = 'invoice_paid'
                                                           AND e.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
                                                           AND e.occurred_at < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                                                           THEN CASE
                                                                    WHEN JSON_EXTRACT(e.metadata_json, '$.paid_on_time') = true
                                                                        THEN 'invoice_paid'
                                                                    WHEN JSON_EXTRACT(e.metadata_json, '$.paid_on_time') = false
                                                                        THEN 'invoice_late'
                                                                    ELSE 'unknown'
                                                           END
                                                       END ORDER BY e.occurred_at DESC
                                           ), ',',
                                           1)                                                                        AS invoice_prev
                    FROM customer c
                             LEFT JOIN event e ON e.customer_id = c.id
                    GROUP BY c.id
                    """)

    prev_map = {}
    with engine.connect() as conn:
        for r in conn.execute(prev_sql).mappings():
            prev_map[r["id"]] = r

    # Recent activity & late invoices flags
    last7_sql = text("""
                     SELECT customer_id,
                            MAX(CASE
                                    WHEN type = 'invoice_paid'
                                        AND JSON_EXTRACT(metadata_json, '$.paid_on_time') = false
                                        AND occurred_at >= NOW() - INTERVAL 30 DAY
                                THEN 1 ELSE 0 END)                                                 AS has_late_30d,
                            MAX(CASE WHEN occurred_at >= NOW() - INTERVAL 7 DAY THEN 1 ELSE 0 END) AS active_7d
                     FROM event
                     GROUP BY customer_id
                     """)
    last7 = {}
    with engine.connect() as conn:
        for r in conn.execute(last7_sql).mappings():
            last7[r["customer_id"]] = r

    for r in rows:
        adoption_rate = min(1.0, (r["distinct_features_60d"] or 0) / denom)
        score_now = compute_health_from_components(
            logins_30d=int(r["logins_30d"] or 0),
            adoption_rate_60d=float(adoption_rate),
            tickets_30d=int(r["tickets_30d"] or 0),
            last_invoice=str(r["last_invoice_type"] or "unknown"),
        )
        scores.append(score_now)
        t = tier(score_now)
        tiers[t] += 1

        if last7.get(r["id"], {}).get("has_late_30d", 0):
            late_count_30d += 1

        prev = prev_map.get(r["id"])
        if prev:
            prev_score = compute_health_from_components(
                logins_30d=int(prev["logins_prev"] or 0),
                adoption_rate_60d=min(1.0, (prev["features_prev"] or 0) / denom),
                tickets_30d=int(prev["tickets_prev"] or 0),
                last_invoice=(prev["invoice_prev"] or "unknown"),
            )
            delta = score_now - prev_score
            if delta >= 10: improving += 1
            if delta <= -10: declining += 1

    total = max(1, len(rows))
    return {
        "total": len(rows),
        "green": tiers["Green"],
        "yellow": tiers["Yellow"],
        "red": tiers["Red"],
        "at_risk_count": tiers["Red"],
        "newly_at_risk_7d": sum(1 for r in rows
                                if tier(compute_health_from_components(
                                      int(r["logins_30d"] or 0),
                                      min(1.0, (r["distinct_features_60d"] or 0) / denom),
                                      int(r["tickets_30d"] or 0),
                                      str(r["last_invoice_type"] or "unknown"),
                                )) == "Red" and last7.get(r["id"], {}).get("active_7d", 0) == 1),
        "improving_30d": improving,
        "declining_30d": declining,
        "pct_late_invoices_30d": round(100.0 * late_count_30d / total, 1),
        "avg_health_score": round(sum(scores) / total, 1) if scores else 0.0,
        "last_refreshed": datetime.utcnow().isoformat() + "Z"
    }
