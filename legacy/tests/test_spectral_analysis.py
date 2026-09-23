import numpy as np
import pandas as pd

from finding_objects.catalog import build_search_index
from finding_objects.classification import SpectralLine, classify_from_lines, line_tags
from finding_objects.sed import build_sed
from finding_objects.spectrum import identify_lines


def test_build_sed_from_ab_magnitudes():
    p = pd.DataFrame({
        "band": ["r", "g"],
        "effective_wavelength_angstrom": [6200.0, 4800.0],
        "ab_mag": [20.0, 21.0],
    })
    sed = build_sed(p)
    assert sed["band"].tolist() == ["g", "r"]
    assert (sed["flux_density_jy"] > 0).all()
    assert (sed["nu_fnu_jy_hz"] > 0).all()


def test_synthetic_emission_lines_and_tags():
    wave = np.arange(4800.0, 6650.0, 1.0)
    flux = np.ones_like(wave)
    for center, amp in [(4861.3, 8.0), (5006.8, 12.0), (6562.8, 15.0)]:
        flux += amp * np.exp(-0.5 * ((wave - center) / 1.2) ** 2)
    lines = identify_lines(pd.DataFrame({"wavelength_angstrom": wave, "flux": flux}),
                           sigma_threshold=3.0)
    names = {x.name for x in lines}
    assert {"Halpha", "Hbeta", "OIII_5007"} <= names
    object_type, tags = classify_from_lines(lines)
    assert object_type == "emission_line_object"
    assert "object:emission_line_object" in tags
    assert "line:Halpha:emission" in line_tags(lines)


def test_absorption_line_tag():
    wave = np.arange(3900.0, 4000.0, 0.5)
    flux = np.ones_like(wave)
    flux -= 0.7 * np.exp(-0.5 * ((wave - 3933.7) / 0.8) ** 2)
    lines = identify_lines(pd.DataFrame({"wavelength_angstrom": wave, "flux": flux}),
                           sigma_threshold=3.0)
    assert any(x.name == "CaII_K" and x.kind == "absorption" for x in lines)


def test_search_index_keeps_line_and_object_tags_separate():
    record = {
        "object_id": "demo-1",
        "object_type": "emission_line_object",
        "redshift": 0.1,
        "line_tags": ["line:Halpha:emission", "line:OIII_5007:emission"],
        "object_tags": ["object:emission_line_object"],
    }
    idx = build_search_index([record])
    assert "line:Halpha:emission" in idx.loc[0, "line_tags"]
    assert idx.loc[0, "object_tags"] == "object:emission_line_object"
