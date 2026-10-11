import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _compact():
    spec = importlib.util.spec_from_file_location("v2_compact_t", ROOT / "axes" / "compact.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_radio_pulsar_candidate_rule():
    c = _compact()
    # alpha(150 MHz - 1.4 GHz) = -1.75, compact, 20 % polarised -> candidate
    psr = {"nvss__S1.4": 3.0, "tgss_adr1__Stotal": 150.0, "tgss_adr1__Speak": 130.0, "nvss__polFlux": 0.6}
    r = c.classify(psr)
    assert r["label"] == "PULSAR_CANDIDATE" and r["evidence"][0]["alpha_150_1400"] < -1.5
    assert c.classify(dict(psr, **{"nvss__S1.4": 30.0}))["label"] == "UNKNOWN"          # alpha = -0.7: ordinary source
    assert c.classify(dict(psr, **{"tgss_adr1__Speak": 60.0}))["label"] == "UNKNOWN"    # extended (S_tot/S_peak = 2.5)
    assert c.classify(dict(psr, **{"nvss__polFlux": 0.05}))["label"] == "UNKNOWN"      # 1.7 % polarised
    # Catalogue evidence still wins.
    assert c.classify(dict(psr, catalogs="ATNF Pulsar Catalog"))["label"] == "PULSAR"


def test_radio_collectors_convert_sexagesimal_positions():
    """NVSS / FIRST RAJ2000 are sexagesimal strings in VizieR; they must not become NaN."""
    import pandas as pd
    for name in ("nvss", "first"):
        spec = importlib.util.spec_from_file_location(f"v2_{name}_t", ROOT.parent / "Get_data" / f"{name}.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        df = pd.DataFrame({"RAJ2000": ["00 34 08.71"], "DEJ2000": ["-07 21 53.4"]})
        try:
            ra, dec = m._degrees(df)
            assert abs(ra.iloc[0] - 8.53629) < 1e-4 and abs(dec.iloc[0] + 7.36483) < 1e-4
        except ImportError:          # astropy missing: only the computed-column path can be checked
            pass
        df["_RAJ2000"], df["_DEJ2000"] = [8.5363], [-7.3648]
        ra, dec = m._degrees(df)
        assert ra.iloc[0] == 8.5363 and dec.iloc[0] == -7.3648
