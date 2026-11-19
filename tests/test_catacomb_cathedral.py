import unittest
from collections import Counter

import nbtlib
import numpy as np

from tools import build_catacomb_cathedral as abyss
from tools import catacomb_finishes as finishes, catacomb_logistics as logistics
from tools import catacomb_routes as routes
from tools import catacomb_access as access, catacomb_funicular as f, catacomb_storage as store
from test_cathedral import unpack


class LightAndStepTests(unittest.TestCase):
    def test_invisible_light_emits_its_own_level_and_is_passable(self):
        grid = np.zeros((5, 5, 7), dtype=np.int16)
        grid[1, 2, 3] = abyss.BRICK
        grid[2, 2, 3] = abyss.lamp(7)
        light = abyss.r.block_light(grid)
        self.assertEqual(light[2, 2, 3], 7)
        self.assertEqual(light[2, 2, 4], 6)
        self.assertEqual(light[3, 2, 5], 4)
        self.assertTrue(abyss.r.spawn_surfaces(grid)[1, 2, 3])
        self.assertFalse(abyss.r.spawn_surfaces(grid)[2, 2, 3])
        self.assertTrue(routes.tread_tables()[0][abyss.lamp(7)])

    def test_half_step_audit_distinguishes_the_face_of_the_stair(self):
        c = abyss.c
        grid = np.zeros((7, 5, 7), dtype=np.int16)
        grid[2, 2, 2] = abyss.TRIM
        grid[3, 2, 4] = abyss.TRIM
        grid[2, 2, 3] = abyss.TRIM
        x, y, z = abyss.X0, abyss.Y0, abyss.Z0
        start = x + 2, y + 2, z + 2
        target = {(x + 4, y + 3, z + 2)}
        grid[3, 2, 3] = c.stairs('polished_blackstone_brick', 'east')
        self.assertEqual(routes.paths(grid, start, target, limit_y=y + 6), target)
        grid[3, 2, 3] = c.stairs('polished_blackstone_brick', 'west')
        self.assertEqual(routes.paths(grid, start, target, limit_y=y + 6), set())


class CatacombsEditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = abyss.build_site()
        cls.blocks = cls.g.blocks
        cls.light = abyss.r.block_light(cls.blocks)
        cls.file = nbtlib.load(abyss.OUTPUT)
        cls.region = cls.file['Regions']['Cathedral']
        cls.bounds = tuple(slice(int(c.min()), int(c.max()) + 1) for c in np.nonzero(cls.blocks))
        cls.palette = cls.region['BlockStatePalette']

    def test_vanilla_round_trip_entire_region(self):
        self.assertEqual((self.file['Version'], self.file['SubVersion'], self.file['MinecraftDataVersion']), (7, 1, 5023))
        meta = self.file['Metadata']
        self.assertEqual(meta['Name'], abyss.TITLE)
        self.assertEqual(self.region['Position'], {'x': 0, 'y': 0, 'z': 0})
        self.assertEqual(self.region['Size'], {'x': 341, 'y': 203, 'z': 346})
        self.assertEqual(meta['TotalVolume'], np.prod(self.blocks[self.bounds].shape))
        self.assertEqual(meta['TotalBlocks'], np.count_nonzero(self.blocks))
        self.assertEqual(len(meta['PreviewImageData']), 128**2)
        self.assertFalse(any(self.region[key] for key in ('Entities', 'PendingBlockTicks', 'PendingFluidTicks')))
        by_state = {entry: i for i, entry in enumerate(abyss.c.STATES)}
        mapping = np.array([by_state[(str(tag['Name']), tuple(sorted((str(k), str(v)) for k, v in tag.get('Properties', {}).items())))]
                            for tag in self.palette], dtype=np.int16)
        np.testing.assert_array_equal(mapping[unpack(self.region)], self.blocks[self.bounds])

    def test_entire_site_has_no_dark_floors_and_low_floors_do_not_depend_on_light(self):
        r = abyss.r
        floor = r.spawn_surfaces(self.blocks)
        self.assertTrue(floor.any())
        self.assertGreaterEqual(int(self.light[1:][floor].min()), abyss.MIN_LIGHT)
        self.assertFalse(floor[:abyss.ROCK_ROOF - abyss.Y0].any(), 'Slime protection must be geometric')
        glow = np.array([name == 'minecraft:light' for name, _ in abyss.c.STATES])[self.blocks]
        self.assertGreater(glow.sum(), 1000)
        self.assertTrue(glow[:abyss.ROCK_ROOF - abyss.Y0].any())
        self.assertTrue(glow[60 - abyss.Y0:].any(), 'Also check roof and tower lighting')
        crops = np.isin(self.blocks, abyss.t.CROPS)
        self.assertEqual(crops.sum(), 176)
        self.assertGreaterEqual(self.light[crops].min(), 9)

    def test_all_districts_and_both_belfries_connect_without_jumps_in_tread_model(self):
        a, r = abyss.a, abyss.r
        y = abyss.LOW
        targets = {
            (0, 0, -31), (0, 4, 120), (-6, 9, 175), (0, 4, 211), (0, -12, 167),
            abyss.CRYPT_GATE, abyss.LOW_CRYPT_GATE, abyss.SERVICE_FOOT, abyss.SERVICE_DOOR,
            (abyss.HUB.x, y, abyss.HUB.z), (abyss.NAMES.x, y, abyss.NAMES.z),
            (abyss.ARCHIVE.x, y, abyss.ARCHIVE.z), (abyss.BELLS.x, y, abyss.BELLS.z),
            (8, y, abyss.HEART.z), (30, y, abyss.HEART.z),
            (-114, 0, 108), (a.CHAPEL[0], 3, a.CHAPEL[1]), (-114, 0, 38), (-114, 8, 38),
            (-165, 0, 75), logistics.FARM_STAND, (-155, 0, 53),
            (72, 2, 183), (r.PX, r.PBASE, r.PZ), (r.PX, r.PBASE, r.PZ + 2),
            (-38, 4, 9), (38, 4, 9), (-31, 76, 5), (31, 76, 5), (0, 30, 10),
        }
        for start in ((0, -5, -66), (abyss.HUB.x, y, abyss.HUB.z)):
            with self.subTest(start=start):
                got = routes.paths(self.blocks, start, targets)
                self.assertFalse(targets - got, f'Unreached floor coordinates: {targets - got}')

    def test_reclaimed_rooms_and_both_rail_platforms_are_reachable(self):
        targets = {access.TRIFORIUM, access.CHAPEL_LOGGIA, access.ROOF_LOBBY,
                   access.ROOF_WALK, access.ROOF_END, *access.ROOF_ENTRIES,
                   f.UPPER, f.LOWER, f.STAIR, (-46, f.TOP_Y, 178), (-22, f.TOP_Y, 179)}
        for start in ((0, -5, -66), (abyss.HUB.x, abyss.LOW, abyss.HUB.z)):
            with self.subTest(start=start):
                self.assertEqual(routes.paths(self.blocks, start, targets), targets)

    def test_roof_walk_directly_links_the_two_tower_stairs(self):
        # Exclude the ground, otherwise the old crossing at the entrance could
        # conceal a gap in the upper route.
        for start, other in (access.ROOF_ENTRIES, access.ROOF_ENTRIES[::-1]):
            targets = {other, access.ROOF_END}
            self.assertEqual(routes.paths(self.blocks, start, targets, first_y=58, limit_y=67), targets)

    def test_funicular_has_a_guarded_stair_even_without_the_track(self):
        only_stair = np.zeros_like(self.blocks)
        a = self.g.box(-33, -30, f.BOTTOM_Y, f.TOP_Y + 4, f.TOP_Z, f.BOTTOM_Z)
        lo = self.g.coord(-33, f.BOTTOM_Y, f.TOP_Z)
        only_stair[tuple(slice(i, i + n) for i, n in zip(lo, a.shape))] = a
        for start, end in ((f.UPPER, f.LOWER), (f.LOWER, f.UPPER)):
            targets = {end, f.STAIR}
            self.assertEqual(routes.paths(only_stair, start, targets,
                                          first_y=f.BOTTOM_Y, limit_y=f.TOP_Y + 4), targets)
        with self.subTest('separation along the entire gradient'):
            for z in range(182, 204):
                for h in (1, 2):
                    self.assertIn(self.g.get(-29, f.floor(z) + h, z), (f.TINT, f.TRIM))

    def test_funicular_exports_a_neutral_interlock_and_clear_track(self):
        grid = self.g
        wiring = f.wiring()
        for pos, (name, props) in wiring.parts.items():
            self.assertEqual(abyss.c.STATES[grid.get(*pos)], ('minecraft:' + name, tuple(sorted(props.items()))), pos)
        for pos in wiring.dust:
            name, props = abyss.c.STATES[grid.get(*pos)]
            self.assertEqual((name, dict(props)['power']), ('minecraft:redstone_wire', '0'), pos)
        # Buffer plates are de-energised. Main traction is continuously powered;
        # plain rail and detector rail separate it from each buffer.
        through, _, _ = routes.tread_tables()
        for z in range(f.TOP_Z, f.BOTTOM_Z + 1):
            y = f.floor(z)
            name, props = abyss.c.STATES[grid.get(f.TRACK_X, y + 1, z)]
            p = dict(props)
            self.assertEqual(p['shape'], 'ascending_north' if 183 <= z <= 203 else 'north_south')
            if z in (f.TOP_Z, f.BOTTOM_Z):
                self.assertEqual((name, p['powered']), ('minecraft:powered_rail', 'false'))
                dz = -1 if z == f.TOP_Z else 1
                self.assertEqual(grid.get(f.TRACK_X, y + 1, z+dz), f.BUMPER)
            elif z in (f.TOP_Z + 2, f.BOTTOM_Z - 2):
                self.assertEqual((name, p['powered']), ('minecraft:detector_rail', 'false'))
            elif z in (f.TOP_Z + 1, f.BOTTOM_Z - 1):
                self.assertEqual(name, 'minecraft:rail')
            else:
                self.assertEqual((name, p['powered']), ('minecraft:powered_rail', 'true'))
            for yy in (y + 2, y + 3):
                self.assertTrue(through[grid.get(f.TRACK_X, yy, z)], (z, yy))
        self.assertFalse(any('command_block' in str(p['Name']) or p['Name'] == 'minecraft:lava' for p in self.palette))
        self.assertTrue(all(abs(x - f.TRACK_X) < 4 for x, _, _ in f.CONTROLS))

    def test_funicular_inventory_survives_region_rebase(self):
        iy, iz, ix = (sl.start for sl in self.bounds)
        tiles = {(int(v['x']) + ix, int(v['y']) + iy, int(v['z']) + iz): v
                 for v in self.region['TileEntities']}
        for p, data in f.inventory_data().items():
            y, z, x = self.g.coord(*p)
            tile = tiles[x, y, z]
            self.assertEqual(tile['id'], data['id'])
            self.assertEqual(tile.get('Items', []), data.get('Items', []))
        self.assertFalse(self.region['Entities'])  # a single cart is placed by the player

    def test_storage_is_reachable_from_the_ring_including_each_pickup_bay(self):
        # Foot positions one block in front of each labelled two-barrel stack.
        pickup = {(cell.x, store.FLOOR, cell.z - 2 * cell.direction) for cell in store.CELLS}
        pickup.update((-62, store.FLOOR, z) for z in (153, 154))
        targets = {store.RING_TURN, store.ENTRY, store.RECEIVING, store.AISLE, store.FAR_AISLE, *pickup}
        for start in ((0, -5, -66), (abyss.HUB.x, abyss.LOW, abyss.HUB.z)):
            with self.subTest(start=start):
                self.assertEqual(routes.paths(self.blocks, start, targets), targets)
        for x, y, z in (*logistics.INTAKE, *logistics.RETURN, *store.OVERFLOW):
            lid = self.g.get(x, y + 1, z)
            # A hopper over a lower chest is non-occluding; a solid lintel isn't.
            self.assertTrue(lid == abyss.AIR or abyss.c.STATES[lid][0] in {'minecraft:light', 'minecraft:hopper'})

    def test_export_ships_all_36_filters_with_seed_and_four_distinct_spacer_slots(self):
        iy, iz, ix = (sl.start for sl in self.bounds)
        min_x, min_y, min_z = ix + abyss.X0, iy + abyss.Y0, iz + abyss.Z0
        tiles = {(int(tag['x']) + min_x, int(tag['y']) + min_y, int(tag['z']) + min_z):
                 nbtlib.Compound({k: v for k, v in tag.items() if k not in 'xyz'}) for tag in self.region['TileEntities']}
        cells = store.CELLS
        self.assertEqual(len(cells), 36)
        self.assertEqual(len({cell.item for cell in cells}), 36)
        expected = store.inventory_data()
        for p, tag in expected.items():
            self.assertEqual(tiles[p], tag, p)
            self.assertEqual(abyss.c.STATES[self.g.get(*p)][0], tag['id'], p)
        seeded = {p for p, tag in tiles.items() if tag['id'] == 'minecraft:hopper' and tag.get('Items')}
        self.assertEqual(seeded, {p for cell in cells for p in (cell.at(), cell.delivery[0])}
                         | {p for unit in logistics.PRESSES for p in (unit.filter, unit.reserve)})
        for cell in cells:
            slots = tiles[cell.at()]['Items']
            self.assertEqual([(v['Slot'], v['count']) for v in slots], [(0, 41), (1, 1), (2, 1), (3, 1), (4, 1)])
            self.assertEqual(slots[0]['id'], 'minecraft:' + cell.item)
            self.assertFalse(slots[0].get('components'))
            reserve = tiles[cell.delivery[0]]['Items']
            self.assertEqual([(v['Slot'], v['count'], v['id']) for v in reserve],
                             [(i, 64, 'minecraft:' + cell.item) for i in range(5)])
            for filler in slots[1:]:
                self.assertEqual(filler['id'], 'minecraft:paper')
                self.assertEqual(filler['components']['minecraft:custom_data']['moonspire_spacer'], 1)
            self.assertTrue(all(not tiles[p]['Items'] for p in cell.barrels))
            sign = tiles[cell.label_pos]
            self.assertEqual([str(line) for line in sign['front_text']['messages'] if line], list(cell.label))

    def test_storage_bus_passes_every_filter_and_drains_to_overflow(self):
        g, c = self.g, abyss.c
        self.assertEqual(len(store.PATH), len(set(store.PATH)))
        self.assertTrue({cell.at(1) for cell in store.CELLS} <= set(store.PATH))
        for here, next_pos in zip(store.PATH, (*store.PATH[1:], store.OVERFLOW_SINK[0])):
            dx, dy, dz = (q-p for p, q in zip(here, next_pos))
            self.assertEqual(abs(dx) + abs(dy) + abs(dz), 1)
            self.assertEqual(g.get(*here), store.hopper('down' if dy == -1 else abyss.t.direction(dx, dz)))
        for cell in store.CELLS:
            self.assertEqual(g.get(*cell.at(-1)), store.hopper(cell.front, enabled=False))
            for dy, dz in ((0, 1), (0, 2), (0, 3), (-1, 4), (-2, 3)):
                self.assertTrue(abyss.r.could_support_spawn(*c.STATES[g.get(*cell.at(dy - 1, dz))]))
        self.assertEqual(g.get(*store.OVERFLOW_LAMP), c.state('redstone_lamp', lit='false'))

    def test_workshop_routes_connect_the_input_return_and_all_compactors(self):
        l = logistics
        targets = {l.STAIR_FOOT, l.WORKSHOP_ENTRY, l.UPPER_ENTRY, l.INTAKE_STAND, l.RETURN_STAND,
                   *((unit.output[0], l.FLOOR, unit.output[2] + 1) for unit in l.PRESSES)}
        reached = routes.paths(self.blocks, (abyss.HUB.x, abyss.LOW, abyss.HUB.z), targets)
        self.assertEqual(targets - reached, set())

    def test_workshop_exports_every_board_and_the_loaded_compactor_filters(self):
        l = logistics
        expected, tags = l.states_and_tiles()
        self.assertEqual(len(l.PRESSES), 20)
        self.assertEqual(len({p.item for p in l.PRESSES}), 20)
        self.assertNotIn('quartz', {p.item for p in l.PRESSES})
        self.assertNotIn('amethyst_shard', {p.item for p in l.PRESSES})
        iy, iz, ix = (sl.start for sl in self.bounds)
        tiles = {(int(v['x'])+ix, int(v['y'])+iy, int(v['z'])+iz):
                 nbtlib.Compound({k: n for k, n in v.items() if k not in 'xyz'}) for v in self.region['TileEntities']}
        for p, state in expected.items():
            self.assertEqual(self.g.get(*p), state, (p, abyss.c.STATES[state]))
        for p, want in tags.items():
            y, z, x = self.g.coord(*p)
            self.assertEqual(tiles[x, y, z], want, p)
        for unit in l.PRESSES:
            self.assertEqual(tags[unit.origin]['id'], 'minecraft:crafter')
            self.assertEqual(tags[unit.filter]['Items'][0]['id'], 'minecraft:' + unit.item)
            self.assertFalse(tags[unit.origin]['Items'])
            self.assertFalse(tags[unit.output]['Items'])
        # One public intake, one private join into the historical sorter. A
        # solid over one half makes that old chest impossible to open normally.
        self.assertIn(l.ENTRY_SPLIT.meter, {l.step(p, 'down') for p in l.INTAKE})
        self.assertEqual(self.g.get(*l.step(store.INTAKE[1], 'up')), store.BRICK)

    def test_farm_water_is_a_contained_continuous_route_to_the_intake(self):
        l = logistics
        self.assertEqual(len(l.FARM_PIPE), 215)
        self.assertEqual(l.FARM_PIPE[0], (l.FARM_PORT[0], -5, l.FARM_PORT[2]))
        self.assertEqual(l.FARM_PIPE[-1], l.FARM_END)
        route = set(l.FARM_PIPE)
        shaft = set(l.path(l.step(l.FARM_PIPE[0], 'up'), l.FARM_PORT))
        for d in l.HORIZONTAL:
            q = l.step(l.step(l.FARM_PORT, 'up'), d)
            name, props = abyss.c.STATES[self.g.get(*q)]
            self.assertEqual(name, 'minecraft:dark_oak_fence', q)
            self.assertTrue(all(dict(props)[v] == 'true' for v in l.HORIZONTAL if v not in (d, l.opposite(d))), q)
        for i, p in enumerate(l.FARM_PIPE):
            name, props = abyss.c.STATES[self.g.get(*p)]
            v = dict(props)
            if i % 9 == 8:
                self.assertEqual((name, v['open']), ('minecraft:dark_oak_fence_gate', 'true'))
            else:
                self.assertEqual((name, v['level']), ('minecraft:water', str(i % 9)))
            for side in l.HORIZONTAL:
                q = l.step(p, side)
                if q not in route:
                    self.assertEqual(self.g.get(*q), store.GLASS, q)
            if i < len(l.FARM_PIPE) - 1:
                self.assertEqual(self.g.get(*l.step(p, 'down')), abyss.c.state('blue_ice'))
            cap = l.step(p, 'up')
            if cap not in shaft:
                # The pipe passes directly below one of the shaft's glass walls.
                roof = store.GLASS if any(l.step(cap, d) in shaft for d in l.HORIZONTAL) else store.TRIM
                self.assertEqual(self.g.get(*cap), roof, cap)
        self.assertEqual(self.g.get(*l.step(l.FARM_END, 'down')), store.hopper('down'))
        # A conductor on top of the second half suppresses the vanilla
        # comparator reading of the entire double chest, but not hopper flow.
        self.assertEqual(self.g.get(*l.step(l.FARM_BUFFER[1], 'up')), store.GLASS)

    def test_both_sides_of_the_catacomb_ring_can_be_used_independently(self):
        y = abyss.LOW
        hub = (abyss.HUB.x, y, abyss.HUB.z)
        target = {(30, y, abyss.HEART.z)}
        for z in (146, 193):
            with self.subTest(closed_at=z):
                blocked = self.blocks.copy()
                yi, zi, xi = self.g.coord(-77, y+1, z)
                blocked[yi:yi+7, zi, xi:xi+7] = abyss.BRICK
                self.assertEqual(routes.paths(blocked, hub, target, first_y=y-3, limit_y=y+6), target)

    def test_mourning_hall_marks_and_archival_relics_have_region_local_data(self):
        tags = self.region['TileEntities']
        kinds = Counter(str(tag['id']) for tag in tags)
        self.assertEqual(kinds['minecraft:bell'], 7 + len(f.DETECTORS))
        self.assertEqual(kinds['minecraft:sign'], len(self.g.signs))
        self.assertGreaterEqual(kinds['minecraft:sign'], 24)
        self.assertEqual(kinds['minecraft:bed'], 12)
        all_positions = set()
        y0, z0, x0 = (n.start for n in self.bounds)
        sign_names = set()
        for tag in tags:
            x, y, z = (int(tag[k]) for k in 'xyz')
            self.assertNotIn((x, y, z), all_positions)
            all_positions.add((x, y, z))
            p = (y + y0, z + z0, x + x0)
            block, props = abyss.c.STATES[self.blocks[p]]
            if tag['id'] == 'minecraft:sign':
                self.assertEqual(block, 'minecraft:dark_oak_wall_sign')
                self.assertEqual(len(tag['front_text']['messages']), 4)
                self.assertTrue(tag['front_text']['has_glowing_text'])
                sign_names.add(str(tag['front_text']['messages'][0]))
                dx, dz = abyss.VECTORS[dict(props)['facing']]
                self.assertTrue(abyss.r.could_support_spawn(*abyss.c.STATES[self.blocks[p[0], p[1]-dz, p[2]-dx]]))
            elif tag['id'] == 'minecraft:bell':
                self.assertEqual(block, 'minecraft:bell')
                if p in {self.g.coord(*q) for q in f.BELLS}:
                    self.assertEqual(dict(props)['attachment'], 'floor')
                    self.assertEqual(self.blocks[p[0]-1, p[1], p[2]], f.METAL)
                else:
                    self.assertEqual(dict(props)['attachment'], 'ceiling')
                    self.assertEqual(self.blocks[p[0]+1, p[1], p[2]], abyss.COPPER)
            elif p == self.g.coord(*abyss.RELIQUARY):
                self.assertEqual(block, 'minecraft:chest')
                self.assertEqual({str(item['id']): int(item['count']) for item in tag['Items']},
                                 {'minecraft:music_disc_5': 1, 'minecraft:echo_shard': 5, 'minecraft:recovery_compass': 1})
        self.assertIn('Печать глубин', sign_names)
        self.assertIn('Лунный архив', sign_names)
        self.assertIn('Семь колоколов', sign_names)
        u, v, w = self.g.coord(*abyss.RELIQUARY)
        self.assertIn((w-x0, u-y0, v-z0), all_positions)

    def test_sculk_is_real_in_the_east_wing_spire_chapel_and_catacombs(self):
        b, s = abyss, abyss.s
        names = {str(tag['Name']).removeprefix('minecraft:') for tag in self.palette}
        self.assertFalse(names & {'sculk_catalyst', 'spawner', 'trial_spawner', 'glow_lichen',
                                  'cyan_concrete', 'blue_concrete', 'black_concrete', 'warped_wart_block'})
        sites = (
            ('east branches', (38, 92, 40, 110, 112, 208), 9_000),
            ('spire', (-14, 14, 139, 159, 112, 135), 350),
            ('choir', (9, 29, 7, 25, 162, 185), 2_500),
            ('chapel', (-200, -128, 0, 60, 146, 201), 700),
        )
        for name, bounds, minimum in sites:
            with self.subTest(site=name):
                self.assertGreater(np.count_nonzero(self.g.box(*bounds) == s.SCULK), minimum)
        self.assertGreater(np.count_nonzero(np.isin(self.blocks, tuple(b.c.GLASS.values()))), 2_000,
                           'Decorative stained glass is not the infestation')
        x, z, y = b.HEART.x, b.HEART.z, b.LOW
        sealed = self.g.box(x-6, x+6, y-3, y+5, z-7, z+7)
        self.assertGreater(np.count_nonzero(sealed == s.SCULK), 200)
        self.assertIn(s.SENSOR, sealed)
        self.assertIn(s.SHRIEKER, sealed)
        self.assertNotIn(s.LUMEN, sealed)
        for side in (-1, 1):
            glass = self.g.box(x-7, x+7, y+1, y+6, z+side*8, z+side*8)
            self.assertTrue(np.isin(glass, (b.c.state('glass'), b.TINT, b.BASALT)).all())

    def test_sculk_devices_are_supported_and_veins_attach_to_real_faces(self):
        b, s = abyss, abyss.s
        used = np.unique(self.blocks)
        sturdy = np.array([name.endswith((':glass', '_glass')) or (
            b.r.could_support_spawn(name, props) and not name.endswith(('_stairs', '_slab')))
            for name, props in b.c.STATES])
        for device in (s.SENSOR, s.SHRIEKER):
            y, z, x = np.where(self.blocks == device)
            self.assertGreater(len(y), 10)
            self.assertTrue(sturdy[self.blocks[y-1, z, x]].all())
        shriekers = [entry for entry in self.palette if entry['Name'] == 'minecraft:sculk_shrieker']
        self.assertTrue(shriekers and all(entry['Properties']['can_summon'] == 'false'
                                         for entry in shriekers))
        vein_count = 0
        for i in used:
            name, props = b.c.STATES[i]
            if name != 'minecraft:sculk_vein':
                continue
            faces = [(dy, dz, dx) for face, dy, dz, dx in s.FACES if dict(props)[face] == 'true']
            self.assertTrue(faces, 'A vein needs at least one attached face')
            y, z, x = np.where(self.blocks == i)
            vein_count += len(y)
            for dy, dz, dx in faces:
                backing = (y-dy, z-dz, x-dx)
                self.assertTrue(all(((axis >= 0) & (axis < size)).all()
                                    for axis, size in zip(backing, self.blocks.shape)))
                supports = self.blocks[backing]
                self.assertTrue(sturdy[supports].all(), f'Unsupported faces for {dict(props)}')
                self.assertFalse(np.any(supports == s.SCULK), 'Veins should fringe the stone, not coat sculk')
        self.assertGreater(vein_count, 5_000)

    def test_exterior_and_interior_profiles_have_recesses_and_clear_spans(self):
        b, at = abyss, self.g.get
        # Main portal, two depths above the opening; the central span is still clear.
        self.assertEqual(at(0, 31, -8), b.TOMB)
        self.assertEqual(at(0, 31, -9), b.TUFF_LIP)
        self.assertEqual(at(0, 29, -8), b.AIR)
        # Blind lancet inset between the two projecting pilasters of a buttress.
        self.assertEqual(at(46, 16, 37), b.AIR)
        self.assertEqual(at(45, 16, 37), b.MORTAR)
        self.assertEqual(at(46, 16, 38), b.MORTAR)
        self.assertEqual(at(47, 18, 38), b.t.stair('tuff_brick', 'east', 'top'))
        # Interior reliefs: nave keystone, profile at the top of a catacomb rib, and tomb canopy.
        self.assertEqual(at(15, 32, 28), b.TOMB)
        self.assertEqual(at(b.NAMES.x-6, b.LOW+9, b.NAMES.z), b.TOMB)
        self.assertEqual(at(b.NAMES.x-6, b.LOW+9, b.NAMES.z+1), b.TUFF_LIP)
        self.assertEqual(at(b.NAMES.x-13, b.LOW+5, b.NAMES.z-6), b.TOMB)

    def test_bridge_guards_cover_outside_edges_without_cutting_the_turn(self):
        b = abyss
        deck = finishes.east_bridge_footprint()
        # The perimeter uses walls/newels, including the staggered edges at turns and grade changes.
        guarded = 0
        for (x, z), y in deck.items():
            if not 154 <= z <= 218 or all((x+dx, z+dz) in deck for _, dx, dz in b.t.CARDINAL):
                continue
            rail = self.g.get(x, y+1, z)
            self.assertTrue(rail == b.CARVED or b.c.STATES[rail][0].endswith('_wall'), (x, y, z))
            self.assertEqual(self.g.get(x, y, z), b.TRIM)
            guarded += 1
        self.assertGreater(guarded, 150)
        mouth = {(95, 0, 176), (91, 1, 177), (84, 2, 180), (79, 2, 181), (72, 2, 183)}
        start = (b.r.road_x(176), 0, 176)
        self.assertEqual(routes.paths(self.blocks, start, mouth), mouth)

    def test_eaves_bench_and_connected_fences_on_used_routes(self):
        b, at = abyss, self.g.get
        self.assertEqual(at(-132, 4, 57), b.t.stair('deepslate_tile', 'south'))
        self.assertEqual(at(-132, 7, 60), b.r.ROOF_CAP)
        self.assertEqual(at(-130, 1, 59), b.t.stair('dark_oak', 'north'))
        name, parts = b.c.STATES[at(-138, 1, 60)]
        self.assertEqual(name, 'minecraft:dark_oak_fence')
        self.assertEqual({key for key, value in parts if key in b.VECTORS and value == 'true'}, {'north', 'south'})
        # The shelter, side aisles of the nave, and steps from the causeway remain connected.
        targets = {(-132, 0, 61), (18, 4, 44), (-18, 4, 80)}
        self.assertEqual(routes.paths(self.blocks, (0, -5, -66), targets), targets)

    def test_portal_is_deliberately_unlit(self):
        b, r = abyss, abyss.r
        self.assertFalse(any(tag['Name'] == 'minecraft:nether_portal' for tag in self.palette))
        half = r.PWIDTH // 2
        clear = self.g.box(r.PX-half, r.PX+half, r.PBASE+1, r.PEND-1, r.PZ-3, r.PZ+3)
        self.assertFalse(clear.any(), 'Even light blocks must stay out of the ignition space')
        frame = self.g.box(r.PX-half-1, r.PX+half+1, r.PBASE, r.PEND, r.PZ, r.PZ)[:, 0, :]
        self.assertTrue(np.all(frame[[0, -1], :] == b.s.OBSIDIAN))
        self.assertTrue(np.all(frame[:, [0, -1]] == b.s.OBSIDIAN))


if __name__ == '__main__':
    unittest.main()
