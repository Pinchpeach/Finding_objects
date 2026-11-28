# Units of the position-error columns: what each collector stores, what the catalogue documents, what the code assumed (2.62.2)

Evidence levels: **text** = read in the original text (paper, survey documentation, a page fetched verbatim this session); **summary** = a fetch agent
passed a summary of a long page, not checked against the text; **data** = measured on the rows the collectors stored (335 regions + 3 real-use
fields, `check_units_from_rows.py`); **none** = not confirmed.  The VizieR ReadMe pages (`cdsarc.cds.unistra.fr`) are not reachable from the session
(DNS / 502), so for the VizieR tables the documented unit rests on the paper or on the data; `dump_vizier_units.py` reads the unit metadata from VizieR
itself and is the way to close every "none" below (run it where the network allows, e.g. in a workflow).

## 1. The table

| catalogue (collector) | position-error columns stored | documented unit | evidence | what the code assumed (`legacy`, the default) | verdict |
|---|---|---|---|---|---|
| **VLASS Epoch 1 QL** (`vlass`) | `e_RAJ2000`, `e_DEJ2000` (= `e_RAMdeg`, `e_DEMdeg`) | **degrees** | VizieR metadata (1b) and data: `e_RAJ2000` equals the `e_RAMdeg` column (named in degrees) in all 384 rows; median 2.2e-5, i.e. 0.079'' as degrees, 2e-5'' as arcsec (a 2.5'' beam at S/N ~ 10 gives ~0.1'', Condon 1997: sigma = beam / (2 S/N)); the catalogue's own accuracy is ~1'' / 0.5'' at Dec > -20 (text: Gordon et al. 2021, ApJS 255, 30, Sect. 2.1). Column unit in the CIRADA guide / ReadMe: none | arcsec | **wrong (x3600)** |
| **NVSS** (`nvss`) | `e_RAJ2000`, `e_DEJ2000` | RA **seconds of time**, Dec arcsec | VizieR metadata (1b) and data: e_RA x 15 cos(dec) / e_Dec has a median 0.94 over all 223 stored rows (the beam is circular at Dec > -10), read as arcsec 0.071; the NRAO page quotes rms 'in arcsec' in prose (text), the column table: none | arcsec | **wrong (RA x15 cos dec)** |
| TGSS ADR1 (`tgss`) | `e_RAJ2000`, `e_DEJ2000` | arcsec | text (PDF read locally): Intema et al. 2017, Sect. 3.4 "The 1-sigma uncertainty in the right ascension in arcseconds"; a 2'' systematic is added in quadrature (so the median 2.05 is the floor) | arcsec | ok |
| LoTSS DR2 (`lotss`) | `e_RAJ2000`, `e_DEJ2000` | arcsec (PyBDSF fitting error only; the astrometric 0.2'' is separate, Shimwell et al. 2022) | summary (VO table description found by search, not fetched); data: 8 rows in the low-latitude regions, `e_RAJ2000` 0.05-1.1 and it grows as the peak flux falls (0.06 at 15 mJy/beam, ~1 at 0.45 mJy/beam: beam / (2 S/N) for a 6'' beam read as arcsec) | arcsec | ok (8 rows only) |
| FIRST (`first`) | none (`Rms` = local noise in mJy, `Maj`, `Min`, `fMaj`) | - | text (FIRST catalogue readme, verbatim by a fetch agent): "unc(90% confidence) = Size (1/SNR + 1/20) arcsec", "Rms is a local noise estimate ... in mJy" | profile constant 1.0'' | not a unit problem; per-source information unused |
| eRASS1 (`erosita`) | `posErr` (also `RADEErr`, `e_RA_ICRS`, `E_RA_ICRS`) | arcsec, 1 sigma, systematic sigma_0 = 0.9'' included | text: Merloni et al. 2024, Sect. 6.2 "circular, Gaussian positional uncertainty with a standard deviation" and sigma_0 = 0.9''; data median 4.9'' | `posErr` as arcsec | ok |
| 4XMM (`xmm`) | `ePos` (= SC_POSERR) | arcsec, 1 sigma, systematic included | text: Webb et al. 2020, Sect. 3.3 (SC_POSERR from RADEC_ERR and SYSERRCC; the unit is not written there, the systematics are in arcsec); data median 0.84'' | `ePos` as arcsec | ok |
| Chandra CSC (`chandra`) | `r0`, `r1` (+ `PA`) | arcsec, semi-axes of the **95 %** error ellipse | text: CSC column documentation "the radii ... correspond to the 95% confidence intervals along these axes"; unit arcsec from the dictionary row (summary); data median r0 0.93'' | `r0 / 2.448` (+) 0.16'' | ok (the CSC 2.1 systematic is 0.29'' at 95 % = 0.12'' at 1 sigma; the code keeps 0.16'') |
| GALEX AIS (`galex`) | `Nerr`, `Ferr`, `Ierr`, `Nperr`, `Fperr` | arcsec: VizieR II/335 ReadMe (CfA mirror, 2026-11-28) `arcsec Nerr [0.4/3.3] Position error of the source in the NUV image (nuv_poserr)`, `Ferr` FUV, `Ierr` inter-band, `Nperr`/`Fperr` Poisson part; **1 sigma or radial: not stated** (ReadMe, Bianchi et al. 2017) | ReadMe text (VERIFIED, mirror); data medians 1.5, 1.3, 1.3, 0.59, 0.22'' | profile constant 0.8'' (Morrissey et al. 2007: 0.49 / 0.59'' absolute, S/N >= 10, R < 0.6 deg) | not a unit problem; unused until 2.62.4 (`V2_POSERR_NATIVE=galex` reads `Nerr`, then `Ferr`; measured in WORK_REPORT_2026-11-28b.md: no gain) |
| AllWISE (`allwise`) | `eeMaj`, `eeMin`, `eePA`, `e_RA_pm`, `e_DE_pm` (not `sigra`) | arcsec: VizieR II/328 ReadMe (CfA mirror, 2026-11-28) `arcsec eeMaj Semi-major axis of the error ellipse (1)`; note (1): the ellipse "is computed from the 1-sigma in RA and Dec (sigra, sigdec) and the co-sigma sigradec", so `eeMaj` is a **1-sigma semi-axis in arcsec**; IRSA: `sigra` "One-sigma uncertainty in right ascension", arcsec. `e_RA_pm`: unit arcsec, relation to IRSA `sigra_pm` not stated. `eePA` was east-of-north corrected 2021-02-16 (use 90 - old value) | ReadMe + explanatory supplement (VERIFIED, mirror); data medians 0.34 / 0.31 / 0.41 / 0.46'' (`eeMaj` and `e_RA_pm` correlate 0.99) | profile constant 0.5'' (the pair `sigra` / `sigdec` is not in the VizieR table) | not a unit problem; unused until 2.62.4 (`V2_POSERR_NATIVE=allwise` reads `eeMaj`; the PSF/6 floor 1.02'' still decides sigma, the order of the detections changes: WORK_REPORT_2026-11-28b.md) |
| 2MASS PSC (`twomass`) | `errMaj`, `errMin` | arcsec | data median 0.08''; not re-read | `errMaj` | ok (not re-verified) |
| Gaia DR3 (`gaia_dr3`) | `ra_error`, `dec_error` | mas (includes cos dec) | the GDR3 datamodel page was a stub; data median 0.28 | / 1000 | ok (not re-verified; unchanged since 2.19.0) |
| Pan-STARRS1 DR2 (`panstarrs1`) | `raMeanErr`, `decMeanErr` | arcsec; **the standard deviation of the single-epoch RAs**, not the error of the mean | summary (STScI ObjectThin definition found by search); data median 0.05'' | arcsec | ok (units); semantics: a scatter, no systematic floor except the 0.02'' pair floor and PSF / 6 |
| Legacy Surveys DR10 (`desi_legacy`) | `ra_ivar`, `dec_ivar` | 1/deg^2, RA **without** the cos(dec) term, "excluding astrometric calibration errors" | text: legacysurvey.org/dr10/catalogs (verbatim); data median 0.049'' | cos(dec) / sqrt(ivar) x 3600, 0.6'' floor for resolved types | ok |
| SDSS DR18 (`sdss_dr18`) | none (`raErr`, `decErr` not collected) | - | schema page not readable | profile constant 0.6'' (0.1'' bright point sources with `profiles`) | not a unit problem |
| SIMBAD (`simbad`) | `coo_err_maj`, `coo_err_min`, `coo_err_angle` | mas, mas, deg: SIMBAD TAP schema (`basic`; simbad.harvard.edu mirror, 2026-11-28); 1 sigma / semi-axis **not stated** | TAP schema (VERIFIED, mirror); data: 19 of 3,226 COSMOS rows filled, median 150 mas (= 0.15''); `coo_qual` (quality A-E) is not collected | profile constant 0.6'' | not a unit problem; unused until 2.62.4 (`V2_ANNOT_ASSOC=err` reads `coo_err_maj` / 1000) |
| Galaxy Zoo DESI, SGA-2020 | `poserr_arcsec` written by the collector (0.1'', 1.0'') | arcsec by construction | - | read as given | ok |
| the other collectors (ATNF, BZCAT, HASH PN, MYStIX, ASAS-SN / Asiago SN, LAMOST, DESI spectroscopy / FastSpecFit, ZTF, Suh AGB) | none stored | - | - | profile constants in `PROFILES` | not a unit problem |

