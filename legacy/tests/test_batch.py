from finding_objects.batch import random_sky_targets, random_footprint_targets, pending_targets, append_checkpoint

def test_sampling_is_reproducible_and_bounded():
    a = random_sky_targets(1000, seed=42)
    b = random_sky_targets(1000, seed=42)
    assert a == b
    assert len(a) == 1000
    assert all(0 <= x.ra < 360 and -90 <= x.dec <= 90 for x in a)

def test_checkpoint_resume(tmp_path):
    targets = random_sky_targets(3, seed=1)
    p = tmp_path / "checkpoint.jsonl"
    append_checkpoint(p, {"sample_id": targets[0].sample_id, "status": "done"})
    assert pending_targets(targets, p) == targets[1:]


def test_footprint_sampling_is_reproducible_and_inside_bounds():
    a = random_footprint_targets(1000, seed=7, ra_ranges=((120, 240),), dec_range=(-5, 65))
    b = random_footprint_targets(1000, seed=7, ra_ranges=((120, 240),), dec_range=(-5, 65))
    assert a == b
    assert all(120 <= x.ra <= 240 and -5 <= x.dec <= 65 for x in a)
