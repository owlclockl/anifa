import tempfile
import unittest
from collections import Counter, deque
from pathlib import Path

import nbtlib
import numpy as np

from tools import build_throne_cathedral as throne
from test_cathedral import unpack


class BlockEntityExportTests(unittest.TestCase):
    def test_tiles_are_rebased_after_cropping_on_all_axes(self):
        c = throne.c
        barrel = c.state('barrel', facing='north', open='false')
        blocks = np.zeros((9, 11, 12), dtype=np.int16)
        blocks[2, 3, 4] = c.STONE
        blocks[5, 7, 10] = barrel
        tag = nbtlib.Compound(id=nbtlib.String('minecraft:barrel'), x=nbtlib.Int(99))
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'tiles.litematic'
            c.save(output, blocks, block_entities={(10, 5, 7): tag})
            region = nbtlib.load(output)['Regions']['Cathedral']
        tile, = region['TileEntities']
        self.assertEqual(tuple(tile[k] for k in 'xyz'), (6, 3, 4))
        self.assertEqual(tag['x'], 99, 'Export must not mutate the source NBT')
        cell = int(unpack(region)[tile['y'], tile['z'], tile['x']])
        self.assertEqual(region['BlockStatePalette'][cell]['Name'], tile['id'])

    def test_tiles_cannot_be_written_into_air_or_outside_the_grid(self):
        blocks = np.zeros((4, 4, 4), dtype=np.int16)
        blocks[0, 0, 0] = blocks[3, 3, 3] = throne.BRICK
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'invalid.litematic'
            for pos in ((1, 1, 1), (-1, 3, 3)):
                with self.subTest(pos=pos), self.assertRaises(ValueError):
                    throne.c.save(output, blocks, block_entities={pos: nbtlib.Compound()})
            self.assertFalse(output.exists())


class ThroneSchematicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file = nbtlib.load(throne.OUTPUT)
        cls.region = cls.file['Regions']['Cathedral']
        cls.drawn = throne.build()
        cls.bounds = tuple(slice(int(a.min()), int(a.max()) + 1) for a in np.nonzero(cls.drawn))
        cls.states = throne.c.STATES
        lookup = {state: i for i, state in enumerate(cls.states)}
        remap = []
        for entry in cls.region['BlockStatePalette']:
            props = tuple(sorted((str(k), str(v)) for k, v in entry.get('Properties', {}).items()))
            remap.append(lookup[(str(entry['Name']), props)])
        cls.blocks = np.array(remap, dtype=np.int16)[unpack(cls.region)]
        cls.light = throne.r.block_light(cls.drawn)
        cls.names = [name.removeprefix('minecraft:') for name, _ in cls.states]

    @classmethod
    def point(cls, x, y, z):
        return tuple(i - bound.start for i, bound in zip(throne.a.Abbey.coord(x, y, z), cls.bounds))

    def at(self, x, y, z):
        return int(self.blocks[self.point(x, y, z)])

    def test_export_matches_the_placement_and_has_no_active_portal(self):
        self.assertEqual((self.file['Version'], self.file['SubVersion'], self.file['MinecraftDataVersion']), (7, 1, 5023))
        self.assertEqual(self.region['Position'], {'x': 0, 'y': 0, 'z': 0})
        self.assertEqual(self.region['Size'], {'x': 341, 'y': 174, 'z': 346})
        meta = self.file['Metadata']
        self.assertEqual(meta['Name'], throne.TITLE)
        self.assertEqual(meta['TotalVolume'], self.blocks.size)
        self.assertEqual(meta['TotalBlocks'], np.count_nonzero(self.blocks))
        self.assertEqual(len(meta['PreviewImageData']), 128**2)
        self.assertFalse(any(self.region[key] for key in ('Entities', 'PendingBlockTicks', 'PendingFluidTicks')))
        np.testing.assert_array_equal(self.blocks, self.drawn[self.bounds])

        r = throne.r
        y, z, x = self.point(r.PX - r.PWIDTH // 2, r.PBASE, r.PZ)
        self.assertFalse(self.blocks[y + 1:y + 1 + r.PHEIGHT, z - 3:z + 4, x:x + r.PWIDTH].any())
        frame = self.blocks[y:y + r.PHEIGHT + 2, z, x - 1:x + r.PWIDTH + 1]
        self.assertTrue((frame[[0, -1], :] == throne.s.OBSIDIAN).all())
        self.assertTrue((frame[:, [0, -1]] == throne.s.OBSIDIAN).all())
        self.assertNotIn('minecraft:nether_portal', {str(tag['Name']) for tag in self.region['BlockStatePalette']})

    def test_arch_and_cupola_use_actual_stairs_slabs_and_connected_rails(self):
        self.assertEqual(self.at(0, 29, -7), throne.c.slab('polished_blackstone_brick', 'top'))
        self.assertEqual(self.at(4, 26, -7), throne.stair('polished_blackstone_brick', 'east', 'top'))
        cx, cz = throne.a.CHAPEL
        y, z, x = self.point(cx - 20, 21, cz - 23)
        shapes = Counter(self.names[i] for i in self.blocks[y:y + 38, z:z + 47, x:x + 41].ravel())
        self.assertGreater(shapes['deepslate_tile_stairs'], 80)
        self.assertGreater(shapes['deepslate_tile_slab'], 100)
        self.assertGreater(shapes['deepslate_tile_wall'], 4)
        name, props = self.states[self.at(-107, 1, 103)]
        self.assertEqual(name, 'minecraft:polished_blackstone_brick_wall')
        data = dict(props)
        self.assertEqual((data['west'], data['east'], data['up']), ('low', 'low', 'false'))
        name, props = self.states[self.at(-153, 1, 52)]
        self.assertEqual(name, 'minecraft:dark_oak_fence')
        self.assertEqual(dict(props)['south'], 'true', 'The fence must meet the gate')
        self.assertEqual(self.names[self.at(-153, 1, 53)], 'dark_oak_fence_gate')

    def test_throne_dais_and_lodge_stair_have_clear_half_steps(self):
        cx, cz = throne.THRONE
        self.assertIn(self.at(cx, 7, cz - 5), (throne.TRIM, throne.SLATE, throne.s.LUMEN))
        self.assertEqual(self.at(cx, 8, cz - 4), throne.stair('polished_blackstone_brick', 'south'))
        self.assertIn(self.at(cx, 8, cz - 3), (throne.TRIM, throne.CARVED))
        self.assertEqual(self.at(cx, 9, cz - 2), throne.PURPUR_STEP)
        self.assertEqual(self.at(cx, 12, cz + 1), throne.VELVET)
        for y, z in ((8, cz - 4), (8, cz - 3), (9, cz - 2)):
            self.assertFalse(self.at(cx, y + 1, z) or self.at(cx, y + 2, z))

        cx, cz = throne.LODGE
        for y in range(1, 9):
            z = cz + 9 - y
            self.assertEqual(self.at(cx + 6, y, z), throne.stair('dark_oak', 'north'))
            self.assertFalse(self.at(cx + 6, y + 1, z) or self.at(cx + 6, y + 2, z))
        self.assertIn(self.at(cx + 6, 8, cz), (throne.WOOD, throne.TRIM, throne.c.LIGHT))

    def test_walkable_connections_to_new_rooms_and_existing_landmarks(self):
        # Topology with manually opened wooden doors and gate, not client collision.
        low = self.blocks[:self.point(0, 14, 0)[0]]
        walk_through = np.array([name in throne.r.NONCOLLIDING or name.endswith(('_carpet', '_door', '_fence_gate'))
                                 for name, _ in self.states])
        stand_on = np.array([throne.r.could_support_spawn(name, props) or name.endswith(('_stairs', '_slab', '_glass', ':glass'))
                             for name, props in self.states])
        floors = stand_on[low[:-2]] & walk_through[low[1:-1]] & walk_through[low[2:]]
        r = throne.r
        targets = {self.point(*p): p for p in (
            (0, 4, 120), (-6, 8, 174), (-6, 9, 175), (0, -12, 167), (0, 4, 211),
            (-114, 0, 108), (-164, 3, 174), (72, 2, 183), (r.PX, r.PBASE, r.PZ),
            (-114, 0, 38), (-114, 8, 38), (-126, 8, 29), (-165, 0, 75), (-172, 0, 78),
            (-168, 0, 29), (-155, 0, 53),
        )}
        start = self.point(0, -5, -66)
        self.assertTrue(floors[start])
        queue, visited = deque([start]), {start}
        remaining = dict(targets)
        while queue and remaining:
            y, z, x = queue.popleft()
            remaining.pop((y, z, x), None)
            for _, dx, dz in throne.CARDINAL:
                zz, xx = z + dz, x + dx
                if not (0 <= zz < floors.shape[1] and 0 <= xx < floors.shape[2]):
                    continue
                for yy in range(max(0, y - 1), min(floors.shape[0], y + 2)):
                    pos = yy, zz, xx
                    if floors[pos] and pos not in visited:
                        queue.append(pos)
                        visited.add(pos)
        self.assertFalse(remaining, f'Unreachable floor positions: {list(remaining.values())}')

    def test_furniture_comes_with_correct_block_entities_and_openable_doors(self):
        tiles = {}
        for tag in self.region['TileEntities']:
            pos = tuple(int(tag[k]) for k in 'yzx')
            self.assertNotIn(pos, tiles)
            self.assertTrue(all(0 <= p < n for p, n in zip(pos, self.blocks.shape)))
            name = self.names[self.blocks[pos]]
            self.assertEqual(tag['id'], 'minecraft:' + throne.BLOCK_ENTITY_IDS[name])
            tiles[pos] = str(tag['id']).removeprefix('minecraft:')
            if tiles[pos] in throne.EMPTY_INVENTORIES:
                self.assertEqual(tag['Items'], [])
        self.assertEqual(Counter(tiles.values()), {
            'bed': 12, 'barrel': 20, 'chest': 4, 'furnace': 3, 'blast_furnace': 2, 'smoker': 2, 'enchanting_table': 1,
        })
        furnishing = [i for i, name in enumerate(self.names) if name in throne.BLOCK_ENTITY_IDS]
        self.assertEqual(set(tiles), set(zip(*np.where(np.isin(self.blocks, furnishing)))))

        cx, cz = throne.LODGE
        for v in (-10, 0, 10):
            for side, facing, color in ((-1, 'west', 'purple'), (1, 'east', 'gray')):
                for u, part in ((12, 'foot'), (13, 'head')):
                    self.assertEqual(self.at(cx + side * u, 9, cz + v),
                                     throne.c.state(color + '_bed', facing=facing, part=part, occupied='false'))
        for x, z, facing in ((cx, cz + 17, 'south'), (-151, 73, 'east'), (-151, 35, 'east')):
            dx, dz = int(facing == 'south'), int(facing == 'east')
            hinges = ('right', 'left') if dx else ('left', 'right')
            for u, hinge in enumerate(hinges):
                for y, half in ((1, 'lower'), (2, 'upper')):
                    self.assertEqual(self.at(x + dx * u, y, z + dz * u), throne.c.state(
                        'dark_oak_door', half=half, facing=facing, hinge=hinge, open='false', powered='false'))

    def test_workshop_has_clear_enchanting_ring_and_operable_stations(self):
        x, z = throne.FORGE
        stations = ('furnace', 'blast_furnace', 'blast_furnace', 'smoker', 'crafting_table', 'smithing_table',
                    'stonecutter', 'anvil', 'grindstone')
        self.assertEqual(tuple(self.names[self.at(x + u, 1, z - 9)] for u in (-10, -8, -6, -3, 1, 3, 5, 7, 9)), stations)
        x, z = x - 7, z + 7
        self.assertEqual(self.names[self.at(x, 1, z)], 'enchanting_table')
        self.assertEqual(sum(self.names[self.at(x + u, 1, z + v)] == 'bookshelf'
                             for v in range(-2, 3) for u in range(-2, 3)), 15)
        self.assertTrue(all(self.at(x + u, y, z + v) == throne.AIR for v in (-1, 0, 1) for u in (-1, 0, 1)
                            if u or v for y in (1, 2)))

    def test_greenhouse_has_contained_sources_and_mature_illuminated_crops(self):
        for x, z in throne.PLOTS:
            self.assertEqual(self.at(x, 0, z), throne.WATER)
            self.assertEqual(self.at(x, 1, z), throne.s.LUMEN)
            for _, dx, dz in throne.CARDINAL:
                self.assertEqual(self.at(x + dx, 0, z + dz), throne.FARMLAND)
        crops = np.isin(self.drawn, throne.CROPS)
        self.assertEqual(crops.sum(), 4 * (7 * 7 - 5))
        self.assertGreaterEqual(self.light[crops].min(), 9, 'Crop light should not depend on daylight')
        self.assertTrue(np.all(self.drawn[:-1][crops[1:]] == throne.FARMLAND))

    def test_dark_spawn_protection_covers_the_entire_site_and_crypt(self):
        r = throne.r
        self.assertFalse(r.spawn_exposure(self.drawn, self.light).any())
        low, north, west = self.point(-35, -14, 145)
        high, south, east = self.point(39, -1, 205)
        self.assertFalse(r.spawn_surfaces(self.blocks[low:high + 1, north:south + 1, west:east + 1]).any())


if __name__ == '__main__':
    unittest.main()
