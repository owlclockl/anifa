"""Vanilla logistics retrofit for the Keepers' Store.

A metered shulker split is not an ordinary hopper filter: its permanent box
accepts *everything except* shulkers. The lower pickup is delayed until the
sideways insertion has had time to succeed. Separate wires hold the input
closed both during that test and while the ordinary-item buffer is blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from nbtlib import tag as nbt

from . import catacomb_storage as s
from . import build_throne_cathedral as t

c = t.c
Vec = tuple[int, int, int]
DIR = dict((name, (x, 0, z)) for name, x, z in t.CARDINAL)
DIR.update(up=(0, 1, 0), down=(0, -1, 0))
HORIZONTAL = ('north', 'east', 'south', 'west')
BED = s.RELAY


def add(a: Vec, b: Vec) -> Vec:
    return tuple(x + y for x, y in zip(a, b))


def step(p: Vec, direction: str, n: int = 1) -> Vec:
    return add(p, tuple(n * k for k in DIR[direction]))


def opposite(direction: str) -> str:
    return next(d for d, v in DIR.items() if v == tuple(-k for k in DIR[direction]))


class Board:
    """A checked block/BE plan; wiring is authored in world XYZ, not encoded IDs."""

    def __init__(self, origin: Vec = (0, 0, 0)) -> None:
        self.origin = origin
        self.blocks: dict[Vec, int] = {}
        self.tiles: dict[Vec, nbt.Compound] = {}
        self.wires: set[Vec] = set()
        self.supports: set[Vec] = set()
        self.clearance: set[Vec] = set()

    def put(self, p: Vec, state: int) -> None:
        p = add(p, self.origin)
        if p in self.blocks and self.blocks[p] != state:
            raise ValueError(f'Two states at {p}: {c.STATES[self.blocks[p]]} and {c.STATES[state]}')
        self.blocks[p] = state

    def block(self, p: Vec, name: str, **props: str) -> None:
        self.put(p, c.state(name, **props))

    def entity(self, p: Vec, kind: str, items=(), *, block=None, **props: str) -> None:
        self.block(p, kind if block is None else block, **props)
        self.tiles[add(p, self.origin)] = s.inventory(kind, items)

    def hopper(self, p: Vec, facing: str = 'down', *, enabled=True) -> None:
        self.entity(p, 'hopper', facing=facing, enabled=str(enabled).lower())

    def barrel(self, p: Vec, facing: str = 'up', items=()) -> None:
        self.entity(p, 'barrel', items, facing=facing, open='false')

    def compare(self, p: Vec, to: str, *, mode='compare', signal=0) -> None:
        self.block(p, 'comparator', facing=opposite(to), mode=mode, powered=str(signal > 0).lower())
        self.tiles[add(p, self.origin)] = nbt.Compound(id=nbt.String('minecraft:comparator'), OutputSignal=nbt.Int(signal))
        self.supports.add(add(step(p, 'down'), self.origin))

    def rep(self, p: Vec, to: str, delay: int = 1, *, on=False) -> None:
        self.block(p, 'repeater', facing=opposite(to), delay=str(delay), locked='false', powered=str(on).lower())
        self.supports.add(add(step(p, 'down'), self.origin))

    def wire(self, *points: Vec) -> None:
        self.wires.update(add(p, self.origin) for p in points)
        for a, b in zip(points, points[1:]):
            n = abs(a[0] - b[0]) + abs(a[2] - b[2])
            if not n or a[0] != b[0] and a[2] != b[2] or abs(a[1] - b[1]) not in (0, n):
                raise ValueError((a, b))
            self.wires.update(add(self.origin, tuple(x + (y-x)*i//n for x, y in zip(a, b))) for i in range(1, n))

    def air(self, *positions: Vec) -> None:
        self.clearance.update(add(self.origin, p) for p in positions)

    def torch(self, p: Vec, *, on=True) -> None:
        self.block(p, 'redstone_torch', lit=str(on).lower())
        self.supports.add(add(step(p, 'down'), self.origin))

    def wire_states(self) -> dict[Vec, int]:
        blocks = self.blocks.copy()
        support = self.supports | {step(p, 'down') for p in self.wires}
        for p in support:
            blocks.setdefault(p, BED)
        if p := self.wires & blocks.keys():
            raise ValueError(f'Dust overlaps block/support: {sorted(p)}')
        for p in sorted(self.wires):
            sides = {}
            for d in HORIZONTAL:
                q = step(p, d)
                high, low = step(q, 'up'), step(q, 'down')
                name, props = c.STATES[blocks.get(q, s.AIR)]
                prop = dict(props)
                if q in self.wires or name in ('minecraft:redstone_torch', 'minecraft:redstone_wall_torch'):
                    sides[d] = 'side'
                elif name in ('minecraft:repeater', 'minecraft:comparator'):
                    sides[d] = 'side' if prop['facing'] in (d, opposite(d)) else 'none'
                elif high in self.wires and q in support:
                    self.clearance.add(step(p, 'up'))
                    sides[d] = 'up'
                elif low in self.wires and q not in blocks:
                    self.clearance.add(q)
                    sides[d] = 'side'
                else:
                    sides[d] = 'none'
            for axis, cross in ((('north', 'south'), ('east', 'west')), (('east', 'west'), ('north', 'south'))):
                if all(sides[d] == 'none' for d in cross):
                    for d in axis:
                        if sides[d] == 'none':
                            sides[d] = 'side'
            blocks[p] = c.state('redstone_wire', power='0', **sides)
        if p := self.clearance & blocks.keys():
            raise ValueError(f'Obstructed release/piston/dust clearance: {sorted(p)}')
        return blocks | dict.fromkeys(self.clearance, s.AIR)


@dataclass(frozen=True)
class Split:
    origin: Vec

    def at(self, x, y, z) -> Vec:
        return add(self.origin, (x, y, z))

    @property
    def meter(self):
        return self.at(-1, 0, 0)

    @property
    def probe(self):
        return self.at(0, 0, 0)

    @property
    def buffer(self):
        return self.at(1, 0, 0)

    @property
    def loose(self):
        return self.at(1, -1, 1)

    @property
    def boxes(self):
        return self.at(0, -1, 1)

    def layout(self) -> Board:
        m = Board(self.origin)
        m.hopper((-1, 0, 0), 'east')
        m.hopper((0, 0, 0), 'east')
        m.entity((1, 0, 0), 'shulker_box', block='gray_shulker_box', facing='up')
        m.hopper((1, -1, 0), 'south')
        m.hopper((1, -1, 1))
        m.hopper((0, -1, 0), 'south', enabled=False)
        m.barrel((0, -1, 1))  # a solid, non-pulling support for the delay comparator
        m.air((0, 1, 0), (1, 0, 1))

        # Immediate input interlock and a two-comparator pulse extender. Each
        # lap loses two signal levels. The tail outlasts both the test and the
        # delayed unlock of the bypass hopper, even for an ordinary item.
        m.compare((0, 0, -1), 'north')
        m.rep((0, 0, -2), 'north')
        m.wire((0, 0, -3), (0, 0, -4))
        m.wire((0, 0, -3), (-1, 0, -3), (-1, 0, -2))
        m.rep((-1, 0, -1), 'south')
        m.compare((1, 0, -3), 'east')
        m.wire((2, 0, -3), (2, 0, -4))
        m.compare((1, 0, -4), 'west')

        # A full downstream line must not turn an ordinary item into a
        # false positive. Don't begin another transaction until the box is empty.
        m.compare((2, 0, 0), 'east')
        m.rep((3, 0, 0), 'east')
        m.wire((4, 0, 0), (4, 0, -6), (-1, 0, -6))
        m.rep((-1, 0, -5), 'south')
        m.wire((-1, 0, -4))

        # Wait longer than the receiving hopper's eight-tick transfer cooldown.
        m.compare((0, 0, 1), 'south')
        m.rep((0, 0, 2), 'south', 4)
        m.rep((0, 0, 3), 'south', 4)
        m.wire((0, 0, 4), (0, -3, 7), (2, -3, 7), (2, -3, -1))
        # Power the comparator's support, keeping the box take-away hopper
        # out of reach of the locking torch at rest.
        m.rep((1, -3, -1), 'west')
        m.torch((0, -2, -1))
        return m


@dataclass(frozen=True)
class Unloader:
    origin: Vec  # the temporary shulker cell, directly above the drain

    @property
    def dispenser(self):
        return add(self.origin, (0, 1, 0))

    @property
    def feed(self):
        return add(self.origin, (-1, 1, 0))

    @property
    def drain(self):
        return add(self.origin, (0, -1, 0))

    def layout(self) -> Board:
        m = Board(self.origin)
        m.entity((0, 1, 0), 'dispenser', facing='down', triggered='false')
        # Carpet above a block entity can pop before that block is placed.
        # Use a nonconductive, spawn-proof cap that survives either paste mode.
        m.put((0, 2, 0), s.GLASS)
        m.hopper((-1, 1, 0), 'east')
        m.hopper((0, -1, 0))
        m.block((1, 0, 0), 'piston', facing='west', extended='true')
        m.block((0, 0, 0), 'piston_head', facing='west', short='false', type='normal')
        m.put((0, 0, -1), s.GLASS)
        m.put((-1, 0, 0), BED)   # comparator reads through this solid chamber wall
        m.put((0, 0, 1), BED)

        # The dispenser contains no more than one box. Fast detector locks its
        # feed before the eight-tick hopper cooldown ends, even at cold start.
        m.compare((0, 1, -1), 'north')
        m.wire((0, 1, -2), (-1, 1, -2))
        m.rep((-1, 1, -1), 'south')
        m.rep((-2, 1, -2), 'west')
        m.rep((1, 1, -2), 'east', 4)
        m.wire((2, 1, -2), (4, 1, -2), (4, 1, -1))
        m.rep((4, 1, 0), 'south', 4)
        m.wire((4, 1, 1), (4, 1, 3), (0, 1, 3))
        # Power the dispenser through one block, not directly: its own
        # strong power would quasi-power the neighbouring break piston.
        m.rep((0, 1, 2), 'north', 4)
        m.put((0, 1, 1), BED)

        # OR of dispenser, live shulker and drain. The analogue tail bridges
        # the hand-offs and leaves the drain empty before breaking a box.
        m.compare((-2, 0, 0), 'west')
        m.rep((-3, 0, 0), 'west')
        m.wire((-4, 0, 0), (-5, 0, 0), (-5, 1, -1), (-5, 1, -2))
        m.compare((0, -1, 1), 'south')
        m.rep((0, -1, 2), 'south')
        m.wire((0, -1, 3), (0, -1, 7), (-7, -1, 7), (-7, 1, 5), (-7, 1, -2))
        m.rep((-6, 1, -2), 'east')
        m.wire((-3, 1, -2), (-3, 1, -3))
        m.compare((-4, 1, -2), 'west')
        m.wire((-5, 1, -2), (-5, 1, -3))
        m.compare((-4, 1, -3), 'east')

        # A longer discharge tail keeps the load gate shut until the empty
        # box has fallen into the hopper, which then keeps it shut if jammed.
        m.rep((-3, 1, -4), 'north')
        m.wire((-3, 1, -5), (2, 1, -5), (2, -1, -3), (2, -1, -2))
        m.rep((2, -1, -1), 'south')
        m.torch((2, 0, 0))
        m.air((2, 1, 0))
        m.wire((-3, 1, -5), (-3, 3, -7), (-6, 3, -7), (-6, 3, 7), (-6, 1, 9), (-1, 1, 9), (-1, 1, 4))
        m.rep((-1, 1, 3), 'north', 4)
        m.rep((-1, 1, 2), 'north', 4)
        m.put((-1, 1, 1), BED)
        # Repeat long legs. Removing the corresponding dust leaves a diode,
        # not a powered-wire unit whose state could bleed into a neighbour.
        for p, direction in (((-7, 1, 1), 'north'), ((-3, -1, 7), 'west'),
                             ((-6, 3, -2), 'south'), ((-6, 3, 5), 'south'),
                             ((-4, 1, 9), 'east')):
            m.wires.remove(add(m.origin, p))
            m.rep(p, direction)
        return m


# All homogeneous nine-to-one recipes in the Java 26.3 data pack whose
# product can be crafted directly back into nine inputs (including hay).
# Quartz, amethyst, nether wart, ice, etc. must never enter a compactor.
RECIPES = (
    ('iron_ingot', 'iron_block', 'Блок железа'),
    ('copper_ingot', 'copper_block', 'Блок меди'),
    ('gold_ingot', 'gold_block', 'Блок золота'),
    ('diamond', 'diamond_block', 'Блок алмазов'),
    ('emerald', 'emerald_block', 'Блок изумрудов'),
    ('raw_iron', 'raw_iron_block', 'Рудное железо'),
    ('raw_copper', 'raw_copper_block', 'Рудная медь'),
    ('raw_gold', 'raw_gold_block', 'Рудное золото'),
    ('coal', 'coal_block', 'Блок угля'),
    ('redstone', 'redstone_block', 'Блок редстоуна'),
    ('lapis_lazuli', 'lapis_block', 'Блок лазурита'),
    ('netherite_ingot', 'netherite_block', 'Блок незерита'),
    ('iron_nugget', 'iron_ingot', 'Жел. самородки'),
    ('copper_nugget', 'copper_ingot', 'Мед. самородки'),
    ('gold_nugget', 'gold_ingot', 'Зол. самородки'),
    ('slime_ball', 'slime_block', 'Блок слизи'),
    ('wheat', 'hay_block', 'Сноп пшеницы'),
    ('bone_meal', 'bone_block', 'Костный блок'),
    ('dried_kelp', 'dried_kelp_block', 'Сушёная ламинария'),
    ('resin_clump', 'resin_block', 'Блок смолы'),
)


@dataclass(frozen=True)
class Press:
    origin: Vec
    item: str
    product: str
    label: str

    @property
    def filter(self):
        return add(self.origin, (0, 2, -5))

    @property
    def reserve(self):
        return step(self.filter, 'down')

    @property
    def bus(self):
        return step(self.filter, 'up')

    @property
    def buffer(self):
        return step(self.origin, 'south')

    @property
    def output(self):
        return step(self.buffer, 'down')

    def layout(self) -> Board:
        m = Board(self.origin)
        name = f'minecraft:{self.item}'

        def q(dy, back):
            return (0, dy + 2, -5 - back)

        # Same saturating filter and full output reserve as in the old hall.
        # Everything passing this first bank is still offered to the store.
        m.entity(q(0, 0), 'hopper', (s.item(0, name, s.SEED),
                 *(s.item(i, s.FILLER_ID, 1, spacer=True) for i in range(1, 5))), facing='north', enabled='true')
        m.entity(q(-1, 0), 'hopper', (s.item(i, name, 64) for i in range(5)), facing='south', enabled='false')
        for dy, dz in ((-1, 1), (-1, 2), (-1, 3), (-2, 2), (-2, 4), (-3, 3)):
            m.put(q(dy, dz), BED)
        m.air(q(0, 4))
        m.compare(q(0, 1), 'north', signal=2)
        m.rep(q(-2, 3), 'south')
        m.block(q(-2, 1), 'redstone_wall_torch', facing='south', lit='true')
        for dy, dz, strength in ((0, 2, 2), (0, 3, 1), (-1, 4, 0)):
            m.block(q(dy, dz), 'redstone_wire', power=str(strength), west='none', east='none',
                    south='up' if dz == 4 else 'side', north='none' if dz == 4 else 'side')
        for z in range(-4, 0):
            m.hopper((0, 1, z), 'south')
        m.hopper((0, 1, 0))
        m.entity((0, 0, 0), 'crafter', orientation='south_up', crafting='false', triggered='false')
        m.hopper((0, 0, 1))
        m.barrel((0, -1, 1), 'south')

        # The crafter reports occupied slots (0..9), not stack size. Subtract
        # an 8-signal cake reference, or 15 while the result hopper is busy.
        # The latter both protects against dropping blocks and re-arms on drain.
        m.compare((0, 0, -1), 'north', mode='subtract')
        m.compare((-1, 0, -1), 'east', signal=8)
        m.block((-2, 0, -1), 'cake', bites='3')
        m.put((-2, -1, -1), BED)
        m.compare((1, 0, 1), 'east')
        m.rep((2, 0, 1), 'east')
        m.wire((3, 0, 1), (3, 0, -1), (2, 0, -1))
        m.block((3, -1, 1), 'redstone_lamp', lit='false')  # lit as long as output is waiting
        m.rep((1, 0, -1), 'west')
        m.rep((0, 0, -2), 'north')
        m.wire((0, 0, -3), (-3, 0, -3), (-3, 0, 0), (-2, 0, 0))
        m.rep((-1, 0, 0), 'east')
        return m


ENTRY_SPLIT = Split((-68, -11, 150))
UNLOADER = Unloader((-56, -15, 151))
RETURN_SPLIT = Split((-55, -18, 151))
INTAKE = ((-69, -10, 150), (-70, -10, 150))
RETURN = ((-55, -24, 155), (-56, -24, 155))
RETURN_LAMP = (-53, -24, 155)
INTAKE_FULL = (-72, -10, 150)
PAUSE = (-69, -11, 151)
PRESSES = tuple(Press((-72 + 8*(i % 5), -23, 101 + 14*(i // 5)), *recipe)
                for i, recipe in enumerate(RECIPES))
FLOOR = -25
HALL = ((-78, -25, 90), (-34, -7, 162))
ENGINE_BOUNDS = ((-80, -37, 88), (-33, -5, 164))
FARM_PORT = (-168, 0, 35)
FARM_STAND = step(FARM_PORT, 'south', 2)  # closest walking tile outside the fence
FARM_END = (-69, -5, 150)
FARM_BUFFER = ((-69, -7, 150), (-68, -7, 150))
FARM_LAMP = (-68, -7, 152)


def path(*pts: Vec) -> tuple[Vec, ...]:
    """Continuous, axis-aligned XYZ item path including both endpoints."""
    result = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d = tuple(y-x for x, y in zip(a, b))
        n = sum(abs(v) for v in d)
        if sum(bool(v) for v in d) != 1:
            raise ValueError((a, b))
        result.extend(add(a, tuple(v*i//n for v in d)) for i in range(1, n+1))
    return tuple(result)


def feed_path(m: Board, pts: tuple[Vec, ...]) -> None:
    for a, b in zip(pts, pts[1:]):
        diff = tuple(y-x for x, y in zip(a, b))
        m.hopper(a, next(d for d, delta in DIR.items() if delta == diff))


PRESS_PATH = path((-38, -20, 96), (-76, -20, 96), (-76, -20, 110), (-38, -20, 110),
                  (-38, -20, 124), (-76, -20, 124), (-76, -20, 138), (-38, -20, 138))
assert {p.bus for p in PRESSES} <= set(PRESS_PATH)
MERGE = (-54, -20, 153)
FARM_PIPE = path((-168, -5, 35), (-69, -5, 35), FARM_END)
BOX_RETURN_PATH = path(step(RETURN_SPLIT.boxes, 'down'), (-55, -22, 152), (-55, -22, 155), RETURN[0])


def links(*, press_feed=None, sorter_feed=None) -> Board:
    m = Board()
    for p, half in zip(INTAKE, ('left', 'right')):
        m.entity(p, 'chest', facing='south', type=half, waterlogged='false')
    m.block(PAUSE, 'lever', face='floor', facing='east', powered='false')
    m.put(step(PAUSE, 'down'), s.BEAM)
    m.put((-70, -11, 150), s.PIER)
    m.compare((-71, -10, 150), 'west', mode='subtract')
    m.compare((-71, -10, 149), 'south', signal=14)
    m.block((-71, -10, 148), 'cake', bites='0')
    m.put((-71, -11, 148), s.BRICK)
    m.block(INTAKE_FULL, 'redstone_lamp', lit='false')
    # Loaded boxes never touch the ordinary-item path. The two permanent gray
    # boxes are behind glass and can't be used as player inputs.
    feed_path(m, path(step(ENTRY_SPLIT.boxes, 'down'), (-70, -13, 151), (-70, -13, 157),
                     (-69, -13, 157), (-69, -13, 158), (-64, -13, 158), (-64, -13, 160),
                     (-63, -13, 160), (-63, -13, 161), (-60, -13, 161), (-60, -13, 159),
                     (-60, -14, 159), (-60, -14, 152), (-59, -14, 152), (-59, -14, 151), UNLOADER.feed))
    feed_path(m, path(step(UNLOADER.drain, 'down'), RETURN_SPLIT.meter))
    feed_path(m, path(step(ENTRY_SPLIT.loose, 'down'), (-67, -20, 151), (-67, -20, 153), MERGE))
    if press_feed is None:
        press_feed = path(MERGE, (-35, -20, 153), (-35, -20, 96), *PRESS_PATH)
    if sorter_feed is None:
        sorter_feed = path(PRESS_PATH[-1], (-38, -26, 138), (-62, -26, 138), (-62, -26, 144), s.INTAKE[0])
    feed_path(m, press_feed)
    m.hopper(step(RETURN_SPLIT.loose, 'down'), 'south')
    feed_path(m, sorter_feed)
    feed_path(m, BOX_RETURN_PATH)
    for p, half in zip(RETURN, ('right', 'left')):
        m.entity(p, 'chest', facing='north', type=half, waterlogged='false')
    m.put(step(RETURN[0], 'down'), s.TILE)
    m.compare((-54, -24, 155), 'east')
    m.block(RETURN_LAMP, 'redstone_lamp', lit='false')
    return m


def farm_receiver() -> Board:
    m = Board()
    m.hopper(step(FARM_END, 'down'))
    for p, half in zip(FARM_BUFFER, ('left', 'right')):
        m.entity(p, 'chest', facing='north', type=half, waterlogged='false')
    # A solid roof over either half silences the comparator even though the
    # hoppers can still move items. Glass seals the pipe without blocking it.
    m.put(step(FARM_BUFFER[1], 'up'), s.GLASS)
    feed_path(m, path(step(FARM_BUFFER[0], 'down'), INTAKE[0]))
    # A steady light on the upper deck means the pipe buffer is still draining.
    m.compare((-68, -7, 151), 'south')
    m.block(FARM_LAMP, 'redstone_lamp', lit='false')
    return m


def boards() -> tuple[Board, ...]:
    return (ENTRY_SPLIT.layout(), UNLOADER.layout(), RETURN_SPLIT.layout(),
            *(p.layout() for p in PRESSES), links(), farm_receiver())


def states_and_tiles(parts=None) -> tuple[dict[Vec, int], dict[Vec, nbt.Compound]]:
    result: dict[Vec, int] = {}
    data: dict[Vec, nbt.Compound] = {}
    for b in boards() if parts is None else parts:
        for p, state in b.wire_states().items():
            if p in result:
                raise ValueError(f'Mechanisms share {p}: {c.STATES[result[p]]}, {c.STATES[state]}')
            result[p] = state
        data.update(b.tiles)
    return result, data


STAIR_FOOT = (-70, -35, 148)
WORKSHOP_ENTRY = (-70, -25, 136)
UPPER_ENTRY = (-76, -12, 152)
INTAKE_STAND = (-69, -12, 152)
RETURN_STAND = (-55, -25, 154)


def waterworks(g, plaque, *, pipe=FARM_PIPE, port=FARM_PORT) -> None:
    # Ice preserves momentum through each dry gate; the next source begins
    # behind the gate, which prevents it from cancelling the upstream flow.
    channel = set(pipe)
    ice = c.state('blue_ice')
    for x, y, z in pipe:
        for d in HORIZONTAL:
            q = step((x,y,z), d)
            if q not in channel:
                g.put(*q, s.GLASS)
        g.put(x, y - 1, z, ice)
        g.put(x, y + 1, z, s.TRIM)
    for i, (x, y, z) in enumerate(pipe):
        level = i % 9
        if level == 8:
            xx, _, zz = pipe[i + 1]
            g.put(x,y,z,c.state('dark_oak_fence_gate', facing=t.direction(xx-x, zz-z),
                                in_wall='false', open='true', powered='false'))
        else:
            g.put(x,y,z,c.state('water', level=str(level)))
    x, y, z = port
    for yy in range(pipe[0][1] + 1, y + 1):
        g.put(x, yy, z, s.AIR)
        for d in HORIZONTAL:
            g.put(*step((x, yy, z), d), s.PIER if yy == y else s.GLASS)
    # A fenced opening, not an uncovered five-block drop in the greenhouse.
    for d in HORIZONTAL:
        g.put(*step((x, y + 1, z), d), t.FENCE)
    for u in (-1, 1):
        for v in (-1, 1):
            g.put(x + u, y, z + v, s.PIER)
            g.put(x + u, y + 1, z + v, t.FENCE)
    g.put(x, y + 2, z - 1, s.PIER)
    g.put(x, y + 3, z - 1, c.LANTERN)
    plaque(g, (x, y + 2, z - 2), 'north', 'Водный ввод', 'В общий сундук', color='orange')


def rooms(g, plaque, states) -> None:
    (x0, y0, z0), (x1, y1, z1) = HALL
    g.box(x0, x1, y0, y0, z0, z1)[:] = s.TILE
    g.box(x0, x1, y1, y1, z0, z1)[:] = s.TRIM
    g.box(x0+1, x1-1, y0+1, y1-1, z0+1, z1-1)[:] = s.AIR
    for x in (x0, x1):
        g.box(x, x, y0+1, y1-1, z0, z1)[:] = s.BRICK
    for z in (z0, z1):
        g.box(x0+1, x1-1, y0+1, y1-1, z, z)[:] = s.BRICK

    # Two short, independent stairs along the west edge: from the ring to
    # the press arcade, and from the arcade to the one input on the balcony.
    for i in range(1, 11):
        z, y = 148-i, -35+i
        g.box(-70, -69, y-2, y-1, z, z)[:] = s.BRICK
        g.box(-70, -69, y, y, z, z)[:] = t.stair('polished_blackstone_brick', 'north')
        g.box(-70, -69, y+1, y+3, z, z)[:] = s.AIR
        for x in (-71, -68):
            if i > 2:
                g.put(x,y,z,s.TRIM)
                g.put(x,y+1,z,s.PATINA if i % 4 == 0 else s.GLASS)
    for i in range(1, 14):
        z, y = 138+i, FLOOR+i
        g.box(-77, -76, y-1, y-1, z,z)[:] = s.BRICK
        g.box(-77, -76, y, y, z,z)[:] = t.stair('dark_oak', 'south')
        g.box(-77, -76, y+1, y+3, z,z)[:] = s.AIR
        g.put(-75,y+1,z,s.GLASS)
        if i % 4 == 1:
            g.put(-75,y,z,s.PATINA)
    g.box(-77,-69,-12,-12,151,155)[:] = s.BEAM
    g.box(-77,-76,-12,-12,151,151)[:] = t.stair('dark_oak', 'south')
    g.box(-77,-69,-11,-8,152,154)[:] = s.AIR
    g.box(-77,-69,-11,-11,155,155)[:] = t.FENCE
    for z in (151,152,153,154):
        if z != 151:
            g.put(-68,-11,z,s.GLASS)
    g.box(-71,-68,-12,-12,150,150)[:] = s.BRICK
    g.put(-71,-9,150,s.PIER)
    plaque(g, (-71,-9,151), 'south', 'Приёмка', 'Шалкеры и вещи', color='orange')
    g.put(-72,-9,150,s.PIER)
    plaque(g, (-72,-9,151), 'south', 'Сундук полон', color='white')
    g.put(-72,-11,150,s.PIER)
    plaque(g, (-72,-11,151), 'south', 'Рычаг: пауза', color='white')
    g.put(-73,-11,155,s.PIER)
    g.put(-73,-10,155,c.LANTERN)
    plaque(g, (-73,-11,154), 'north', 'Мастерская ↓', 'Выходы ниже', color='white')

    # Rib the tall workshop with a few continuous arches. They are well
    # above the sorting buses and stop short of the unloader's wiring bay.
    for z in (99, 113, 127, 141):
        for x in range(-77,-34):
            frac = (x+56)/21
            h = -15 + round(7*sqrt(max(0., 1-frac**2)))
            g.box(x,x,h,-8,z,z)[:] = s.BRICK if abs(frac) > .92 else s.TRIM
            if x in (-76,-70,-56,-42,-36):
                g.put(x,h,z,s.PATINA if x != -56 else s.PIER)
                g.put(x,h-1,z,s.LANTERN)
        for x in (-77,-35):
            if x == -77 and z > 138:
                continue
            g.box(x,x,-24,-15,z,z)[:] = s.BRICK
            for at in (-24,-20,-16):
                g.put(x,at,z,s.PIER)
    g.put(-74,-8,152,s.PIER)
    g.put(-74,-9,152,s.LANTERN)

    # Each bank has a continuous walkway and lit storage fronts. Service
    # components are visible through glass, separate from the player's bins.
    for i in range(4):
        z = 102 + 14*i
        for x in range(-75,-35):
            if (x,FLOOR,z+2) not in states:
                g.put(x,FLOOR,z+2,s.PATINA if x % 8 == 0 else s.TILE)
            for y in (-24,-23,-22):
                p = (x,y,z)
                if p not in states:
                    g.put(*p, s.BRICK if (x+2) % 8 in (0,4) or y == -22 else s.GLASS)
        for unit in PRESSES[5*i:5*(i+1)]:
            x = unit.origin[0]
            plaque(g, (x,-22,z+1), 'south', *split_label(unit.label), color='orange')
            g.put(x,-20,z+2,s.PIER)
            g.put(x,-21,z+2,s.LANTERN)
            # Hang the carved lantern cap from the roof or a circuit beam.
            for y in range(-19, y1):
                p = (x, y, z+2)
                if states.get(p, g.get(*p)) != s.AIR:
                    break
                if p in states:
                    raise ValueError(f'Lantern chain crosses circuit clearance at {p}')
                g.put(*p, c.CHAIN)
        for x in (-77,-36):
            g.put(x,-16,z+2,s.PATINA)
    for x in (-77,-36):
        for z in (94,107,121,135,149,159):
            g.put(x,-8,z,s.PIER)
            g.put(x,-9,z,s.LANTERN)
    g.put(-56,-22,155,s.PIER)
    plaque(g, (-56,-22,154), 'north', 'Пустые шалкеры', 'Забирай здесь', color='orange')
    g.put(-53,-23,155,s.PIER)
    plaque(g, (-53,-23,154), 'north', 'Есть коробки', color='white')
    g.put(-69,-8,153,s.PIER)
    plaque(g, (-69,-8,154), 'south', 'С ферм', 'Свет: очередь', color='white')

    # Old intake is now a hidden transit chest, not a second player input.
    for x in (-62,-61):
        g.put(x,-29,145,s.GLASS)
    g.put(-61,-28,144,s.BRICK)
    g.put(-62,-27,145,s.AIR)  # the original "Вещи сюда" sign no longer has backing
    for pos in ((-62,-27,145), (-70,-32,146)):
        iy, iz, ix = g.coord(*pos)
        g.signs.pop((ix, iy, iz), None)
    plaque(g, (-64,-27,145), 'south', 'Сборка и ввод', 'Лестница у входа', color='orange')
    g.put(-71,-32,146,s.PIER)
    plaque(g, (-72,-32,146), 'west', 'Автосклад', 'Кладовая', 'хранителей', color='orange')
    plaque(g, (-71,-32,147), 'south', 'К приёмке ↑', 'Мастерская выше', color='orange')
    plaque(g, (-66,-32,152), 'west', 'Бочки прямо', 'Цех по лестнице', color='white')


def split_label(label: str) -> tuple[str, ...]:
    if len(label) <= 13:
        return (label,)
    a, b = label.rsplit(' ', 1)
    return (a,b)


def build(g, plaque) -> dict[Vec, nbt.Compound]:
    states, data = states_and_tiles()
    rooms(g, plaque, states)
    waterworks(g, plaque)
    for p, state in states.items():
        g.put(*p, state)
    return data
