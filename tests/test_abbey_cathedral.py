import unittest
from collections import deque

import nbtlib
import numpy as np

from tools import build_abbey_cathedral as abbey
from test_cathedral import unpack


class AbbeySchematicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file = nbtlib.load(abbey.OUTPUT)
        cls.region = cls.file['Regions']['Cathedral']
        cls.drawn = abbey.build()
        cls.bounds = tuple(slice(int(a.min()), int(a.max()) + 1) for a in np.nonzero(cls.drawn))
        lookup = {entry: i for i, entry in enumerate(abbey.c.STATES)}
        indices = []
        for entry in cls.region['BlockStatePalette']:
            props = tuple(sorted((str(k), str(v)) for k, v in entry.get('Properties', {}).items()))
            indices.append(lookup[(str(entry['Name']), props)])
        cls.blocks = np.array(indices, dtype=np.int16)[unpack(cls.region)]
        cls.names = [name for name, _ in abbey.c.STATES]
        cls.decor = [i for i, name in enumerate(cls.names) if name.endswith(('_carpet', '_lichen', '_vein'))]

    @classmethod
    def point(cls, x, y, z):
        return tuple(a - b.start for a, b in zip(abbey.Abbey.coord(x, y, z), cls.bounds))

    def at(self, x, y, z):
        return int(self.blocks[self.point(x, y, z)])

    def test_export_round_trip_and_ignition_space(self):
        self.assertEqual((self.file['Version'], self.file['SubVersion'], self.file['MinecraftDataVersion']), (7, 1, 5023))
        self.assertEqual(self.region['Size'], {'x': 341, 'y': 174, 'z': 346})
        self.assertEqual(self.region['Position'], {'x': 0, 'y': 0, 'z': 0})
        meta = self.file['Metadata']
        self.assertEqual(meta['EnclosingSize'], self.region['Size'])
        self.assertEqual(meta['Name'], abbey.TITLE)
        self.assertEqual(meta['TotalBlocks'], np.count_nonzero(self.blocks))
        self.assertEqual(len(meta['PreviewImageData']), 128**2)
        np.testing.assert_array_equal(self.blocks, self.drawn[self.bounds])
        r = abbey.r
        half = r.PWIDTH // 2
        bottom = [self.at(x, r.PBASE, r.PZ) for x in range(r.PX - half - 1, r.PX + half + 2)]
        self.assertTrue(all(value == abbey.s.OBSIDIAN for value in bottom))
        y, z, x = self.point(r.PX - half, r.PBASE + 1, r.PZ - 3)
        self.assertFalse(self.blocks[y:y + r.PHEIGHT, z:z + 7, x:x + r.PWIDTH].any())

    def test_altar_approach_uses_six_half_block_levels(self):
        levels = ((157, 1), (158, 2), (160, 3), (161, 4), (163, 5), (165, 6))
        for z, level in levels:
            y = (10 + level - 1) // 2
            state = self.at(-6, y, z)
            with self.subTest(z=z):
                if level % 2:
                    self.assertEqual(state, abbey.SLATE_STEP)
                else:
                    self.assertIn(state, (abbey.TRIM, abbey.SLATE, abbey.s.LUMEN))
                self.assertIn(self.at(-6, y + 1, z), {0, *self.decor})
        # Horizontal and longitudinal symmetry of the bounds of the west portion of the dais.
        self.assertEqual(abbey.choir_level(-10, 169), abbey.choir_level(-2, 181))

    def walkable_treads(self, cx):
        """Compute clear tread centers in sixteenths of a block, not voxel step counts."""
        treads = {}
        walk_through = {0, *self.decor}
        for z in range(-1, 20):
            for x in range(cx - 12, cx + 12):
                bottom, zi, xi = self.point(x, 0, z)
                col = self.blocks[bottom:bottom + 81, zi, xi]
                usable = []
                for y, block in enumerate(col[:-2]):
                    name, props = abbey.c.STATES[block]
                    if block == 0 or name.endswith(('_stairs', '_bars', '_chain', '_lantern', '_vein', '_lichen', '_carpet')):
                        continue
                    if col[y + 1] not in walk_through or col[y + 2] not in walk_through:
                        continue
                    slab = name.endswith('_slab') and dict(props)['type'] == 'bottom'
                    height = y * 16 + (8 if slab else 16)
                    if self.names[col[y + 1]].endswith('_carpet'):
                        height += 1
                    usable.append(height)
                treads[x, z] = usable
        return treads

    def test_spirals_reach_the_belfries_and_organ_without_jumps_in_model(self):
        # The node model checks headroom and the vanilla 0.6-block step limit at cell centers.
        # It does not simulate client movement or reconstruct finite-width player collision.
        for side in (-1, 1):
            with self.subTest(side=side):
                cx = side * 31
                treads = self.walkable_treads(cx)
                start = cx + side * 7, 9, 16 * 5
                self.assertIn(start[2], treads[start[:2]])
                queue, reached = deque([start]), {start}
                while queue:
                    x, z, y = queue.popleft()
                    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        for h in treads.get((x + dx, z + dz), ()):
                            dest = x + dx, z + dz, h
                            if abs(h - y) <= 9 and dest not in reached:
                                reached.add(dest)
                                queue.append(dest)
                reached_heights = {h for _, _, h in reached}
                self.assertIn(77 * 16, reached_heights)
                self.assertGreater(sum(h % 16 == 8 for h in reached_heights), 45)
                if side > 0:
                    self.assertIn((22, 9, 31 * 16), reached)

    def test_ground_paths_reach_both_new_buildings_and_inherited_destinations(self):
        highest = self.point(0, 13, 0)[0]
        low = self.blocks[:highest]
        free = np.isin(low, [0, *self.decor])
        floor = ~free[:-2] & free[1:-1] & free[2:]
        start = self.point(0, -5, -66)
        r = abbey.r
        cx, cz = abbey.CHAPEL
        targets = {self.point(x, y, z) for x, y, z in (
            (0, 4, 120), (-6, 7, 171), (0, -12, 167), (0, 4, 211), (-84, 0, 120),
            (-95, 0, 120), (-114, 0, 108), (-133, 0, 120), (-143, 0, 121),
            (cx, 3, cz - 22), (cx, 3, cz), (r.PX, r.PBASE, r.PZ), (72, 2, 183),
        )}
        self.assertTrue(floor[start])
        queue, seen = deque([start]), {start}
        while queue and not targets <= seen:
            y, z, x = queue.popleft()
            for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                zi, xi = z + dz, x + dx
                if not (0 <= zi < floor.shape[1] and 0 <= xi < floor.shape[2]):
                    continue
                for yi in range(max(0, y - 1), min(floor.shape[0], y + 2)):
                    pos = yi, zi, xi
                    if floor[pos] and pos not in seen:
                        seen.add(pos)
                        queue.append(pos)
        self.assertFalse(targets - seen, f'Unreachable standing positions: {targets - seen}')

    def test_whole_abbey_keeps_night_spawn_protection(self):
        r = abbey.r
        self.assertFalse(r.spawn_exposure(self.blocks, r.block_light(self.blocks)).any())
        palette = self.region['BlockStatePalette']
        self.assertNotIn('minecraft:nether_portal', {str(tag['Name']) for tag in palette})
        shriekers = [tag for tag in palette if tag['Name'] == 'minecraft:sculk_shrieker']
        self.assertTrue(shriekers)
        self.assertTrue(all(tag['Properties']['can_summon'] == 'false' for tag in shriekers))


if __name__ == '__main__':
    unittest.main()