Only the two rows in bold had a wrong unit.  Everything else that reaches `infer_poserr_arcsec` is arcsec (or, for Gaia, mas and divided).

## 1b. The units VizieR documents (2026-11-28, `v2_vizier_units.yml` runs 46087889093 and 46088138972, served by the CfA mirror)

`dump_vizier_units.py` read the `unit` and `description` VizieR stores for every column below.  Strasbourg answered 404; the mirror failover served CfA.

| catalogue | column: unit (description) | agrees with the code |
|---|---|---|
| NVSS `VIII/65/nvss` | `e_RAJ2000`: **s** ("Mean error on RA"), `e_DEJ2000`: arcsec ("Mean error on Dec") | **yes, the fix** (RA in seconds of time, Dec in arcsec) |
| VLASS `J/ApJS/255/30/comp` | `e_RAJ2000`, `e_DEJ2000`: **deg** ("1-sigma uncertainty in RA (E_RA)" / "in DEC (E_DEC)"), `e_RAMdeg`, `e_DEMdeg`: deg, `Maj`, `e_Maj`: arcsec (run 46088138972, 0.5 deg cone; the first run's 0.1 deg cone had no row) | **yes, the fix** (degrees x 3600) |
| LoTSS DR2 `J/A+A/659/A1/catalog` | `e_RAJ2000`, `e_DEJ2000`: arcsec ("rms uncertainty on RA (E_RA)") | yes (read as arcsec) |
| TGSS ADR1 `J/A+A/598/A78/table3` | `e_RAJ2000`, `e_DEJ2000`: arcsec ("Uncertainty on right ascension (1 sigma)") | yes |
| GALEX `II/335/galex_ais` | `Nerr`, `Ferr`, `Ierr`, `Nperr`, `Fperr`, `Sep`: arcsec | yes |
| AllWISE `II/328/allwise` | `eeMaj`, `eeMin`, `e_RA_pm`, `e_DE_pm`: arcsec | yes |
| 2MASS `II/246/out` | `errMaj`, `errMin`: arcsec | yes |
| Chandra CSC `IX/57/csc2master` | `r0`, `r1`: arcsec ("radius of the 95% confidence level position error ellipse"), `PA`: deg | yes (95 % radius / 2.448) |
| eRASS1 `J/A+A/682/A34` | `posErr` ("1-sigma positional uncertainty"), `RADEErr`, `e_RA_ICRS`, `E_RA_ICRS`: arcsec | yes |
| 4XMM `IX/69/xmm4d13s` | `ePos` ("Mean error on position (SC_POSERR)"): arcsec | yes |
| FIRST `VIII/92/first14` | `Rms`: mJy, `Maj`, `Min`: arcsec (no position-error column) | yes (profile constant) |

## 2. What the fix is

`association_model.native_radec_errors_arcsec` converts the `e_RAJ2000` / `e_DEJ2000` pair per catalogue: VLASS x 3600; NVSS RA x 15 cos(dec), Dec as is;
everything else as before.  `V2_POSERR_UNITS=legacy` (the default since 2.62.2, until `fixed` becomes the default) keeps the reading of the earlier releases.  A row-by-row check over every stored raw file
(`check_units_from_rows.py`, result in `results_2026-11-27h/rows_changed.csv`: 860 000 rows of 22 catalogues, **only VLASS (314 of 384 rows) and NVSS (70 of 223) change**) lists exactly which rows change; the unit test
`test_poserr_units.py::test_nothing_else_changes_between_fixed_and_legacy` fixes the same for one row of every other catalogue.

## 3. What this study could not confirm, and the way to close it

* VizieR ReadMe / column units of VLASS (`J/ApJS/255/30`), NVSS (`VIII/65`), LoTSS (`J/A+A/659/A1`), GALEX (`II/335`), AllWISE (`II/328`), 2MASS,
  Gaia, SIMBAD: `python dump_vizier_units.py` (astroquery returns the `unit` and `description` of every column; it needs the network the session does not have).
* Only 8 LoTSS rows are stored; a larger LoTSS field would tighten the check of `e_RAJ2000` against the documented arcsec.
* The CIRADA user guide (`sao.ru/cats/doc/VLASS.html`) answered 503 twice.

## 4. Truth for radio counterparts

The VLA-COSMOS 3 GHz Large Project is usable as truth for a radio-optical join in the 26 deep COSMOS fields (summary of search results; the papers were not
read in full): Smolcic et al. 2017, A&A 602, A1 (the continuum catalogue: 10 830 radio sources to 5 sigma over 2 deg^2, 0.75'' resolution, median rms 2.3 uJy/beam;
VizieR `J/A+A/602/A1`) and the companion paper A&A 602, A2 whose VizieR table lists 9 161 optical / mid-infrared counterparts (COSMOS2015, i band, IRAC), with the
flag of the COSMOS2015 masked area (`flag_C15 = 0` is the 1.77 deg^2 unmasked part).  The fields of this study lie inside the 2 deg^2.  Not done here: the tables
are VizieR downloads (unreachable from the session), and the 61 VLASS rows of those fields (41 within 1'' of an optical row) cannot show a false-join rate below
0/41 = 8.6 % (Wilson 95 % upper bound) anyway; the radio rows of the 2.60.9 association measurement are not in it either (it used COSMOS2020 fluxes of AllWISE, 2MASS, GALEX).
What the study can say without radio truth is therefore how many rows change status and objects change anchor, not whether the new status is right; for the VLASS
rows whose status changes, the separations to the optical row are listed in `results_2026-11-27h/` so the size of the change can be read against the 0.5'' / 1''
astrometric accuracy of the Quick Look images.
