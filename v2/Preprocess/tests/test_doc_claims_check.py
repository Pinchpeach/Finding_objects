"""``benchmark/doc_claims_check.py`` (task "머", 2.62.7): the recount of the numbers that README / overview / deck / ALGORITHM / LOCKED docs quote.

The tool is checked, not the documents: the facts below are what the committed data say today (they change only if the data change), so a failure here means the recount drifted
or a truth table was replaced; the documents themselves are corrected at the next release (``document/NEXT_RELEASE_DOCS.md``).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmark"))
import doc_claims_check as D  # noqa: E402


def by_id():
    return {r["id"]: r for r in D.claims()}


def test_every_claim_has_a_status_and_a_source():
    c = D.claims()
    assert len(c) >= 30
    for r in c:
        assert r["status"] and r["source"] and r["quoted"] and r["recounted"], r["id"]
    assert len({r["id"] for r in c}) == len(c)


def test_plates_142_is_a_sum_of_per_class_counts_not_distinct_plates():
    r = by_id()["old_plates"]
    assert r["status"] == "differs" and "84 distinct plates" in r["recounted"] and "STAR 51, GALAXY 7, QSO 84" in r["recounted"]


def test_sky_benchmark_cells_are_the_grid_not_the_occupied_cells():
    r = by_id()["sky_cells"]
    assert r["status"] == "misleading" and "355 occupied" in r["recounted"]


def test_reference_validation_scores_recount_exactly_but_the_plan_is_not_inside_the_list():
    c = by_id()
    assert c["ref520_scores"]["status"] == "ok" and c["ref520_design"]["status"] == "ok"
    assert c["ref520_in_list"]["status"] == "differs" and c["ref520_in_list"]["recounted"].startswith("466 of 520")


def test_locked_set_c_numbers_recount():
    c = by_id()
    for k in ("setc_n", "setc_classes", "setc_pools", "setc_dsc"):
        assert c[k]["status"] == "ok", k
    assert c["setc_regions"]["status"].startswith("ok") and "59 with truth" in c["setc_regions"]["recounted"]
