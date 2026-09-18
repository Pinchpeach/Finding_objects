from finding_objects.association import (
    CounterpartEvidence,
    association_score,
    chance_coincidence_probability,
    classify_association,
)

def test_close_counterpart_scores_high():
    r = association_score(CounterpartEvidence("xray", "optical", 0.5, 1.0, 0.2))
    assert r["positional_likelihood"] > 0.8
    assert classify_association(0.5, 5.0, r["positional_likelihood"]) == "matched"

def test_ambiguous_and_missing_states():
    assert classify_association(1, 5, 0.9, candidate_count=2) == "ambiguous"
    assert classify_association(0, 5, None, candidate_count=0) == "no_counterpart"
    assert classify_association(0, 5, None, covered=False) == "not_covered"
    assert classify_association(0, 5, None, service_responded=False) == "no_response"

def test_chance_coincidence_increases_with_density():
    low = chance_coincidence_probability(1e-5, 2)
    high = chance_coincidence_probability(1e-3, 2)
    assert 0 <= low < high <= 1
