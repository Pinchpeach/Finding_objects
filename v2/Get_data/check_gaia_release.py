#!/usr/bin/env python3
"""Check a Gaia release on the ESA archive against what the collector needs (2.9.0; DR4 mode 2.60.6).

    python v2/Get_data/check_gaia_release.py --release DR3      # the product map of Get_data/gaia_release.py
    python v2/Get_data/check_gaia_release.py --release DR4      # schema discovery against the locked draft

DR3: for every product of the release's product map (``gaia_release.DR3_PRODUCTS``) the archive's table metadata is
read and the columns the collector requests that the archive does not have are listed, together with the reference
epoch the archive reports.  Exit code 1 if a table or a required column is missing.

DR4 (step "a" of the protocol locked in ``v2/GAIA_DR4_READINESS_2026-11-25.md``): there is no product map yet, so the
script *discovers*.  It finds the schema that holds DR4 (``--schema`` or by looking for ``gaia_source`` with the DR4
column ``tentative_parallax_bias``), reads the metadata of the tables the project needs, compares every table with the
2026-06-26 draft data model (``benchmark/gaia_dr4/dr4_draft_tables.json``: columns that the draft promised and the
archive lacks, columns the archive has that the draft did not know), reports where each DR3 column of the collector
lives in the live schema, whether the DR3 schema is still served, and the reference epoch.  Nothing is written; the
product map and the classification constants are set by hand afterwards, from this report.  Exit code 1 if a wanted
table is missing or a DR3 column the classification needs has no home.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import throttle  # noqa: E402
from gaia_release import RELEASES, table  # noqa: E402

DRAFT = Path(__file__).resolve().parents[1] / "benchmark" / "gaia_dr4" / "dr4_draft_tables.json"
# DR4 tables the project would read (draft data model names); the DR3 columns are looked for in all of them
WANTED_DR4 = [
    "gaia_source", "all_source_astrometry", "all_source_photometry", "all_source_flags",
    "ap_xp", "ap_rvs", "ap_class", "ap_emission", "vari_summary", "vari_classifier_result",
    "xp_continuous_mean_spectrum", "dr3_neighbourhood",
]  # fmt: skip
# DR3 columns without which the classification loses evidence (everything else degrades gracefully)
NEEDED_DR3_COLUMNS = [
    "source_id", "ra", "dec", "parallax", "parallax_error", "pmra", "pmra_error", "pmdec", "pmdec_error", "ruwe",
    "phot_g_mean_mag", "phot_bp_mean_mag", "phot_rp_mean_mag", "bp_rp",
]  # fmt: skip


def compare_tables(draft: dict, live: dict) -> dict:
    """Table-by-table comparison of the draft data model with the archive's metadata (both: table -> column names)."""
    out = {"missing_tables": [], "new_tables": sorted(set(live) - set(draft)), "per_table": {}}
    for t, cols in draft.items():
        if t not in live:
            out["missing_tables"].append(t)
            continue
        have, want = {c.lower() for c in live[t]}, [c.lower() for c in cols]
        out["per_table"][t] = {
            "in_draft_not_in_archive": [c for c in want if c not in have],
            "in_archive_not_in_draft": sorted(have - set(want)),
        }
    return out


def where_is(columns: list[str], live: dict) -> dict:
    """column -> the live tables that carry it (case-insensitive)."""
    found = {c: [] for c in columns}
    for t, cols in live.items():
        have = {c.lower() for c in cols}
        for c in columns:
            if c.lower() in have:
                found[c].append(t)
    return found


def _meta(Gaia, name: str):
    meta = Gaia.load_table(name)
    return [c.name for c in meta.columns]


def check_dr3(Gaia, rel) -> bool:
    bad = False
    for key, prod in rel.products.items():
        t = table(rel, prod.table)
        try:
            have = {c.lower() for c in _meta(Gaia, t)}
        except Exception as exc:
            print(f"{t}: NOT AVAILABLE ({type(exc).__name__}: {str(exc)[:120]})")
            bad = True
            continue
        missing = [c for c in prod.columns if c.lower() not in have]
        print(f"{t}: {len(have)} columns; missing {len(missing)}: {missing}")
        bad |= bool(missing)
    return bad


