import unittest
from collections import deque

import nbtlib
import numpy as np

from tools import build_rift_cathedral as rift
from test_cathedral import unpack


class SpawnModelTests(unittest.TestCase):
    def test_block_light_does_not_cross_an_opaque_wall(self):
        cells = np.zeros((5, 5, 8), dtype=np.int16)
        cells[2, 2, 1] = rift.s.LUMEN
        cells[:, :, 4] = rift.BLACK_BRICK
        light = rift.block_light(cells)
        self.assertEqual(light[2, 2, 1], 15)
        self.assertEqual(light[1, 1, 3], 11)
        self.assertFalse(light[:, :, 4:].any())

    def test_bottom_and_top_shapes_are_not_interchangeable(self):
        c = rift.c
        floor = [rift.BLACKSTONE, rift.DARK_STEP, c.slab('polished_blackstone_brick', 'top'),
                 c.slab('polished_blackstone_brick', 'double'), c.stairs('polished_blackstone_brick', 'east'),
                 c.stairs('polished_blackstone_brick', 'east', 'top'), rift.TEAL_GLASS,
                 rift.BLACKSTONE, rift.BLACKSTONE]
        blocks = np.zeros((3, 1, len(floor)), dtype=np.int16)
        blocks[0, 0] = floor
        blocks[1, 0, 7:] = [rift.DARK_CARPET, rift.LICHEN]
        np.testing.assert_array_equal(rift.spawn_surfaces(blocks)[0, 0],
                                      [True, False, True, True, False, True, False, False, True])


class RiftCathedralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file = nbtlib.load(rift.OUTPUT)
        cls.region = cls.file['Regions']['Cathedral']
        cls.palette = cls.region['BlockStatePalette']
        cls.drawn = rift.build()
        cls.bounds = tuple(slice(int(a.min()), int(a.max()) + 1) for a in np.nonzero(cls.drawn))
        states = {state: i for i, state in enumerate(rift.c.STATES)}
        remap = []
        for tag in cls.palette:
            props = tuple(sorted((str(k), str(v)) for k, v in tag.get('Properties', {}).items()))
            remap.append(states[(str(tag['Name']), props)])
        cls.blocks = np.array(remap, dtype=np.int16)[unpack(cls.region)]

    @classmethod
    def point(cls, x, y, z):
        return tuple(a - b.start for a, b in zip(rift.Valley.coord(x, y, z), cls.bounds))

    def at(self, x, y, z):
        return int(self.blocks[self.point(x, y, z)])

    def test_litematic_round_trip(self):
        self.assertEqual((self.file['Version'], self.file['SubVersion'], self.file['MinecraftDataVersion']), (7, 1, 5023))
        self.assertEqual(self.region['Size'], {'x': 259, 'y': 174, 'z': 346})
        self.assertEqual(self.region['Position'], {'x': 0, 'y': 0, 'z': 0})
        meta = self.file['Metadata']
        self.assertEqual(meta['EnclosingSize'], self.region['Size'])
        self.assertEqual(meta['Name'], rift.TITLE)
        self.assertEqual(meta['TotalBlocks'], np.count_nonzero(self.blocks))
        self.assertEqual(meta['TotalVolume'], self.blocks.size)
        self.assertEqual(len(meta['PreviewImageData']), 128**2)
        self.assertEqual(self.palette[0]['Name'], 'minecraft:air')
        self.assertFalse(any(self.region[key] for key in ('Entities', 'TileEntities', 'PendingBlockTicks', 'PendingFluidTicks')))
        np.testing.assert_array_equal(self.blocks, self.drawn[self.bounds])

    def test_obsidian_frame_is_rectangular_with_empty_ignition_space(self):
        x, z = rift.PX, rift.PZ
        bottom, top, half = rift.PBASE, rift.PEND, rift.PWIDTH // 2
        self.assertEqual((2 * half + 1, top - bottom - 1), (13, 18))
        for y in (bottom, top):
            for u in range(-half - 1, half + 2):
                self.assertEqual(self.at(x + u, y, z), rift.s.OBSIDIAN)
        for y in range(bottom + 1, top):
            self.assertEqual(self.at(x - half - 1, y, z), rift.s.OBSIDIAN)
            self.assertEqual(self.at(x + half + 1, y, z), rift.s.OBSIDIAN)
        y1, z1, x1 = self.point(x - half, bottom + 1, z - 3)
        y2, z2, x2 = self.point(x + half, top - 1, z + 3)
        self.assertFalse(self.blocks[y1:y2 + 1, z1:z2 + 1, x1:x2 + 1].any())
        self.assertNotIn('minecraft:nether_portal', {str(tag['Name']) for tag in self.palette})

    def test_export_has_no_dark_spawn_surfaces_even_ignoring_skylight(self):
        exposed = rift.spawn_exposure(self.blocks, rift.block_light(self.blocks))
        self.assertFalse(exposed.any())
        self.assertGreater(np.count_nonzero(self.blocks == rift.ROOF_CAP), 1000)
        self.assertGreater(np.count_nonzero(self.blocks == rift.DARK_STEP), 1000)
        a, b, c = self.point(-35, rift.Y0, 145)
        u, v, w = self.point(39, -1, 205)
        self.assertFalse(rift.spawn_surfaces(self.blocks[a:u + 1, b:v + 1, c:w + 1]).any(),
                         'The crypt should still have covered floors without any light')

    def test_growth_and_lights_retain_their_supports(self):
        state_ids = np.unique(self.blocks)
        c, s = rift.c, rift.s
        for i in state_ids:
            name, props = c.STATES[i]
            if name not in ('minecraft:sculk_vein', 'minecraft:glow_lichen'):
                continue
            y, z, x = np.where(self.blocks == i)
            attached = {face for face, active in props if active == 'true'}
            self.assertTrue(attached)
            for face, dy, dz, dx in s.FACES:
                if face in attached:
                    neighbor = (y - dy, z - dz, x - dx)
                    self.assertTrue(all(a.min() >= 0 and a.max() < n for a, n in zip(neighbor, self.blocks.shape)))
                    # Full-size glass can support a thin attachment but is not a mob platform.
                    for j in np.unique(self.blocks[neighbor]):
                        support, p = c.STATES[j]
                        self.assertTrue(support.endswith('_glass') or rift.could_support_spawn(support, p), support)
        for i, offset in ((c.LANTERN, -1), (s.SOUL, -1), (c.HANGING, 1), (s.SOUL_HANGING, 1)):
            y, z, x = np.where(self.blocks == i)
            for j in np.unique(self.blocks[y + offset, z, x]):
                name, _ = c.STATES[j]
                self.assertNotEqual(j, c.AIR)
                self.assertFalse(name.endswith(('_carpet', '_lichen', '_vein')))
        shriekers = [tag for tag in self.palette if tag['Name'] == 'minecraft:sculk_shrieker']
        self.assertTrue(shriekers)
        self.assertTrue(all(tag['Properties']['can_summon'] == 'false' for tag in shriekers))

    def test_causeway_nave_crypt_overlook_and_nether_gate_connect(self):
        # Two-block path topology, not a full Minecraft player-collision simulation.
        highest = self.point(0, 13, 0)[0]
        low = self.blocks[:highest]
        decor = [i for i, (name, _) in enumerate(rift.c.STATES) if name.endswith(('_carpet', '_vein', '_lichen'))]
        free = (low == 0) | np.isin(low, decor)
        floors = ~free[:-2] & free[1:-1] & free[2:]
        start = self.point(0, -5, -66)
        targets = {self.point(*p) for p in ((0, 0, -31), (0, 4, 120), (-28, -12, 165), (0, -12, 167),
                    (0, 4, 211), (84, 0, 120), (rift.road_x(191), 0, 191), (72, 2, 183),
                    (rift.PX, rift.PBASE, rift.PZ), (rift.PX, rift.PBASE, rift.PZ + 2))}
        self.assertTrue(floors[start])
        queue, seen = deque([start]), {start}
        while queue and not targets <= seen:
            y, z, x = queue.popleft()
            for dz, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                a, b = z + dz, x + dx
                if not (0 <= a < floors.shape[1] and 0 <= b < floors.shape[2]):
                    continue
                for h in range(max(0, y - 1), min(floors.shape[0], y + 2)):
                    cell = h, a, b
                    if floors[cell] and cell not in seen:
                        seen.add(cell)
                        queue.append(cell)
        self.assertFalse(targets - seen, f'Unreachable destinations: {targets - seen}')


if __name__ == '__main__':
    unittest.main()
