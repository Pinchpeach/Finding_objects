"""Network smoke test for the MVP pipeline.

Downloads a small Legacy Surveys cutout and performs Gaia cross-match.
Run manually because external survey services can be temporarily unavailable.
"""

from finding_objects.pipeline import RunConfig, run_pipeline

if __name__ == "__main__":
    output = run_pipeline(RunConfig(
        ra=150.116321,
        dec=2.205830,
        size=128,
        band="r",
    ))
    print(output)
    import pandas as pd
    df = pd.read_csv(output)
    print(df[["source_id", "ra", "dec", "snr", "gaia_source_id",
              "vizier_catalog", "vizier_sep_arcsec", "candidate_label"]].to_string(index=False))

    from pathlib import Path
    from finding_objects.visualize import render_candidate_pngs
    fits_files = list(Path("data/raw").glob("*_legacy_r.fits"))
    for image in render_candidate_pngs(fits_files[-1], output, Path("results/visualizations")):
        print(f"Visualization: {image}")
