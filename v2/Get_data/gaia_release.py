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
class GaiaRelease:
    name: str
    tap_schema: str
    ref_epoch: float
    designation_prefix: str
    vizier_source: str | None


RELEASES = {
    "DR3": GaiaRelease("DR3", "gaiadr3", 2016.0, "Gaia DR3", "I/355/gaiadr3"),
    "DR4": GaiaRelease("DR4", "gaiadr4", 2017.5, "Gaia DR4", None),
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