def check_dr4(Gaia, schema: str | None) -> bool:
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    schemas = [schema] if schema else ["gaiadr4", "gaia_dr4", "dr4"]
    live, used = {}, None
    for sc in schemas:
        try:
            cols = _meta(Gaia, f"{sc}.gaia_source")
        except Exception as exc:
            print(f"schema {sc!r}: gaia_source not readable ({type(exc).__name__}: {str(exc)[:100]})")
            continue
        used = sc
        live["gaia_source"] = cols
        break
    if used is None:
        print("no DR4 schema found: give --schema NAME (the ESA pages name only bare table names)")
        return True
    print(f"schema {used}: gaia_source has {len(live['gaia_source'])} columns")
    print("  DR4 marker tentative_parallax_bias in gaia_source:", "tentative_parallax_bias" in live["gaia_source"])
    for t in WANTED_DR4:
        if t in live:
            continue
        try:
            live[t] = _meta(Gaia, f"{used}.{t}")
        except Exception as exc:
            print(f"{used}.{t}: NOT AVAILABLE ({type(exc).__name__}: {str(exc)[:100]})")
    bad = False
    report = compare_tables({t: draft[t] for t in WANTED_DR4 if t in draft}, live)
    for t in report["missing_tables"]:
        print(f"MISSING TABLE {t}")
        bad = True
    for t, d in report["per_table"].items():
        print(
            # full lists (2.60.6 review): this output is committed as the record of the first check
            f"{t}: promised by the draft but absent {d['in_draft_not_in_archive']}; new in the archive {d['in_archive_not_in_draft']}"
        )
    import gaia_release

    dr3_cols = []
    for prod in gaia_release.RELEASES["DR3"].products.values():
        dr3_cols += list(prod.columns)
    homes = where_is(sorted(set(dr3_cols)), live)
    print("\nDR3 column -> live DR4 tables (empty: the column is gone or renamed)")
    for c, ts in homes.items():
        print(f"  {c:38s} {', '.join(ts) if ts else '-'}")
        if not ts and c in NEEDED_DR3_COLUMNS:
            bad = True
    try:
        r = Gaia.launch_job(f"SELECT TOP 1 ref_epoch FROM {used}.gaia_source").get_results()
        print(f"\nref_epoch on the archive: {float(r['ref_epoch'][0])} (gaia_release.py: {RELEASES['DR4'].ref_epoch})")
    except Exception as exc:
        print("\nref_epoch query failed:", str(exc)[:120])
    for sc in ("gaiadr3", "gaiaedr3"):
        try:
            n = len(_meta(Gaia, f"{sc}.gaia_source"))
            print(f"{sc}.gaia_source still served ({n} columns)")
        except Exception as exc:
            print(f"{sc}.gaia_source NOT served ({type(exc).__name__})")
    return bad


def check_vizier_copies() -> None:
    """Which Gaia releases VizieR holds (protocol step a.2): the DR3 copy the fallback reads, and any DR4 copy."""
    try:
        from astroquery.vizier import Vizier

        for key in ("I/355", "Gaia DR4"):
            cats = Vizier.find_catalogs(key)
            print(f"VizieR find_catalogs({key!r}): {sorted(cats)[:15]}")
    except Exception as exc:
        print("VizieR copy check failed:", f"{type(exc).__name__}: {str(exc)[:120]}")


def main() -> None:
    throttle.install()  # 3-5 s before every archive request (2.33.0)
    from astroquery.gaia import Gaia

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--release", default="DR4", choices=sorted(RELEASES))
    p.add_argument("--schema", default=None, help="TAP schema that holds the release (DR4: default tries gaiadr4)")
    a = p.parse_args()
    rel = RELEASES[a.release]
    if rel.products is None:
        bad = check_dr4(Gaia, a.schema) if a.release == "DR4" else True
        check_vizier_copies()
        sys.exit(1 if bad else 0)
    bad = check_dr3(Gaia, rel)
    try:
        r = Gaia.launch_job(f"SELECT TOP 1 ref_epoch FROM {table(rel, rel.products['source'].table)}").get_results()
        ep = float(r["ref_epoch"][0])
        print(f"ref_epoch on archive: {ep}; gaia_release.py: {rel.ref_epoch}")
        bad |= abs(ep - rel.ref_epoch) > 1e-6
    except Exception as exc:
        print("ref_epoch query failed:", str(exc)[:120])
        bad = True
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
