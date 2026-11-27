"""The tools that measure what the survey-count switches cost (2.61.5): synthetic inputs, no archive data."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT.parent / "benchmark" / "lowlat_qso"
sys.path.insert(0, str(TOOLS))
import benchmark_cost as BC  # noqa: E402
import reweight as RW  # noqa: E402
import survey_distribution as SD  # noqa: E402


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, TOOLS / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_wilson_upper_limit():
    assert RW.wilson_hi(0, 0) == 1.0
    assert RW.wilson_hi(0, 90) == pytest.approx(0.0409, abs=2e-3)  # no label among 90 type 1 AGN with 1-2 surveys
    assert RW.wilson_hi(45, 90) < 0.65


def test_q_pools_bins_with_few_objects_by_half():
    cross = pd.DataFrame([
        dict(ps1_i="20-21", surveys="4+", n_type1=40, base_labels_qso=30),
        dict(ps1_i="19-20", surveys="4+", n_type1=2, base_labels_qso=2),  # too few: takes the pooled bright-half value
        dict(ps1_i="no PS1", surveys="1", n_type1=28, base_labels_qso=0),
        dict(ps1_i="21-22", surveys="1", n_type1=0, base_labels_qso=0),
    ])  # fmt: skip
    q = RW.q_table(cross).set_index(["ps1_i", "surveys"])
    assert q.loc[("20-21", "4+"), "q"] == pytest.approx(0.75) and not q.loc[("20-21", "4+"), "pooled"]
    assert q.loc[("19-20", "4+"), "q"] == pytest.approx(32 / 42) and q.loc[("19-20", "4+"), "pooled"]
    assert q.loc[("no PS1", "1"), "q"] == 0.0 and q.loc[("no PS1", "1"), "q_upper95"] > 0.1


def test_survey_distribution_table_shares():
    d = pd.DataFrame({
        "primary_class": ["QSO", "STAR", "STAR", "QSO", "STAR"],
        "ls_cone": [False, False, True, True, False],
        "n_surveys": [3, 1, 2, 1, 4],
        "ps1_i": [20.5, 20.7, 21.5, np.nan, 20.2],
    })  # fmt: skip
    t = SD.table(d)
    x = t[(t.population == "all objects") & (t.cones == "no-LS cones") & (t.ps1_i == "20-21")].iloc[0]
    assert x.objects == 3 and x.surveys_1 == 1 and x.surveys_3 == 1 and x.surveys_4plus == 1
    assert x.share_ge2 == pytest.approx(2 / 3, abs=1e-3) and x.share_ge3 == pytest.approx(2 / 3, abs=1e-3)  # shares are rounded to 4 decimals
    q = t[(t.population == "labelled QSO") & (t.cones == "LS cones") & (t.ps1_i == "no PS1")].iloc[0]
    assert q.objects == 1 and q.surveys_1 == 1 and q.share_ge2 == 0.0


def test_benchmark_survey_counts(tmp_path):
    truth = pd.DataFrame({"benchmark_id": ["A", "B"], "truth_class": ["QSO", "QSO"], "psfmag_r": [20.5, 22.4]})
    feat = tmp_path / "feat"
    feat.mkdir()
    for name, ids in (("gaia_dr3", ["A"]), ("allwise", ["A", "B"]), ("panstarrs1", ["A"])):
        pd.DataFrame({"benchmark_id": ids, "catalog_object_id": [1] * len(ids)}).to_csv(feat / f"{name}_trd.csv.gz", index=False)
    s = BC.survey_table(truth, feat, "*_trd.csv.gz").set_index("benchmark_id")
    assert s.loc["A", "n_catalogues"] == 3 and s.loc["B", "n_catalogues"] == 1


def test_spectro_held_counts_only_what_the_base_labels_qso(tmp_path):
    sh = _load("spectro_held_test", "spectro_held.py")
    for v, label in (("base", "QSO"), ("v", "UNKNOWN")):
        d = tmp_path / v / "r1"
        d.mkdir(parents=True)
        pd.DataFrame([
            dict(object_id="O1", ra=1.0, dec=1.0, catalogs="LAMOST DR catalog", primary_class=label, classification_status="x",
                 rules_QSO="SPC-LAMOST-003", parent_object_id=np.nan),
            dict(object_id="O2", ra=1.0, dec=1.0, catalogs="AllWISE|Gaia DR3|Pan-STARRS1 DR2 MeanObject", primary_class="QSO",
                 classification_status="x", rules_QSO="WISE-AGN-001", parent_object_id=np.nan),
        ]).to_csv(d / "objects.csv.gz", index=False)  # fmt: skip
    import subprocess

    out = tmp_path / "o.csv"
    run = subprocess.run([sys.executable, str(TOOLS / "spectro_held.py"), "--base", str(tmp_path / "base"),
                          "--variants", f"v={tmp_path / 'v'}", "--out", str(out)], capture_output=True, text=True)  # fmt: skip
    assert run.returncode == 0, run.stderr
    o = pd.read_csv(out)
    assert list(o.object_id) == ["O1"] and o.n_surveys.iloc[0] == 1 and o.label_v.iloc[0] == "UNKNOWN"
    assert "of 1 labelled QSO by the base, 1 are not" in run.stdout
