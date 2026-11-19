import unittest
from collections import Counter, deque

import nbtlib
import numpy as np

from tools import build_compact_store as compact, catacomb_logistics as l, catacomb_storage as s
from tools.catacomb_routes import tread_tables
from tools.vanilla_catacomb_test import unpack_region


class CompactStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = compact.build()
        cls.file = nbtlib.load(compact.OUTPUT)
        cls.region = cls.file['Regions']['Cathedral']

    def test_export_is_the_small_standalone_module(self):
        g, r = self.g, self.region
        self.assertEqual(self.file['MinecraftDataVersion'], 5023)
        self.assertEqual(self.file['Metadata']['RegionCount'], 1)
        self.assertEqual(compact.extents(g), compact.BOUNDS)
        lo, hi = compact.BOUNDS
        size = tuple(b-a+1 for a, b in zip(lo, hi))
        self.assertEqual(tuple(int(r['Size'][axis]) for axis in 'xyz'), size)
        self.assertEqual(tuple(int(r['Position'][axis]) for axis in 'xyz'), (0, 0, 0))
        self.assertLessEqual(max(size), 44)
        total = int(self.file['Metadata']['TotalBlocks'])
        self.assertEqual(total, np.count_nonzero(g.blocks))
        self.assertLess(total, 6000)
        palette = [compact.c.state(str(acc['Name']).removeprefix('minecraft:'), **acc.get('Properties', {}))
                   for acc in r['BlockStatePalette']]
        np.testing.assert_array_equal(np.asarray(palette)[unpack_region(r)],
                                      g.box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))

    def test_both_banks_ship_with_nbt_and_no_second_public_input(self):
        g, r = self.g, self.region
        tiles = {tuple(int(t[a])+v for a, v in zip('xyz', compact.ORIGIN)): t for t in r['TileEntities']}
        self.assertEqual(len(tiles), len(r['TileEntities']))
        self.assertEqual(len(tiles), len(g.tiles) + len(g.signs))
        expected_hoppers = {compact.raw(cell.at()): cell.item for cell in s.CELLS} | {p.filter: p.item for p in compact.PRESSES}
        self.assertEqual(len(expected_hoppers), 56)
        self.assertEqual(Counter(t['id'] for t in tiles.values())['minecraft:crafter'], 20)
        for spot, item in expected_hoppers.items():
            tag = tiles[spot]
            self.assertEqual(tag['Items'][0]['id'], 'minecraft:' + item)
            self.assertEqual(tag['Items'][0]['count'], 41)
            self.assertEqual([int(v['components']['minecraft:custom_data']['moonspire_spacer']) for v in tag['Items'][1:]], [1]*4)
            self.assertEqual([int(v['count']) for v in tiles[l.step(spot, 'down')]['Items']], [64]*5)
        self.assertEqual({p for p, t in tiles.items() if t['id'] == 'minecraft:chest'},
                         {*l.INTAKE, *l.RETURN, *l.FARM_BUFFER, *(compact.raw(p) for p in (*s.INTAKE, *s.OVERFLOW))})
        self.assertEqual(g.get(*l.step(compact.raw(s.INTAKE[1]), 'up')), s.BRICK)
        for p, tag in tiles.items():
            if tag['id'] == 'minecraft:sign':
                name, props = compact.c.STATES[g.get(*p)]
                self.assertEqual(name, 'minecraft:dark_oak_wall_sign', p)
                back = l.step(p, l.opposite(dict(props)['facing']))
                self.assertTrue(compact.r.could_support_spawn(*compact.c.STATES[g.get(*back)]), p)

    def test_pipe_is_built_in_and_drains_to_shared_intake(self):
        g = self.g
        pipe = compact.WATER_PIPE
        self.assertEqual((len(pipe), pipe[-1]), (17, l.FARM_END))
        x, y, z = compact.WATER_PORT
        self.assertEqual(pipe[0], (x, -5, z))
        for yy in range(-4, y+1):
            self.assertEqual(g.get(x, yy, z), s.AIR)
        channel = set(pipe)
        for i, p in enumerate(pipe):
            name, props = compact.c.STATES[g.get(*p)]
            v = dict(props)
            if i == 8:
                self.assertEqual((name, v['open']), ('minecraft:dark_oak_fence_gate', 'true'))
            else:
                self.assertEqual((name, v['level']), ('minecraft:water', str(i % 9)))
            for d in l.HORIZONTAL:
                q = l.step(p, d)
                if q not in channel:
                    self.assertEqual(g.get(*q), s.GLASS, q)
            if p != l.FARM_END:
                self.assertEqual(g.get(*l.step(p, 'down')), compact.c.state('blue_ice'))
        self.assertEqual(g.get(*l.step(l.FARM_END, 'down')), s.hopper('down'))
        for n in (1, 2):
            self.assertEqual(g.get(*l.step(l.FARM_BUFFER[0], 'down', n)), s.hopper('down'))

    def test_guarded_decks_reach_every_output_from_the_ladder(self):
        g = self.g
        x, z = compact.LADDER_XZ
        for y in range(compact.BASE, compact.WATER_PORT[1]+2):
            self.assertEqual(g.get(x, y, z), compact.LADDER)
            self.assertTrue(compact.r.could_support_spawn(*compact.c.STATES[g.get(x-1, y, z)]))
        goals = {compact.BASE: {(cell.x, compact.BASE, cell.label_pos[2]) for cell in s.CELLS}
                              | {compact.ENTRANCE, (-62, compact.BASE, 154)},
                 -12: {l.INTAKE_STAND}, compact.WATER_PORT[1]: {compact.WATER_STAND}}
        for y in compact.FLOORS:
            goals[y] = {(p.output[0], y, p.output[2]+1) for p in compact.PRESSES if p.output[1] == y+1}
        goals[compact.FLOORS[0]].add(l.RETURN_STAND)
        through, support, _ = tread_tables()
        x0, x1, _, _, z0, z1 = g.limits
        for y, targets in goals.items():
            with self.subTest(y=y):
                seen = set()
                todo = deque([(x+1, y, z)])
                while todo:
                    spot = todo.popleft()
                    px, _, pz = spot
                    if spot in seen or not (x0 <= px <= x1 and z0 <= pz <= z1):
                        continue
                    if support[g.get(*spot)] and all(through[g.get(px, y+h, pz)] for h in (1, 2)):
                        seen.add(spot)
                        todo.extend(l.step(spot, d) for d in l.HORIZONTAL)
                self.assertEqual(targets - seen, set())


if __name__ == '__main__':
    unittest.main()
