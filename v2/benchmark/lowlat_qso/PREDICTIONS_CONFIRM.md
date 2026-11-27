# Predictions for the confirmation regions, written before any of them was collected (2026-11-27, 2.61.2)

The calibration regions (`fields_lowlat.csv`, 169 regions) were used to choose which switches (`Preprocess/lowlat_qso.py`) to try.  The
confirmation regions are 140 new regions drawn by the same rule from the pool that remains (`select_fields_lowlat.py --exclude
fields_lowlat.csv --prefix lqc --quota 0,60,40,40`; |b| < 5 deg has no quasar left; **SHA-256 of `fields_lowlat_confirm.csv`:
`8638a9dff5a583420b44e347f418974c0cad9511a08a6155eed986ac8fc75a09`**).  They are collected once, with the code of the commit that
holds this file, and scored with `ab_variants.py` for the control (`base`) and the candidates below.

**Candidates** (fixed here; calibration, 150 quasars and 170 false labels): `surveys2` (a QSO label needs 2 surveys at |b| < 20 deg: the
minimum that every quasar selection in the literature uses), `surveys3` (3 surveys: stricter, fitted to the calibration set), `pm`,
`wise_second`, and the combination `surveys2,wise_second,wise_footprint`.  `wise_footprint` lost 2 sample quasars for 8 false labels in
calibration and is not a candidate.

## What calibration says (the numbers the predictions come from)

| | sample quasars labelled QSO | false QSO labels (per deg², region-bootstrap 95 %) | with PS1 i < 19.5 | removed vs `base` (paired) |
|---|---|---|---|---|
| base | 86 / 150 | 170 (144 [90-211]) | 23 (19.5) | - |
| surveys2 | 86 | 93 (79 [53-109]) | 16 (13.6) | 77 (65 [32-108]) |
| surveys3 | 86 | 43 (36.5 [25-48]) | 12 (10.2) | 127 (108 [61-170]) |
| pm | 86 | 170 | 23 | 0 |
| wise_second | 86 | 142 (121 [68-188]) | 17 | 28 (24 [14-34]) |
| surveys2 + wise_second + wise_footprint | 84 | 87 (74 [48-104]) | 13 | 83 |

Recall by |b| in calibration: 5-10 deg 46 % (23/50), 10-15 deg 78 % (31/40), 15-20 deg 75 % (30/40).

## Predictions for the confirmation regions (area 140 x 0.00786 = 1.10 deg²)

1. **`base` recall**: 5-10 deg 46 %, 10-15 deg 78 %, 15-20 deg 75 %, so about 63 % overall (88 of 140; 95 % interval 55-70 %).
2. **`base` false QSO density**: about 156 deg⁻² (stratum rates 38 / 197 / 293 deg⁻² weighted by 60 / 40 / 40 regions), the bootstrap
   interval about 90-250 deg⁻² because the false labels cluster (30 of 170 in one calibration cone).  Share of them resting on one
   survey: 45 % (35-55 %).
3. **`surveys2`**: no sample quasar lost (at most 2 of 140); removes 45 % (30-60 %) of the false labels, i.e. about 70 deg⁻² (paired).
4. **`surveys3`**: at most 3 sample quasars lost; removes 75 % (60-85 %), i.e. about 117 deg⁻²; the remaining density about 39 deg⁻².
5. **`pm`**: changes nothing (at most 2 labels), because the false labels with a Gaia row are faint (G ~ 20) and pass the proper-motion cut.
6. **`wise_second`**: removes 16 % (8-25 %) of the false labels, no sample quasar.
7. The false labels with PS1 i < 19.5 stay above the high-latitude quasar density (5-8 deg⁻²) for every candidate: `surveys3` leaves
   about 10 deg⁻² there.
8. At |b| >= 20 deg every switch is inert: identical labels (checked on deep COSMOS fields, NGC 4522 and COSMOS 2').

## What would count as success (fixed here)

A candidate is adopted as an option for the user (default stays off) when, on the confirmation regions:
(a) the paired 95 % interval of the false-QSO density it removes is above 0;
(b) it loses at most 3 sample quasars of the 140 (about 2 %);
(c) the high-latitude check is identical.
If both `surveys2` and `surveys3` meet (a)-(c) both are reported with the exchange table and the choice is left to the user; `surveys2` is
the one the literature supports.  A prediction that fails is reported as failed.

## Limits stated in advance

The sample quasars are bright (PS1 i < 20) and every one has three or more catalogues, so the recall cannot show what `surveys2` or
`surveys3` cost faint real quasars with two catalogues; the false density has no purity behind it (no non-quasar truth here beyond the
19 stars and galaxies of the calibration set); Gaia is the VizieR copy until 2026-12-02; the regions are collected from this session's
container with live archives.
