from datetime import datetime, timedelta, date
from fastapi.testclient import TestClient
import importlib
import re

main = importlib.import_module("backend.api.main")

class FakeResult:
    def __init__(self, rows=None, lastrowid=None):
        self._rows = rows or []
        self.lastrowid = lastrowid

    def mappings(self):
        return self
    def all(self):
        return list(self._rows)
    def first(self):
        return self._rows[0] if self._rows else None
    def scalar(self):
        if not self._rows:
            return None
        row = self._rows[0]
        if isinstance(row, dict):
            return next(iter(row.values()))
        return row

class FakeConn:
    def __init__(self, ds):
        self.ds = ds

    def __enter__(self): return self
    def __exit__(self, *exc): return False

    def execute(self, stmt, params=None):
        sql = str(stmt)

        if "FROM customer" in sql and "ORDER BY name" in sql:
            return FakeResult(self.ds["customers"])

        if "MAX(occurred_at) AS last_activity_at" in sql:
            return FakeResult(self.ds["last_activity"])

        # events by type / joins
        if "WHERE type='login'" in sql:
            return FakeResult(self.ds["logins"])
        if "JOIN feature_event" in sql:
            return FakeResult(self.ds["features"])
        if "JOIN ticket_opened_event" in sql:
            return FakeResult(self.ds["tickets"])
        if "JOIN invoice_paid_event" in sql:
            return FakeResult(self.ds["invoices"])

        # existence check used in POST
        if "SELECT 1 FROM customer WHERE id" in sql:
            cid = params.get("id")
            exists = any(c["id"] == cid for c in self.ds["customers"])
            return FakeResult([{"one": 1}] if exists else [])

        # inserts: base event + child tables
        if re.search(r"\bINSERT\s+INTO\s+event\b", sql, re.I):
            return FakeResult(lastrowid=101)
        if re.search(r"\bINSERT\s+INTO\s+(login_event|feature_event|ticket_opened_event|invoice_paid_event)\b", sql, re.I):
            return FakeResult(lastrowid=None)

        return FakeResult([])

class FakeBegin(FakeConn):
    pass

class FakeEngine:
    def __init__(self, ds): self.ds = ds
    def connect(self): return FakeConn(self.ds)
    def begin(self):   return FakeBegin(self.ds)

def make_dataset():
    today = datetime.utcnow().date()
    def d(days): return today - timedelta(days=days)

    # customers table rows
    customers = [
        {"id": 1, "name": "Acme A",   "segment": "startup",    "plan": "pro",
         "created_at": datetime(today.year, today.month, 1), "updated_at": datetime.utcnow()},
        {"id": 2, "name": "Beacon B", "segment": "enterprise", "plan": "enterprise",
         "created_at": datetime(today.year, today.month, 1) - timedelta(days=60), "updated_at": datetime.utcnow()},
        {"id": 3, "name": "Crimson C","segment": "smb",        "plan": "basic",
         "created_at": datetime(today.year, today.month, 1) - timedelta(days=120), "updated_at": datetime.utcnow()},
    ]

    # last activity
    last_activity = [
        {"customer_id": 1, "last_activity_at": datetime.utcnow() - timedelta(days=1)},
        {"customer_id": 2, "last_activity_at": datetime.utcnow() - timedelta(days=3)},
        {"customer_id": 3, "last_activity_at": datetime.utcnow() - timedelta(days=7)},
    ]

    # login days within 90d window
    logins = []
    for k in range(15): logins.append({"customer_id": 1, "day": d(k*2)})
    for k in range(7):  logins.append({"customer_id": 2, "day": d(k*4)})
    for k in range(2):  logins.append({"customer_id": 3, "day": d(10 + k*15)})

    # feature use (distinct features)
    features = [
        {"customer_id": 1, "feature": "dashboards", "day": d(5)},
        {"customer_id": 1, "feature": "reports",    "day": d(8)},
        {"customer_id": 1, "feature": "export",     "day": d(12)},
        {"customer_id": 2, "feature": "dashboards", "day": d(20)},
        {"customer_id": 3, "feature": "dashboards", "day": d(70)},
    ]

    # tickets (weighted)
    tickets = [
        {"customer_id": 1, "severity": "low",      "day": d(6)},
        {"customer_id": 2, "severity": "high",     "day": d(14)},
        {"customer_id": 2, "severity": "medium",   "day": d(40)},
        {"customer_id": 3, "severity": "critical", "day": d(30)},
        {"customer_id": 3, "severity": "high",     "day": d(55)},
    ]

    # invoices with lateness
    invoices = [
        {"customer_id": 1, "days_late": 0,  "day": d(20)},
        {"customer_id": 1, "days_late": 2,  "day": d(50)},
        {"customer_id": 2, "days_late": 0,  "day": d(25)},
        {"customer_id": 3, "days_late": 10, "day": d(15)},
    ]

    return {
        "customers": customers,
        "last_activity": last_activity,
        "logins": logins,
        "features": features,
        "tickets": tickets,
        "invoices": invoices,
    }

