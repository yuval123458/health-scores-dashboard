import os
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# ---------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------
load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

app = FastAPI(title="Customer Health Score API")

origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if FRONTEND_URL:
    origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
# Constants + Helpers
# ---------------------------------------------------------------------
MAX_HISTORY_DAYS = 90
SEVERITY_W = {"low": 0.25, "medium": 0.50, "high": 0.75, "critical": 1.00}
W = {"E": 0.35, "A": 0.30, "S": 0.20, "F": 0.15}  # combine weights

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def tier(score: int) -> str:
    return "Green" if score >= 80 else ("Yellow" if score >= 60 else "Red")

def _median(xs: List[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    if n == 0: return 0.0
    m = n // 2
    return float(xs[m]) if n % 2 == 1 else (xs[m-1] + xs[m]) / 2.0

def _parse_occurred_at(value) -> datetime:
    if value is None:
        raise HTTPException(400, "Field 'occurred_at' is required")
    s = str(value).strip()
    try:
        if len(s) == 10:  # YYYY-MM-DD
            return datetime.strptime(s, "%Y-%m-%d")
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        raise HTTPException(400, "Invalid 'occurred_at' format")

def compute_window_and_confidence(created_at: Optional[datetime], today: Optional[date] = None
                                  ) -> Tuple[date, int, float]:
    if today is None:
        today = datetime.utcnow().date()
    join_day = (created_at or datetime.utcnow()).date()
    window_start = max(join_day, today - timedelta(days=MAX_HISTORY_DAYS))
    obs_days = max(1, (today - window_start).days)
    s_day = min(1.0, obs_days / float(MAX_HISTORY_DAYS))
    return window_start, obs_days, s_day

def compute_time_normalized_rates(row: Dict[str, Any], effective_days: int) -> Dict[str, Any]:
    denom = max(1, int(effective_days))
    # smoothed late ratio prior
    ALPHA, BETA = 1.0, 3.0
    E_rate_30 = (float(row.get("active_days_total", 0)) / denom) * 30.0
    A_rate_60 = (float(row.get("features_total", 0))     / denom) * 60.0
    S_rate_30 = (float(row.get("tickets_w_total", 0.0))  / denom) * 30.0
    invoices_total = int(row.get("invoices_total", 0) or 0)
    late_count = int(row.get("late_count_total", 0) or 0)
    F_harm = (late_count + ALPHA) / (invoices_total + ALPHA + BETA)
    return {
        "E_rate_30": E_rate_30, "A_rate_60": A_rate_60,
        "S_rate_30": S_rate_30, "F_harm": float(F_harm),
        "invoices_total": invoices_total
    }

def midrank_percentiles(values_by_id: Dict[int, float]) -> Dict[int, float]:
    items = sorted(values_by_id.items(), key=lambda kv: kv[1])
    n = len(items)
    out: Dict[int, float] = {}
    i = 0
    while i < n:
        j = i
        v = items[i][1]
        while j + 1 < n and items[j + 1][1] == v:
            j += 1
        midrank = (i + 1 + j + 1) / 2.0
        p = midrank / (n + 1.0)
        for k in range(i, j + 1):
            out[items[k][0]] = p
        i = j + 1
    return out

def shrink_to_median(p_raw: float, strength: float) -> float:
    s = clamp01(strength)
    return (1.0 - s) * 0.5 + s * float(p_raw)

def compute_percentiles_and_shrink(rows: List[Dict[str, Any]]) -> Dict[int, Dict[str, float]]:
    E_map = {int(r["id"]): float(r["E_rate_30"]) for r in rows}
    A_map = {int(r["id"]): float(r["A_rate_60"]) for r in rows}
    S_map = {int(r["id"]): float(r["S_rate_30"]) for r in rows}
    F_map = {int(r["id"]): float(r["F_harm"])    for r in rows}
    pE_raw = midrank_percentiles(E_map)
    pA_raw = midrank_percentiles(A_map)
    pS_raw = {cid: 1.0 - p for cid, p in midrank_percentiles(S_map).items()}  # harm invert
    pF_raw = {cid: 1.0 - p for cid, p in midrank_percentiles(F_map).items()}  # harm invert
    out: Dict[int, Dict[str, float]] = {}
    for r in rows:
        cid = int(r["id"])
        s_day = float(r["s_day"])
        s_F = min(1.0, float(r.get("invoices_total", 0)) / 3.0)  # trust finance after ~3 invoices
        out[cid] = {
            "pE": shrink_to_median(pE_raw[cid], s_day),
            "pA": shrink_to_median(pA_raw[cid], s_day),
            "pS": shrink_to_median(pS_raw[cid], s_day),
            "pF": shrink_to_median(pF_raw[cid], s_F),
        }
    return out

def combine_score(pE: float, pA: float, pS: float, pF: float) -> int:
    raw = W["E"]*pE + W["A"]*pA + W["S"]*pS + W["F"]*pF
    shifted = 0.30 + 0.70*raw
    return int(round(100 * clamp01(shifted)))

# ---------------------------------------------------------------------
# SQL (keep SQL dumb; aggregate in Python)
# ---------------------------------------------------------------------
CUSTOMERS_SQL = text("""
  SELECT id, name, segment, plan, created_at, updated_at
  FROM customer
  ORDER BY name
""")

LAST_ACTIVITY_SQL = text("""
  SELECT customer_id, MAX(occurred_at) AS last_activity_at
  FROM event
  GROUP BY customer_id
""")

LOGINS_SQL = text("""
  SELECT customer_id, DATE(occurred_at) AS day
  FROM event
  WHERE type='login' AND occurred_at >= :cutoff
""")

FEATURES_SQL = text("""
  SELECT e.customer_id, fe.feature, DATE(e.occurred_at) AS day
  FROM event e
  JOIN feature_event fe ON fe.event_id = e.id
  WHERE e.occurred_at >= :cutoff
""")

TICKETS_SQL = text("""
  SELECT e.customer_id, te.severity, DATE(e.occurred_at) AS day
  FROM event e
  JOIN ticket_opened_event te ON te.event_id = e.id
  WHERE e.occurred_at >= :cutoff
""")

INVOICES_SQL = text("""
  SELECT e.customer_id, ipe.days_late, DATE(e.occurred_at) AS day
  FROM event e
  JOIN invoice_paid_event ipe ON ipe.event_id = e.id
  WHERE e.occurred_at >= :cutoff
""")

# ---------------------------------------------------------------------
# Data shaping helpers (DRY)
# ---------------------------------------------------------------------
def load_population(cutoff_days: int) -> Dict[int, Dict[str, Any]]:
    cutoff_dt = datetime.utcnow() - timedelta(days=cutoff_days)
    with engine.connect() as conn:
        customers = conn.execute(CUSTOMERS_SQL).mappings().all()
        last_act  = {r["customer_id"]: r["last_activity_at"]
                     for r in conn.execute(LAST_ACTIVITY_SQL).mappings()}
        logins   = conn.execute(LOGINS_SQL,   {"cutoff": cutoff_dt}).mappings().all()
        features = conn.execute(FEATURES_SQL, {"cutoff": cutoff_dt}).mappings().all()
        tickets  = conn.execute(TICKETS_SQL,  {"cutoff": cutoff_dt}).mappings().all()
        invoices = conn.execute(INVOICES_SQL, {"cutoff": cutoff_dt}).mappings().all()

    base: Dict[int, Dict[str, Any]] = {}
    for c in customers:
        cid = int(c["id"])
        base[cid] = {
            "id": cid, "name": c["name"], "segment": c["segment"], "plan": c["plan"],
            "created_at": c["created_at"], "updated_at": c["updated_at"],
            "last_activity_at": last_act.get(cid),
            "login_days": set(),
            "feature_days": [],        # (feature, day)
            "ticket_days": [],         # (severity, day)
            "invoice_days": [],        # (days_late, day)
        }
    for r in logins:
        cid = int(r["customer_id"])
        if cid in base and r["day"]:
            base[cid]["login_days"].add(r["day"])
    for r in features:
        cid = int(r["customer_id"])
        if cid in base:
            base[cid]["feature_days"].append((r["feature"], r["day"]))
    for r in tickets:
        cid = int(r["customer_id"])
        if cid in base:
            base[cid]["ticket_days"].append((r["severity"], r["day"]))
    for r in invoices:
        cid = int(r["customer_id"])
        if cid in base:
            base[cid]["invoice_days"].append((int(r["days_late"] or 0), r["day"]))
    return base

def snapshot_rows(base: Dict[int, Dict[str, Any]], today: date, include_raw_sets: bool = False) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for cid, rec in base.items():
        join_day = rec["created_at"].date() if rec["created_at"] else today
        window_start = max(join_day, today - timedelta(days=MAX_HISTORY_DAYS))

        active_days_total = sum(1 for d in rec["login_days"] if d and d >= window_start)
        feat_set = {feat for feat, day in rec["feature_days"] if day and day >= window_start}
        tickets_w_total = sum(
            SEVERITY_W.get((sev or "").lower(), 0.25)
            for sev, day in rec["ticket_days"] if day and day >= window_start
        )
        invoices_total = 0
        late_count_total = 0
        for dl, day in rec["invoice_days"]:
            if day and day >= window_start:
                invoices_total += 1
                if (dl or 0) > 0:
                    late_count_total += 1

        row: Dict[str, Any] = {
            "id": cid, "name": rec["name"], "segment": rec["segment"], "plan": rec["plan"],
            "created_at": rec["created_at"], "updated_at": rec["updated_at"],
            "last_activity_at": rec["last_activity_at"],
            "window_start": window_start,
            "active_days_total": active_days_total,
            "features_total": len(feat_set),
            "tickets_w_total": tickets_w_total,
            "invoices_total": invoices_total,
            "late_count_total": late_count_total,
        }
        if include_raw_sets:
            row.update({
                "login_days": rec["login_days"],
                "feature_days": rec["feature_days"],
                "ticket_days": rec["ticket_days"],
                "invoice_days": rec["invoice_days"],
            })
        rows.append(row)
    return rows

def enrich_rows(rows: List[Dict[str, Any]], today: date) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for r in rows:
        _, obs_days, s_day = compute_window_and_confidence(r["created_at"], today)
        rates = compute_time_normalized_rates(r, obs_days)
        enriched.append({**r, "obs_days": obs_days, "s_day": s_day, **rates})
    return enriched

def score_population(enriched: List[Dict[str, Any]]):
    P = compute_percentiles_and_shrink(enriched)
    scored: List[Dict[str, Any]] = []
    for r in enriched:
        cid = int(r["id"]); p = P[cid]
        score = combine_score(p["pE"], p["pA"], p["pS"], p["pF"])
        scored.append({**r, "score": score, "tier": tier(score), "p": p})
    return scored, P

def recent_prior_changes_for_customer(base: Dict[int, Dict[str, Any]], id: int, today: date) -> Dict[str, Any]:
    # simple recent vs prior windows
    r30 = today - timedelta(days=30)
    p30s, p30e = today - timedelta(days=60), today - timedelta(days=30)
    r60 = today - timedelta(days=60)
    p60s, p60e = today - timedelta(days=120), today - timedelta(days=60)
    r90 = today - timedelta(days=90)
    p90s, p90e = today - timedelta(days=180), today - timedelta(days=90)

    rec = base[id]
    join = rec["created_at"].date() if rec["created_at"] else today

    # helper: effective window length respecting join date
    def eff_len(start: date, end: date) -> int:
        return max(1, (min(today, end) - max(start, join)).days)

    # engagement (distinct login days) per 30d
    e_recent_cnt = sum(1 for d in rec["login_days"] if d and d >= r30)
    e_prior_cnt  = sum(1 for d in rec["login_days"] if d and p30s <= d < p30e)
    e_recent = (e_recent_cnt / eff_len(r30, today)) * 30.0
    e_prior  = (e_prior_cnt  / eff_len(p30s, p30e)) * 30.0

    # adoption (distinct features) per 60d
    a_recent_set = {f for (f, day) in rec["feature_days"] if day and day >= r60}
    a_prior_set  = {f for (f, day) in rec["feature_days"] if day and p60s <= day < p60e}
    a_recent = (len(a_recent_set) / eff_len(r60, today)) * 60.0
    a_prior  = (len(a_prior_set)  / eff_len(p60s, p60e)) * 60.0

    # support (weighted tickets) per 30d
    s_recent_cnt = sum(SEVERITY_W.get((sev or "").lower(), 0.25)
                       for (sev, day) in rec["ticket_days"] if day and day >= r30)
    s_prior_cnt  = sum(SEVERITY_W.get((sev or "").lower(), 0.25)
                       for (sev, day) in rec["ticket_days"] if day and p30s <= day < p30e)
    s_recent = (s_recent_cnt / eff_len(r30, today)) * 30.0
    s_prior  = (s_prior_cnt  / eff_len(p30s, p30e)) * 30.0

    # finance late ratio recent/prior (90d windows)
    inv_r = [(dl, day) for (dl, day) in rec["invoice_days"] if day and day >= r90]
    inv_p = [(dl, day) for (dl, day) in rec["invoice_days"] if day and p90s <= day < p90e]
    def late_ratio(lst):
        total = len(lst)
        late = sum(1 for (dl, _d) in lst if (dl or 0) > 0)
        # small smoothing to avoid 0/0
        return (late + 1.0) / (total + 4.0)
    f_recent = late_ratio(inv_r)
    f_prior  = late_ratio(inv_p)

    return {
        "engagement_per_30d": {"recent": round(e_recent, 3), "prior": round(e_prior, 3), "delta": round(e_recent - e_prior, 3)},
        "adoption_per_60d":   {"recent": round(a_recent, 3), "prior": round(a_prior, 3), "delta": round(a_recent - a_prior, 3)},
        "support_per_30d":    {"recent": round(s_recent, 3), "prior": round(s_prior, 3), "delta": round(s_recent - s_prior, 3)},
        "late_ratio_90d":     {"recent": round(f_recent, 3),  "prior": round(f_prior, 3),  "delta": round(f_recent - f_prior, 3)},
    }

# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------

# === Minimal customers list: ONLY health info needed for table ===
@app.get("/api/customers")
def list_customers():
    today = datetime.utcnow().date()
    base = load_population(MAX_HISTORY_DAYS)
    rows = snapshot_rows(base, today)
    enriched = enrich_rows(rows, today)
    scored, _ = score_population(enriched)
    return [{
        "id": s["id"],
        "name": s["name"],
        "segment": s["segment"],  
        "plan": s["plan"],          
        "health_score": s["score"],
        "health_tier": s["tier"],
        "last_activity_at": (
            s["last_activity_at"].strftime("%Y-%m-%d")
            if s["last_activity_at"] else None
        ),
    } for s in scored]

# === Summary for Cards component (exact fields you use) ===
@app.get("/api/dashboard/summary")
def dashboard_cards():
    today = datetime.utcnow().date()
    base = load_population(120)  # grab enough window for legacy peeks & late flags
    rows = snapshot_rows(base, today, include_raw_sets=True)
    enriched = enrich_rows(rows, today)
    scored, _ = score_population(enriched)

    total = max(1, len(scored))
    counts = {"Green": 0, "Yellow": 0, "Red": 0}
    for s in scored:
        counts[s["tier"]] += 1
    avg_score = round(sum(s["score"] for s in scored) / total, 1)

    thirty = today - timedelta(days=30)
    sixty  = today - timedelta(days=60)

    def _legacy_counts(s):
        logins_30d  = sum(1 for d in s["login_days"] if d and d >= thirty)
        feats_60d   = {f for (f, day) in s["feature_days"] if day and day >= sixty}
        tickets_30d = sum(1 for (_sev, day) in s["ticket_days"] if day and day >= thirty)
        return logins_30d, len(feats_60d), tickets_30d

    late_30_flags = [1 if any((dl or 0) > 0 and (day and day >= thirty)
                              for dl, day in s.get("invoice_days", [])) else 0
                     for s in scored]
    leg = [_legacy_counts(s) for s in scored]
    avg_logins_30d  = round(sum(x[0] for x in leg) / len(leg), 2) if leg else 0.0
    avg_feats_60d   = round(sum(x[1] for x in leg) / len(leg), 2) if leg else 0.0
    avg_tickets_30d = round(sum(x[2] for x in leg) / len(leg), 2) if leg else 0.0

    E_med = _median([s["E_rate_30"] for s in scored])
    A_med = _median([s["A_rate_60"] for s in scored])
    S_med = _median([s["S_rate_30"] for s in scored])
    F_med = _median([s["F_harm"]    for s in scored])

    return {
        "summary": {
            "total": len(scored),
            "green": counts["Green"], "yellow": counts["Yellow"], "red": counts["Red"],
            "avg_health_score": avg_score,
            "pct_late_invoices_30d": round(100.0 * sum(late_30_flags) / total, 1),
            "last_refreshed": datetime.utcnow().isoformat() + "Z",
        },
        "benchmarks": {
            "median_E_per_30d": round(E_med, 3),
            "median_A_per_60d": round(A_med, 3),
            "median_S_per_30d": round(S_med, 3),
            "median_F_harm":    round(F_med, 3),
        },
        "legacy_peek": {
            "avg_logins_30d": avg_logins_30d,
            "avg_adoption_distinct_features_60d": avg_feats_60d,
            "avg_tickets_30d": avg_tickets_30d,
        },
    }

@app.get("/api/customers/{id}/health")
def customer_health_detail(id: int):
    today = datetime.utcnow().date()
    base = load_population(365 * 5)  # use full history
    if id not in base:
        raise HTTPException(404, "Customer not found")

    rec = base[id]

    # ----- current 90d health (kept so table/summary stays consistent) -----
    base90 = load_population(MAX_HISTORY_DAYS)
    rows = snapshot_rows(base90, today)
    enriched = enrich_rows(rows, today)
    scored, _ = score_population(enriched)
    me = next((s for s in scored if int(s["id"]) == int(id)), None)
    health_score = me["score"] if me else 50
    health_tier_ = me["tier"] if me else tier(health_score)

    # ----- totals over entire history (small overview) -----
    total_logins_days = len(rec["login_days"])
    distinct_features_total = len({f for (f, _d) in rec["feature_days"]})
    tickets_weighted_total = sum(SEVERITY_W.get((sev or "").lower(), 0.25) for (sev, _d) in rec["ticket_days"])
    invoices_total = len(rec["invoice_days"])
    late_invoices_total = sum(1 for (dl, _d) in rec["invoice_days"] if (dl or 0) > 0)

    # ----- monthly series (this is what your chart needs) -----
    def first_of_month(d: date) -> date:
        return date(d.year, d.month, 1)

    def add_month(d: date) -> date:
        return date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)

    # determine month range from first activity or created_at to today
    all_days: List[date] = []
    all_days.extend(list(rec["login_days"]))
    all_days.extend([d for (_f, d) in rec["feature_days"]])
    all_days.extend([d for (_s, d) in rec["ticket_days"]])
    all_days.extend([d for (_dl, d) in rec["invoice_days"]])

    start_day = (rec["created_at"].date() if rec["created_at"] else today)
    if all_days:
        start_day = min(start_day, min(all_days))

    start_m = first_of_month(start_day)
    end_m = first_of_month(today)

    # generate month keys
    months: List[str] = []
    cur = start_m
    guard = 0
    while cur <= end_m and guard < 600:  # safety cap ~50 years
        months.append(cur.strftime("%Y-%m"))
        cur = add_month(cur)
        guard += 1

    # prep buckets
    logins_by = {m: 0 for m in months}                  # distinct login days per month
    feats_by = {m: set() for m in months}               # distinct features used per month
    tickets_by = {m: 0.0 for m in months}               # weighted tickets per month
    invoices_by = {m: 0 for m in months}                # invoices per month
    late_invoices_by = {m: 0 for m in months}           # late invoices per month

    for d in rec["login_days"]:
        if d:
            k = first_of_month(d).strftime("%Y-%m")
            if k in logins_by: logins_by[k] += 1

    for f, d in rec["feature_days"]:
        if d:
            k = first_of_month(d).strftime("%Y-%m")
            if k in feats_by: feats_by[k].add(f)

    for sev, d in rec["ticket_days"]:
        if d:
            k = first_of_month(d).strftime("%Y-%m")
            if k in tickets_by:
                tickets_by[k] += SEVERITY_W.get((sev or "").lower(), 0.25)

    for dl, d in rec["invoice_days"]:
        if d:
            k = first_of_month(d).strftime("%Y-%m")
            if k in invoices_by:
                invoices_by[k] += 1
                if (dl or 0) > 0:
                    late_invoices_by[k] += 1

    series = {
        "logins":           [{"month": m, "value": logins_by[m]} for m in months],
        "features":         [{"month": m, "value": len(feats_by[m])} for m in months],
        "tickets_weighted": [{"month": m, "value": round(tickets_by[m], 3)} for m in months],
        "invoices":         [{"month": m, "value": invoices_by[m]} for m in months],
        "late_invoices":    [{"month": m, "value": late_invoices_by[m]} for m in months],
    }

    return {
        "id": id,
        "name": rec["name"],
        "created_at": rec["created_at"].strftime("%Y-%m-%d") if rec["created_at"] else None,
        "last_activity_at": rec["last_activity_at"].strftime("%Y-%m-%d") if rec["last_activity_at"] else None,
        "health_score": health_score,
        "health_tier": health_tier_,
        "totals_all_time": {
            "login_days": total_logins_days,
            "distinct_features": distinct_features_total,
            "tickets_weighted": round(tickets_weighted_total, 3),
            "invoices_total": invoices_total,
            "late_invoices_total": late_invoices_total,
        },
        # keep your short recent/prior block if you still use it elsewhere
        # "recent_vs_prior": recent_prior_changes_for_customer(base, id, today),
        "series": series,
    }


@app.post("/api/customers/{id}/events")
def record_event(id: int, payload: Dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid JSON body")

    evt_type = (payload.get("type") or "").strip()
    if evt_type not in {"login", "feature_use", "ticket_opened", "invoice_paid"}:
        raise HTTPException(400, "Field 'type' must be one of: login|feature_use|ticket_opened|invoice_paid")

    occurred_dt = _parse_occurred_at(payload.get("occurred_at"))
    occurred_at_sql = occurred_dt.strftime("%Y-%m-%d %H:%M:%S")
    meta = payload.get("metadata") or {}

    with engine.begin() as conn:
        exists = conn.execute(text("SELECT 1 FROM customer WHERE id=:id"), {"id": id}).scalar()
        if not exists:
            raise HTTPException(404, "Customer not found")

        # base event
        res = conn.execute(
            text("INSERT INTO event (customer_id, type, occurred_at, created_at) VALUES (:cid, :t, :ts, NOW())"),
            {"cid": id, "t": evt_type, "ts": occurred_at_sql}
        )
        event_id = int(getattr(res, "lastrowid", 0) or 0)

        # child row (minimal validation)
        if evt_type == "login":
            device = (meta.get("device") or "").strip()
            region = (meta.get("region") or "").strip()
            conn.execute(
                text("INSERT INTO login_event (event_id, device, region) VALUES (:eid, :d, :r)"),
                {"eid": event_id, "d": device, "r": region}
            )
        elif evt_type == "feature_use":
            feature = (meta.get("feature") or "").strip()
            conn.execute(
                text("INSERT INTO feature_event (event_id, feature) VALUES (:eid, :f)"),
                {"eid": event_id, "f": feature}
            )
        elif evt_type == "ticket_opened":
            sev = (meta.get("severity") or "low").lower().strip()
            feature = meta.get("feature")
            conn.execute(
                text("INSERT INTO ticket_opened_event (event_id, severity, feature) VALUES (:eid, :s, :f)"),
                {"eid": event_id, "s": sev, "f": feature}
            )
        elif evt_type == "invoice_paid":
            days_late = int(meta.get("days_late", 0) or 0)
            conn.execute(
                text("INSERT INTO invoice_paid_event (event_id, days_late) VALUES (:eid, :dl)"),
                {"eid": event_id, "dl": max(0, days_late)}
            )

    return {
        "status": "stored",
        "customer_id": id,
        "event_id": event_id,
        "type": evt_type,
        "occurred_at": occurred_at_sql,
    }
