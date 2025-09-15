from datetime import datetime, timedelta
from fastapi.testclient import TestClient
import re
import importlib

# Import the FastAPI app module
main = importlib.import_module("backend.api.main")

# ---------- Fake layer ----------
class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class FakeConn:
    def __init__(self, dataset):
        self.dataset = dataset  # dict of query_name -> rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        sql = str(stmt)

        # /api/customers aggregation query
        if "Per-customer current-window metrics" in sql:
            return FakeResult(self.dataset["agg_now"])

        # /api/customers/{id}/health: load the customer by id
        if "FROM customer WHERE id" in sql:
            cid = params["id"]
            rows = [r for r in self.dataset["customers"] if r["id"] == cid]
            return FakeResult(rows)

        # monthly history query
        if "GROUP BY mw.month_start" in sql and "feature_adoption" in sql:
            return FakeResult(self.dataset["history"])

        # prev_sql in dashboard
        if "COUNT(CASE" in sql and "features_prev" in sql:
            return FakeResult(self.dataset["prev"])

        # last7_sql in dashboard
        if "MAX(CASE" in sql and "active_7d" in sql:
            return FakeResult(self.dataset["last7"])

        # default: empty
        return FakeResult([])


class FakeBegin(FakeConn):
    pass


class FakeEngine:
    def __init__(self, dataset):
        self.dataset = dataset

    def connect(self):
        return FakeConn(self.dataset)

    def begin(self):
        return FakeBegin(self.dataset)


# ---------- Test fixtures / dataset ----------
def make_dataset():
    now = datetime.utcnow()
    d = []

    base = dict(
        segment="smb",
        plan="standard",
        created_at=now - timedelta(days=120),
        updated_at=now - timedelta(days=1),
        last_activity_at=now - timedelta(days=2),
    )

    # GREEN
    d.append({
        "id": 1, "name": "Acorn Inc", **base,
        "logins_30d": 22, "distinct_features_60d": 5, "tickets_30d": 0,
        "last_invoice_type": "invoice_paid", "last_paid_on_time": 1, "last_days_late": 0,
    })
    # YELLOW
    d.append({
        "id": 2, "name": "Beacon LLC", **base,
        "logins_30d": 10, "distinct_features_60d": 2, "tickets_30d": 3,
        "last_invoice_type": "invoice_paid", "last_paid_on_time": None, "last_days_late": None,
    })
    # RED
    d.append({
        "id": 3, "name": "Crimson Co", **base,
        "logins_30d": 2, "distinct_features_60d": 0, "tickets_30d": 8,
        "last_invoice_type": "invoice_late", "last_paid_on_time": 0, "last_days_late": 14,
    })

    dataset = {
        "agg_now": d,       # for /api/customers + dashboard
        "customers": d,     # for SELECT ... WHERE id=:id
        "history": [        # for /api/customers/{id}/health
            {"month": (now.replace(day=1)).strftime("%Y-%m"),
             "login_count": 8, "feature_adoption": 2, "support_tickets": 1, "payment_status": "invoice_paid"},
            {"month": (now.replace(day=1) - timedelta(days=31)).strftime("%Y-%m"),
             "login_count": 6, "feature_adoption": 1, "support_tickets": 2, "payment_status": "invoice_paid"},
            {"month": (now.replace(day=1) - timedelta(days=62)).strftime("%Y-%m"),
             "login_count": 3, "feature_adoption": 1, "support_tickets": 2, "payment_status": "invoice_late"},
        ],
        "prev": [
            {"id": 1, "logins_prev": 18, "tickets_prev": 1, "features_prev": 4, "invoice_prev": "invoice_paid"},
            {"id": 2, "logins_prev": 12, "tickets_prev": 2, "features_prev": 2, "invoice_prev": "invoice_paid"},
            {"id": 3, "logins_prev": 4,  "tickets_prev": 6, "features_prev": 0, "invoice_prev": "invoice_late"},
        ],
        "last7": [
            {"customer_id": 1, "has_late_30d": 0, "active_7d": 1},
            {"customer_id": 2, "has_late_30d": 0, "active_7d": 1},
            {"customer_id": 3, "has_late_30d": 1, "active_7d": 1},
        ],
    }
    return dataset


def patch_engine(monkeypatch):
    dataset = make_dataset()
    fake_engine = FakeEngine(dataset)
    monkeypatch.setattr(main, "engine", fake_engine)
    return dataset


# ---------- Tests ----------
def test_get_customers_contract(monkeypatch):
    patch_engine(monkeypatch)
    client = TestClient(main.app)

    r = client.get("/api/customers")
    assert r.status_code == 200
    js = r.json()
    assert isinstance(js, list) and len(js) == 3

    item = js[0]
    for k in ["id", "name", "segment", "plan", "health_score", "health_tier"]:
        assert k in item
    m = item["metrics"]
    for k in [
        "logins_30d", "adoption_distinct_features_60d",
        "adoption_rate_60d", "tickets_30d", "last_invoice",
        "last_activity_at",
    ]:
        assert k in m

    tiers = {c["health_tier"] for c in js}
    assert {"Green", "Yellow", "Red"} & tiers


def test_customer_health_detail(monkeypatch):
    patch_engine(monkeypatch)
    client = TestClient(main.app)

    r = client.get("/api/customers/1/health")
    assert r.status_code == 200
    js = r.json()
    assert js["id"] == 1
    assert "history" in js and len(js["history"]) >= 3

    row = js["history"][0]
    for k in ["month", "health_score", "health_tier", "metrics"]:
        assert k in row
    for k in ["login_count", "feature_adoption", "support_tickets", "payment_status"]:
        assert k in row["metrics"]


def test_post_event_insert_path(monkeypatch):
    # capture INSERT parameters
    captured = {"inserts": []}

    class CaptureConn(FakeBegin):
        def execute(self, stmt, params=None):
            sql = str(stmt)
            # capture only INSERT INTO event; delegate all SELECTs to parent
            if re.search(r"\bINSERT\s+INTO\s+event\b", sql, re.I):
                captured["inserts"].append(params)
                return FakeResult([])
            return super().execute(stmt, params)

    class CaptureEngine(FakeEngine):
        def begin(self):
            return CaptureConn(self.dataset)

    # patch the engine used by the app
    dataset = make_dataset()
    cap_engine = CaptureEngine(dataset)
    monkeypatch.setattr(main, "engine", cap_engine)

    client = TestClient(main.app)

    payload = {
        "type": "login",
        "occurred_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "metadata": {"device": "mac", "region": "eu-west"},
    }

    r = client.post("/api/customers/1/events", json=payload)
    assert r.status_code == 200, r.text

    # ensure we actually captured an INSERT
    assert captured["inserts"], "expected an INSERT capture"
    params = captured["inserts"][0]
    assert params["cid"] == 1
    assert params["type"] == "login"


def test_dashboard_summary_contract(monkeypatch):
    patch_engine(monkeypatch)
    client = TestClient(main.app)

    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    js = r.json()

    for k in [
        "total", "green", "yellow", "red",
        "at_risk_count", "improving_30d", "declining_30d",
        "pct_late_invoices_30d", "avg_health_score", "last_refreshed"
    ]:
        assert k in js

    assert js["total"] == js["green"] + js["yellow"] + js["red"]
    assert 0.0 <= js["pct_late_invoices_30d"] <= 100.0
    assert 0 <= js["avg_health_score"] <= 100
