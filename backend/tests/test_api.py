from fastapi.testclient import TestClient
import importlib

main = importlib.import_module("backend.api.main")

class _EmptyResult:
    def mappings(self): return self
    def all(self): return []
    def first(self): return None
    def scalar(self): return None
    def __iter__(self): return iter([])

class _EmptyConn:
    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def execute(self, *args, **kwargs): return _EmptyResult()

class _EmptyEngine:
    def connect(self): return _EmptyConn()
    def begin(self):   return _EmptyConn()

def _patch_engine(monkeypatch):
    monkeypatch.setattr(main, "engine", _EmptyEngine())

def test_customers_min_contract(monkeypatch):
    _patch_engine(monkeypatch)
    client = TestClient(main.app)

    r = client.get("/api/customers")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)

    if data:
        item = data[0]
        assert {"id","name","segment","plan","health_score","health_tier"} <= set(item.keys())
        assert 0 <= item["health_score"] <= 100
        assert item["health_tier"] in {"Green","Yellow","Red"}

def test_customer_health_not_found_or_min(monkeypatch):
    _patch_engine(monkeypatch)
    client = TestClient(main.app)

    r = client.get("/api/customers/1/health")
    assert r.status_code in (404, 200)
    if r.status_code == 200:
        js = r.json()
        assert {"id","name","health_score","health_tier"} <= set(js.keys())

def test_dashboard_summary_min(monkeypatch):
    _patch_engine(monkeypatch)
    client = TestClient(main.app)

    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    js = r.json()

    if "summary" in js:
        s = js["summary"]
        assert {"total","avg_health_score","pct_late_invoices_30d","last_refreshed"} <= set(s.keys())
    else:
        assert {"total","avg_health_score","pct_late_invoices_30d","last_refreshed"} <= set(js.keys())
