"""Faint star:galaxy number-count prior and the dual GALAXY/QSO label (2.46.0)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

PRE = Path(__file__).resolve().parents[1]


def _load(name, file):
    s = importlib.util.spec_from_file_location(name, PRE / file)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


FP = _load("t_faint_prior", "faint_class_prior.py")
AH = _load("t_agn_host", "agn_host.py")
CLASSES = ("STAR", "GALAXY", "QSO")


def _rows(r):
    # (ra, dec) of the north Galactic pole: |b| = 90
    return pd.DataFrame({"ra": [192.85948] * len(r), "dec": [27.12825] * len(r), "std_mag__ls_r": r})


def test_shipped_table_is_galaxy_dominated_when_faint_at_high_latitude():
    t = FP.load_table()
    hi_b = t.xs(4, level="bb")  # |b| >= 60
    bright, faint = hi_b.loc[np.digitize(17.2, FP.R_EDGES)], hi_b.loc[np.digitize(22.2, FP.R_EDGES)]
    assert bright["STAR"] > bright["GALAXY"]
    assert faint["GALAXY"] > faint["STAR"]


def test_prior_only_for_faint_objects():
    f = FP.star_galaxy_factors(_rows([18.0, 21.5, np.nan]))
    assert np.isnan(f[0]).all() and np.isnan(f[2]).all()
    assert np.isfinite(f[1]).all()


def test_faint_point_source_with_weak_star_evidence_becomes_galaxy():
    table = pd.DataFrame({"bb": [4], "rb": [np.digitize(21.5, FP.R_EDGES)], "STAR": [10], "GALAXY": [88], "QSO": [2]})
    table = table.set_index(["bb", "rb"]).astype(float) + 1
    table = table.div(table.sum(axis=1), axis=0)
    f = FP.star_galaxy_factors(_rows([21.5]), table)[0]
    assert FP.apply(np.array([0.6, 0.35, 0.05]), f, CLASSES)[0] == "GALAXY"
    # decisive star evidence survives the prior
    assert FP.apply(np.array([0.995, 0.004, 0.001]), f, CLASSES)[0] == "STAR"
    # outside the table: unchanged
    assert FP.apply(np.array([0.6, 0.35, 0.05]), np.array([np.nan, np.nan]), CLASSES) is None


def test_dual_label():
    df = pd.DataFrame({"desi_legacy_surveys_dr10__type": ["SER", "PSF", "REX", "SER"]})
    items = [[], [], [{"rule_id": "WISE-AGN-001", "class": "EXTRAGALACTIC"}], []]
    sec, why = AH.secondary(df, ["QSO", "QSO", "GALAXY", "GALAXY"], items)
    assert sec == ["GALAXY", "", "QSO", ""]
    assert why[0] == AH.QSO_RESOLVED_HOST and why[2] == AH.GALAXY_WISE_AGN
