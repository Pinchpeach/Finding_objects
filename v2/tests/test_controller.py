"""Offline tests of sky coverage and failure-isolated collector orchestration."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u

spec = importlib.util.spec_from_file_location(
    'controller', Path(__file__).resolve().parents[1] / 'Get_data/controller.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def frame(ids=('a',), ra=10., dec=20.):
    return pd.DataFrame([dict(catalog='test', catalog_object_id=i, object_name=str(i),
                              ra=ra, dec=dec) for i in ids], columns=c.BASE_COLUMNS)


class ControllerTests(unittest.TestCase):
    def test_coverage_wrap_and_poles(self):
        for ra, dec in [(10, 20), (359.999, 0), (23, 89.999), (123, -90)]:
            center = SkyCoord(ra * u.deg, dec * u.deg)
            chunks = c.plan_chunks(ra, dec, 3, 1)
            self.assertGreater(len(chunks), 1)
            for r in np.linspace(0, 3, 21):
                points = center.directional_offset_by(np.linspace(0, 360, 361) * u.deg, r * u.arcmin)
                covered = np.zeros(len(points), dtype=bool)
                for x, y, radius in chunks:
                    self.assertLessEqual(radius, 1)
                    covered |= SkyCoord(x * u.deg, y * u.deg).separation(points).arcmin <= radius + 1e-8
                self.assertTrue(covered.all(), (ra, dec, r))

    def test_small_cone_and_invalid_inputs(self):
        self.assertEqual(c.plan_chunks(10, 20, .5, 1), [(10, 20, .5)])
        for ra, dec, radius, chunk in [(0, 91, 1, 1), (0, 0, 0, 1),
                                       (0, 0, 1, 0), (float('nan'), 0, 1, 1),
                                       (0, 0, 5400, 1), (0, 0, 100, .01)]:
            with self.assertRaises(ValueError):
                c.plan_chunks(ra, dec, radius, chunk)

    def run_collection(self, module, folder, names=('test',)):
        with patch.object(c, 'COLLECTORS', names), patch.object(c, '_load_collector', return_value=module):
            return c.collect_all(10, 20, .5, Path(folder), chunk_radius_arcmin=.36)

    def test_merge_filter_failure_and_later_collector(self):
        outside = frame(('outside',), ra=11)
        module = SimpleNamespace(fetch=Mock(side_effect=[frame(), TimeoutError('timeout'),
                                 pd.concat([frame(('a', 'b')), outside]), frame(('c',))] * 2),
                                 save=lambda df, path: df.to_csv(path, index=False))
        with tempfile.TemporaryDirectory() as folder:
            summary = self.run_collection(module, folder, ('first', 'second'))
            self.assertEqual(module.fetch.call_count, 8)
            self.assertEqual(summary.status.tolist(), ['partial', 'partial'])
            self.assertEqual(summary.chunks_failed.tolist(), [1, 1])
            self.assertEqual(summary.chunks_succeeded.tolist(), [3, 3])
            self.assertEqual(summary.rows.tolist(), [3, 3])
            for path in summary.output_file:
                self.assertEqual(pd.read_csv(path).catalog_object_id.tolist(), ['a', 'b', 'c'])

    def test_all_failed_removes_stale_file(self):
        module = SimpleNamespace(fetch=Mock(side_effect=RuntimeError('offline')), save=Mock())
        with tempfile.TemporaryDirectory() as folder:
            stale = Path(folder) / f'test_{c._tag(10,20,.5)}.csv'
            stale.write_text('stale')
            summary = self.run_collection(module, folder)
            self.assertEqual(summary.iloc[0].status, 'error')
            self.assertEqual(summary.iloc[0].chunks_failed, 4)
            self.assertFalse(stale.exists())
            module.save.assert_not_called()

    def test_empty_and_none_outputs(self):
        module = SimpleNamespace(fetch=Mock(side_effect=[None, frame(()), pd.DataFrame(), None]),
                                 save=lambda df, path: df.to_csv(path, index=False))
        with tempfile.TemporaryDirectory() as folder:
            summary = self.run_collection(module, folder)
            self.assertEqual(summary.iloc[0].status, 'empty')
            self.assertEqual(list(pd.read_csv(summary.iloc[0].output_file).columns), c.BASE_COLUMNS)

    def test_missing_ids_and_large_integer_ids(self):
        ids = ['9223372036854775807', '9223372036854775806']
        one = frame([*ids, None, None])
        one.loc[3, 'object_name'] = 'different source'
        merged = c._merge_frames([one, frame(ids)])
        self.assertEqual(len(merged), 4)
        self.assertEqual(merged.catalog_object_id.dropna().tolist(), ids)

    def test_save_failure_is_reported(self):
        module = SimpleNamespace(fetch=Mock(return_value=frame()), save=Mock(side_effect=OSError('disk full')))
        with tempfile.TemporaryDirectory() as folder:
            summary = self.run_collection(module, folder)
            self.assertEqual(summary.iloc[0].status, 'error')
            self.assertEqual(summary.iloc[0].chunks_succeeded, 4)
            self.assertEqual(summary.iloc[0].output_file, '')

    def test_sdss_save_writes_deduplicated_csv(self):
        module = c._load_collector('sdss_dr18')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sdss.csv'
            module.save(frame(('a', 'a', 'b')), path)
            self.assertEqual(pd.read_csv(path).catalog_object_id.tolist(), ['a', 'b'])


if __name__ == '__main__':
    unittest.main()
