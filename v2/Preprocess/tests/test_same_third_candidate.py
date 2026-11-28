"""What the ``same`` rule does with three candidates (2.62.2): it looks at the two best only.

``V2_ASSOC_AMBIG=same`` resolves a row whose two best candidates have anchors within 0.3'' (fragments of one object) by taking the better of them.  A third candidate
that is ANOTHER object and scores nearly as well is not looked at.  These tests state that behaviour as it is (``benchmark/association_ambiguity/third_candidate.py`` counts
how often it happens in the COSMOS fields: 86 of the 213 rows with three or more candidates that ``same`` resolves), so a change of it is a decision and not a surprise.
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
import association_model as am  # noqa: E402

ARC = 1.0 / 3600.0


def _s1():
    spec = importlib.util.spec_from_file_location("s1_third_cand", V2 / "Preprocess" / "01_source_association.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(tmp_path, monkeypatch, ls_x, sdss_x=0.08, fix=("same",)):
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset(fix))
    s1 = _s1()
    monkeypatch.setattr(s1, "AMBIG_FIX", frozenset(fix))
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rows = [dict(catalog="DESI Legacy Surveys DR10", catalog_object_id=f"ls{i}", ra=150.0 + x * ARC, dec=2.0, query_radius_arcmin=1.0) for i, x in enumerate(ls_x)]
    pd.DataFrame(rows).to_csv(raw / "ls_x.csv", index=False)
    pd.DataFrame([dict(catalog="SDSS DR18 PhotoObj", catalog_object_id="s0", ra=150.0 + sdss_x * ARC, dec=2.0, query_radius_arcmin=1.0)]).to_csv(raw / "sdss_x.csv", index=False)
    out = tmp_path / "assoc.csv"
    s1.run(raw, out)
    t = pd.read_csv(out)
    return t[t.catalog == "SDSS DR18 PhotoObj"].iloc[0], t[t.catalog == "DESI Legacy Surveys DR10"].reset_index(drop=True), t


def test_two_fragments_alone_are_one_object(tmp_path, monkeypatch):
    s, ls, _ = _run(tmp_path, monkeypatch, ls_x=(0.0, 0.2))
    assert s.association_status == "matched" and s.ambiguity_resolution == "same_object" and s.candidate_count == 2


def test_a_third_candidate_that_is_another_object_and_scores_nearly_as_well_is_not_looked_at(tmp_path, monkeypatch):
    """LS rows at 0.0'' and 0.2'' (fragments) and one at -0.35'' (0.35'' from the first: another object); the SDSS row at 0.08'' is 0.43'' from the third, whose
    score is above 0.67 times the best.  ``same`` still takes the best fragment and the row is not left ambiguous."""
    seen = []
    real = _s1  # the helper builds a fresh module per call: wrap the function it will use
    def run_recording():
        monkeypatch.setattr(am, "AMBIG_FIX", frozenset({"same"}))
        s1 = real()
        monkeypatch.setattr(s1, "AMBIG_FIX", frozenset({"same"}))
        orig = s1._resolve_ambiguity
        monkeypatch.setattr(s1, "_resolve_ambiguity", lambda c, g: (seen.append([x[0] for x in c]) or orig(c, g)))
        raw = tmp_path / "rec_raw"
        raw.mkdir()
        rows = [dict(catalog="DESI Legacy Surveys DR10", catalog_object_id=f"ls{i}", ra=150.0 + x * ARC, dec=2.0, query_radius_arcmin=1.0) for i, x in enumerate((0.0, 0.2, -0.35))]
        pd.DataFrame(rows).to_csv(raw / "ls_x.csv", index=False)
        pd.DataFrame([dict(catalog="SDSS DR18 PhotoObj", catalog_object_id="s0", ra=150.0 + 0.08 * ARC, dec=2.0, query_radius_arcmin=1.0)]).to_csv(raw / "sdss_x.csv", index=False)
        s1.run(raw, tmp_path / "rec.csv")
    run_recording()
    scores = seen[0]
    assert len(scores) == 3 and scores[2] >= 0.67 * scores[0]  # the third candidate would by itself have made the row ambiguous (second / best >= 0.67)
    s, ls, t = _run(tmp_path, monkeypatch, ls_x=(0.0, 0.2, -0.35))
    assert s.candidate_count == 3 and s.association_status == "matched" and s.ambiguity_resolution == "same_object"
    at = lambda x: ls[((ls.ra - 150.0) / ARC - x).abs() < 0.02].iloc[0]  # noqa: E731  (the LS row at offset x arcsec; output rows are not in input order)
    first, second, third = at(0.0), at(0.2), at(-0.35)
    assert len({first.object_id, second.object_id, third.object_id}) == 3  # three LS rows of one catalogue are three objects
    assert s.object_id == first.object_id  # the nearest fragment, not the competitor 0.43'' away
    # the competitor really is a competitor: with the switch off the row is ambiguous between the first two and the third is within the score ratio (see third_candidate.py)
    assert abs(-0.35 - 0.0) >= _s1().SAME_OBJECT_ARCSEC  # farther from the best fragment than the 0.3'' that makes two anchors one object


def test_without_the_switch_the_same_row_stays_ambiguous(tmp_path, monkeypatch):
    s, _, t = _run(tmp_path, monkeypatch, ls_x=(0.0, 0.2, -0.35), fix=())
    assert s.association_status == "ambiguous_new"
