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
