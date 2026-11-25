"""Gaia data-release settings in one place (2.9.0, Gaia DR4 readiness).

Select the release with the environment variable ``V2_GAIA_RELEASE``
(``DR3`` by default; ``DR4`` once the archive serves it).  Only facts that are
fixed by the release are kept here:

* TAP schema of the Gaia archive (``gaiadr3`` ...);
* astrometric reference epoch: DR3 J2016.0 (Lindegren et al. 2021, A&A 649,
  A2); DR4 J2017.5 (66 months of data centred on 2017.5, ESA Gaia DR4
  release scenario);
* designation prefix ("Gaia DR3 <source_id>");
* the VizieR mirror used as an outage fallback (DR3 only for now).

2.60.4 (DR4 readiness, ``v2/GAIA_DR4_READINESS_2026-11-25.md``): the tables and columns the collector reads are a
per-release *product map* (``GaiaRelease.products``), not module constants of ``gaia_dr3.py``.  DR3 holds the map the
collector always used (unchanged); DR4 holds ``None`` until the archive's own metadata has been checked
(``check_gaia_release.py --release DR4``): the 2026-06-26 draft data model splits the astrophysical parameters into
``ap_xp`` / ``ap_rvs`` / ``ap_class`` / ``ap_emission``, drops several DR3 columns and renames others (see
``benchmark/gaia_dr4/dr3_columns_vs_dr4_draft.csv``), so DR3's column lists must not be sent to a DR4 table.

Downstream the Gaia evidence keeps the column slot ``gaia_dr3__*`` (catalogue
name "Gaia DR3") for every release: the classifier rules, fusion weights and
stored benchmark features use that slot.  Each row carries ``gaia_release``
and ``ref_epoch`` of the data it really holds, and the association uses the
row's own ``ref_epoch`` for proper-motion propagation.
Run ``python v2/Get_data/check_gaia_release.py --release DR4`` when DR4 is
public: it lists the columns the collector needs that the archive lacks.
"""

from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    """One archive table the collector reads and the columns it needs from it.

    ``status_column`` is the collector column that records how the query of an optional product went
    (``gaia_ap_query_status`` ...); the base table (``"source"``) has none.
    """

    table: str
    columns: tuple[str, ...]
    status_column: str | None = None


@dataclass(frozen=True)
class GaiaRelease:
    name: str
    tap_schema: str
    ref_epoch: float
    designation_prefix: str
    vizier_source: str | None
    # product key -> Product; "source" first, then the optional products merged by source_id.
    # None: the release has not been checked against the archive's metadata, so no query is built.
    products: dict | None = None


# --- DR3 column lists (moved from gaia_dr3.py in 2.60.4; the collector's behaviour is unchanged) -------------
SOURCE = [
    "source_id",
    "designation",
    "ra",
    "dec",
    "ra_error",
    "dec_error",
    "parallax",
    "parallax_error",
    "pmra",
    "pmra_error",
    "pmdec",
    "pmdec_error",
    "pmra_pmdec_corr",  # full proper-motion covariance for the zero-motion test (2.38.0; Li & Fynbo 2026)
    "ruwe",
    "phot_g_mean_flux",
    "phot_g_mean_flux_error",
    "phot_g_mean_mag",
    "phot_bp_mean_flux",
    "phot_bp_mean_flux_error",
    "phot_bp_mean_mag",
    "phot_rp_mean_flux",
    "phot_rp_mean_flux_error",
    "phot_rp_mean_mag",
    "bp_rp",
    "bp_g",
    "g_rp",
    "phot_bp_rp_excess_factor",
    "radial_velocity",
    "radial_velocity_error",
    "rv_nb_transits",
]
AP = [
    "teff_gspphot",
    "logg_gspphot",
    "mh_gspphot",
    "distance_gspphot",
    "ag_gspphot",
    "ebpminrp_gspphot",
    "mass_flame",
    "age_flame",
    "evolstage_flame",
    "flags_flame",
    "classprob_dsc_combmod_quasar",
    "classprob_dsc_combmod_galaxy",
    "classprob_dsc_combmod_star",
    "classprob_dsc_combmod_whitedwarf",
    "classprob_dsc_combmod_binarystar",
]
# Spectroscopic parameters: GSP-Spec from RVS spectra (Recio-Blanco et al.
# 2023) and the ESP-ELS emission-line class from BP/RP (Creevey et al. 2023).
# Same table as AP, fetched in the same query (column names checked against
# the archive metadata, 2026-10-10): a second query would leave one more
# abandoned daemon thread when TAP is slow, and abandoned threads crashed the
# interpreter at exit (scientific cross-validation, compact-pulsar shard).
# ESP-UCD (2.22.0): Teff of ultracool-dwarf candidates (< 2700 K, ~M7 and
# later) from the RP spectrum and its quality category (Sarro et al. 2023,
# A&A 669, A139); names checked against the archive (v2_new_targets.yml).
# Not in the VizieR fallback (left empty there).
SPEC_AP = [
    "teff_gspspec",
    "logg_gspspec",
    "mh_gspspec",
    "flags_gspspec",
    "classlabel_espels",
    "classlabel_espels_flag",
    "teff_espucd",
    "flags_espucd",
]
VAR_SUMMARY = [
    "in_vari_classification_result",
    "in_vari_rrlyrae",
    "in_vari_cepheid",
    "in_vari_long_period_variable",
    "in_vari_eclipsing_binary",
    "in_vari_rotation_modulation",
    "in_vari_agn",
    "in_vari_microlensing",
    "in_vari_compact_companion",
]

DR3_PRODUCTS = {
    "source": Product("gaia_source", tuple(SOURCE)),
    "astrophysical_parameters": Product("astrophysical_parameters", tuple(AP + SPEC_AP), "gaia_ap_query_status"),
    "vari_classifier_result": Product(
        "vari_classifier_result", ("best_class_name", "best_class_score"), "gaia_vari_classifier_query_status"
    ),
    "vari_summary": Product("vari_summary", tuple(VAR_SUMMARY), "gaia_vari_summary_query_status"),
}

RELEASES = {
    "DR3": GaiaRelease("DR3", "gaiadr3", 2016.0, "Gaia DR3", "I/355/gaiadr3", DR3_PRODUCTS),
    # DR4: the schema name is assumed (the ESA content page names only bare tables) and the products stay None
    # until check_gaia_release.py has read the live metadata.  Reference epoch: ESA DR4 content page, "J2017.5".
    "DR4": GaiaRelease("DR4", "gaiadr4", 2017.5, "Gaia DR4", None, None),
}
# The pipeline slot (catalogue name / column prefix) is independent of the release.
SLOT_CATALOG = "Gaia DR3"


def current() -> GaiaRelease:
    name = os.environ.get("V2_GAIA_RELEASE", "DR3").strip().upper()
    if name not in RELEASES:
        raise ValueError(f"unknown Gaia release {name!r}; choose one of {sorted(RELEASES)}")
    return RELEASES[name]


def table(rel: GaiaRelease, name: str) -> str:
    return f"{rel.tap_schema}.{name}"
