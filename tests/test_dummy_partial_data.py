import numpy as np
import pandas as pd

from finding_objects.sed import build_sed
from finding_objects.spectrum import identify_lines
from finding_objects.classification import classify_from_lines, line_tags


def make_dummy_photometry(missing=("u",)):
    bands = {"u": (3551., 21.3), "g": (4686., 20.4), "r": (6165., 19.8),
             "i": (7481., 19.5), "z": (8931., 19.3)}
    return pd.DataFrame([
        {"band": b, "effective_wavelength_angstrom": w, "ab_mag": mag}
        for b, (w, mag) in bands.items() if b not in missing
    ])


def make_dummy_spectrum(z=0.05):
    wave = np.arange(3800., 7200., 1.)
    flux = np.ones_like(wave)
    # Strong nebular emission plus one metal absorption feature.
    for rest, amp in [(4861.3, 7.), (5006.8, 10.), (6562.8, 12.)]:
        center = rest * (1 + z)
        flux += amp * np.exp(-0.5 * ((wave-center)/1.3)**2)
    center = 3933.7 * (1 + z)
    flux -= 4.0 * np.exp(-0.5 * ((wave-center)/1.0)**2)
    return pd.DataFrame({"wavelength_angstrom": wave, "flux": flux})


def test_partial_photometry_continues_without_u_band():
    sed = build_sed(make_dummy_photometry())
    assert sed["band"].tolist() == ["g", "r", "i", "z"]
    assert len(sed) == 4


def test_partial_spectrum_detects_only_covered_lines():
    z = 0.05
    spectrum = make_dummy_spectrum(z)
    lines = identify_lines(spectrum, redshift=z, sigma_threshold=3)
    names = {line.name for line in lines}
    assert {"Halpha", "Hbeta", "OIII_5007", "CaII_K"} <= names
    assert "Lyalpha" not in names
    tags = line_tags(lines)
    assert "line:Halpha:emission" in tags
    assert "line:CaII_K:absorption" in tags


def test_no_spectrum_is_a_status_not_a_classification_failure():
    record = {"spectrum_status": "not_observed", "line_tags": [],
              "object_tags": ["spectrum:not_observed", "object:photometry_only"]}
    assert record["spectrum_status"] == "not_observed"
    assert record["line_tags"] == []


def test_no_response_is_distinct_from_not_observed():
    assert "spectrum:no_response" != "spectrum:not_observed"


def test_dummy_lines_produce_conservative_object_class():
    lines = identify_lines(make_dummy_spectrum(), redshift=.05, sigma_threshold=3)
    object_type, tags = classify_from_lines(lines)
    assert object_type == "emission_line_object"
    assert "object:emission_line_object" in tags


def test_partial_photometry_adapter_skips_missing_and_invalid_bands():
    from finding_objects.sdss import photometry_from_sdss_row
    row = pd.Series({"OBJID": 42, "G": 20.4, "r": 19.8, "i": np.nan, "z": 19.3})
    phot = photometry_from_sdss_row(row)
    assert phot["band"].tolist() == ["g", "r", "z"]
    assert "u" not in phot["band"].tolist()
