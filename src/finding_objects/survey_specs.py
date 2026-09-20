"""Survey specifications used by counterpart inference.
Official footprint membership should be supplied by survey-specific footprint services/maps.
FWHM values are explicit defaults and must be provenance-tracked/calibrated before science release.
"""
SURVEY_SPECS={
"GALEX":{"fwhm_arcsec":5.0,"footprint_provider":"official_required"},
"Pan-STARRS_DR1":{"fwhm_arcsec":1.1,"footprint_provider":"official_required"},
"2MASS":{"fwhm_arcsec":2.5,"footprint_provider":"official_required"},
"AllWISE":{"fwhm_arcsec":6.1,"footprint_provider":"official_required"},
"NVSS":{"fwhm_arcsec":45.0,"footprint_provider":"official_required"},
"FIRST":{"fwhm_arcsec":5.0,"footprint_provider":"official_required"},
"Planck_PCCS2":{"fwhm_arcsec":None,"footprint_provider":"official_required","note":"use frequency-dependent official FWHM"},
"XMM_4XMM":{"fwhm_arcsec":None,"footprint_provider":"official_required","note":"use source/observation-specific PSF/positional error"},
}
