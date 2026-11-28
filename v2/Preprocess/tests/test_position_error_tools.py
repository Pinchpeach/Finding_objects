"""The tools of the position-error study and of the combined decision table (2.62.2), on small synthetic inputs."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
sys.path.insert(0, str(V2 / "benchmark"))


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


CU = _load(V2 / "benchmark" / "position_errors" / "check_units_from_rows.py", "check_units_from_rows")
CM = _load(V2 / "benchmark" / "position_errors" / "compare_by_members.py", "compare_by_members")
RF = _load(V2 / "benchmark" / "association_ambiguity" / "recount_fixed_broken.py", "recount_fixed_broken")
LC = _load(V2 / "benchmark" / "association_ambiguity" / "label_changes.py", "label_changes")
DT = _load(V2 / "benchmark" / "lowlat_qso" / "decision_table_combos.py", "decision_table_combos")


def test_check_units_lists_only_the_catalogues_whose_error_changes(tmp_path):
    raw = tmp_path / "reg1" / "raw"
    raw.mkdir(parents=True)
    pd.DataFrame([dict(catalog="VLASS", catalog_object_id="v", ra=10.0, dec=2.0, e_RAJ2000=2e-5, e_DEJ2000=2e-5, e_RAMdeg=2e-5)]).to_csv(raw / "vlass_ra10_dec2_r1arcmin.csv", index=False)
    pd.DataFrame([dict(catalog="NVSS", catalog_object_id="n", ra=10.0, dec=2.0, e_RAJ2000=0.09, e_DEJ2000=1.1)]).to_csv(raw / "nvss_ra10_dec2_r1arcmin.csv", index=False)
    pd.DataFrame([dict(catalog="TGSS ADR1", catalog_object_id="t", ra=10.0, dec=2.0, e_RAJ2000=2.05, e_DEJ2000=2.05)]).to_csv(raw / "tgss_ra10_dec2_r1arcmin.csv", index=False)
    pd.DataFrame([dict(catalog="Gaia DR3", catalog_object_id="g", ra=10.0, dec=2.0, ra_error=0.3, dec_error=0.2)]).to_csv(raw / "gaia_dr3_ra10_dec2_r1arcmin.csv", index=False)
    rows, ev, regs = CU.scan([tmp_path])
    changed = set(rows[rows.changed > 0].catalog)
    assert changed == {"VLASS", "NVSS"}
    assert list(regs.region) == ["reg1"] and int(regs.vlass.iloc[0]) == 1 and int(regs.nvss.iloc[0]) == 1 and int(regs.other.iloc[0]) == 0
    assert CU.am.POSERR_UNITS == "fixed"  # the scan leaves the module in the default mode
    e = ev.set_index("evidence").value
    assert e["VLASS e_RAJ2000 identical to e_RAMdeg (share of rows)"] == 1.0


def _run(objs, assoc):
    return pd.DataFrame(assoc), pd.DataFrame(objs)


def test_compare_by_members_separates_same_objects_from_changed_ones_and_sees_the_anchor():
    cols = ["detection_id", "catalog", "object_id", "object_anchor_catalog", "object_ra", "object_dec", "association_status", "poserr_arcsec"]
    # run a (legacy): the radio row anchors the object O1 with the optical row; run b (fixed): the optical row anchors it.  O2 is a lone SDSS row in both.
    a = pd.DataFrame([["vlass:0", "VLASS", "O1", "VLASS", 10.0, 2.0, "new", 1e-5], ["ps1:0", "Pan-STARRS1 DR2 MeanObject", "O1", "VLASS", 10.0, 2.0, "matched", 0.02],
                      ["sdss:0", "SDSS DR18 PhotoObj", "O2", "SDSS DR18 PhotoObj", 10.01, 2.0, "new", 0.6]], columns=cols)
    b = pd.DataFrame([["vlass:0", "VLASS", "P1", "Pan-STARRS1 DR2 MeanObject", 10.0 + 0.4 / 3600, 2.0, "matched", 0.08], ["ps1:0", "Pan-STARRS1 DR2 MeanObject", "P1", "Pan-STARRS1 DR2 MeanObject", 10.0 + 0.4 / 3600, 2.0, "new", 0.02],
                      ["sdss:0", "SDSS DR18 PhotoObj", "P2", "SDSS DR18 PhotoObj", 10.01, 2.0, "new", 0.6]], columns=cols)
    oa = pd.DataFrame([dict(object_id="O1", ra=10.0, dec=2.0, catalogs="Pan-STARRS1 DR2 MeanObject|VLASS", parent_object_id=None, primary_class="GALAXY", std_radio_vlass_3ghz_mjy=2.0),
                       dict(object_id="O2", ra=10.01, dec=2.0, catalogs="SDSS DR18 PhotoObj", parent_object_id=None, primary_class="STAR", std_radio_vlass_3ghz_mjy=None)])
    ob = pd.DataFrame([dict(object_id="P1", ra=10.0 + 0.4 / 3600, dec=2.0, catalogs="Pan-STARRS1 DR2 MeanObject|VLASS", parent_object_id=None, primary_class="QSO", std_radio_vlass_3ghz_mjy=2.0),
                       dict(object_id="P2", ra=10.01, dec=2.0, catalogs="SDSS DR18 PhotoObj", parent_object_id=None, primary_class="STAR", std_radio_vlass_3ghz_mjy=None)])
    c = CM.compare_region((a, oa), (b, ob))
    assert (c["n_objects_a"], c["n_objects_b"], c["same"], c["changed_a"], c["changed_b"]) == (2, 2, 2, 0, 0)  # the same members, only the anchor moved
    assert len(c["label_changes"]) == 1  # O2 has the same class in both runs
    lc = c["label_changes"].iloc[0]
    assert lc.kind == "same_members" and lc.columns == "primary_class" and lc.primary_class_a == "GALAXY" and lc.primary_class_b == "QSO"
    assert (c["anchors_a"], c["anchors_b"]) == (1, 0)  # the object that carries the radio position although it holds an optical row
    r = c["radio"].iloc[0]
    assert bool(r.joined_a) and bool(r.joined_b)
    # the anchor of O1 moved from the radio row to the optical row without a change of members (Codex review of 2.62.2)
    ac = c["anchor_changes"]
    assert len(ac) == 1 and ac.iloc[0].kind == "same_members" and (ac.iloc[0].anchor_a, ac.iloc[0].anchor_b) == ("VLASS", "Pan-STARRS1 DR2 MeanObject")
    assert ac.iloc[0].shift_arcsec == pytest.approx(0.4, abs=1e-3) and len(c["shifts"]) == 2  # both mapped objects have a shift (O2: 0)


def test_compare_by_members_pairs_a_changed_object_with_the_one_that_shares_most_detections():
    cols = ["detection_id", "catalog", "object_id", "object_anchor_catalog", "object_ra", "object_dec", "association_status", "poserr_arcsec"]
    a = pd.DataFrame([["x:0", "Pan-STARRS1 DR2 MeanObject", "A1", "Pan-STARRS1 DR2 MeanObject", 1.0, 1.0, "new", 0.02], ["x:1", "SDSS DR18 PhotoObj", "A2", "SDSS DR18 PhotoObj", 1.0, 1.0, "new", 0.6]], columns=cols)
    b = pd.DataFrame([["x:0", "Pan-STARRS1 DR2 MeanObject", "B1", "Pan-STARRS1 DR2 MeanObject", 1.0, 1.0, "new", 0.02], ["x:1", "SDSS DR18 PhotoObj", "B1", "Pan-STARRS1 DR2 MeanObject", 1.0, 1.0, "matched", 0.6]], columns=cols)
    oa = pd.DataFrame([dict(object_id="A1", ra=1.0, dec=1.0, catalogs="p", parent_object_id=None, primary_class="UNKNOWN"), dict(object_id="A2", ra=1.0, dec=1.0, catalogs="s", parent_object_id=None, primary_class="GALAXY")])
    ob = pd.DataFrame([dict(object_id="B1", ra=1.0, dec=1.0, catalogs="p|s", parent_object_id=None, primary_class="GALAXY")])
    c = CM.compare_region((a, oa), (b, ob))
    assert (c["same"], c["changed_a"], c["changed_b"]) == (0, 2, 1)  # two fragments became one object
    assert set(c["label_changes"].kind) == {"changed_members"} and len(c["label_changes"]) == 1  # A1 UNKNOWN -> GALAXY; A2 GALAXY -> GALAXY is no change


def test_mcnemar_and_recount_helpers():
    assert RF.mcnemar(0, 0) == 1.0
    assert RF.mcnemar(20, 5) == pytest.approx(0.00408, abs=1e-4)
    assert RF.mcnemar(14, 3) == pytest.approx(0.01273, abs=1e-4)


def test_the_new_join_bound_is_left_empty_for_an_association_without_its_own_exchange_table(tmp_path):
    """2.62.6 review: the three-switch row (fixed_same_nearest) got the same_nearest numbers; it has no exchange table of its own."""
    for half in ("calibration", "confirmation"):
        d = tmp_path / half / "cosmos"
        d.mkdir(parents=True)
        pd.DataFrame([dict(variant="same_nearest", catalog=c, new_false=0, new_correct=10) for c in ("AllWISE", "2MASS PSC", "GALEX AIS")]).to_csv(d / "exchange.csv", index=False)
    assert DT.new_join_bound(tmp_path, "base") == {}
    assert DT.new_join_bound(tmp_path, "fixed_same_nearest") == {}
    assert DT.new_join_bound(tmp_path, "same_nearest")["assoc_new_joins_false_all"].startswith("0/60 ")


def test_decision_table_held_counts_the_spectroscopic_qso_the_switch_leaves_out(tmp_path):
    for part, rows in (("b", [("QSO", "QSO", "STAR"), ("QSO", "STAR", "STAR")]), ("d", [("QSO", "QSO", "QSO"), ("STAR", "STAR", "STAR")])):
        pd.DataFrame(rows, columns=["label_base", "label_surveys2", "label_surveys2_keep"]).to_csv(tmp_path / f"held_{part}_base.csv", index=False)
    assert DT.held(tmp_path, "base", "surveys2") == "1/3"  # 3 base QSO, the switch leaves 1 of them out
    assert DT.held(tmp_path, "base", "surveys2_keep") == "2/3"
    assert DT.held(tmp_path, "base", None) == "0/32 (no switch)"


def test_label_changes_runs_when_the_two_fields_leave_objects_unpaired_in_different_numbers(tmp_path, monkeypatch):
    """pd.concat compares the ``attrs`` of its parts; two numpy arrays of different lengths there raised ValueError (found with the survey-switch variants, 2.62.2)."""
    cols = ["object_id", "ra", "dec", "primary_class", "std_mag__ls_r"]
    def write(root, field, rows):
        d = root / field
        d.mkdir(parents=True)
        pd.DataFrame(rows, columns=cols).to_csv(d / "classified_objects.csv", index=False)
    base, var = tmp_path / "base", tmp_path / "var"
    write(base, "f1", [["A", 10.0, 2.0, "QSO", 21.5], ["B", 10.1, 2.0, "STAR", 19.0]])
    write(var, "f1", [["A", 10.0, 2.0, "UNKNOWN", 21.5]])  # B has no counterpart: one object only in the base
    write(base, "f2", [["C", 20.0, 3.0, "GALAXY", 22.5]])
    write(var, "f2", [["C", 20.0, 3.0, "GALAXY", 22.5], ["D", 20.1, 3.0, "STAR", 18.0], ["E", 20.2, 3.0, "STAR", 18.5]])  # two only in the variant
    monkeypatch.setattr(sys, "argv", ["label_changes.py", "--base", str(base), "--variant", str(var), "--fields", "f1,f2", "--out", str(tmp_path / "out")])
    assert LC.main() == 0
    t = pd.read_csv(tmp_path / "out" / "label_changes.csv").set_index("r")
    assert int(t.loc["all", "pairs"]) == 2 and int(t.loc["all", "changed"]) == 1 and int(t.loc["all", "from_QSO"]) == 1
    assert int(t.loc["all", "only_in_base"]) == 1 and int(t.loc["all", "only_in_variant"]) == 2


def test_combos_exchange_uses_each_variants_own_coordinates():
    """Codex review of 2.62.2: combos_table.py passed a one-row-per-id table, which lowlat_exchange.py refuses (and which gave a renumbered id the base's position)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("combos_table_test", V2 / "benchmark" / "lowlat_qso" / "combos_table.py")
    ct = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ct)
    a = 1 / 3600
    base = pd.DataFrame(dict(region="r1", object_id=["O2"], ra=[150.0 + 30 * a], dec=[2.0], ps1_i=[19.0], n_catalogs=[2]))
    var = pd.DataFrame(dict(region="r1", object_id=["O2"], ra=[150.0 + 60 * a], dec=[2.0], ps1_i=[20.0], n_catalogs=[2]))  # the same id, another source
    e = ct.exchange_vs_base({"base": base, "v": var}, "base", 1.0)["v"]
    assert (e["kept"], e["lost"], e["gained"]) == (0, 1, 1)

