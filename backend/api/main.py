import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv


load_dotenv(override=True)

# -- config --
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
app = FastAPI(title="customer health score API", version="0.1.0")

def compute_health(row, segment):
    feat = max(0, min(100, int(row["feature_adoption"])))
    nps_pct = max(0, min(100, int(row["nps_score"]) * 10))
    cap = 300 if segment == "Enterprise" else (150 if segment == "SMB" else 120)
    login_pct = max(0.0, min(1.0, (int(row["login_count"]) / cap))) * 100.0
    tickets_penalty = min(20, max(0, int(row["support_tickets"])) * 5)
    pay = row["payment_status"]
    payment_penalty = 10 if pay == "Late" else (25 if pay == "Delinquent" else 0)
    score = (0.40 * feat) + (0.25 * nps_pct) + (0.25 * login_pct) - tickets_penalty - payment_penalty
    score = int(max(0, min(100, round(score))))
    return score

def tier(score): return "Green" if score >= 70 else ("Yellow" if score >= 50 else "Red")

@app.get("/api/customers")
def list_customers():
    sql = text("""
        SELECT c.id, c.name, c.segment,
               m.month_date, m.login_count, m.feature_adoption, m.nps_score,
               m.support_tickets, m.payment_status, m.health_tier
        FROM customers c
        JOIN (SELECT customer_id, MAX(month_date) max_month FROM monthly_metrics GROUP BY customer_id) lm
          ON lm.customer_id = c.id
        JOIN monthly_metrics m
          ON m.customer_id = c.id AND m.month_date = lm.max_month
        ORDER BY c.name
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    out = []
    for r in rows:
        score = compute_health(r, r["segment"])
        out.append({
            "id": r["id"],
            "name": r["name"],
            "segment": r["segment"],
            "month_date": r["month_date"].strftime("%Y-%m-%d"),
            "health_score": score,
            "health_tier": tier(score),
            "metrics": {
                "month_date": r["month_date"].strftime("%Y-%m-%d"),
                "login_count": r["login_count"],
                "feature_adoption": r["feature_adoption"],
                "nps_score": r["nps_score"],
                "support_tickets": r["support_tickets"],
                "payment_status": r["payment_status"],
                "health_tier": r["health_tier"],
            }
        })
    return out

@app.get("/api/customers/{id}/health")
def customer_health_detail(id: int):
    with engine.connect() as conn:
        customer = conn.execute(text("SELECT id, name, segment FROM customers WHERE id=:id"), {"id": id}).mappings().first()
        if not customer:
            raise HTTPException(404, "Customer not found")
        history = conn.execute(text("""
            SELECT month_date, login_count, feature_adoption, nps_score,
                   support_tickets, payment_status, health_tier
            FROM monthly_metrics
            WHERE customer_id=:id
            ORDER BY month_date DESC
        """), {"id": id}).mappings().all()

    if not history:
        raise HTTPException(404, "No metrics for this customer")

    out = []
    for h in history:
        row = {
            "feature_adoption": h["feature_adoption"],
            "nps_score": h["nps_score"],
            "login_count": h["login_count"],
            "support_tickets": h["support_tickets"],
            "payment_status": h["payment_status"],
        }
        score = compute_health(row, customer["segment"])
        out.append({
            "id": customer["id"],
            "name": customer["name"],
            "segment": customer["segment"],
            "month_date": h["month_date"].strftime("%Y-%m-%d"),
            "health_score": score,
            "health_tier": tier(score),
            "metrics": {
                "month_date": h["month_date"].strftime("%Y-%m-%d"),
                "login_count": h["login_count"],
                "feature_adoption": h["feature_adoption"],
                "nps_score": h["nps_score"],
                "support_tickets": h["support_tickets"],
                "payment_status": h["payment_status"],
                "health_tier": h["health_tier"],
            }
        })
    return {"id": customer["id"], "name": customer["name"], "segment": customer["segment"], "history": out}

@app.post("/api/customers/{id}/events")
def record_event_stub(id: int, payload: dict):
    # Just validate customer exists and echo back; not stored yet
    with engine.connect() as conn:
        if not conn.execute(text("SELECT 1 FROM customers WHERE id=:id"), {"id": id}).first():
            raise HTTPException(404, "Customer not found")
    # (you could check 'type' in payload here)
    return {"status": "accepted", "stored": False, "customer_id": id, "received": payload}

