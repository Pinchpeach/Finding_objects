# Independent-truth validation, set B

200 further regions (2026-10-26), each >= 3.5 deg from the 200 regions of set A
(`../independent_fields/`) and from each other, so the two sets share no truth
object. List: `../select_fields_b.py` (reproducible), workflow
`.github/workflows/v2_independent_truth_b.yml`.

- 50 special regions not in set A: 12 globular clusters, 12 open clusters,
  13 star-forming regions, 5 starburst / interacting galaxies, 8 Magellanic
  Cloud outskirt and Bridge fields.
- 150 survey regions where the truth surveys are dense: 30 2dFGRS/2QZ SGP,
  15 NGP, 9 Stripe 82, 15 6dFGS/RAVE south, 81 LAMOST footprint.

As for set A, the raw products live on the `validation-data` branch only; main
keeps the score tables. Scoring:

    python v2/benchmark/score_independent_fields.py --root v2/benchmark/independent_fields_b --which blind --out DIR
    python v2/benchmark/compare_qso_options.py score --root v2/benchmark/independent_fields_b --out DIR
