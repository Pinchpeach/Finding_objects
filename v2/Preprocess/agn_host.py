"""Dual GALAXY/QSO label for active galaxies (2.46.0).

"Quasar" and "galaxy with an active nucleus" are one population cut at a
convention, and catalogues draw the line differently:

* SDSS quasar catalogues keep an object as a QSO when the nucleus dominates
  (M_i < -22 with broad lines, Schneider et al. 2010, AJ 139, 2360; Lyke et
  al. 2020, ApJS 250, 8), even when the host is resolved in the image;
* the SDSS/BOSS spectral pipeline files most active galaxies as GALAXY with
  an AGN or BROADLINE sub-class (Bolton et al. 2012, AJ 144, 144);
* mid-IR AGN selection (W1 - W2 >= 0.8, Stern et al. 2012, ApJ 753, 30;
  Assef et al. 2018, ApJS 234, 23) finds obscured AGN whose optical light is
  the host's (Hickox & Alexander 2018, ARA&A 56, 625).

Choosing one class for these objects therefore disagrees with one convention
or the other (independent regions, 2.45.0: 36 of 174 errors are GALAXY <->
QSO).  Following the user's decision (2026-11-07), the primary class is kept
and the other reading is reported next to it:

* QSO with a resolved host (Legacy Surveys model REX/EXP/DEV/SER):
  secondary GALAXY, reason ``QSO_RESOLVED_HOST``;
* GALAXY that passes a WISE AGN colour selection (Stage-4 rules WISE-AGN-001,
  Stern 2012, or WISE-AGN-R90-001, Assef 2018): secondary QSO, reason
  ``GALAXY_WISE_AGN``.

``primary_class`` is unchanged, so every accuracy reported elsewhere stays
strict; the dual label is a separate column.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LS_TYPE = "desi_legacy_surveys_dr10__type"
EXTENDED = frozenset({"REX", "EXP", "DEV", "SER"})
WISE_AGN_RULES = frozenset({"WISE-AGN-001", "WISE-AGN-R90-001"})
QSO_RESOLVED_HOST = "QSO_RESOLVED_HOST"
GALAXY_WISE_AGN = "GALAXY_WISE_AGN"


def secondary(df: pd.DataFrame, labels, item_lists):
    """Per-row (secondary_class, reason); empty strings where there is none."""
    typ = (
        df[LS_TYPE].astype(str).str.strip().str.upper().to_numpy()
        if LS_TYPE in df
        else np.full(len(df), "", dtype=object)
    )
    sec, why = [], []
    for label, t, items in zip(labels, typ, item_lists):
        if label == "QSO" and t in EXTENDED:
            sec.append("GALAXY")
            why.append(QSO_RESOLVED_HOST)
        elif label == "GALAXY" and any(e.get("rule_id") in WISE_AGN_RULES for e in items):
            sec.append("QSO")
            why.append(GALAXY_WISE_AGN)
        else:
            sec.append("")
            why.append("")
    return sec, why
