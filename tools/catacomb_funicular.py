"""The Keepers' Incline, with a two-dropper interlock and a dry stair alongside it.

Directions/coordinates are local to the build (north = -Z). Power is normally off;
only the single token in the first dropper is needed to initialise the interlock.
"""

from __future__ import annotations

from nbtlib import tag as nbt

from . import build_throne_cathedral as t

c, a, s = t.c, t.a, t.s
TRACK_X = -28
TOP_Z, BOTTOM_Z = 176, 211
TOP_Y, BOTTOM_Y = -14, -35
UPPER = (-30, TOP_Y, TOP_Z)
LOWER = (-30, BOTTOM_Y, BOTTOM_Z)
STAIR = (-32, -24, 192)
CONTROLS = ((-31, TOP_Y + 2, TOP_Z), (-31, BOTTOM_Y + 2, BOTTOM_Z))
LAMPS = ((-34, TOP_Y + 1, TOP_Z + 2), (-34, BOTTOM_Y + 1, BOTTOM_Z + 2))
PARKS = ((TRACK_X, TOP_Y + 1, TOP_Z), (TRACK_X, BOTTOM_Y + 1, BOTTOM_Z))
DETECTORS = ((TRACK_X, TOP_Y + 1, TOP_Z + 2), (TRACK_X, BOTTOM_Y + 1, BOTTOM_Z - 2))
STOCK = ((-34, TOP_Y + 1, 180), (-34, BOTTOM_Y + 1, 215))
BOARD_X, BOARD_Y, BOARD_Z = -62, -17, 172
TOKEN = (BOARD_X, BOARD_Y, BOARD_Z)
LATCH = (BOARD_X + 1, BOARD_Y, BOARD_Z)
TOKEN_ITEM = 'iron_nugget'
BELLS = tuple((x + 1, y, z) for x, y, z in DETECTORS)
BELL = c.state('bell', attachment='floor', facing='east', powered='false')

AIR = 0
SLATE = t.SLATE
TRIM = t.TRIM
BRICK = t.BRICK
BASALT = t.BASALT
METAL = a.BRASS
GLASS = c.state('glass')
TINT = c.state('tinted_glass')
PIER = c.state('chiseled_tuff_bricks')
BED = c.state('polished_deepslate')
BUMPER = a.VERDIGRIS
RED = c.state('redstone_block')
DIR = {'north': (0, -1), 'east': (1, 0), 'south': (0, 1), 'west': (-1, 0)}


def opposite(d: str) -> str:
    dx, dz = DIR[d]
    return next(name for name, v in DIR.items() if v == (-dx, -dz))


def floor(z: int) -> int:
    return TOP_Y - min(max(z - 182, 0), TOP_Y - BOTTOM_Y)


def inventory_data() -> dict[tuple[int, int, int], nbt.Compound]:
    def container(kind, item=None):
        data = nbt.Compound(id=nbt.String('minecraft:' + kind))
        if item:
            data['Items'] = nbt.List[nbt.Compound]([nbt.Compound(
                Slot=nbt.Byte(0), id=nbt.String('minecraft:' + item), count=nbt.Int(1))])
        return data

    return {TOKEN: container('dropper', TOKEN_ITEM), LATCH: container('dropper'),
            **{p: container('barrel', 'minecart') for p in STOCK}, **{p: container('bell') for p in BELLS}}


