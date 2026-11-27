#!/usr/bin/env python3
"""The table of the bare columns that two or more catalogues share (2.61.4): ``shared_columns.csv``.

    python build_table.py            # writes shared_columns.csv next to this file

``shared_candidates.json`` is the list the table starts from: every field name that two or more collectors write, with the raw-file
prefix of each collector (the headers of the raw files of the 26 deep COSMOS fields, the 309 low-latitude regions and the real-use
fields).  The same names are ``SHARED_FIELDS`` of ``Preprocess/02_integrate_objects.py`` (a test keeps the two equal).  The reader
columns were filled by reading the code (``rg`` for each name in ``v2``, excluding ``legacy/`` and the truth-set builders, which
read external tables, not Stage 2 products); the test column is computed here.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parents[1]

# curated: where the bare name of a Stage 2 table is (or was) read.  Everything not listed here has no reader of the bare name.
READERS = {
    "type": ("04_build_evidence.py:557,567 (SDSS-PHOTO rules, through CatalogFields: namespaced when the table has the catalogue; a "
             "table without any sdss_dr18_photoobj__ column fell back to the bare name = Legacy Surveys' string); "
             "coarse_gbm.py:71 (LS point-source flag: fall-back to the bare name when desi_legacy_surveys_dr10__type is absent, which "
             "turned SDSS's numeric type into 'not PSF' instead of 'unknown'); Stage 1 association_model.py:314 reads the raw row, not Stage 2",
             "04 CatalogFields unchanged (fall-back kept for namespace-less benchmark tables: nothing bare any more); coarse_gbm fall-back kept for the benchmark's one-catalogue tables"),
    "Type": ("04_build_evidence.py:697 (NED type, CatalogFields); 03_extract_features.py:333 field('ned','Type') (without a NED namespace "
             "it accepted the bare Type of another catalogue and created an all-empty catalog_confidence_ned_type); Classifier/axes/variability.py "
             "reads ZTF's namespaced Type",
             "none needed: the fall-back finds nothing now (the all-empty column catalog_confidence_ned_type is no longer created without NED)"),
    "pmra": ("03_extract_features.py:60 and 04_build_evidence.py:361 (Gaia motion, through field()/CatalogFields: bare fall-back only when the "
             "table has no gaia_dr3 namespace); Classifier/branches/star.py:143 _gaia_num and Classifier/subclass.py:669 star_tags (bare fall-back = SIMBAD's "
             "pmra when Gaia is absent); coarse_gbm.py:56; Classifier/validate_real_samples.py:224 (snapshot)",
             "star.py, subclass.py and validate_real_samples.py now read gaia_dr3__pmra / gaia_dr3__pmdec only; coarse_gbm keeps its benchmark fall-back"),
    "pmdec": ("as pmra", "as pmra"),
    "RAJ2000": ("04_build_evidence.py:482,548 (WISE-AGN rules read AllWISE's RAJ2000 for the R90 sky, through CatalogFields)",
                "none needed (CatalogFields reads allwise__RAJ2000; the rule has no AllWISE row without it)"),
    "DEJ2000": ("as RAJ2000", "as RAJ2000"),
    "Jmag": ("Preprocess/units.py:118 reads {2MASS}__Jmag and {AllWISE}__Jmag, both namespaced", "none needed"),
    "Hmag": ("as Jmag", "none needed"),
    "Kmag": ("as Jmag; association_model.py:140,471 read the raw 2MASS row (Stage 1)", "none needed"),
    "e_Jmag": ("as Jmag", "none needed"),
    "e_Hmag": ("as Jmag", "none needed"),
    "e_Kmag": ("as Jmag", "none needed"),
    "objid": ("Preprocess/table_io.py:19 (64-bit identifier dtype of any column whose name ends in objid: the namespaced columns keep it); "
              "association_model.py:221 reads the raw Legacy row (Stage 1)", "none needed"),
    "entity_kind": ("Stage 2 writes its own object-level entity_kind / ref_epoch (02_integrate_objects.py) before the copy loop: the bare "
                    "column stays and is not the raw field; Classifier/validate_real_samples.py:176-221 reads that object-level column",
                    "none needed"),
    "ref_epoch": ("as entity_kind", "none needed"),
    "poserr_arcsec": ("Stage 1 detection field (01_source_association.py:211, association_model.py:278,378): raw rows, not the Stage 2 table", "none"),
    "query_radius_arcmin": ("Stage 1 only (01_source_association.py:141): raw rows", "none"),
    "psf_fwhm_arcsec": ("Stage 1 detection field (01_source_association.py:212, association_model.py:329,379,420): raw rows, not the Stage 2 table", "none"),
    "RA_ICRS": ("Classifier/collect_star_gaia.py renames its own Gaia table; no reader of a Stage 2 column", "none"),
    "DE_ICRS": ("as RA_ICRS", "none"),
    "Source": ("Classifier/collect_star_gaia.py and evaluate_star_diverse.py: their own tables", "none"),
}
LINE_NOTE = ("Classifier/subclass.py:1271 reads f'{prefix}line_ha_ew' with the catalogue prefix (namespaced)", "none needed")
for n in ("line_ha_ew", "line_ha_ew_err", "line_ha_flux", "line_ha_flux_err", "line_hb_flux", "line_hb_flux_err", "line_nii6584_ew",
          "line_nii6584_flux", "line_nii6584_flux_err", "line_oiii5007_flux", "line_oiii5007_flux_err", "line_source"):
    READERS.setdefault(n, LINE_NOTE)


def tests_mentioning(name: str) -> list[str]:
    pat = re.compile(r"""["']%s["']""" % re.escape(name))
    out = []
    for p in sorted(V2.rglob("tests/**/*.py")):
        if "legacy" in p.parts:
            continue
        if pat.search(p.read_text(errors="ignore")):
            out.append(p.name)
    return out


def main() -> int:
    shared = json.loads((HERE / "shared_candidates.json").read_text())
    rows = []
    for name in sorted(shared):
        readers, handling = READERS.get(name, ("no reader of the bare name", "none needed"))
        rows.append(dict(
            name=name,
            n_catalogues=len(shared[name]),
            catalogues=";".join(shared[name]),
            readers_of_the_bare_name=readers,
            reader_change=handling,
            app_or_summary="none (objects_summary.csv has 29 columns, none of them a shared name; the app reads namespaced or object-level columns)",
            tests_that_mention_it=";".join(tests_mentioning(name)),
            stage2_now="no bare column (namespaced columns only)" if name not in ("entity_kind", "ref_epoch")
            else "object-level bare column kept (Stage 2's own value); raw copies are namespaced only",
        ))
    with open(HERE / "shared_columns.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
