# Controller request chunks

`controller.py` preserves each collector's `fetch(ra, dec, radius_arcmin)` and
`save(df, path)` interfaces. It covers the requested sky cone with smaller,
overlapping cones, calls each collector sequentially for every chunk, clips
returned coordinates to the original cone, and merges by catalog/object ID.
The last occurrence of a duplicated ID wins. Missing IDs use exact-row
deduplication instead. Fields at RA 0/360 and the poles use a rotated sky frame.

The default maximum request radius is 1 arcminute. Smaller requested fields
still use one call. For example, to exercise four calls per survey:

```sh
python v2/Get_data/controller.py --ra 188.4155 --dec 9.1751 --radius 0.5 --chunk-radius 0.36
```

Python callers may pass the keyword-only `chunk_radius_arcmin` option to
`collect_all`; existing positional arguments remain valid. Radius must be
finite, positive, and below 90 degrees. Plans larger than 10,000 grid cells are
rejected before any network calls. Chunking bounds query area, not row count;
catalog-specific server row limits still apply in dense fields.

Each failed chunk is logged and the remaining chunks and surveys continue.
The summary adds `chunks_planned`, `chunks_attempted`, `chunks_succeeded`, and
`chunks_failed`. `partial` means at least one chunk succeeded and at least one
failed, even if the successful chunks returned no objects. `empty` means all
chunks succeeded without objects. All-chunk failures report `error`/`timeout`
without publishing a CSV; stale output for that same query is removed. Save
failures also report an error. Successful results are saved once via a temporary
file and then replaced atomically. Partial results are not complete coverage.

Run offline regression tests with `python -m unittest discover -s v2/tests -v`.
The existing NGC4522 controller workflow runs these tests and four live chunks
for each of the 19 collectors, validates the summary and saved CSVs, and uploads
an artifact. A green workflow confirms orchestration and at least one nonempty
catalog, not that every external catalog service is healthy; consult the
summary for individual failures. PR runs never commit generated data to main.

This controller is separate from `v2/benchmark/collect_catalog_truth.py`, which
has its own multi-target query path; its request strategy is unchanged.
