"""Low-latitude quasar recall measurement (2.61.2): the scoring, the causes of a miss, the region draw."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

LL = Path(__file__).resolve().parents[2] / "benchmark" / "lowlat_qso"
sys.path.insert(0, str(LL))
import score_lowlat_qso as S  # noqa: E402
import select_fields_lowlat as SEL  # noqa: E402


def test_wilson_interval():
    lo, hi = S.wilson(0, 10)
    assert abs(lo) < 1e-12 and abs(hi - 0.2775) < 1e-3
    lo, hi = S.wilson(10, 10)
    assert abs(hi - 1.0) < 1e-12 and abs(lo - 0.7225) < 1e-3
    lo, hi = S.wilson(50, 100)
    assert abs(lo - 0.4038) < 2e-3 and abs(hi - 0.5962) < 2e-3
    assert all(math.isnan(x) for x in S.wilson(0, 0))


def test_r90_sky_is_the_pipelines_footprint():
    # high latitude, away from the Galactic Centre: inside; the plane: outside; near the Centre: outside
    assert bool(S.r90_sky(150.0, 2.0))
    assert not bool(S.r90_sky(283.8, -2.1))  # b ~ +1 deg... Galactic plane
    assert not bool(S.r90_sky(266.4, -28.9))  # 5 deg from the Galactic Centre (b ~ 0)
    assert not bool(S.r90_sky(270.0, -20.0))  # |b| ~ 5, inside 30 deg of the Centre


def _row(**kw):
    base = dict(primary_class="STAR", classification_basis="evidence", classification_status="CLASSIFIED",
                p_star=0.5, p_galaxy=0.2, p_qso=0.3, p_star_training_prior=0.3, p_galaxy_training_prior=0.2,
                p_qso_training_prior=0.5, prior_position=1.0, prior_qso_magnitude=1.0, prior_qso_veto=1.0,
                prior_faint_star=np.nan, prior_faint_galaxy=np.nan)  # fmt: skip
    base.update(kw)
    return pd.Series(base)


def _with_final(row: pd.Series) -> pd.Series:
    """Fill p_* from the stored factors, as Stage 5 does."""
    P = np.array([row[f"p_{c.lower()}_training_prior"] for c in S.CLASSES], float)
    P[1] *= row.prior_position
    P[2] *= row.prior_position * row.prior_qso_magnitude * row.prior_qso_veto
    P = P / P.sum()
    for c, v in zip(S.CLASSES, P):
        row[f"p_{c.lower()}"] = v
    return row


def test_cause_of_a_miss():
    # the evidence alone says STAR
    r = _with_final(_row(p_star_training_prior=0.6, p_galaxy_training_prior=0.1, p_qso_training_prior=0.3))
    assert S.cause(r, True)[0] == "evidence"
    # the evidence says QSO, the position factor turns it
    r = _with_final(_row(p_star_training_prior=0.3, p_galaxy_training_prior=0.1, p_qso_training_prior=0.6,
                         prior_position=0.3, prior_qso_magnitude=1.0))  # fmt: skip
    r["p_star_training_prior"] = 0.4  # star 0.4, galaxy 0.1 x 0.3, qso 0.5 x 0.3 -> star wins after the position factor
    r["p_qso_training_prior"] = 0.5
    r = _with_final(r)
    assert S.cause(r, True)[0] == "position_prior"
    # only the QSO magnitude prior turns it
    r = _with_final(_row(p_star_training_prior=0.3, p_galaxy_training_prior=0.1, p_qso_training_prior=0.6,
                         prior_position=1.0, prior_qso_magnitude=0.1))  # fmt: skip
    assert S.cause(r, True)[0] == "qso_magnitude"
    # only the veto
    r = _with_final(_row(p_star_training_prior=0.3, p_galaxy_training_prior=0.1, p_qso_training_prior=0.6,
                         prior_position=1.0, prior_qso_magnitude=1.0, prior_qso_veto=0.1))  # fmt: skip
    assert S.cause(r, True)[0] == "qso_veto"
    # a rule set the label
    r = _with_final(_row(classification_basis="gaia_motion"))
    assert S.cause(r, True) == ("rule_decided", "gaia_motion")
    # abstained
    r = _with_final(_row(primary_class="UNKNOWN", classification_status="LOW_CONFIDENCE"))
    c, d = S.cause(r, True)
    assert c == "abstained" and "LOW_CONFIDENCE" in d
    # no object
    assert S.cause(_row(), False)[0] == "no_object"
    # stored factors that do not reproduce p_*
    r = _with_final(_row())
    r["p_qso"] = 0.0001
    assert S.cause(r, True)[0] == "other"


def test_match_prefers_more_catalogues_then_nearest():
    a = 1 / 3600
    o = pd.DataFrame(
        dict(ra=[150.0 + 0.5 * a, 150.0 + 1.5 * a, 150.0 + 5 * a], dec=[2.0] * 3, catalogs=["A", "A|B|C", "A|B|C|D"])
    )
    assert S.match_truth(o, 150.0, 2.0) == 1  # the 1.5'' object has more catalogues than the 0.5'' one; the 5'' one is out
    assert S.match_truth(o, 151.0, 2.0) == -1


def _write_region(root: Path, name: str, rows: list[dict]):
    d = root / name
    d.mkdir(parents=True)
    cols = {"object_id": "", "ra": 0.0, "dec": 0.0, "catalogs": "A|B", "primary_class": "STAR", "parent_object_id": np.nan,
            "classification_basis": "evidence", "classification_status": "CLASSIFIED", "rules_QSO": ""}  # fmt: skip
    df = pd.DataFrame([{**cols, **r} for r in rows])
    df.to_csv(d / "objects.csv.gz", index=False)


def test_scoring_counts_labels_causes_and_density(tmp_path):
    a = 1 / 3600
    truth = pd.DataFrame(
        dict(sample=["huo", "huo", "huo", "fu_contaminant"], name=["q1", "q2", "q3", "s1"],
             ra=[150.0, 150.0 + 20 * a, 150.0 + 40 * a, 150.0 + 60 * a], dec=[2.0] * 4, l=[100.0] * 4,
             b=[-12.0, -12.0, -3.0, -12.0], z=[1.0, 2.0, 3.0, np.nan], imag=[18.0, 19.0, 19.2, 17.0],
             ebv=[0.1, 0.15, 0.4, np.nan], cls=["qso", "qso", "qso", "star"], also_in=[""] * 4)
    )  # fmt: skip
    regions = pd.DataFrame(dict(name=["r1"], stratum=["b10-15"], kind=["qso"], ra=[150.0], dec=[2.0]))
    _write_region(tmp_path, "r1", [
        dict(object_id="O1", ra=150.0, dec=2.0, primary_class="QSO"),
        dict(object_id="O2", ra=150.0 + 20 * a, dec=2.0, primary_class="STAR"),  # q2 missed: evidence says STAR (no p_*): other
        dict(object_id="O4", ra=150.0 + 60 * a, dec=2.0, primary_class="QSO"),  # the star is labelled QSO
        dict(object_id="O5", ra=150.0 + 90 * a, dec=2.0, primary_class="QSO"),  # another QSO label, not a sample quasar
    ])  # fmt: skip
    res = S.score_regions(regions, truth, tmp_path, radius_arcmin=3.0)
    T = res["per_truth"].set_index("name")
    assert T.loc["q1", "label"] == "QSO" and T.loc["q2", "label"] == "STAR" and T.loc["q3", "label"] == "NO_OBJECT"
    assert T.loc["q3", "cause"] == "no_object"
    assert T.loc["s1", "label"] == "QSO"  # contaminant labelled QSO
    tabs = S.summarise(res)
    rs = tabs["recall_summary"].set_index(["by", "bin"])
    assert rs.loc[("all", "all"), "n"] == 2 and rs.loc[("all", "all"), "qso"] == 1  # q1, q2 have objects
    assert rs.loc[("all", "all incl. no object"), "n"] == 3
    dens = tabs["qso_density"].iloc[0]
    assert dens.qso_labelled_other == 1  # O5 only (O1 and O4 are matched to truth objects)
    assert tabs["contaminants"].label.tolist() == ["QSO"]


def test_region_draw_is_deterministic_and_non_overlapping():
    rng = np.random.default_rng(3)
    n = 800
    ra = rng.uniform(0, 360, n)
    dec = rng.uniform(-10, 70, n)
    d = pd.DataFrame(dict(sample=np.where(rng.random(n) < 0.8, "huo", "fu"), name=[f"J{i}" for i in range(n)], ra=ra, dec=dec,
                          l=rng.uniform(0, 240, n), b=rng.uniform(-20, 20, n), z=1.0, imag=18.0,
                          ebv=np.where(rng.random(n) < 0.8, rng.uniform(0.02, 0.5, n), np.nan), cls="qso", also_in=""))  # fmt: skip
    d.loc[:5, ["cls", "sample"]] = ["star", "fu_contaminant"]
    f1, f2 = SEL.select(d), SEL.select(d.sample(frac=1.0, random_state=1).reset_index(drop=True))
    assert f1.equals(f2)  # the order of the input does not matter
    quota = pd.Series({"b0-5": 20, "b5-10": 50, "b10-15": 40, "b15-20": 40})
    got = f1[f1.kind == "qso"].groupby("stratum").size()
    assert (got <= quota.reindex(got.index)).all()
    for i in range(len(f1)):
        s = SEL._sep_arcmin(f1.ra[i], f1.dec[i], f1.ra.values, f1.dec.values)
        s[i] = 99
        assert (s > 2 * SEL.R_ARCMIN).all()
    # the Fu quasars that are also in the Huo table are not drawn twice
    d2 = d.copy()
    d2.loc[d2.index[10:20], "also_in"] = "huo"
    assert not set(d2.name[10:20]) & set(SEL.select(d2).center_name)


def test_the_workflow_runs_the_locked_list():
    import hashlib

    import yaml

    root = Path(__file__).resolve().parents[3]
    w = yaml.safe_load((root / ".github" / "workflows" / "v2_lowlat_qso.yml").read_text())
    lst = LL / "fields_lowlat.csv"
    assert w["env"]["LOCK_SHA256"] == hashlib.sha256(lst.read_bytes()).hexdigest()
    f = pd.read_csv(lst)
    assert len(f) == 169 and f.name.is_unique
    # the list is what the rule gives on the committed truth table
    again = SEL.select(pd.read_csv(LL / "lowlat_truth.csv.gz"))
    assert again.name.tolist() == f.name.tolist() and np.allclose(again.ra.round(5), f.ra) and np.allclose(again.dec.round(5), f.dec)
