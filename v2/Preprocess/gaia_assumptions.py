"""What the classification assumes about the Gaia release its Gaia columns come from (2.60.5, DR4 readiness).

Collection (tables, columns, epoch) is in ``Get_data/gaia_release.py``.  This module holds the *classification-side*
constants that are properties of one Gaia release, so that they live in one table keyed by the release name and a
different release cannot silently inherit DR3's values.  The release of a data set is read from its own
``gaia_release`` column (each Gaia row records the release it really holds, 2.9.0); no column means DR3 (the stored
benchmark features, and every raw file collected before DR4).

DR3 is the only release with values.  ``for_release("DR4")`` raises ``LookupError``: the DR4 values are decided by the
protocol locked in ``v2/GAIA_DR4_READINESS_2026-11-25.md`` after the release, not guessed now.  The classification then
stops with a message instead of running DR4 columns through DR3 assumptions (a wrong zero point or a wrong C* cut would
change labels without any warning).

========================  =====================================================  ================================
constant                  DR3 value and basis                                    why it can change in DR4
========================  =====================================================  ================================
parallax_offset_mas       0.017, added to the parallax: the Gaia-CRF3 quasar     DR4 ``gaia_source`` has
                          zero point (Lindegren+2021 A&A 649 A2; Klioner+2022    ``tentative_parallax_bias``
                          Eq. 2)                                                 (subtract), per source
ext_max_parallax_error    0.3 mas: AST-EXT-001 is informative only when the      DR4 errors differ
                          parallax error is small (2.16.0)
crf_error_scale           1.1: Gaia-CRF3 quasar astrometry is 1.05-1.1 times     CRF4, new astrometric solution
                          wider than the formal errors (Lindegren+2021)
ruwe_binary               1.4 (Lindegren+2018; Belokurov+2020)                   RUWE is re-derived per solution
density_reference_deg2    5,000 deg^-2: the local Gaia density at which the      DR4 has more sources
                          position prior of GALAXY and QSO starts to fall
C* (cstar_*)              Riello+2021 A&A 649 A3 Eq. 6 / Table 2 and Eq. 18     DR4 passbands are revised; the
                                                                                 draft has no excess factor column
========================  =====================================================  ================================
"""

# No ``from __future__ import annotations``: the stage modules load this file by path without registering it in
# sys.modules, and dataclasses with string annotations need the module there.
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GaiaAssumptions:
    release: str
    parallax_offset_mas: float
    ext_max_parallax_error_mas: float
    crf_error_scale: float
    ruwe_binary: float
    density_reference_deg2: float

    def cstar_correction(self, bp_rp):
        """f(BP-RP) of Riello+2021 Eq. 6 / Table 2: C* = C - f (isolated-source locus of the BP/RP flux excess)."""
        if self.release != "DR3":  # pragma: no cover - only DR3 has coefficients
            raise LookupError(f"no C* coefficients for Gaia {self.release}")
        x = bp_rp
        if x < 0.5:
            return 1.154360 + 0.033772 * x + 0.032277 * x * x
        if x < 4.0:
            return 1.162004 + 0.011464 * x + 0.049255 * x * x - 0.005879 * x**3
        return 1.057572 + 0.140537 * x

    def cstar_scatter(self, g):
        """Riello+2021 Eq. 18: 1-sigma scatter of C* for well-behaved isolated sources."""
        if self.release != "DR3":  # pragma: no cover
            raise LookupError(f"no C* scatter for Gaia {self.release}")
        return 0.0059898 + 8.817481e-12 * g**7.618399


ASSUMPTIONS = {
    "DR3": GaiaAssumptions(
        release="DR3",
        parallax_offset_mas=0.017,
        ext_max_parallax_error_mas=0.3,
        crf_error_scale=1.1,
        ruwe_binary=1.4,
        density_reference_deg2=5.0e3,
    ),
}
KNOWN_RELEASES = ("DR3", "DR4")  # releases the collection side knows (Get_data/gaia_release.py)


def for_release(name: str | None = "DR3") -> GaiaAssumptions:
    key = "DR3" if name is None else str(name).strip().upper()
    if key in ASSUMPTIONS:
        return ASSUMPTIONS[key]
    if key in KNOWN_RELEASES:
        raise LookupError(
            f"Gaia {key}: the classification assumptions (parallax zero point, C*, RUWE, density reference, ...) "
            "are not set; they are decided by the protocol in v2/GAIA_DR4_READINESS_2026-11-25.md, not guessed. "
            "Classify DR3 data, or set the values first."
        )
    raise ValueError(f"unknown Gaia release {name!r}")


def release_of(values) -> str:
    """The release named by the ``gaia_release`` values of a data set (null, empty or missing: DR3).

    Several releases in one data set cannot be classified with one set of constants: ``ValueError``.
    """
    if values is None:
        return "DR3"
    seen = set()
    for v in np.asarray(values, dtype=object).ravel() if not isinstance(values, str) else [values]:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        t = str(v).strip().upper()
        if t and t not in ("NAN", "NONE", "<NA>"):
            seen.add(t)
    if not seen:
        return "DR3"
    if len(seen) > 1:
        raise ValueError(f"one data set holds Gaia rows of several releases: {sorted(seen)}")
    return seen.pop()


def for_values(values) -> GaiaAssumptions:
    """Assumptions of the release the ``gaia_release`` values name (see ``release_of``)."""
    return for_release(release_of(values))
