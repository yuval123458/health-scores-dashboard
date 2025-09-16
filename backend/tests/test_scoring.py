import importlib

m = importlib.import_module("backend.api.main")


def test_tier_mapping_soft_scores():
    assert m.tier(85) == "Green"
    assert m.tier(65) == "Yellow"
    assert m.tier(45) == "Red"


def test_combine_score_bounds_and_type():
    # Must return an int in [0, 100] for valid inputs in [0,1]
    low = m.combine_score(0.0, 0.0, 0.0, 0.0)
    mid = m.combine_score(0.5, 0.5, 0.5, 0.5)
    high = m.combine_score(1.0, 1.0, 1.0, 1.0)

    for s in (low, mid, high):
        assert isinstance(s, int)
        assert 0 <= s <= 100

    assert low <= mid <= high  # monotonic with better inputs


def test_combine_score_responds_to_each_component():
    # Improving a single percentile should not decrease the score
    base = m.combine_score(0.2, 0.2, 0.2, 0.2)
    better_E = m.combine_score(0.8, 0.2, 0.2, 0.2)
    better_A = m.combine_score(0.2, 0.8, 0.2, 0.2)
    better_S = m.combine_score(0.2, 0.2, 0.8, 0.2)
    better_F = m.combine_score(0.2, 0.2, 0.2, 0.8)

    assert better_E >= base
    assert better_A >= base
    assert better_S >= base
    assert better_F >= base
