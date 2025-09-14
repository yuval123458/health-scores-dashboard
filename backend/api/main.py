
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
app = FastAPI(title="customer health score API", version="0.1.0")

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

@app.on_event("startup")
def test_db_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        import sys
        print("Database connection failed:", e)
        sys.exit(1)

@app.get("/api/customers")
def list_customers():
    sql = text("""
        SELECT c.id, c.external_id, c.name, c.segment, c.plan, c.created_at, c.updated_at,
               m.month, m.login_count, m.feature_adoption, m.nps_score,
               m.support_tickets, m.payment_status, m.health_tier
        FROM customers c
        JOIN (
            SELECT customer_id, MAX(month) max_month
            FROM customer_monthly_metrics
            GROUP BY customer_id
        ) lm ON lm.customer_id = c.id
        JOIN customer_monthly_metrics m
          ON m.customer_id = c.id AND m.month = lm.max_month
        ORDER BY c.name
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    out = []
    for r in rows:
        score = compute_health(r, r["segment"])
        out.append({
            "id": r["id"],
            "external_id": r["external_id"],
            "name": r["name"],
            "segment": r["segment"],
            "plan": r["plan"],
            "created_at": r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else None,
            "updated_at": r["updated_at"].strftime("%Y-%m-%d") if r["updated_at"] else None,
            "month": r["month"],
            "health_score": score,
            "health_tier": tier(score),
            "metrics": {
                "month": r["month"],
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
        customer = conn.execute(
            text("SELECT id, external_id, name, segment, plan, created_at, updated_at FROM customers WHERE id=:id"),
            {"id": id}
        ).mappings().first()
        if not customer:
            raise HTTPException(404, "Customer not found")
        history = conn.execute(text("""
            SELECT month, login_count, feature_adoption, nps_score,
                   support_tickets, payment_status, health_tier
            FROM customer_monthly_metrics
            WHERE customer_id=:id
            ORDER BY month DESC
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
            "external_id": customer["external_id"],
            "name": customer["name"],
            "segment": customer["segment"],
            "plan": customer["plan"],
            "created_at": customer["created_at"].strftime("%Y-%m-%d") if customer["created_at"] else None,
            "updated_at": customer["updated_at"].strftime("%Y-%m-%d") if customer["updated_at"] else None,
            "month": h["month"].strftime("%Y-%m-%d") if h["month"] else None,
            "health_score": score,
            "health_tier": tier(score),
            "metrics": {
                "month": h["month"].strftime("%Y-%m-%d") if h["month"] else None,
                "login_count": h["login_count"],
                "feature_adoption": h["feature_adoption"],
                "nps_score": h["nps_score"],
                "support_tickets": h["support_tickets"],
                "payment_status": h["payment_status"],
                "health_tier": h["health_tier"],
            }
        })
    return {
        "id": customer["id"],
        "external_id": customer["external_id"],
        "name": customer["name"],
        "segment": customer["segment"],
        "plan": customer["plan"],
        "created_at": customer["created_at"].strftime("%Y-%m-%d") if customer["created_at"] else None,
        "updated_at": customer["updated_at"].strftime("%Y-%m-%d") if customer["updated_at"] else None,
        "history": out
    }

@app.post("/api/customers/{id}/events")
def record_event_stub(id: int, payload: dict):
    with engine.connect() as conn:
        if not conn.execute(text("SELECT 1 FROM customers WHERE id=:id"), {"id": id}).first():
            raise HTTPException(404, "Customer not found")
    return {"status": "accepted", "stored": False, "customer_id": id, "received": payload}
