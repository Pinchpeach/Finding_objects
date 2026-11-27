"""The association does not depend on the order of the rows in the raw files (2.61.0).

Until 2.60.x detections with the same assumed position error (every AllWISE / SDSS / GALEX row, the 0.6'' floor of the
resolved Legacy Surveys models) were put in groups in the order of the input file, so the same detections in another
order (a Legacy Surveys viewer answer against its TAP answer) gave another set of objects: 1.1 % of the objects of the
26 deep COSMOS fields differ between two orders.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT.parent / "rawdata"
RULES = ROOT / "classification_rules.csv"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "benchmark" / "order_dependence"))
import association_model as am  # noqa: E402
import shuffle_check as SC  # noqa: E402


def _load(name, env=None, monkeypatch=None):
    if env and monkeypatch:
        for k, v in env.items():
            monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location(f"pre_order_{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_raw(tmp_path: Path) -> Path:
    """Four AllWISE rows with one assumed error around two Legacy Surveys sources, so that which of two AllWISE rows
    joins an LS source depends on who is processed first; plus an SDSS row and two LS rows of one resolved model."""
    a = 1 / 3600
    raw = tmp_path / "raw"
    raw.mkdir()
    ls = pd.DataFrame(
        {
            "catalog": "DESI Legacy Surveys DR10",
            "catalog_object_id": ["ls1", "ls2", "ls3"],
            "ra": [150.0, 150.0 + 3 * a, 150.0 + 3.2 * a],
            "dec": [2.0, 2.0, 2.0 + 0.1 * a],
            "type": ["SER", "SER", "REX"],
            "ra_ivar": 1e10,
            "dec_ivar": 1e10,
            "flux_r": [30.0, 12.0, 11.0],
        }
    )
    wise = pd.DataFrame(
        {
            "catalog": "AllWISE",
            "catalog_object_id": ["w1", "w2", "w3", "w4"],
            "ra": [150.0 + 1 * a, 150.0 + 1.6 * a, 150.0 + 3.1 * a, 150.0 + 9 * a],
            "dec": [2.0, 2.0, 2.0, 2.0],
            "W1mag": [14.0, 14.5, 15.0, 16.0],
        }
    )
    sdss = pd.DataFrame(
        {
            "catalog": "SDSS DR18 PhotoObj",
            "catalog_object_id": ["s1", "s2"],
            "ra": [150.0 + 0.5 * a, 150.0 + 3.0 * a],
            "dec": [2.0, 2.0],
            "modelMag_r": [18.0, 19.0],
        }
    )
    ls.to_csv(raw / "desi_legacy_syn.csv", index=False)
    wise.to_csv(raw / "allwise_syn.csv", index=False)
    sdss.to_csv(raw / "sdss_dr18_syn.csv", index=False)
    return raw


def _compare(raw: Path, tmp_path: Path, seed: int):
    s1 = _load("01_source_association")
    ref_dir, new_dir = tmp_path / "ref_raw", tmp_path / f"new_raw_{seed}"
    SC.shuffle_raw(raw, ref_dir, None)
    perms = SC.shuffle_raw(raw, new_dir, seed)
    ref = SC.members(pd.read_csv(s1.run(ref_dir, tmp_path / "ref.csv"), low_memory=False), {})
    new = SC.members(pd.read_csv(s1.run(new_dir, tmp_path / f"new_{seed}.csv"), low_memory=False), perms)
    return SC.compare_groups(ref, new), ref, new


@pytest.mark.parametrize("seed", range(8))
def test_synthetic_tied_rows_give_the_same_objects_in_any_order(tmp_path, seed):
    res, ref, new = _compare(_synthetic_raw(tmp_path), tmp_path, seed)
    assert res["objects_only_ref"] == res["objects_only_new"] == 0, res
    assert res["status_changed"] == 0, res
    # the object ids follow the order of the association, so they are the same too
    r = ref.set_index("key").object_id
    n = new.set_index("key").object_id
    assert (r.loc[n.index] == n).all()


@pytest.mark.parametrize("seed", [1, 2])
def test_position_order_is_order_independent_too(tmp_path, monkeypatch, seed):
    """V2_ASSOC_TIE_ORDER=position (no brightness key, for the ablation) does not use the row either."""
    monkeypatch.setenv("V2_ASSOC_TIE_ORDER", "position")
    res, _, _ = _compare(_synthetic_raw(tmp_path), tmp_path, seed)
    assert res["objects_only_ref"] == res["objects_only_new"] == 0, res
    (tmp_path / "field").mkdir()
    res, _, _ = _compare(RAW, tmp_path / "field", seed)
    assert res["objects_only_ref"] == res["objects_only_new"] == 0, res


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_committed_field_gives_the_same_objects_in_any_order(tmp_path, seed):
    res, _, _ = _compare(RAW, tmp_path, seed)
    assert res["objects_only_ref"] == res["objects_only_new"] == 0, res
    assert res["status_changed"] == 0, res


def test_likelihood_vectors_do_not_depend_on_row_order(tmp_path):
    """Stages 1-5: the same objects and the same class likelihoods from shuffled raw files."""
    outs = []
    for tag, seed in (("ref", None), ("new", 5)):
        raw = tmp_path / f"raw_{tag}"
        SC.shuffle_raw(RAW, raw, seed)
        a, i, f, e, l = (tmp_path / f"{tag}_{n}.csv" for n in "aifel")
        _load("01_source_association").run(raw, a)
        _load("02_integrate_objects").run(a, raw, i)
        _load("03_extract_features").run(i, RULES, f)
        _load("04_build_evidence").run(f, RULES, e)
        _load("05_likelihood_vectors").run(e, l)
        outs.append(pd.read_csv(l, low_memory=False).set_index("object_id").sort_index())
    ref, new = outs
    assert list(ref.index) == list(new.index)
    assert (ref.primary_class == new.primary_class).all()
    cols = ["likelihood_star", "likelihood_galaxy", "likelihood_qso"]
    assert np.allclose(ref[cols].to_numpy(float), new[cols].to_numpy(float), atol=1e-9)


def test_file_order_switch_restores_the_old_tie_break(tmp_path, monkeypatch):
    """V2_ASSOC_TIE_ORDER=file: tied rows keep the order of the input file (the 2.60.x behaviour, for A/B runs)."""
    raw = _synthetic_raw(tmp_path)
    order = {}
    for mode in ("file", "brightness"):
        monkeypatch.setenv("V2_ASSOC_TIE_ORDER", mode)
        s1 = _load("01_source_association")
        dets, _ = s1.load(raw)
        dets.sort(key=s1._order_key)
        order[mode] = [d["catalog_object_id"] for d in dets if d["catalog"] == "AllWISE"]
    assert order["file"] == ["w1", "w2", "w3", "w4"]  # file order
    assert order["brightness"] == ["w1", "w2", "w3", "w4"]  # also the brightest first here
    # reverse the AllWISE file: the file order follows it, the brightness order does not
    w = pd.read_csv(raw / "allwise_syn.csv").iloc[::-1]
    w.to_csv(raw / "allwise_syn.csv", index=False)
    for mode in ("file", "brightness"):
        monkeypatch.setenv("V2_ASSOC_TIE_ORDER", mode)
        s1 = _load("01_source_association")
        dets, _ = s1.load(raw)
        dets.sort(key=s1._order_key)
        order[mode] = [d["catalog_object_id"] for d in dets if d["catalog"] == "AllWISE"]
    assert order["file"] == ["w4", "w3", "w2", "w1"]
    assert order["brightness"] == ["w1", "w2", "w3", "w4"]


def test_unknown_tie_order_is_refused(monkeypatch):
    monkeypatch.setenv("V2_ASSOC_TIE_ORDER", "random")
    with pytest.raises(ValueError, match="V2_ASSOC_TIE_ORDER"):
        _load("01_source_association")


def test_tie_magnitude_bands_and_missing_values():
    assert am.tie_magnitude("AllWISE", {"W1mag": 14.2}) == 14.2
    assert abs(am.tie_magnitude("DESI Legacy Surveys DR10", {"flux_r": 100.0}) - 17.5) < 1e-12  # 22.5 - 2.5 log10(100)
    assert am.tie_magnitude("DESI Legacy Surveys DR10", {"flux_r": 0.0}) is None
    assert am.tie_magnitude("DESI Legacy Surveys DR10", {"flux_r": -3.0}) is None
    assert am.tie_magnitude("SDSS DR18 PhotoObj", {"modelMag_r": -9999.0}) is None
    assert am.tie_magnitude("Pan-STARRS1 DR2 MeanObject", {"rMeanPSFMag": float("nan")}) is None
    assert am.tie_magnitude("SGA-2020", {"W1mag": 10.0}) is None  # no band for this catalogue
    assert am.tie_magnitude("Gaia DR3", {"phot_g_mean_mag": 19.5}) == 19.5
