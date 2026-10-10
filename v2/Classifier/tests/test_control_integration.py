#!/usr/bin/env python3
"""End-to-end smoke test for the main Classifier/control.py entry point."""
from __future__ import annotations
import importlib.util
import tempfile
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("classifier_control",ROOT/"control.py")
control=importlib.util.module_from_spec(spec); spec.loader.exec_module(control)

rows=[
    {
        "object_uid":"wd1","primary_class":"STAR",
        "classprob_dsc_combmod_whitedwarf":0.95,
        "classprob_dsc_combmod_star":0.02,
    },
    {
        "object_uid":"rgb_rr","primary_class":"STAR",
        "classprob_dsc_combmod_star":0.96,
        "evolstage_flame":700,"logg_gspphot":2.4,
        "mass_flame":1.2,"age_flame":5.0,
        "best_class_name":"RR","best_class_score":0.91,
    },
    {
        "object_uid":"sn1","primary_class":"UNKNOWN",
        "best_class_name":"SN","best_class_score":0.93,
    },
]
with tempfile.TemporaryDirectory() as td:
    td=Path(td); inp=td/"input.csv"; out=td/"output.csv"
    pd.DataFrame(rows).to_csv(inp,index=False)
    control.run(inp,out)
    d=pd.read_csv(out).set_index("object_uid")
    assert d.loc["wd1","physical_class"]=="WD",d.loc["wd1"].to_dict()
    assert d.loc["rgb_rr","physical_class"]=="RGB",d.loc["rgb_rr"].to_dict()
    assert d.loc["rgb_rr","variability_class"]=="RR_LYRAE",d.loc["rgb_rr"].to_dict()
    assert "variability_subtype" in d.columns
    assert d.loc["sn1","phenomenon_class"]=="SN",d.loc["sn1"].to_dict()
    assert "compact_status" in d.columns
    assert "extragalactic_status" in d.columns
print("[OK] main classifier controller integration")


def test_qso_branch_uses_catalog_membership_for_detections():
    import importlib.util
    from pathlib import Path
    p=Path(__file__).resolve().parents[1]/"branches"/"qso.py"
    s=importlib.util.spec_from_file_location("qso_branch",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
    r=m.classify({"catalogs":"Gaia DR3|NVSS","first__catalog_object_id":"J1"})
    assert r["radio_detected"] is True and r["xray_detected"] is False
    r=m.classify({"catalogs":"Gaia DR3","nvss__RAJ2000":188.4})
    assert r["radio_detected"] is False
    assert m.classify({"rx_radio_peak":2.5})["radio_detected"] is True
