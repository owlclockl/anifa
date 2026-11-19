import json
import unittest
from collections import Counter, deque

import nbtlib
import numpy as np

from tools import build_universal_store as u, catacomb_logistics as l, catacomb_storage as s
from tools.catacomb_routes import tread_tables
from tools.vanilla_catacomb_test import unpack_region


class UniversalStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = u.layout()
        cls.schematic = nbtlib.load(u.OUTPUT)
        cls.region = cls.schematic['Regions']['Cathedral']
        cls.tiles = {tuple(int(t[a]) for a in 'xyz'): t for t in cls.region['TileEntities']}

    def state(self, p):
        return u.c.STATES[self.grid.get(*p)]

    def test_smaller_export_matches_builder(self):
        r, meta = self.region, self.schematic['Metadata']
        self.assertEqual(self.schematic['MinecraftDataVersion'], 5023)
        self.assertEqual(tuple(int(r['Position'][a]) for a in 'xyz'), u.ORIGIN)
        dims = tuple(int(r['Size'][a]) for a in 'xyz')
        self.assertEqual(dims, tuple(t + 1 for t in u.BOUNDS[1]))
        self.assertTrue(all(a < b for a, b in zip(dims, (44, 41, 39))))
        self.assertEqual(meta['TotalBlocks'], np.count_nonzero(self.grid.blocks))
        self.assertLess(meta['TotalBlocks'], 5353)
        self.assertEqual(len(meta['PreviewImageData']), 128**2)
        self.assertEqual(len(self.tiles), len(r['TileEntities']))
        self.assertEqual(len(self.tiles), len(self.grid.tiles))
        palette = [u.c.state(str(t['Name']).split(':')[-1], **t.get('Properties', {})) for t in r['BlockStatePalette']]
        np.testing.assert_array_equal(np.asarray(palette)[unpack_region(r)], self.grid.blocks)
        self.assertFalse(any(str(b['Name']).endswith('command_block') for b in r['BlockStatePalette']))

    def test_complete_registry_catalog_is_preseeded(self):
        info = json.loads(u.CATALOG.read_text(encoding='utf-8'))
        self.assertEqual(info['java'], '26.3')
        counts = Counter()
        for cabinet in u.CABINETS:
            inv = [it for p in cabinet.pair for it in self.tiles[p]['Items']]
            ids = [str(it['id']).removeprefix('minecraft:') for it in inv]
            self.assertCountEqual(ids, cabinet.items)
            self.assertTrue(all(it['count'] == 1 for it in inv))
            self.assertLessEqual(len(inv), 42)
            counts.update(ids)
        self.assertEqual(len(counts), info['registry_items'] - 1)
        self.assertEqual(len(counts), 1657)
        self.assertEqual(set(counts.values()), {1})
        self.assertNotIn('air', counts)
        for id_, label in [('cobblestone', 'Камень 1'), ('diamond_pickaxe', 'Инструменты'), ('potion', 'Зелья'),
                           ('written_book', 'Книги и карты'), ('red_shulker_box', 'Шалкеры')]:
            self.assertEqual(u.BY_ID[id_].label, label)

    def test_carts_isolate_each_cell_and_relay_is_last(self):
        entities = self.region['Entities']
        self.assertEqual(len(entities), len(u.CELLS) * u.CART_COUNT)
        origins = Counter()
        regular = {p for chest in u.CABINETS for p in chest.pair} | {p for c in u.CELLS for p in c.relay} | set(u.INTAKE)
        for cart in entities:
            self.assertEqual(cart['id'], 'minecraft:minecart')
            self.assertEqual(len(cart['Passengers']), 1)
            golem = cart['Passengers'][0]
            self.assertEqual(golem['id'], 'minecraft:copper_golem')
            self.assertEqual(golem['next_weather_age'], -2)
            origins[tuple(int(k) for k in golem['Pos'])] += 1
        self.assertEqual(origins, {c.center: u.CART_COUNT for c in u.CELLS})
        for cell in u.CELLS:
            within = {p for p in regular if all(abs(a-b) <= 1 for a,b in zip(p,cell.center))}
            self.assertEqual(within, {b.near for b in cell.cabinets} | {cell.relay[0]})
            center = tuple(a+b for a,b in zip(cell.center,(.5,.25,.5)))
            def distance(p):
                return sum((f+.5 - o)**2 for f,o in zip(p,center))
            self.assertTrue(all(distance(b.near) < distance(cell.relay[0]) for b in cell.cabinets))
            for p in (*cell.inputs, *(p for b in cell.cabinets for p in b.pair)):
                self.assertNotEqual(self.state(l.step(p, 'down'))[0], 'minecraft:hopper', p)

    def path(self, p):
        seen = set()
        while True:
            name, props = self.state(p)
            self.assertNotIn(p, seen, 'A hopper route looped')
            yield p
            if name != 'minecraft:hopper':
                return
            seen.add(p)
            p = l.step(p, dict(props)['facing'])

    def test_dual_transfers_reach_every_bank_and_overflow(self):
        # A lower hopper pulls from the upper one even if their facings are
        # unrelated. Do not allow an X/Z crossing to bypass a stage.
        for p in u.storage().blocks:
            q = l.step(p, 'down')
            if self.state(p)[0] == self.state(q)[0] == 'minecraft:hopper':
                self.assertEqual(tuple(self.path(p))[-1], tuple(self.path(q))[-1], p)
        for a, b in zip(u.CELLS, u.CELLS[1:]):
            self.assertEqual({tuple(self.path(l.step(p,'down')))[-1] for p in a.relay}, set(b.inputs))
        self.assertEqual({tuple(self.path(l.step(p,'down')))[-1] for p in u.CELLS[-1].relay}, set(u.OVERFLOW))
        for p in u.OVERFLOW:
            self.assertEqual(self.state(l.step(p, 'east'))[0], 'minecraft:comparator')
        for pos, unit in zip(u.INTAKE, u.UNLOADERS):
            self.assertEqual(tuple(self.path(unit.drain))[-1], pos)
        self.assertIn(tuple(self.path(l.step(u.WATER_END, 'down')))[-1], u.INTAKE)

    def test_products_and_fallthrough_only_join_downstream(self):
        bus = set(u.PRESS_PATH[:max(u.PRESS_PATH.index(v.bus) for v in u.PRESSES)+1])
        self.assertEqual({u.PRESS_PATH.count(p.bus) for p in u.PRESSES}, {1})
        for press in u.PRESSES:
            filter_items = self.tiles[press.filter]['Items']
            self.assertEqual(filter_items[0]['id'], 'minecraft:'+press.item)
            self.assertEqual([it['count'] for it in filter_items], [1,11,11,11,11])
            self.assertEqual([(it['id'], it['count']) for it in self.tiles[press.reserve]['Items']],
                             [('minecraft:'+press.item, 1)])
            route = tuple(self.path(l.step(press.output, 'down')))
            self.assertFalse(set(route) & bus)
            self.assertFalse({l.step(p, 'down') for p in route[:-1]} & bus)
            self.assertIn(route[-1], u.INTAKE)
            self.assertIn(press.product, u.BY_ID)
        self.assertIn(tuple(self.path(l.step(u.RAW_INPUT, 'down')))[-1], u.INTAKE)

    def test_walkable_landings_from_ground(self):
        # Strict two-cell standing clearance with vertical movement on ladders.
        free, solid, _ = tread_tables()
        all_states = u.c.STATES
        ladders = {i for i,(name,_) in enumerate(all_states) if name == 'minecraft:ladder'}
        free[list(ladders)] = True
        for i,(name,_) in enumerate(all_states):
            if name.endswith('_sign'):
                free[i] = True

        def at(p):
            if all(0 <= a <= b for a,b in zip(p,u.BOUNDS[1])):
                return self.grid.get(*p)
            return s.AIR

        def stand(p):
            return solid[at(l.step(p,'down'))]

        def climb(p):
            return at(p) in ladders

        def occupiable(p):
            return all(free[at(l.step(p,'up',i))] for i in (0,1)) and (stand(p) or climb(p) or climb(l.step(p,'down')))

        first = (1,1,31)
        seen = {first}
        todo = deque((first,))
        while todo:
            p = todo.popleft()
            sides = [l.step(p,d) for d in l.HORIZONTAL]
            moves = list(sides)
            if climb(p):
                moves.extend((l.step(p,'up'), l.step(p,'down')))
            if climb(l.step(p,'down')):
                moves.append(l.step(p,'down'))
            if stand(p) or climb(l.step(p,'down')):
                moves.extend(l.step(v,'down') for v in sides)
                if free[at(l.step(p,'up',2))]:
                    moves.extend(l.step(v,'up') for v in sides)
            for q in moves:
                if q not in seen and occupiable(q):
                    seen.add(q)
                    todo.append(q)
        for cell in u.CELLS:
            x,y,z = cell.center
            for v in cell.cabinets:
                xx,_,zz = v.far
                spot = (xx,y,zz-1) if zz == z-2 else (xx+(1 if xx>x else -1),y,zz)
                self.assertTrue(spot in seen, f'{v.label} is inaccessible at {spot}')
        required = {(2,29,5), (3,17,28), (1,20,25), (10,25,29), (25,25,29), (13,1,20)}
        self.assertLessEqual(required, seen)


if __name__ == '__main__':
    unittest.main()