def patch_engine(monkeypatch):
    ds = make_dataset()
    monkeypatch.setattr(main, "engine", FakeEngine(ds))
    return ds

# ---------- tests ----------
def test_get_customers_minimal_contract(monkeypatch):
    patch_engine(monkeypatch)
    client = TestClient(main.app)

    r = client.get("/api/customers")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list) and len(items) == 3

    # minimal renewed shape
    required = {"id","name","segment","plan","health_score","health_tier"}
    assert required.issubset(items[0].keys())

    # bounds + tier coherency
    for it in items:
        s = it["health_score"]
        assert 0 <= s <= 100
        t = it["health_tier"]
        assert t in {"Green","Yellow","Red"}
    scores_by_tier = {it["health_tier"]: it["health_score"] for it in items}
    assert max(scores_by_tier.get("Green",0), 0) >= scores_by_tier.get("Yellow",0)

def test_customer_health_detail_compact(monkeypatch):
    patch_engine(monkeypatch)
    client = TestClient(main.app)

    r = client.get("/api/customers/1/health")
    assert r.status_code == 200
    js = r.json()

    for k in ["id","name","created_at","last_activity_at","health_score","health_tier","totals_all_time","recent_vs_prior"]:
        assert k in js

    ta = js["totals_all_time"]
    for k in ["login_days","distinct_features","tickets_weighted","invoices_total","late_invoices_total"]:
        assert k in ta

    rp = js["recent_vs_prior"]
    for k in ["engagement_per_30d","adoption_per_60d","support_per_30d","late_ratio_90d"]:
        assert k in rp
        sub = rp[k]
        for kk in ["recent","prior","delta"]:
            assert kk in sub

def test_post_event_insert_path(monkeypatch):
    patch_engine(monkeypatch)
    client = TestClient(main.app)

    payload = {
        "type": "login",
        "occurred_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "metadata": {"device": "mac", "region": "eu-west"},
    }
    r = client.post("/api/customers/1/events", json=payload)
    assert r.status_code == 200
    js = r.json()
    assert js["status"] == "stored"
    assert js["customer_id"] == 1
    assert js["type"] == "login"
    # lastrowid was faked as 101
    assert js["event_id"] == 101

def test_dashboard_summary_nested_contract(monkeypatch):
    patch_engine(monkeypatch)
    client = TestClient(main.app)

    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    js = r.json()

    assert "summary" in js and "benchmarks" in js and "legacy_peek" in js

    s = js["summary"]
    for k in ["total","green","yellow","red","avg_health_score","pct_late_invoices_30d","last_refreshed"]:
        assert k in s
    assert s["total"] == s["green"] + s["yellow"] + s["red"]
    assert 0 <= s["avg_health_score"] <= 100
    assert 0.0 <= s["pct_late_invoices_30d"] <= 100.0