def architecture(g, plaque) -> None:
    # Reclaim the broad shoulder of the old crypt; keep the old west approach
    # to the ring intact. The new entrance branches off it, towards +Z.
    g.box(-36, -19, TOP_Y - 1, TOP_Y, 172, 183)[:] = BED
    g.box(-36, -19, TOP_Y + 1, -8, 172, 183)[:] = AIR
    g.box(-36, -19, -7, -7, 172, 183)[:] = BRICK
    g.box(-37, -37, -14, -7, 172, 183)[:] = BRICK
    g.box(-18, -18, -14, -7, 172, 183)[:] = BRICK
    g.box(-36, -19, -14, -7, 172, 172)[:] = BRICK
    g.box(-36, -19, -14, -7, 183, 183)[:] = BRICK
    for z in range(169, 174):
        y = -12 if z <= 171 else -13 if z == 172 else TOP_Y
        g.box(-32, -30, y, y, z, z)[:] = (t.stair('polished_blackstone_brick', 'north')
                                         if z in (171, 172) else BED)
        g.box(-32, -30, y + 1, y + 4, z, z)[:] = AIR
    # A recessed, lit viewing bay for the relay bank, behind two tiers of glass.
    g.box(-47, -36, TOP_Y - 1, TOP_Y, 174, 182)[:] = BED
    g.box(-47, -34, TOP_Y + 1, -9, 174, 182)[:] = AIR
    g.box(-47, -34, -8, -8, 174, 182)[:] = BRICK
    g.box(-68, -48, -18, -10, 173, 181)[:] = AIR
    g.box(-63, -57, -18, -12, 181, 197)[:] = AIR
    g.box(-48, -48, -17, -9, 174, 182)[:] = BRICK
    g.box(-48, -48, -16, -10, 175, 180)[:] = GLASS
    g.box(-48, -48, -15, -10, 178, 178)[:] = METAL
    g.box(-52, -48, -14, -14, 177, 179)[:] = GLASS
    for z in (174, 181):
        for x in (-47, -43, -38, -22):
            if x <= -38:
                g.box(x, x, -14, -9, z, z)[:] = PIER
            g.put(x, -9, z, s.SOUL_HANGING)
            g.put(x, -8, z, TRIM)
    for x in (-23, -20):
        g.box(x, x, -13, -13, 175, 180)[:] = c.WOOD
        g.put(x, -12, 175, c.state('stonecutter', facing='south'))
        g.put(x, -12, 179, c.state('flower_pot'))
    for z in (173, 181):
        g.box(-36, -20, -8, -8, z, z)[:] = TRIM
        for x in (-35, -30, -26, -21):
            g.put(x, -9, z, t.stair('tuff_brick', 'east' if x in (-35, -26) else 'west', 'top'))
    g.box(-22, -20, -13, -13, 181, 181)[:] = c.slab('dark_oak')
    g.box(-22, -20, -12, -12, 182, 182)[:] = c.state('bookshelf')

    # The track and the independent footway descend at the same grade, with a
    # glazing rib between them. Don't cut into the decorated bells at Z=226.
    for z in range(TOP_Z - 1, BOTTOM_Z + 2):
        y = floor(z)
        g.box(-33, -26, y - 1, y, z, z)[:] = BED
        if z >= 182:
            g.box(-33, -26, y + 1, y + 4, z, z)[:] = AIR
            g.box(-34, -34, y, y + 5, z, z)[:] = BRICK
            g.box(-25, -25, y, y + 5, z, z)[:] = BRICK
            g.box(-33, -26, y + 5, y + 5, z, z)[:] = BRICK
        for x in (-33, -32, -31, -30):
            g.put(x, y, z, t.stair('polished_blackstone_brick', 'north') if 182 <= z <= 202 else BED)
        if 180 <= z <= 206:
            ribs = z in (180, 184, 192, 200, 206)
            g.box(-29, -29, y + 1, y + 3, z, z)[:] = TRIM if ribs else TINT
            if ribs and z >= 184:
                g.put(-33, y + 4, z, c.LIGHT)
                g.put(-27, y + 4, z, c.LIGHT)
            if z % 3 == 0:
                g.put(-32, y + 3, z, s.SOUL_HANGING if z in (186, 195, 204) else AIR)
                if z in (186, 195, 204):
                    g.put(-32, y + 4, z, TRIM)
        if z in (TOP_Z - 1, BOTTOM_Z + 1):
            g.box(TRACK_X, TRACK_X, y + 1, y + 3, z, z)[:] = BUMPER
            g.put(TRACK_X, y + 4, z, PIER)
            continue
        shape = 'ascending_north' if 183 <= z <= 203 else 'north_south'
        if z in (TOP_Z, BOTTOM_Z):
            rail = c.state('powered_rail', shape=shape, powered='false', waterlogged='false')
        elif z in (TOP_Z + 2, BOTTOM_Z - 2):
            rail = c.state('detector_rail', shape=shape, powered='false', waterlogged='false')
            g.put(-27, y, z, METAL)
            g.put(-27, y + 1, z, BELL)
        elif z in (TOP_Z + 1, BOTTOM_Z - 1):
            rail = c.state('rail', shape=shape, waterlogged='false')
        else:
            if z in (181, 189, 197, 205):
                g.put(TRACK_X, y, z, RED)
            rail = c.state('powered_rail', shape=shape, powered='true', waterlogged='false')
        g.put(TRACK_X, y + 1, z, rail)

    # A warm lower landing leads straight into the north of the Seven Bells.
    g.box(-34, -30, BOTTOM_Y, BOTTOM_Y, 210, 216)[:] = BED
    g.box(-33, -30, BOTTOM_Y + 1, BOTTOM_Y + 4, 210, 216)[:] = AIR
    # The side of the entrance is inset, leaving the adjoining bone niche intact.
    g.box(-34, -34, BOTTOM_Y + 1, BOTTOM_Y + 4, 210, 215)[:] = BRICK
    g.box(-33, -30, BOTTOM_Y + 4, BOTTOM_Y + 4, 215, 215)[:] = PIER
    g.put(-33, BOTTOM_Y + 3, 215, s.SOUL_HANGING)
    g.put(-30, BOTTOM_Y + 3, 215, s.SOUL_HANGING)
    g.box(-29, -29, BOTTOM_Y + 1, BOTTOM_Y + 3, 212, 212)[:] = PIER
    g.box(-29, -29, BOTTOM_Y + 1, BOTTOM_Y + 3, 214, 214)[:] = PIER
    for (x, sy, z), (lx, ly, lz), stock in zip(CONTROLS, LAMPS, STOCK):
        # The operating face is under four blocks from the parked cart, so
        # one can mount first and press without rushing for a moving cart.
        g.box(x - 1, x - 1, sy - 1, sy + 1, z, z)[:] = PIER
        g.put(x - 1, sy, z, BED)
        g.put(x - 2, sy + 1, z, METAL)
        g.box(lx - 1, lx - 1, ly, ly + 2, lz, lz)[:] = PIER
        g.put(lx - 1, ly + 2, lz, METAL)
        g.put(*stock, c.state('barrel', facing='east', open='false'))
        plaque(g, (x, sy + 1, z), 'east', 'Вызов / пуск', 'Одна вагонетка', color='orange')
        g.put(lx, ly + 1, lz, c.slab('polished_blackstone'))
        plaque(g, (lx, ly + 2, lz), 'east', 'Горит — жди', 'Тележка в пути', color='light_gray')
    plaque(g, (-32, -10, 171), 'north', 'Перевоз ключей', 'К Семи колоколам', color='orange', post=True)
    plaque(g, (-29, -32, 215), 'south', 'Перевоз ключей', 'Верхняя крипта', color='orange')
    plaque(g, (-47, -11, 178), 'east', 'Релейная', 'Два гнезда', 'Один жетон', color='orange')
    plaque(g, (-34, -11, 180), 'east', 'Запасная тележка', color='light_gray', post=True)


