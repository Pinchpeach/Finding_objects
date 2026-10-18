"""Radio-only objects: catalogue artefacts, lobes of radio galaxies, or
optically faint radio sources (2.31.0).

An object seen only by radio surveys (VLASS, FIRST, NVSS, LoTSS, TGSS) has no
optical/IR measurement for the coarse STAR/GALAXY/QSO classifier.  Three
literature-based cases, in this order:

1. Catalogue artefact (status UNCONFIRMED): the only radio entry is
   * VLASS QL with Duplicate_flag = 2 (a non-preferred duplicate), Quality_flag
     not in {0, 4} (peak S/N < 5 or a sidelobe-like peak-to-ring ratio), or
     S_Code 'E' (empty island) -- the primary-sample selection of Gordon et al.
     2021 (ApJS 255, 30, Sects. 2.2-2.3, 3.4; < 1 % spurious after it);
   * FIRST with sidelobe probability P(S) >= 0.1, the cut that "eliminates the
     vast majority of the obvious sidelobes" (Helfand et al. 2015, ApJ 801,
     26, Sect. 4).
2. Component of a multi-component radio source (status RADIO_COMPONENT): another
   entry of the same arcsecond-resolution survey (VLASS, FIRST, LoTSS) within
   GROUP_RADIUS_ARCSEC with a flux ratio < MAX_FLUX_RATIO -- the grouping and
   lobe-ratio limits of van Velzen et al. 2015 (MNRAS 446, 2985, Sect. 2.1,
   Table 1) -- and bright enough for its separation, S1 + S2 >= K (d/100")^2
   with K = 10 mJy at 1.4 GHz (Huynh et al. 2005) and 50 mJy at 150 MHz
   (Williams et al. 2019, Sect. 6.5), 5.9 mJy at 3 GHz (alpha = -0.7):
   without it, chance pairs dominate in deep surveys (LoTSS ~780 sources
   per deg^2, i.e. 0.7 unrelated neighbours within 60").  A lobe has no
   optical counterpart because the host is elsewhere; the optical/IR object
   nearest the pair midpoint (within HOST_RADIUS_ARCSEC) is reported as the
   host candidate.
3. Otherwise the reason says what such sources usually are: AGN whose host
   lies below the optical/IR limits, typically at high redshift (13-27 % of
   LoTSS sources unidentified; Williams et al. 2019, A&A 622, A2; Shimwell et
   al. 2022; Kondapally et al. 2021, A&A 648, A3: "AGN at z ~ 3-4").
NVSS and TGSS (45" / 25" beams) are not used for grouping.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

RADIO = {"VLASS", "FIRST", "NVSS", "LoTSS DR2", "TGSS ADR1"}
LITERATURE = {"SIMBAD", "NED"}
GROUP_SURVEYS = {
    "VLASS": ("vlass__Ftot", "vlass__Total_flux"),
    "FIRST": ("first__Fint",),
    "LoTSS DR2": ("lotss_dr2__SpeakTot", "lotss_dr2__Stotal", "lotss_dr2__Total_flux"),
}
# Flux-separation constant K (mJy) of S1 + S2 >= K (d / 100")^2 per survey.
PAIR_K_MJY = {"VLASS": 10.0 * (3.0 / 1.4) ** -0.7, "FIRST": 10.0, "LoTSS DR2": 50.0}
GROUP_RADIUS_ARCSEC = 60.0
MAX_FLUX_RATIO = 10.0
HOST_RADIUS_ARCSEC = 10.0
FIRST_MAX_PS = 0.1
VLASS_GOOD_QUALITY = {0, 4}
SKIP = {"SOLAR_SYSTEM", "UNCONFIRMED", "WITHIN_LARGE_GALAXY"}


def _unit(ra, dec):
    ra, dec = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    return np.column_stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


def _sep_arcsec(a, b):
    return np.degrees(np.arccos(np.clip(a @ b.T, -1.0, 1.0))) * 3600.0


def _num(row, *keys):
    for k in keys:
        try:
            v = float(row.get(k))
        except (TypeError, ValueError):
            continue
        if np.isfinite(v):
            return v
    return None


def _artefact(row, cats):
    if cats == {"VLASS"}:
        dup, qual, code = _num(row, "vlass__DupFlag"), _num(row, "vlass__QualFlag"), str(row.get("vlass__SCode") or "")
        if dup == 2:
            return "VLASS duplicate entry (Duplicate_flag 2; Gordon+2021)"
        if qual is not None and int(qual) not in VLASS_GOOD_QUALITY:
            return f"VLASS low-quality component (Quality_flag {int(qual)}: low S/N or sidelobe-like; Gordon+2021)"
        if code.strip() == "E":
            return "VLASS empty island (S_Code E; Gordon+2021)"
    if cats == {"FIRST"}:
        ps = _num(row, "first__p(S)")
        if ps is not None and ps >= FIRST_MAX_PS:
            return f"FIRST probable sidelobe (P(S) = {ps:.2f} >= {FIRST_MAX_PS}; Helfand+2015)"
    return None


def classify(out: pd.DataFrame) -> pd.DataFrame:
    """Per-row (status, reason) for radio-only UNKNOWN objects; other rows NaN."""
    res = pd.DataFrame({"status": None, "reason": None}, index=out.index)
    if out.empty or "catalogs" not in out:
        return res
    cats = out.catalogs.astype(str).map(lambda s: frozenset(c for c in s.split("|") if c) - LITERATURE)
    unknown = out.get("primary_class", pd.Series("UNKNOWN", index=out.index)).astype(str).str.upper().eq("UNKNOWN")
    status = out.get("classification_status", pd.Series("", index=out.index)).astype(str)
    radio_only = unknown & cats.map(lambda c: bool(c) and c <= RADIO) & ~status.isin(SKIP)
    if not radio_only.any():
        return res
    xyz = _unit(out.ra, out.dec)
    optical_none = cats.map(lambda c: not (c - RADIO)).to_numpy()
    pos = {i: k for k, i in enumerate(out.index)}
    artefacts = {i: _artefact(out.loc[i], set(cats[i])) for i in out.index[radio_only]}
    bad = out.index.isin([i for i, w in artefacts.items() if w])  # never a companion
    for i in out.index[radio_only]:
        row, c = out.loc[i], set(cats[i])
        why = artefacts[i]
        if why:
            res.loc[i] = ("UNCONFIRMED", "radio-only " + why)
            continue
        best = None
        for survey, keys in GROUP_SURVEYS.items():
            f = _num(row, *keys)
            if survey not in c or f is None or f <= 0:
                continue
            same = cats.map(lambda s: survey in s) & (out.index != i) & ~bad
            if not same.any():
                continue
            idx = out.index[same]
            sep = _sep_arcsec(xyz[[pos[i]]], xyz[[pos[j] for j in idx]])[0]
            for j, d in zip(idx, sep):
                g = _num(out.loc[j], *keys)
                if (
                    d <= GROUP_RADIUS_ARCSEC
                    and g
                    and g > 0
                    and max(f, g) / min(f, g) < MAX_FLUX_RATIO
                    and f + g >= PAIR_K_MJY[survey] * (d / 100.0) ** 2
                ):
                    if best is None or d < best[1]:
                        best = (j, d, f / g, survey)
        if best:
            j, d, ratio, survey = best
            mid = xyz[pos[i]] + xyz[pos[j]]
            mid /= np.linalg.norm(mid)
            hsep = _sep_arcsec(mid[None, :], xyz)[0]
            hsep[[pos[i], pos[j]]] = np.inf
            hsep[optical_none] = np.inf  # a host has optical/IR measurements
            hosts = np.flatnonzero(hsep <= HOST_RADIUS_ARCSEC)
            host = ""
            if len(hosts):
                h = hosts[np.argmin(hsep[hosts])]
                name = out.iloc[h].get("designation") or out.iloc[h].get("object_id")
                host = (
                    f"; host candidate {name} ({out.iloc[h].get('primary_class')}) {hsep[h]:.1f}\" from the pair centre"
                )
            other = out.loc[j].get("designation") or out.loc[j].get("object_id")
            if not optical_none[pos[j]]:
                other += " (optical/IR object with radio emission: probable core or host)"
            res.loc[i] = (
                "RADIO_COMPONENT",
                f'part of a multi-component radio source: {survey} companion {other} {d:.0f}" away, flux ratio '
                f"{ratio:.2f} (van Velzen+2015 grouping){host}",
            )
            continue
        res.loc[i] = (
            None,
            "radio source without an optical/IR counterpart: usually an AGN whose host is below the optical "
            "limits (high redshift or obscured; Williams+2019, Kondapally+2021)",
        )
    return res


def apply(out: pd.DataFrame) -> pd.DataFrame:
    r = classify(out)
    if r.reason.isna().all():
        return out
    out = out.copy()
    has = r.reason.notna()
    out.loc[has, "unknown_reason"] = r.reason[has]
    st = r.status.notna()
    out.loc[st, "classification_status"] = r.status[st]
    return out
