"""Survey specifications from official project documentation.
FWHM is resolution/PSF context; positional errors should be preferred when available.
"""
SURVEY_SPECS={
"GALEX":{"footprint":"observed tiles only; mission observed ~77% of sky","fwhm_arcsec":5.3,"fwhm_note":"NUV; FUV ~4.2","astrometry_arcsec":None,"official":"https://archive.stsci.edu/missions-and-data/galex"},
"2MASS":{"footprint":"99.997% PSC nominal sky coverage","fwhm_arcsec":2.5,"fwhm_note":"practical minimum ~2.4-2.5 arcsec","astrometry_arcsec":0.1,"official":"https://irsa.ipac.caltech.edu/data/2MASS/docs/releases/allsky/doc/sec2_2.html"},
"AllWISE":{"footprint":"all-sky Atlas tile tessellation; depth varies","fwhm_arcsec":6.1,"fwhm_note":"W1 representative; band dependent","astrometry_arcsec":None,"official":"https://irsa.ipac.caltech.edu/data/WISE/docs/release/AllWISE/expsup/sec4_2.html"},
"NVSS":{"footprint":"declination > -40 deg","fwhm_arcsec":45.0,"fwhm_note":"1.4 GHz maps","astrometry_arcsec":5.0,"official":"https://science.nrao.edu/science/surveys"},
"FIRST":{"footprint":"coverage-map based; NGC4522 coordinates lie inside broad northern bounds but map coverage must decide","fwhm_arcsec":5.4,"fwhm_note":"northern beam circular 5.4 arcsec","astrometry_arcsec":1.0,"official":"https://sundog.stsci.edu/first/catalogs/"},
"XMM":{"footprint":"pointed observations only; use observation footprint, not empty catalogue as non-detection","fwhm_arcsec":None,"fwhm_note":"source/observation dependent; use catalogue positional error","astrometry_arcsec":None,"official":"https://xmmssc.irap.omp.eu/"}
}
