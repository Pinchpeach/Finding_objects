"""PS1 and SIMBAD alternative sources when the primary archive fails (2.54.0)."""

import sys
from pathlib import Path

import pandas as pd

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import _catalog_utils  # noqa: E402
import atnf_pulsar  # noqa: E402
import panstarrs1  # noqa: E402
import simbad  # noqa: E402


def _ii389():
    # columns as VizieR II/389/ps1_dr2 serves them (practical-use probe, 2026-11-15)
    d = {
        "objID": [108761501191226839, 108761501191226840],
        "RAJ2000": [150.1191, 150.1195],
        "DEJ2000": [2.2058, 2.2061],
        "e_RAJ2000": [0.01, 0.02],
        "e_DEJ2000": [0.01, 0.02],
        "Nd": [12, 3],
        "Epoch": [56000.1, 56001.0],
        "f_objID": [1, 2],
        "Qual": [52, 60],
    }
    for b in "grizy":
        d.update(
            {
                f"N{b}": [3, 1],
                f"{b}mag": [20.0, 21.0],
                f"e_{b}mag": [0.02, 0.05],
                f"{b}magStd": [0.03, 0.1],
                f"o_{b}mag": [3, 1],
                f"{b}Kmag": [19.8, 21.0],
                f"e_{b}Kmag": [0.03, 0.06],
            }
        )
    return pd.DataFrame(d)


def test_ps1_uses_the_vizier_dr2_copy_when_mast_fails(monkeypatch, tmp_path):
    def mast_down(*a, **k):
        raise ConnectionError("certificate verify failed")

    monkeypatch.setattr(panstarrs1, "_fetch_mast", mast_down)
    monkeypatch.setattr(
        _catalog_utils, "vizier_cone", lambda cat, *a, **k: _ii389() if cat == "II/389/ps1_dr2" else None
    )
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


def test_simbad_falls_back_to_the_harvard_mirror(monkeypatch, tmp_path):
    """2.60.0: the direct TAP query (one POST) asks the mirror when Strasbourg answers 404."""

    class Table:  # what fetch() uses of an astropy table (no astropy in the Preprocess CI job)
        def __init__(self, cols):
            self.cols = cols

        def to_pandas(self):
            return pd.DataFrame(self.cols)

        def __len__(self):
            return len(next(iter(self.cols.values())))

    tried = []

    def tap(server, adql, maxrec=simbad.MAXREC):
        tried.append(server)
        if server == "simbad.cds.unistra.fr":
            raise simbad._ServerFailed("HTTP 404")
        if "has_ref" in adql:
            raise RuntimeError("references failed in this test")
        return Table({"main_id": ["NGC 4522"], "ra": [188.4155], "dec": [9.1751], "otype": ["G"]}), False

    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(simbad, "_tap_sync", tap)
    monkeypatch.setattr(simbad, "_cone_numbers", lambda ra, dec, r: (ra, dec, r / 60.0))
    d = simbad.fetch(188.4155, 9.1751, 1.0)
    assert tried == ["simbad.cds.unistra.fr", "simbad.harvard.edu", "simbad.harvard.edu"]  # CDS, cone, references
    assert d.object_name.tolist() == ["NGC 4522"] and d.simbad_server.iloc[0] == "simbad.harvard.edu"
    assert d.simbad_reference_query_status.iloc[0].startswith("error")  # references failed: not cached


def test_simbad_astroquery_path_when_the_direct_query_is_rejected(monkeypatch, tmp_path):
    """A column SIMBAD renamed (plx -> plx_value was one) is a 400: astroquery's mapping takes over."""

    class Table:
        def to_pandas(self):
            return pd.DataFrame({"main_id": ["NGC 4522"], "ra": [188.4155], "dec": [9.1751], "otype": ["G"]})

    class Client:
        def query_tap(self, q):
            raise RuntimeError("no TAP in this test")

    def rejected(server, adql, maxrec=simbad.MAXREC):
        raise simbad._QueryRejected("Incorrect ADQL query: 1 unresolved identifiers: plx_value")

    tried = []

    def query(server, ra, dec, radius):
        tried.append(server)
        return Client(), Table()

    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(simbad, "_tap_sync", rejected)
    monkeypatch.setattr(simbad, "_cone_numbers", lambda ra, dec, r: (ra, dec, r / 60.0))
    monkeypatch.setattr(simbad, "_query", query)
    d = simbad.fetch(188.4155, 9.1751, 1.0)
    assert tried == ["simbad.cds.unistra.fr"] and d.object_name.tolist() == ["NGC 4522"]
    assert d.simbad_reference_query_status.iloc[0].startswith("error")


def test_atnf_uses_the_vizier_copy_when_heasarc_fails(monkeypatch):
    def overloaded(*a, **k):
        raise RuntimeError("DALQueryError: System overloaded. Please try again later.")

    v = pd.DataFrame(
        {"PSRJ": ["J1234+0901", "J1235+0902"], "_RAJ2000": [188.5, 188.75], "_DEJ2000": [9.02, 9.03], "P0": [0.5, 1.2]}
    )
    monkeypatch.setattr(atnf_pulsar, "_fetch_heasarc", overloaded)
    monkeypatch.setattr(_catalog_utils, "vizier_cone", lambda cat, *a, **k: v if cat == "B/psr/psr" else None)
    d = atnf_pulsar.fetch(188.5, 9.0, 2.0)
    assert d.catalog.unique().tolist() == [atnf_pulsar.CATALOG]  # the same catalogue for Stage 1 and the compact axis
    assert d.catalog_object_id.tolist() == ["J1234+0901", "J1235+0902"] and d.ra.tolist() == [188.5, 188.75]
    assert set(d.atnf_query_status) == {"vizier_fallback"}


def test_atnf_slow_heasarc_is_abandoned(monkeypatch):
    import time as _t

    monkeypatch.setattr(atnf_pulsar, "HEASARC_BUDGET_S", 0.2)
    monkeypatch.setattr(atnf_pulsar, "_fetch_heasarc", lambda *a: _t.sleep(5))
    monkeypatch.setattr(_catalog_utils, "vizier_cone", lambda *a, **k: None)
    t0 = _t.monotonic()
    d = atnf_pulsar.fetch(188.5, 9.0, 2.0)
    assert d.empty and _t.monotonic() - t0 < 2
