#!/usr/bin/env python3
"""Build a compact survival category warehouse for Minecraft Java 26.3."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from nbtlib import tag as nbt

from . import build_catacomb_cathedral as abbey, catacomb_logistics as l, catacomb_storage as s
from .catalog_universal import OUTPUT as CATALOG

c, t = s.c, s.t
OUTPUT = abbey.OUTPUT.with_name('moonspire-universal-store.litematic')
TITLE = 'Кладовая хранителей — сортировка по категориям'
DESCRIPTION = 'Minecraft Java 26.3: медные големы, параллельная приёмка, 20 автокрафтов с выходом в общие секции.'
ORIGIN = (0, 0, 0)
BOUNDS = (ORIGIN, (36, 30, 37))
BINS = tuple((name, tuple(items)) for name, items in json.loads(CATALOG.read_text(encoding='utf-8'))['bins'])
CART_COUNT = 8
MAX_BINS = 8
SEED = 1
SPACER_COUNT = 11
SPACER_TITLE = 'Метка упаковщика'
CHEST = 'chest'
WAXED = 'waxed_copper_chest'
GLASS = s.GLASS
LIGHT = c.state('ochre_froglight', axis='y')
STRIPE = c.state('waxed_oxidized_cut_copper')
BOARD = s.PIER
LADDER = c.state('ladder', facing='south', waterlogged='false')
RAIL = c.state('rail', shape='north_south', waterlogged='false')
Vec = l.Vec


@dataclass(frozen=True)
class Cabinet:
    label: str
    items: tuple[str, ...]
    near: Vec
    far: Vec
    face: str

    @property
    def pair(self):
        return self.near, self.far


@dataclass(frozen=True)
class Cell:
    center: Vec
    bins: tuple[tuple[str, tuple[str, ...]], ...]

    def at(self, dx, dy, dz):
        return l.add(self.center, (dx, dy, dz))

    @property
    def ladder(self):
        return self.at(-3, 0, -5)

    @property
    def cabinets(self):
        # From a centered cart, every seeded half in range is strictly closer
        # than the relay; outside halves never add another candidate chest.
        # Near cells in the vertical side stacks are visible over the cart.
        offsets = (
            ((0, 0, -1), (0, 0, -2), 'east'),
            ((-1, 0, 0), (-2, 0, 0), 'north'),
            ((1, 0, 0), (2, 0, 0), 'south'),
            ((0, 1, -1), (0, 1, -2), 'east'),
            ((-1, 1, 0), (-2, 1, 0), 'north'),
            ((1, 1, 0), (2, 1, 0), 'south'),
            ((-1, 0, -1), (-1, 0, -2), 'east'),
            ((1, 0, -1), (1, 0, -2), 'east'),
        )
        return tuple(Cabinet(name, items, self.at(*near), self.at(*far), side)
                     for (name, items), (near, far, side) in zip(self.bins, offsets))

    @property
    def inputs(self):
        return self.at(-1, 0, 1), self.at(0, 0, 1)

    @property
    def relay(self):
        return self.at(1, 1, 1), self.at(1, 1, 2)


CELLS = tuple(Cell(p, BINS[i*MAX_BINS:(i+1)*MAX_BINS])
              for i, p in enumerate(((4, 15, 26), (12, 13, 26), (20, 11, 26), (28, 9, 26),
                                      (28, 7, 17), (20, 5, 17), (12, 3, 17))))
CABINETS = tuple(chest for cell in CELLS for chest in cell.cabinets)
BY_ID = {v: chest for chest in CABINETS for v in chest.items}
assert len(CABINETS) == len(BINS)
OVERFLOW = tuple(l.step(p, 'down', 2) for p in CELLS[-1].relay)
INTAKE = ((3, 17, 27), (4, 17, 27))
WATER_PATH = l.path((3, 19, 25), (3, 19, 27))
WATER_PORT, WATER_END = WATER_PATH[0], WATER_PATH[-1]
UNLOADERS = l.Unloader((12, 24, 28)), l.Unloader((27, 24, 28))
BOX_INPUTS = tuple(l.step(unit.feed, 'up') for unit in UNLOADERS)
RAW_INPUT = (2, 29, 4)
PRESSES = tuple(l.Press((5 + 7*(i%5), 25 - 6*(i//10), (9, 20)[i//5%2]), *recipe)
                for i, recipe in enumerate(l.RECIPES))
PRESS_PATH = l.path((2, 28, 4), (36, 28, 4), (36, 28, 15), (2, 28, 15),
                    (2, 22, 15), (34, 22, 15), (34, 22, 4), (1, 22, 4),
                    (1, 17, 4), (1, 17, 27), (2, 17, 27))
# Last point joins the left intake path, after all ingredient filters.


class Grid(abbey.s.DeepGrid):
    limits = (0, BOUNDS[1][0], 0, BOUNDS[1][1], 0, BOUNDS[1][2])

    def __init__(self):
        xx, yy, zz = BOUNDS[1]
        self.blocks = np.zeros((yy+1, zz+1, xx+1), dtype=np.int16)
        self.tiles = {}


def double_chest(board, a, b, facing, items=()):
    """The right half is the one on your right when looking *with* facing."""
    dx, _, dz = l.DIR[facing]
    offset = tuple(v-u for u, v in zip(a, b))
    assert offset in ((-dz, 0, dx), (dz, 0, -dx)), (a, b, facing)
    halves = ('left', 'right') if offset == (-dz, 0, dx) else ('right', 'left')
    # Use the left BE for the first half on the GUI. Counts are kept at one
    # per seed so a bare anvil-free survival installation is possible.
    for point, side in zip((a, b), halves):
        batch = items[:27] if side == 'left' else items[27:]
        board.entity(point, CHEST, (s.item(i, 'minecraft:' + v, 1) for i, v in enumerate(batch)),
                     type=side, facing=facing, waterlogged='false')


def through(board, *points):
    points = tuple(p for i, p in enumerate(points) if i == 0 or p != points[i-1])
    if len(points) > 1:
        l.feed_path(board, l.path(*points))


def storage():
    m = l.Board()
    for cell in CELLS:
        for v in cell.cabinets:
            double_chest(m, *v.pair, v.face, v.items)
        for p in cell.inputs:
            m.entity(p, 'copper_chest', block=WAXED, type='single', facing='east', waterlogged='false')
        double_chest(m, *cell.relay, 'east')
        m.put(cell.at(0, -1, 0), LIGHT)
        m.put(cell.at(0, 0, 0), RAIL)
        # Keep path finding inside the pocket without covering any chest.
        m.block(cell.at(0, 1, 0), 'smooth_stone_slab', type='top', waterlogged='false')
        m.put(cell.at(0, 2, 0), GLASS)
    for cell, nxt in zip(CELLS, CELLS[1:]):
        x, y, z = cell.center
        ax, _, az = nxt.center
        a, b = cell.at(1, 0, 1), cell.at(1, 0, 2)
        aa, bb = l.step(a, 'down'), l.step(b, 'down')
        u, v = (l.step(p, 'up') for p in nxt.inputs)
        if az != z:
            # Detour around both sides of the upstream bank. A route directly
            # under a chest would pull out its calibration items.
            through(m, a, aa, (x+1, y-2, z+1), (x-4, y-2, z+1),
                    (x-4, y-2, az+1), nxt.inputs[0])
            through(m, b, bb, (x+4, y-1, z+2), (x+4, y-1, az+5),
                    (x+4, y-2, az+5), (ax, y-2, az+5), nxt.inputs[1])
        elif ax > x:
            through(m, a, aa, u, nxt.inputs[0])
            through(m, b, bb, (ax, y-1, z+2), v, nxt.inputs[1])
        else:
            # Approaching from the right would cross the next relay. Run
            # behind it at intake height and come in from the south instead.
            through(m, a, aa, (x+1, y-2, z+1), (x+2, y-2, z+1),
                    (x+2, y-2, z+6), (ax-1, y-2, z+6), nxt.inputs[0])
            through(m, b, bb, (x+1, y-2, z+2), (x+1, y-2, z+5),
                    (ax, y-2, z+5), nxt.inputs[1])
    for p in OVERFLOW:
        m.hopper(l.step(p, 'up'))
        m.barrel(p, 'south')
        m.compare(l.step(p, 'east'), 'east')
        m.block(l.step(p, 'east', 2), 'redstone_lamp', lit='false')
    # A hopper may pull from the inventory one block above even if it points
    # horizontally somewhere else. No route may steal a seed or skip a bank.
    protected = {p for cell in CELLS for p in cell.inputs} | {p for cabinet in CABINETS for p in cabinet.pair}
    for p in protected:
        if c.STATES[m.blocks.get(l.step(p, 'down'), s.AIR)][0] == 'minecraft:hopper':
            raise ValueError(f'Unwanted inventory extraction from {p}')
    return m


def receiving():
    m = l.Board()
    double_chest(m, *INTAKE, 'south')
    for copper in CELLS[0].inputs:
        m.hopper(l.step(copper, 'up'))
    # The water collector pushes whole arriving stacks into a buffer, while
    # its hopper mediates backup instead of exposing the live sorter cell.
    m.hopper(l.step(WATER_END, 'down'))
    for x, y, z in WATER_PATH:
        if z != WATER_END[2]:
            m.put((x, y-1, z), c.state('blue_ice'))
        for dx in (-1, 1):
            m.put((x+dx, y, z), GLASS)
        m.block((x, y, z), 'water', level=str(z - WATER_PORT[2]))
    m.put(l.step(WATER_PORT, 'north'), GLASS)
    m.put(l.step(WATER_END, 'south'), GLASS)

    for i, (u, p) in enumerate(zip(UNLOADERS, BOX_INPUTS)):
        x, y, z = u.origin
        m.barrel(l.step(p, 'up'))
        m.hopper(p)
        dst = INTAKE[i]
        # Lower the route below the unloader's feedback tail before turning.
        side, track = (2, 5)[i], z-4+i
        through(m, l.step(u.drain, 'down'), (x, y-4-i, z), (x, y-4-i, track),
                (side, y-4-i, track), (side, dst[1], track), (side, dst[1], dst[2]), dst)
    return m


def compaction():
    m = l.Board()
    m.barrel(RAW_INPUT)
    l.feed_path(m, PRESS_PATH)
    # Products join the raw lane only below and after every ingredient filter.
    paths = (
        l.path((33, 23, 10), (0, 23, 10), (0, 17, 10), (1, 17, 10)),
        l.path((33, 17, 10), (1, 17, 10)),
        l.path((33, 23, 21), (1, 23, 21), (1, 23, 22), (1, 17, 22)),
        l.path((33, 17, 21), (1, 17, 21)),
    )
    for i, path in enumerate(paths):
        points = {l.step(p.output, 'down') for p in PRESSES}
        # The hopper underneath each output buffer is always downstream.
        l.feed_path(m, path)
        assert len(points.intersection(path)) == 5, i
    return m


def machines():
    # BUS is planned once upstream, never through the press-output collectors.
    primary = compaction()
    press_boards = []
    for unit in PRESSES:
        p = unit.layout()
        filler = [s.item(i, s.FILLER_ID, SPACER_COUNT) for i in range(1, 5)]
        for v in filler:
            v['components'] = nbt.Compound({'minecraft:custom_name': nbt.String(SPACER_TITLE)})
        p.tiles[unit.filter] = s.inventory('hopper', (s.item(0, 'minecraft:'+unit.item, SEED), *filler))
        # The pulse is long enough for one push/pull cycle. One priming item
        # lets the pulse push first, then replenish, with no lost ninth item.
        p.tiles[unit.reserve] = s.inventory('hopper', (s.item(0, 'minecraft:'+unit.item, SEED),))
        press_boards.append(p)
    return l.states_and_tiles((*press_boards, primary, storage(), receiving(), *(u.layout() for u in UNLOADERS)))


def mob_entities():
    for cell in CELLS:
        x, y, z = cell.center
        position = (x+.5, y+.0625, z+.5)
        for _ in range(CART_COUNT):
            yield nbt.Compound(id=nbt.String('minecraft:minecart'), Pos=nbt.List[nbt.Double](position),
                               Motion=nbt.List[nbt.Double]((0,0,0)), Passengers=nbt.List[nbt.Compound]([
                nbt.Compound(id=nbt.String('minecraft:copper_golem'),
                             Pos=nbt.List[nbt.Double]((position[0], position[1]+.1875, position[2])),
                             PersistenceRequired=nbt.Byte(1), next_weather_age=nbt.Long(-2),
                             weather_state=nbt.String('unaffected'))]))


def decor(g, claims):
    def free(p, state):
        """Finish only unclaimed spaces; claims also reserve redstone air."""
        if p not in claims and g.get(*p) == s.AIR:
            g.put(*p,state)

    def line(p, q, state):
        for v in l.path(p, q):
            free(v, state)

    def sign(p, facing, *text, color='white'):
        support = l.step(p,l.opposite(facing))
        assert p not in claims and g.get(*p) == s.AIR, p
        free(support, BOARD)
        assert g.get(*support) != s.AIR, (p,support)
        g.put(*p, c.state('dark_oak_wall_sign', facing=facing, waterlogged='false'))
        x, y, z = p
        g.tiles[x, y, z] = abbey.text_data(text, color)

    def deck(x0, x1, y, z0, z1):
        for x in range(x0, x1+1):
            for z in range(z0, z1+1):
                free((x,y,z), LIGHT if (x+z)%13 == 0 else s.TILE)

    def standing(pos, facing, *text, color='white'):
        assert pos not in claims and g.get(*pos) == s.AIR, pos
        free(l.step(pos, 'down'), STRIPE)
        rotations = {'south': '0', 'west': '4', 'north': '8', 'east': '12'}
        g.put(*pos, c.state('dark_oak_sign', rotation=rotations[facing], waterlogged='false'))
        g.tiles[pos] = abbey.text_data(text, color)

    for i, cell in enumerate(CELLS, 1):
        x,y,z = cell.center
        lx, _, lz = cell.ladder
        if lz < 14:
            deck(lx-1,lx+1,0,lz-1,15)
        line((lx,0,lz-1),(lx,y,lz-1),BOARD)
        for yy in range(1,y+1):
            free((lx,yy,lz),LADDER)
        deck(x-3,x+3,y-1,z-4,z+2)
        # A short north and side walkway displays both tiers; the rear glass
        # stripes hide live pockets without enclosing the whole warehouse.
        posts = {}
        for cabinet in cell.cabinets:
            fx,fy,fz = cabinet.far
            if fz == z-2:
                p, facing = (fx,y,fz-1), 'north'
            else:
                facing = 'west' if fx < x else 'east'
                dx = l.DIR[facing][0]
                p = (fx+dx,y,fz)
            posts.setdefault((p,facing), []).append((fy, cabinet.label))
        for (p,facing), labels in posts.items():
            lines = (labels[0][1],) if len(labels) == 1 else ('Верх:', labels[1][1], 'Низ:', labels[0][1])
            standing(p,facing,*lines)
        standing((x,y,z-4),'north',f'Секция {i}',color='orange')

    # The ground ribbon provides a stable place to start each service ladder.
    deck(0,34,0,14,33)
    deck(0,2,0,3,13)
    for (x,y,z) in ((0, 28, 3), (2,20,30), (10, 25, 32), (25, 25, 32)):
        line((x,0,z),(x,y,z),BOARD)
        for yy in range(1,y+1):
            free((x,yy,z+1),LADDER)
    deck(0,4,28,5,6)
    deck(1,5,16,28,31)
    deck(0,1,19,25,31)
    # Linking high feed half-balconies costs less than full floors.
    deck(9,28,24,30,33)
    for bx,_,bz in BOX_INPUTS:
        deck(bx-1,bx+1,24,bz+1,30)
    sign((2,30,5),'south','Автоупаковка','20 рецептов',color='orange')
    sign((2,17,29),'south','Общая приёмка','Вещи россыпью',color='orange')
    standing((0,20,26),'south','Водный ввод',color='aqua')
    for i, (x,y,z) in enumerate(BOX_INPUTS,1):
        sign((x,y+2,z+1),'south',f'Разгрузка {i}','Только шалкеры', color='orange')
    x,y,z=OVERFLOW[1]
    sign((x,y,z+1),'south','Переполнение','Проверь секции',color='red')
    # Service lights also expose each landing during survival installation.
    for y in (2,6,10,14,18,22,26):
        free((0,y,3),LIGHT)


def layout():
    g = Grid()
    states, tiles = machines()
    for pos, state in states.items():
        g.put(*pos,state)
    g.tiles.update(tiles)
    decor(g, states)
    return g


def build(path=OUTPUT, preview=None):
    g = layout()
    c.save(path, g.blocks, preview, title=TITLE, description=DESCRIPTION,
           block_entities=g.tiles, entities=tuple(mob_entities()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    build(args.output, args.preview)


if __name__ == '__main__':
    main()
