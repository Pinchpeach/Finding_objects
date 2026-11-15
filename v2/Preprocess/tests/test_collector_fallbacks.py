"""PS1 and SIMBAD alternative sources when the primary archive fails (2.54.0)."""

import sys
from pathlib import Path

import pandas as pd

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import _catalog_utils  # noqa: E402
import panstarrs1  # noqa: E402
import simbad  # noqa: E402


def _ii389():
    # columns as VizieR II/389/ps1_dr2 serves them (practical-use probe, 2026-11-15)
    d = {"objID": [108761501191226839, 108761501191226840], "RAJ2000": [150.1191, 150.1195], "DEJ2000": [2.2058, 2.2061],
         "e_RAJ2000": [0.01, 0.02], "e_DEJ2000": [0.01, 0.02], "Nd": [12, 3], "Epoch": [56000.1, 56001.0],
         "f_objID": [1, 2], "Qual": [52, 60]}
    for b in "grizy":
        d.update({f"N{b}": [3, 1], f"{b}mag": [20.0, 21.0], f"e_{b}mag": [0.02, 0.05], f"{b}magStd": [0.03, 0.1],
                  f"o_{b}mag": [3, 1], f"{b}Kmag": [19.8, 21.0], f"e_{b}Kmag": [0.03, 0.06]})
    return pd.DataFrame(d)


def test_ps1_uses_the_vizier_dr2_copy_when_mast_fails(monkeypatch, tmp_path):
    def mast_down(*a, **k):
        raise ConnectionError("certificate verify failed")

    monkeypatch.setattr(panstarrs1, "_fetch_mast", mast_down)
    monkeypatch.setattr(_catalog_utils, "vizier_cone", lambda cat, *a, **k: _ii389() if cat == "II/389/ps1_dr2" else None)
    d = panstarrs1.fetch(150.1191, 2.2058, 1.0)
    assert len(d) == 2 and set(d.ps1_query_status) == {"vizier_fallback"}
    assert d.catalog.iloc[0] == panstarrs1.CATALOG  # the same catalogue for Stage 1
    r = d.set_index("catalog_object_id").loc["108761501191226839"]
    assert r.gMeanPSFMag == 20.0 and r.gMeanKronMag == 19.8 and r.nDetections == 12
    assert r.gMeanPSFMagStd == 0.03 and r.gMeanPSFMagNpt == 3 and r.ng == 3
    assert pd.isna(r.gMeanApMag)  # not in the copy
    panstarrs1.save(d, tmp_path / "ps1.csv")
    assert set(panstarrs1.COLUMNS) <= set(pd.read_csv(tmp_path / "ps1.csv").columns)


def test_ps1_vizier_copy_keeps_the_detection_cut(monkeypatch):
    v = _ii389()
    v.loc[1, "Nd"] = 1
    monkeypatch.setattr(_catalog_utils, "vizier_cone", lambda *a, **k: v)
    assert len(panstarrs1._fetch_vizier(150.1191, 2.2058, 1.0)) == 1


def test_simbad_falls_back_to_the_harvard_mirror(monkeypatch):
    from astropy.table import Table

    tried = []

    class Client:
        def query_tap(self, q):
            raise RuntimeError("no TAP in this test")

    def query(server, ra, dec, radius):
        tried.append(server)
        if server == "simbad.cds.unistra.fr":
            raise RuntimeError("404 Not Found: sim-tap/capabilities")
        return Client(), Table({"main_id": ["NGC 4522"], "ra": [188.4155], "dec": [9.1751], "otype": ["G"]})

    monkeypatch.setattr(simbad, "_query", query)
    d = simbad.fetch(188.4155, 9.1751, 1.0)
    assert tried == ["simbad.cds.unistra.fr", "simbad.harvard.edu"]
    assert d.object_name.tolist() == ["NGC 4522"] and d.simbad_server.iloc[0] == "simbad.harvard.edu"
    assert d.simbad_reference_query_status.iloc[0].startswith("error")  # references failed: not cached
