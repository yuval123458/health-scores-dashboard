import importlib

m = importlib.import_module("backend.api.main")

def _score(**kw):
    return m.compute_health_from_components(**kw)

def test_bounds_and_type():
    cases = [
        dict(logins_30d=0,  adoption_rate_60d=0.0, tickets_30d=0, last_invoice="unknown"),
        dict(logins_30d=10, adoption_rate_60d=0.4, tickets_30d=2, last_invoice="invoice_paid",
             last_invoice_paid_on_time=True, last_invoice_days_late=0),
        dict(logins_30d=35, adoption_rate_60d=1.2, tickets_30d=12, last_invoice="invoice_paid",
             last_invoice_paid_on_time=False, last_invoice_days_late=20),
    ]
    for c in cases:
        s = _score(**c)
        assert isinstance(s, int)
        assert 0 <= s <= 100

def test_invoice_gradient_with_metadata():
    base_inputs = dict(logins_30d=20, adoption_rate_60d=0.6, tickets_30d=1, last_invoice="invoice_paid")
    on_time   = _score(**base_inputs, last_invoice_paid_on_time=True,  last_invoice_days_late=0)
    late_3    = _score(**base_inputs, last_invoice_paid_on_time=False, last_invoice_days_late=3)
    late_10   = _score(**base_inputs, last_invoice_paid_on_time=False, last_invoice_days_late=10)
    late_25   = _score(**base_inputs, last_invoice_paid_on_time=False, last_invoice_days_late=25)
    assert on_time > late_3 > late_10 >= late_25  # monotonic decrease

def test_logins_soft_saturation_marginal_returns():
    tgt = m.TARGETS["logins_30d"]  # e.g., 20
    common = dict(adoption_rate_60d=0.5, tickets_30d=1, last_invoice="invoice_paid",
                  last_invoice_paid_on_time=True, last_invoice_days_late=0)

    s0  = _score(logins_30d=0,         **common)
    s10 = _score(logins_30d=tgt//2,    **common)   # ~10
    s20 = _score(logins_30d=tgt,       **common)   # target
    s40 = _score(logins_30d=tgt*2,     **common)   # beyond target

    # increasing, but diminishing returns after target
    gain_0_to_10 = s10 - s0
    gain_20_to_40 = s40 - s20
    assert s10 > s0 and s20 > s10 and s40 >= s20
    assert gain_0_to_10 > 0
    assert gain_20_to_40 >= 0
    assert gain_0_to_10 > gain_20_to_40  # saturation effect

def test_tickets_soft_penalty_cap():
    cap = m.TARGETS["tickets_cap_30d"]  # e.g., 5
    common = dict(logins_30d=20, adoption_rate_60d=0.6, last_invoice="invoice_paid",
                  last_invoice_paid_on_time=True, last_invoice_days_late=0)

    few   = _score(tickets_30d=0,      **common)
    some  = _score(tickets_30d=cap//2, **common)
    many  = _score(tickets_30d=cap,    **common)
    tons  = _score(tickets_30d=cap*4,  **common)

    assert few > some > many >= tons  # saturating penalty
    # extra penalty above cap should be tiny
    assert (many - tons) <= 2

def test_adoption_soft_ratio_saturates():
    common = dict(logins_30d=15, tickets_30d=1, last_invoice="invoice_paid",
                  last_invoice_paid_on_time=True, last_invoice_days_late=0)

    a0   = _score(adoption_rate_60d=0.0, **common)
    a25  = _score(adoption_rate_60d=0.25, **common)
    a50  = _score(adoption_rate_60d=0.50, **common)
    a100 = _score(adoption_rate_60d=1.00, **common)
    a200 = _score(adoption_rate_60d=2.00, **common)  # >1 should ~saturate

    assert a25 > a0 and a50 > a25 and a100 > a50
    assert (a200 - a100) <= 2  # saturation past 1.0

def test_perfect_case_is_high_but_not_excessive():
    # Depending on your cap (some folks clamp to <=98), allow 90..100
    s = _score(
        logins_30d=m.TARGETS["logins_30d"],
        adoption_rate_60d=1.0,
        tickets_30d=0,
        last_invoice="invoice_paid",
        last_invoice_paid_on_time=True,
        last_invoice_days_late=0,
    )
    assert 90 <= s <= 100

def test_tier_mapping_soft_scores():
    assert m.tier(85) == "Green"
    assert m.tier(65) == "Yellow"
    assert m.tier(45) == "Red"
