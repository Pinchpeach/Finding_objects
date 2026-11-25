"""Gaia release table and classification assumptions (2.60.6, DR4 readiness).

DR3 must behave exactly as before the constants were gathered into per-release tables: the column lists and the
queries the collector sends, the numbers Stage 3/4/5 use.  DR4 must not run through DR3's assumptions silently.
"""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Get_data"))
import check_gaia_release as chk  # noqa: E402
import gaia_dr3 as g  # noqa: E402
import gaia_release as gr  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


GA = _load(V2 / "Preprocess" / "gaia_assumptions.py", "t_gaia_assumptions")


def _sha(cols):
    return hashlib.sha256(json.dumps(list(cols)).encode()).hexdigest()


# --------------------------------------------------------------------------------------------- collection side
def test_dr3_column_lists_are_what_the_collector_always_asked():
    # hashes of the lists as they were in gaia_dr3.py before 2.60.6 (30 / 15 / 8 / 9 columns)
    assert _sha(gr.SOURCE) == "142419ccaf003568e0cd72ebf2cc7f11616c252999d17170805cc5fa985cc136"
    assert _sha(gr.AP) == "f1bdba4d991aed54733a914bbf700b37dbcfe372032edef7fd8bfe37eddf356a"
    assert _sha(gr.SPEC_AP) == "6b09b949197f7174b43c024b84a58de1c26c173f66f924b7fdfe892b43146507"
    assert _sha(gr.VAR_SUMMARY) == "17703702b092ae0d1e22f651ef06347e5e78d11fd4476e01ec64e7b58a2d19a3"
    assert g.SOURCE is gr.SOURCE and g.AP is gr.AP and g.SPEC_AP is gr.SPEC_AP and g.VAR_SUMMARY is gr.VAR_SUMMARY


def test_dr3_product_map_has_the_old_tables_status_columns_and_order():
    p = gr.RELEASES["DR3"].products
    assert list(p) == ["source", "astrophysical_parameters", "vari_classifier_result", "vari_summary"]
    assert [x.table for x in p.values()] == [
        "gaia_source",
        "astrophysical_parameters",
        "vari_classifier_result",
        "vari_summary",
    ]
    assert [x.status_column for x in p.values()] == [
        None,
        "gaia_ap_query_status",
        "gaia_vari_classifier_query_status",
        "gaia_vari_summary_query_status",
    ]
    assert p["astrophysical_parameters"].columns == tuple(gr.AP + gr.SPEC_AP)
    assert p["vari_classifier_result"].columns == ("best_class_name", "best_class_score")
    rel = gr.RELEASES["DR3"]
    assert (rel.tap_schema, rel.ref_epoch, rel.designation_prefix, rel.vizier_source) == (
        "gaiadr3",
        2016.0,
        "Gaia DR3",
        "I/355/gaiadr3",
    )


def test_dr3_queries_are_unchanged(monkeypatch):
    monkeypatch.delenv("V2_GAIA_RELEASE", raising=False)
    monkeypatch.delenv("V2_GAIA_SOURCE", raising=False)
    sent = []
    merged = []
    monkeypatch.setattr(g, "_bounded", lambda fn, budget, q, *a, **k: (sent.append(q), _one_row())[1])
    monkeypatch.setattr(
        g,
        "_merge_optional",
        lambda df, tab, cols, status, deadline: (merged.append((tab, list(cols), status)), df)[1],
    )
    monkeypatch.setattr(g, "_merge_fidelity", lambda df, deadline=None: df)
    g.fetch(150.0, 2.0, 3.0)
    select = ",".join(gr.SOURCE)
    assert sent == [
        f"SELECT {select} FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),"
        "CIRCLE('ICRS',150.0000000000,2.0000000000,0.0500000000))"
    ]
    assert merged == [
        ("gaiadr3.astrophysical_parameters", gr.AP + gr.SPEC_AP, "gaia_ap_query_status"),
        (
            "gaiadr3.vari_classifier_result",
            ["best_class_name", "best_class_score"],
            "gaia_vari_classifier_query_status",
        ),
        ("gaiadr3.vari_summary", gr.VAR_SUMMARY, "gaia_vari_summary_query_status"),
    ]


def _one_row():
    df = pd.DataFrame({c: [np.nan] for c in gr.SOURCE})
    df["source_id"] = [1]
    df["ra"], df["dec"] = [150.0], [2.0]
    df["designation"] = ["Gaia DR3 1"]
    return df


def test_dr4_without_a_product_map_asks_no_dr4_table_and_uses_the_dr3_copy(monkeypatch, capsys):
    monkeypatch.setenv("V2_GAIA_RELEASE", "DR4")
    monkeypatch.delenv("V2_GAIA_SOURCE", raising=False)
    asked = []
    monkeypatch.setattr(g, "_bounded", lambda *a, **k: asked.append(a) or _one_row())
    copy = _one_row()
    copy["gaia_base_query_status"] = "vizier_fallback"
    monkeypatch.setattr(g, "_vizier_fallback", lambda ra, dec, r: copy.copy())
    monkeypatch.setattr(g, "_merge_fidelity", lambda df, deadline=None: df)
    out = g.fetch(150.0, 2.0, 3.0)
    assert asked == []  # no query was built from DR3's lists for a DR4 table
    assert set(out["gaia_release"]) == {"DR3"} and set(out["ref_epoch"]) == {2016.0}  # honestly labelled
    assert set(out["gaia_base_query_status"]) == {"vizier_fallback"}
    assert gr.RELEASES["DR4"].products is None and gr.RELEASES["DR4"].ref_epoch == 2017.5
    # not silent: the run log says DR4 was asked and the DR3 copy answered (2.60.6 review)
    assert "Gaia DR4 was requested; answered by the VizieR DR3 copy" in capsys.readouterr().out