class Circuit:
    """A small block layout. Wire runs describe physical cells, not abstract nets."""

    def __init__(self):
        self.parts = {}
        self.dust = set()

    def part(self, p, name, **props):
        if p in self.parts:
            raise ValueError(f'Two components at {p}')
        self.parts[p] = (name, props)

    def run(self, *points):
        self.dust.update(points)
        for (x, y, z), (xx, yy, zz) in zip(points, points[1:]):
            n = abs(xx - x) + abs(zz - z)
            assert n and (x == xx or z == zz) and (yy == y or abs(yy - y) == n), (x, y, z, xx, yy, zz)
            for i in range(1, n):
                self.dust.add((x + (xx - x)*i//n, y + (yy - y)*i//n, z + (zz - z)*i//n))

    def rep(self, p, direction, delay=1):
        self.dust.discard(p)
        self.part(p, 'repeater', facing=opposite(direction), delay=str(delay), locked='false', powered='false')

    def compare(self, p, direction, mode='compare'):
        self.part(p, 'comparator', facing=opposite(direction), mode=mode, powered='false')

    def install(self, g):
        if intersection := self.dust & self.parts.keys():
            raise ValueError(f'Wire on component: {sorted(intersection)}')
        supports = {(x, y - 1, z) for (x, y, z) in self.dust | self.parts.keys()
                    if (x, y, z) in self.dust or self.parts[x, y, z][0] in ('comparator', 'repeater')}
        if intersection := supports & (self.dust | self.parts.keys()):
            raise ValueError(f'Support on component: {sorted(intersection)}')
        for p in supports:
            g.put(*p, BED)
        for (x, y, z), (name, props) in self.parts.items():
            g.put(x, y, z, c.state(name, **props))
        # Preserve connection geometry at paste time, before any block updates.
        # Voxel neighbours along the inclined cable trench are real dust steps.
        clears = set()
        for x, y, z in sorted(self.dust):
            props = {}
            for d, (dx, dz) in DIR.items():
                q = (x + dx, y, z + dz)
                higher = (q[0], y + 1, q[2])
                lower = (q[0], y - 1, q[2])
                if q in self.dust:
                    props[d] = 'side'
                elif q in self.parts and self.parts[q][0] in ('repeater', 'comparator'):
                    f = self.parts[q][1]['facing']
                    props[d] = 'side' if DIR[f] in ((dx, dz), (-dx, -dz)) else 'none'
                elif higher in self.dust:
                    props[d] = 'up'
                    clears.add((x, y + 1, z))
                elif lower in self.dust:
                    props[d] = 'side'
                    clears.add(q)
                else:
                    props[d] = 'none'
            north_south = any(props[d] != 'none' for d in ('north', 'south'))
            east_west = any(props[d] != 'none' for d in ('east', 'west'))
            if not east_west:
                props['north'] = 'side' if props['north'] == 'none' else props['north']
                props['south'] = 'side' if props['south'] == 'none' else props['south']
            if not north_south:
                props['east'] = 'side' if props['east'] == 'none' else props['east']
                props['west'] = 'side' if props['west'] == 'none' else props['west']
            g.put(x, y, z, c.state('redstone_wire', power='0', **props))
        if conflict := clears & (supports | self.dust | self.parts.keys()):
            raise ValueError(f'Inclined dust shares clearance with circuitry: {sorted(conflict)}')
        for p in clears:
            g.put(*p, AIR)


def wiring() -> Circuit:
    m = Circuit()

    def board(u, v, h=0):
        return BOARD_X + u, BOARD_Y + h, BOARD_Z + v

    def trace(*points):
        m.run(*(board(*p) for p in points))

    m.part(TOKEN, 'dropper', facing='east', triggered='false')
    m.part(LATCH, 'dropper', facing='west', triggered='false')
    # The latch's nonzero analogue output is restored before splitting.
    m.compare(board(2, 0), 'east')
    m.rep(board(3, 0), 'east')
    m.compare(board(9, 0), 'east', 'subtract')
    m.compare(board(-4, 6), 'north', 'subtract')
    trace((4, 0), (7, 0))
    m.rep(board(8, 0), 'east')
    # Forty ticks of launch, then inhibit until the trailing edge returns.
    for v in range(1, 6):
        m.rep(board(4, v), 'south', 4)
    trace((4, 6), (9, 6), (9, 2))
    m.rep(board(9, 1), 'north')
    trace((4, 6), (-2, 6))
    m.rep(board(-3, 6), 'west')
    trace((-4, 5), (-4, -3), (0, -3), (0, -2, 1))
    m.rep(board(0, -1, 1), 'south')
    m.rep(board(-4, 1), 'north')
    trace((10, 0), (12, 0), (12, 6))
    m.rep(board(12, 3), 'south')
    trace((9, 6), (12, 6))
    m.rep(board(10, 6), 'east')
    # Delay the positive edge, then return the token from B to A. Even while
    # the falling edge is still travelling through the bank, it precedes the
    # next cycle's positive edge. Nothing needs an oscillator or scheduled ticks.
    for v in range(7, 24):
        m.rep(board(4, v), 'south', 4)
    trace((4, 24), (1, 24))
    for v in range(10, 24):
        m.rep(board(1, v), 'north', 4)
    trace((1, 9), (1, 7, -2), (1, 5, -2), (1, 2, 1))
    m.rep(board(1, 1, 1), 'north')

    def cable(x, d):
        # All three cables are separate (including diagonal neighbours). Service
        # spurs add level repeaters where the cable cannot repeat on an incline.
        for z0, z1, at in ((182, 191, x), (191, 200, x - 2), (200, 204, x)):
            for zz in range(z0, z1):
                m.run((at, floor(zz) - 3, zz), (at, floor(zz + 1) - 3, zz + 1))
        for z in (191, 200):
            y = floor(z) - 3
            m.rep((x - 1, y, z), ('west' if z == 191 else 'east') if d == 'south'
                  else ('east' if z == 191 else 'west'))

    cable(-46, 'south')
    cable(-40, 'south')
    cable(-35, 'north')
    # Launch rises into the buffer rail supports from the east. The north-south
    # branch dives beneath the busy indication on the upper floor.
    m.run((-50, -17, 172), (-31, -17, 172), (-26, -17, 172), (-26, -14, 175), (-26, -14, 176))
    m.rep((-48, -17, 172), 'east')
    m.rep((-40, -17, 172), 'east')
    m.rep((-31, -17, 172), 'east')
    m.rep((-27, -14, 176), 'west')
    m.run((-46, -17, 172), (-46, -17, 174), (-46, -20, 177), (-46, -20, 178),
          (-46, -19, 179), (-48, -19, 179), (-48, -17, 181), (-48, -17, 182))
    m.rep((-46, -17, 173), 'south')
    m.rep((-47, -17, 182), 'east')
    m.run((-46, -38, 204), (-46, -40, 206), (-26, -40, 206), (-26, -35, 211))
    m.rep((-44, -40, 206), 'east')
    m.rep((-35, -40, 206), 'east')
    m.rep((-27, -35, 211), 'west')

    m.run((-50, -17, 178), (-40, -17, 178), (-40, -17, 182))
    m.rep((-48, -17, 178), 'east')
    m.rep((-43, -17, 178), 'east')
    m.rep((-40, -17, 180), 'south')
    m.run((-40, -17, 178), (-36, -13, 178))
    m.rep((-35, -13, 178), 'east')
    m.run((-40, -38, 204), (-40, -38, 209), (-40, -34, 213), (-36, -34, 213))
    m.rep((-40, -38, 205), 'south')
    m.rep((-35, -34, 213), 'east')

    # Both push buttons OR onto the one interlock input.
    for p in CONTROLS:
        m.part(p, 'oak_button', face='wall', facing='east', powered='false')
        m.rep((p[0] - 2, p[1], p[2]), 'west')
    m.run((-34, -12, 176), (-43, -21, 176), (-43, -21, 170), (-68, -21, 170), (-68, -21, 181))
    m.rep((-43, -21, 173), 'north')
    for x in (-50, -59, -67):
        m.rep((x, -21, 170), 'west')
    m.rep((-68, -21, 178), 'south')
    m.run((-34, -33, 211), (-37, -36, 211), (-37, -38, 209), (-37, -38, 207), (-35, -38, 207), (-35, -38, 204))
    m.rep((-35, -38, 206), 'north')
    m.run((-35, -17, 182), (-35, -21, 178), (-39, -21, 178), (-39, -21, 181),
          (-68, -21, 181), (-68, -17, 185), (-66, -17, 185), (-66, -17, 179))
    m.rep((-37, -21, 178), 'west')
    for x in (-42, -51, -60, -67):
        m.rep((x, -21, 181), 'west')
    m.rep((-66, -17, 180), 'north')
    for p in LAMPS:
        m.part(p, 'redstone_lamp', lit='false')
    return m


def build(g, plaque) -> None:
    architecture(g, plaque)
    wiring().install(g)
    # Power the air just above each dropper (Java quasi-connectivity), not
    # the dropper body itself, which would conduct power to its neighbour.
    for x, y, z in (TOKEN, LATCH):
        g.put(x, y + 1, z, AIR)
