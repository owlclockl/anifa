import unittest
from collections import deque

import nbtlib
import numpy as np

from tools import build_sculk_cathedral as deep
from test_cathedral import unpack


class SculkCathedralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file = nbtlib.load(deep.OUTPUT)
        cls.region = cls.file['Regions']['Cathedral']
        cls.palette = cls.region['BlockStatePalette']
        cls.blocks = unpack(cls.region)
        cls.drawn = deep.build()
        cls.bounds = tuple(slice(a.min(), a.max() + 1) for a in np.nonzero(cls.drawn))

    def test_export_includes_crypt_and_matches_model(self):
        self.assertEqual((self.file['Version'], self.file['SubVersion'], self.file['MinecraftDataVersion']), (7, 1, 5023))
        self.assertEqual(self.region['Size'], {'x': 169, 'y': 173, 'z': 266})
        self.assertEqual(self.region['Position'], {'x': 0, 'y': 0, 'z': 0})
        self.assertEqual(self.file['Metadata']['Name'], deep.TITLE)
        self.assertEqual(self.file['Metadata']['TotalBlocks'], np.count_nonzero(self.blocks))
        self.assertEqual(len(self.file['Metadata']['PreviewImageData']), 128**2)
        self.assertEqual(self.palette[0]['Name'], 'minecraft:air')
        by_state = {state: i for i, state in enumerate(deep.c.STATES)}
        lookup = []
        for tag in self.palette:
            props = tuple(sorted((str(k), str(v)) for k, v in tag.get('Properties', {}).items()))
            lookup.append(by_state[(str(tag['Name']), props)])
        np.testing.assert_array_equal(np.array(lookup, dtype=np.int16)[self.blocks], self.drawn[self.bounds])

    def test_spread_is_localized_and_shriekers_cannot_summon(self):
        blocks = self.drawn
        sculk = blocks == deep.SCULK
        self.assertFalse(sculk[:, :36 - deep.Z0].any())
        self.assertGreater(np.count_nonzero(sculk[100 - deep.Y0:]), 100)
        self.assertGreater(np.count_nonzero(sculk[:-deep.Y0]), 500)
        shriekers = [tag for tag in self.palette if tag['Name'] == 'minecraft:sculk_shrieker']
        self.assertTrue(shriekers)
        self.assertTrue(all(tag['Properties']['can_summon'] == 'false' for tag in shriekers))

    def test_veins_and_lichen_are_attached_to_neighboring_blocks(self):
        for i, tag in enumerate(self.palette):
            if tag['Name'] not in ('minecraft:glow_lichen', 'minecraft:sculk_vein'):
                continue
            directions = [(dy, dz, dx) for face, dy, dz, dx in deep.FACES if tag['Properties'][face] == 'true']
            self.assertTrue(directions)
            y, z, x = np.where(self.blocks == i)
            for dy, dz, dx in directions:
                for axis, offset, size in zip((y, z, x), (dy, dz, dx), self.blocks.shape):
                    self.assertGreaterEqual((axis - offset).min(), 0)
                    self.assertLess((axis - offset).max(), size)
                self.assertTrue(np.all(self.blocks[y - dy, z - dz, x - dx]))

    def test_stairs_connect_front_entrance_to_the_undercroft(self):
        # Topology of a two-block-high passage; not a full game collision simulation.
        low = self.drawn[:12 - deep.Y0]
        decor = [i for i, (name, _) in enumerate(deep.c.STATES) if name.endswith(('_carpet', '_vein', '_lichen'))]
        free = (low == 0) | np.isin(low, decor)
        floors = ~free[:-2] & free[1:-1] & free[2:]
        point = deep.DeepGrid.coord
        start = point(0, 0, -31)
        targets = {point(0, 4, 120), point(-28, -12, 165), point(0, -12, 167), point(0, 4, 211)}
        self.assertTrue(floors[start])
        seen = {start}
        queue = deque([start])
        while queue and targets - seen:
            y, z, x = queue.popleft()
            for dz, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                a, b = z + dz, x + dx
                if not (0 <= a < floors.shape[1] and 0 <= b < floors.shape[2]):
                    continue
                for h in range(max(0, y - 1), min(floors.shape[0], y + 2)):
                    cell = (h, a, b)
                    if floors[cell] and cell not in seen:
                        seen.add(cell)
                        queue.append(cell)
        self.assertFalse(targets - seen, 'The crypt or the main ambulatory is blocked')


if __name__ == '__main__':
    unittest.main()