def test_the_cache_key_names_the_release(monkeypatch):
    import archive_cache as ac

    monkeypatch.setenv("V2_GAIA_RELEASE", "DR3")
    a = ac._code_hash(Path(g.__file__))
    monkeypatch.setenv("V2_GAIA_RELEASE", "DR4")
    b = ac._code_hash(Path(g.__file__))
    assert a.endswith("-DR3") and b.endswith("-DR4") and a.split("-")[0] == b.split("-")[0]  # DR3 rows never serve DR4


# --------------------------------------------------------------------------------------------- schema comparison
def test_compare_tables_reports_what_the_draft_promised():
    draft = {"gaia_source": ["source_id", "ra", "tentative_parallax_bias"], "ap_xp": ["source_id", "teff_gspphot"]}
    live = {"gaia_source": ["source_id", "ra", "new_col"], "extra": ["x"]}
    r = chk.compare_tables(draft, live)
    assert r["missing_tables"] == ["ap_xp"] and r["new_tables"] == ["extra"]
    assert r["per_table"]["gaia_source"] == {
        "in_draft_not_in_archive": ["tentative_parallax_bias"],
        "in_archive_not_in_draft": ["new_col"],
    }
    assert chk.where_is(["ra", "teff_gspphot"], {"gaia_source": ["RA"], "ap_xp": ["teff_gspphot"]}) == {
        "ra": ["gaia_source"],
        "teff_gspphot": ["ap_xp"],
    }


def test_the_locked_draft_matches_the_comparison_file():
    d = json.loads((V2 / "benchmark" / "gaia_dr4" / "dr4_draft_tables.json").read_text())
    assert "tentative_parallax_bias" in d["gaia_source"] and "ap_xp" in d and "ap_class" in d
    assert "phot_bp_rp_excess_factor" not in d["all_source_photometry"]  # no excess factor in the draft
    rows = pd.read_csv(V2 / "benchmark" / "gaia_dr4" / "dr3_columns_vs_dr4_draft.csv")
    assert len(rows) == 64 and (rows.in_draft == "no").sum() == 7
    assert set(rows[rows.in_draft == "no"].column) == {
        "phot_bp_rp_excess_factor",
        "classprob_dsc_combmod_whitedwarf",
        "classprob_dsc_combmod_binarystar",
        "classlabel_espels_flag",
        "best_class_name",
        "best_class_score",
        "in_vari_classification_result",
    }


# --------------------------------------------------------------------------------------------- classification side
def test_dr3_assumptions_are_the_numbers_the_stages_always_used():
    a = GA.for_release("DR3")
    assert (a.parallax_offset_mas, a.ext_max_parallax_error_mas, a.crf_error_scale) == (0.017, 0.3, 1.1)
    assert (a.ruwe_binary, a.density_reference_deg2) == (1.4, 5000.0)


def test_cstar_matches_the_inline_formula_of_stage_4_and_the_star_branch():
    star = _load(V2 / "Classifier" / "branches" / "star.py", "t_star_branch")
    a = GA.for_release("DR3")
    for x in (-0.2, 0.0, 0.49, 0.5, 1.0, 3.99, 4.0, 5.5):
        assert a.cstar_correction(x) == star.corrected_excess_factor(0.0, x) * -1
    for g_mag in (8.0, 12.5, 17.0, 20.9):
        assert a.cstar_scatter(g_mag) == star.sigma_corrected_excess(g_mag)


def test_release_detection_and_dr4_refusal():
    assert GA.release_of(None) == "DR3" and GA.release_of([]) == "DR3" and GA.release_of([np.nan, None, ""]) == "DR3"
    assert GA.release_of(pd.Series(["DR3", "dr3", None])) == "DR3"
    assert GA.for_values(pd.Series(["DR3"])).release == "DR3"
    with pytest.raises(ValueError):
        GA.release_of(["DR3", "DR4"])  # one set of constants cannot serve two releases
    with pytest.raises(LookupError, match="not set"):
        GA.for_values(["DR4"])  # no silent DR3 assumptions for DR4 data
    with pytest.raises(ValueError):
        GA.for_release("DR9")
    assert set(GA.ASSUMPTIONS) <= set(gr.RELEASES) and set(GA.KNOWN_RELEASES) == set(gr.RELEASES)


def test_stage4_refuses_dr4_rows_instead_of_using_dr3_zero_point():
    s4 = _load(V2 / "Preprocess" / "04_build_evidence.py", "t_stage4")
    src = {"phot_bp_rp_excess_factor": 1.25, "bp_rp": 1.0, "phot_g_mean_mag": 15.0}
    dr3 = s4.cstar_sigma(src)
    assert dr3 == s4.cstar_sigma({**src, "gaia_release": "DR3"})
    with pytest.raises(LookupError):
        s4.cstar_sigma({**src, "gaia_release": "DR4"})
