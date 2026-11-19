#!/usr/bin/env python3
"""Build the Keepers' Store as open, stacked machinery, without any abbey shell."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np

from . import build_catacomb_cathedral as abbey, catacomb_logistics as l, catacomb_storage as s

c, t, r = abbey.c, abbey.t, abbey.r
OUTPUT = abbey.OUTPUT.with_name('moonspire-compact-store.litematic')
TITLE = 'Кладовая хранителей — компактный автосклад'
DESCRIPTION = 'Открытый модуль: одна приёмка, разгрузка шалкеров, водоввод, 20 сборщиков и 36 заполненных фильтров. Minecraft Java 26.3.'

# Keep the input, unloader and return board at their proven relative offsets.
# Two 10-crafter levels fold the previous four long rows over the same footprint.
ROWS = (132, 144)
FLOORS = (-25, -32)
STORE_DY = -4
BASE = s.FLOOR + STORE_DY
LADDER_XZ = (-77, 153)
WATER_PORT = (-69, -3, 134)
WATER_PIPE = l.path((-69, l.FARM_END[1], WATER_PORT[2]), l.FARM_END)
WATER_STAND = l.step(WATER_PORT, 'west', 2)
ENTRANCE = (-76, BASE, 160)
PRESSES = tuple(replace(p, origin=(p.origin[0], FLOORS[i//10] + 2, ROWS[i//5 % 2]))
                for i, p in enumerate(l.PRESSES))
PRESS_FEED = l.path(l.MERGE, (-35, -20, 153), (-35, -20, 127), (-76, -20, 127),
                    (-76, -20, 139), (-36, -20, 139), (-36, -27, 139), (-76, -27, 139),
                    (-76, -27, 127), (-36, -27, 127))


def raw(p: l.Vec) -> l.Vec:
    return l.add(p, (0, STORE_DY, 0))


SORTER_FEED = l.path(PRESS_FEED[-1], (-36, -33, 127), (-36, -33, 143), (-62, -33, 143), raw(s.INTAKE[0]))
assert {p.bus for p in PRESSES} <= set(PRESS_FEED)

# Engineering coordinates. The file uses offsets relative to ORIGIN, never
# these absolute numbers. An extra air border serves railing and light audits.
ORIGIN = (-78, BASE - 1, 123)
BOUNDS = (ORIGIN, (-35, 0, 161))
LANTERN = c.LANTERN
STRIPE = s.METAL
LUMEN = c.state('ochre_froglight', axis='y')
LADDER = c.state('ladder', facing='east', waterlogged='false')


class Grid(abbey.s.DeepGrid):
    limits = (-79, -34, BASE - 1, 2, 122, 162)

    def __init__(self):
        x, xx, y, yy, z, zz = self.limits
        self.blocks = np.zeros((yy-y+1, zz-z+1, xx-x+1), dtype=np.int16)
        self.signs = {}
        self.tiles = {}


class RawLevel:
    def __init__(self, target):
        self.target = target

    def put(self, x, y, z, block):
        self.target.put(*raw((x, y, z)), block)


def machine():
    parts = (l.ENTRY_SPLIT.layout(), l.UNLOADER.layout(), l.RETURN_SPLIT.layout(),
             *(p.layout() for p in PRESSES), l.links(press_feed=PRESS_FEED, sorter_feed=SORTER_FEED), l.farm_receiver())
    return l.states_and_tiles(parts)


def put_tile(g, p, tag):
    iy, iz, ix = g.coord(*p)
    g.tiles[ix, iy, iz] = tag


def floor(g, y, x0, x1, z0, z1):
    g.box(x0, x1, y, y, z0, z1)[:] = s.TILE


def rails(g, y, coords):
    for x, z in coords:
        if g.get(x, y, z) != s.AIR and g.get(x, y+1, z) == s.AIR:
            g.put(x, y+1, z, t.FENCE)


def scaffold(g):
    # A few piers support the work decks, without an outer wall or roof.
    for x, z in ((-78, 153), (-77, 134), (-37, 134), (-37, 146)):
        top = WATER_PORT[1] + 1 if (x, z) == (-78, 153) else FLOORS[0] + 1
        for y in range(BASE-1, top+1):
            g.put(x, y, z, s.PIER if (y-BASE) % 7 == 0 else s.RELAY)
    floor(g, BASE, -77, -38, 144, 156)
    floor(g, BASE, -77, -75, 157, 160)
    floor(g, BASE-1, -77, -75, 160, 161)
    for x in (-77, -76, -75):
        g.put(x, BASE, 160, t.stair('polished_blackstone_brick', 'north'))
    for x in range(-74, -38, 6):
        g.put(x, BASE, 149, LUMEN)
        g.put(x, BASE, 152, LUMEN)
    rails(g, BASE, ((x, z) for x in range(-74, -37) for z in (144, 156)))
    rails(g, BASE, ((-38, z) for z in range(145, 156)))
    rails(g, BASE, ((-77, z) for z in range(147, 160) if z != LADDER_XZ[1]))
    g.put(-77, BASE+2, 158, s.PIER)
    abbey.plaque(g, (-76, BASE+2, 158), 'east', 'Кладовая', 'Приёмка ↑', color='orange')
    g.put(-77, BASE+3, 158, LANTERN)


def raw_deck(g):
    s.machinery(RawLevel(g), lambda _, p, d, *text, **kw: abbey.plaque(g, raw(p), d, *text, **kw))
    for p, tag in s.inventory_data().items():
        put_tile(g, raw(p), tag)
    # This is a hand-off from the last press, not a second public input.
    g.put(*l.step(raw(s.INTAKE[1]), 'up'), s.BRICK)
    for j, (group, _) in enumerate(s.GROUPS):
        side = j < 3
        xs = s.COLUMNS if side else s.COLUMNS[::-1]
        x = xs[j % 3 * 6 + 2]
        z = 146 if side else 154
        g.put(x, BASE+6, 145 if side else 155, s.BEAM)
        abbey.plaque(g, (x, BASE+6, z), 'south' if side else 'north', group, color='orange')
    g.put(-62, BASE+5, 155, s.BEAM)
    abbey.plaque(g, (-62, BASE+5, 154), 'north', 'Остаток', 'Лампа: есть вещи', color='orange')


def press_decks(g, states):
    for level, y in enumerate(FLOORS):
        floor(g, y, -77, -75, 133, 155)
        floor(g, y, -75, -73, 147, 154)
        for z in ROWS:
            floor(g, y, -76, -37, z+1, z+4)
            for x in range(-74, -37, 6):
                g.put(x, y, z+3, LUMEN)
            g.put(-76, y, z+2, STRIPE)
            rails(g, y, ((x, z+4) for x in range(-73, -36)))
            rails(g, y, ((-37, zz) for zz in range(z+2, z+4)))
            # The two west cells stay open: they are the ladder-to-row aisle.
            for x in range(-74, -37):
                for yy in (y+1, y+2, y+3):
                    p = (x, yy, z+1)
                    if p not in states:
                        g.put(*p, s.RELAY if yy == y+3 else s.GLASS)
        for p in PRESSES[10*level:10*(level+1)]:
            x, _, z = p.output
            abbey.plaque(g, (x, y+3, z+1), 'south', *l.split_label(p.label), color='orange')
        rails(g, y, ((-77, z) for z in range(135, 156) if z != LADDER_XZ[1]))
        rails(g, y, ((x, 155) for x in range(-77, -72)))
        g.put(-78, y+2, 153, s.PIER)
        abbey.plaque(g, (-78, y+2, 152), 'north', 'Сборка ' + str(level+1), 'Сундук наверху', color='orange')

    y = FLOORS[0]
    floor(g, y, -76, -53, 152, 155)
    for x in range(-74, -53, 6):
        g.put(x, y, 154, LUMEN)
    rails(g, y, ((x, 155) for x in range(-73, -56)))
    rails(g, y, ((-53, z) for z in range(152, 155)))
    rails(g, y, ((x, 152) for x in range(-72, -53)))
    g.put(-56, -22, 155, s.PIER)
    abbey.plaque(g, (-56, -22, 154), 'north', 'Пустые шалкеры', 'Забирай здесь', color='orange')
    g.put(-53, -23, 155, s.PIER)
    abbey.plaque(g, (-53, -23, 154), 'north', 'Есть коробки', color='white')


def arrival_and_water(g):
    floor(g, -12, -77, -69, 151, 155)
    floor(g, -12, -73, -68, 150, 150)
    for x, z in ((-76, 151), (-76, 154), (-73, 154), (-70, 154), (-69, 152)):
        g.put(x, -12, z, LUMEN)
    rails(g, -12, ((x, z) for x in range(-77, -68) for z in ((155,) if x >= -73 else (151, 155))))
    for x, y, text in ((-71, -9, ('Приёмка', 'Шалкеры и вещи')),
                       (-72, -9, ('Сундук полон',)), (-72, -11, ('Рычаг: пауза',))):
        g.put(x, y, 150, s.PIER)
        abbey.plaque(g, (x, y, 151), 'south', *text, color='orange' if x == -71 else 'white')
    g.put(-69, -8, 153, s.PIER)
    abbey.plaque(g, (-69, -8, 154), 'south', 'С ферм', 'Свет: очередь', color='white')
    g.put(-70, -7, 152, s.GLASS)  # bracket for the visible end of the water receiver
    g.put(-69, -7, 152, s.GLASS)
    g.put(-69, -7, 153, s.BEAM)
    g.put(-71, -7, 152, s.BEAM)
    g.put(-71, -7, 153, s.BEAM)
    g.put(-71, -8, 153, abbey.s.SOUL_HANGING)

    x, y, z = WATER_PORT
    floor(g, y, -77, -75, z-2, 154)
    floor(g, y, -75, x+1, z-2, z+1)
    floor(g, y-1, -77, -77, z-2, 153)
    for zz in (z+2, z+8, 150):
        g.put(-76, y, zz, LUMEN)
    rails(g, y, ((-77, zz) for zz in range(z-2, 155) if zz != LADDER_XZ[1]))
    rails(g, y, ((-75, zz) for zz in range(z+2, 155)))
    rails(g, y, ((xx, z-2) for xx in range(-76, x)))
    rails(g, y, ((xx, z+1) for xx in range(-74, x-1)))
    l.waterworks(g, abbey.plaque, pipe=WATER_PIPE, port=WATER_PORT)


def build() -> Grid:
    g = Grid()
    states, tags = machine()
    scaffold(g)
    raw_deck(g)
    press_decks(g, states)
    arrival_and_water(g)
    # Run the ladder through the landing decks, with an exit at every level.
    x, z = LADDER_XZ
    for y in range(BASE, WATER_PORT[1] + 2):
        g.put(x, y, z, LADDER)
    for p, state in states.items():
        iy, iz, ix = g.coord(*p)
        if (ix, iy, iz) in g.tiles:
            raise ValueError(f'Circuit overlaps lower storage at {p}')
        g.put(*p, state)
    for p, tag in tags.items():
        put_tile(g, p, tag)
    t.connect_railings(g)
    return g


def extents(g):
    y, z, x = np.nonzero(g.blocks)
    x0, _, y0, _, z0, _ = g.limits
    return ((x0+int(x.min()), y0+int(y.min()), z0+int(z.min())),
            (x0+int(x.max()), y0+int(y.max()), z0+int(z.max())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    g = build()
    if extents(g) != BOUNDS:
        raise ValueError(f'Unexpected export bounds {extents(g)}; expected {BOUNDS}')
    c.save(args.output, g.blocks, args.preview, title=TITLE, description=DESCRIPTION, block_entities=g.tiles | g.signs)


if __name__ == '__main__':
    main()
