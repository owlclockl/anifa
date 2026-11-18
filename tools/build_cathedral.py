#!/usr/bin/env python3
"""Build Moonspire Cathedral and export it as a Java 26.3 Litematica schematic."""

from __future__ import annotations

import argparse
import gzip
import math
from dataclasses import dataclass
from pathlib import Path

import nbtlib as nbt
import numpy as np


TITLE = 'Собор Лунных Шпилей'
OUTPUT = Path(__file__).resolve().parents[1] / 'moonspire-cathedral.litematic'
DATA_VERSION = 5023  # Minecraft Java Edition 26.3
STATES: list[tuple[str, tuple[tuple[str, str], ...]]] = []
STATE_IDS: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}


@dataclass(frozen=True)
class Colorway:
    label: str
    description: str
    materials: dict[str, str]


COLORWAYS = {
    'original': Colorway('', '', {}),
    'dark': Colorway('Тёмный', 'Чернит, глубинный сланец и багровые витражи.', {
        'stone_bricks': 'polished_blackstone_bricks',
        'cracked_stone_bricks': 'cracked_polished_blackstone_bricks',
        'tuff_bricks': 'deepslate_bricks',
        'polished_andesite': 'smooth_basalt',
        'smooth_stone': 'polished_deepslate',
        'polished_diorite': 'polished_tuff',
        'chiseled_stone_bricks': 'chiseled_polished_blackstone',
        'polished_deepslate': 'blackstone',
        'polished_blackstone_bricks': 'nether_bricks',
        'waxed_oxidized_cut_copper': 'red_nether_bricks',
        'waxed_weathered_cut_copper': 'nether_bricks',
        'waxed_exposed_cut_copper': 'waxed_cut_copper',
        'stone_brick_stairs': 'polished_blackstone_brick_stairs',
        'smooth_quartz': 'polished_blackstone',
        'smooth_quartz_stairs': 'polished_blackstone_stairs',
        'smooth_quartz_slab': 'polished_blackstone_slab',
        'dark_oak_planks': 'crimson_planks',
        'dark_oak_stairs': 'crimson_stairs',
        'dark_oak_slab': 'crimson_slab',
        'stripped_dark_oak_log': 'stripped_crimson_stem',
        'blue_stained_glass': 'red_stained_glass',
        'light_blue_stained_glass': 'orange_stained_glass',
        'cyan_stained_glass': 'purple_stained_glass',
        'purple_stained_glass': 'magenta_stained_glass',
        'red_stained_glass': 'pink_stained_glass',
        'orange_stained_glass': 'brown_stained_glass',
    }),
    'light': Colorway('Светлый', 'Кварц, кальцит и бирюзовая медная кровля.', {
        'stone_bricks': 'quartz_bricks',
        'cracked_stone_bricks': 'calcite',
        'tuff_bricks': 'polished_diorite',
        'polished_andesite': 'smooth_sandstone',
        'smooth_stone': 'smooth_quartz',
        'polished_diorite': 'calcite',
        'chiseled_stone_bricks': 'chiseled_quartz_block',
        'deepslate_tiles': 'waxed_oxidized_cut_copper',
        'deepslate_bricks': 'prismarine_bricks',
        'polished_deepslate': 'dark_prismarine',
        'polished_blackstone_bricks': 'waxed_oxidized_copper',
        'waxed_oxidized_cut_copper': 'waxed_weathered_cut_copper',
        'waxed_weathered_cut_copper': 'prismarine_bricks',
        'stone_brick_stairs': 'smooth_sandstone_stairs',
        'dark_oak_planks': 'birch_planks',
        'dark_oak_stairs': 'birch_stairs',
        'dark_oak_slab': 'birch_slab',
        'stripped_dark_oak_log': 'stripped_birch_log',
        'ochre_froglight': 'pearlescent_froglight',
        'red_carpet': 'cyan_carpet',
        'blue_stained_glass': 'light_blue_stained_glass',
        'light_blue_stained_glass': 'white_stained_glass',
        'purple_stained_glass': 'pink_stained_glass',
        'red_stained_glass': 'purple_stained_glass',
    }),
}


def output_for(variant: str) -> Path:
    return OUTPUT if variant == 'original' else OUTPUT.with_stem(f'{OUTPUT.stem}-{variant}')


def state(name: str, **properties: str) -> int:
    key = ('minecraft:' + name, tuple(sorted(properties.items())))
    if key not in STATE_IDS:
        STATE_IDS[key] = len(STATES)
        STATES.append(key)
    return STATE_IDS[key]


AIR = state('air')  # index zero, as expected by Litematica
STONE = state('stone_bricks')
BASE = state('polished_andesite')
PALE = state('smooth_stone')
CARVED = state('polished_diorite')
QUARTZ = state('smooth_quartz')
ORNATE = state('chiseled_stone_bricks')
TUFF = state('tuff_bricks')
DARK = state('polished_deepslate')
DEEP = state('deepslate_tiles')
BLACK = state('polished_blackstone_bricks')
TEAL = state('waxed_oxidized_cut_copper')
JADE = state('waxed_weathered_cut_copper')
BRONZE = state('waxed_exposed_cut_copper')
GOLD = state('gold_block')
LIGHT = state('ochre_froglight', axis='y')
LANTERN = state('lantern', hanging='false', waterlogged='false')
HANGING = state('lantern', hanging='true', waterlogged='false')
WOOD = state('dark_oak_planks')
WOOD_END = state('stripped_dark_oak_log', axis='y')
CARPET = state('red_carpet')
CHAIN = state('iron_chain', axis='y', waterlogged='false')
WALL, ROOF = -1, -2  # replaced by deterministic masonry/shingle textures at export
GLASS = {c: state(f'{c}_stained_glass') for c in ('blue', 'light_blue', 'cyan', 'purple', 'magenta', 'red', 'yellow', 'orange', 'white')}
X0, X1, Y1, Z0, Z1 = -85, 85, 162, -32, 225
FLOOR = 4
CROSS = 120
NAVE = (20, 37, 54, 71, 88, 105)
CHOIR = (135, 153, 171, 190)
BAYS = tuple(zip(NAVE, NAVE[1:])) + tuple(zip(CHOIR, CHOIR[1:]))
LOW_APSE = ((37, 0), (37, 3), (26, 22), (11, 31), (0, 31))
HIGH_APSE = ((19, 0), (19, 1), (13, 12), (5, 18), (0, 18))


def stairs(material: str, facing: str, half: str = 'bottom') -> int:
    return state(material + '_stairs', facing=facing, half=half, shape='straight', waterlogged='false')


def slab(material: str, kind: str = 'bottom') -> int:
    return state(material + '_slab', type=kind, waterlogged='false')


def bars(axis: str) -> int:
    return state('iron_bars', waterlogged='false', **{d: str(d in axis.split()).lower() for d in ('north', 'east', 'south', 'west')})


def octagon(x: int, z: int, radius: int) -> bool:
    return max(abs(x), abs(z)) <= radius and abs(x) + abs(z) <= radius + radius * 3 // 5


def pointed(u: float) -> float:
    """Height of a unit Gothic arch, with its spring points at ±1."""
    return math.sqrt(max(0.0, 4 - (1 + abs(u)) ** 2) / 3)


def arch_top(dx: int, width: int, spring: int, rise: int) -> int:
    return spring + round(rise * pointed(dx / width))


def apse_ratio(x: int, z: int, outline: tuple) -> float:
    """Radial coordinate, equal to one on the faceted apse perimeter."""
    d = z - 190
    return max(((z2 - z1) * abs(x) + (x1 - x2) * d) / (x1 * z2 - x2 * z1)
               for (x1, z1), (x2, z2) in zip(outline, outline[1:]))


class Grid:
    def __init__(self) -> None:
        self.voxels = np.zeros((Y1 + 1, Z1 - Z0 + 1, X1 - X0 + 1), dtype=np.int16)

    def get(self, x: int, y: int, z: int) -> int:
        return int(self.voxels[y, z - Z0, x - X0])

    def put(self, x: int, y: int, z: int, block: int) -> None:
        assert X0 <= x <= X1 and 0 <= y <= Y1 and Z0 <= z <= Z1, (x, y, z)
        self.voxels[y, z - Z0, x - X0] = block

    def box(self, x1: int, x2: int, y1: int, y2: int, z1: int, z2: int, block: int) -> None:
        assert X0 <= x1 <= x2 <= X1 and 0 <= y1 <= y2 <= Y1 and Z0 <= z1 <= z2 <= Z1, (x1, x2, y1, y2, z1, z2)
        self.voxels[y1:y2 + 1, z1 - Z0:z2 - Z0 + 1, x1 - X0:x2 - X0 + 1] = block

    def column(self, x: int, z: int, y1: int, y2: int, block: int) -> None:
        self.box(x, x, y1, y2, z, z, block)

    def oct(self, cx: int, cz: int, y: int, radius: int, block: int, thickness: int | None = None, edge: int | None = None) -> None:
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if octagon(dx, dz, radius) and (thickness is None or not octagon(dx, dz, radius - thickness)):
                    rib = abs(abs(dx) - radius) <= 1 and abs(abs(dz) - radius * 3 // 5) <= 1
                    rib |= abs(abs(dz) - radius) <= 1 and abs(abs(dx) - radius * 3 // 5) <= 1
                    self.put(cx + dx, y, cz + dz, edge if edge is not None and rib else block)


@dataclass(frozen=True)
class Plane:
    """Local coordinates: u along the wall, d positive towards the exterior."""

    grid: Grid
    x: int
    z: int
    nx: int
    nz: int

    def pt(self, u: int, d: int) -> tuple[int, int]:
        return self.x + self.nx * d + abs(self.nz) * u, self.z + self.nz * d + abs(self.nx) * u

    def put(self, u: int, y: int, d: int, block: int) -> None:
        x, z = self.pt(u, d)
        self.grid.put(x, y, z, block)

    def rect(self, u1: int, u2: int, y1: int, y2: int, d1: int, d2: int, block: int) -> None:
        x1, z1 = self.pt(u1, d1)
        x2, z2 = self.pt(u2, d2)
        self.grid.box(min(x1, x2), max(x1, x2), y1, y2, min(z1, z2), max(z1, z2), block)

    def cut(self, center: int, sill: int, width: int, spring: int, rise: int, depth: int) -> None:
        for u in range(-width, width + 1):
            self.rect(center + u, center + u, sill, arch_top(u, width, spring, rise), -depth, 1, AIR)

    def mould(self, center: int, sill: int, width: int, spring: int, rise: int, lip: int, d1: int, d2: int, block: int) -> None:
        for u in range(-width - lip, width + lip + 1):
            y = arch_top(u, width, spring, rise) + 1 if abs(u) <= width else sill
            top = arch_top(u, width + lip, spring + lip, rise)
            if y <= top:
                self.rect(center + u, center + u, y, top, d1, d2, block)

    def portal(self, center: int, width: int, spring: int, rise: int, depth: int, grand: bool = False) -> None:
        self.cut(center, 5, width, spring, rise, depth)
        rows = ((0, 2, 0, 1, BASE), (2, 1, 1, 2, PALE), (3, 2, 2, 3, CARVED)) if grand else ((0, 1, 0, 1, CARVED), (1, 1, 1, 2, BASE))
        for offset, lip, d1, d2, material in rows:
            self.mould(center, 5, width + offset, spring + offset, rise, lip, d1, d2, material)
        for sign in (-1, 1):
            u = center + sign * (width + (4 if grand else 2))
            self.rect(u - 1, u + 1, 5, 6, 1, 4 if grand else 2, DARK)
            self.rect(u, u, 7, spring - 2, 2, 4 if grand else 2, PALE)
            self.rect(u - 1, u + 1, spring - 1, spring, 2, 4 if grand else 2, ORNATE)

    def lancet(self, center: int, sill: int, width: int, spring: int, rise: int, depth: int, seed: int = 0, kind: str = 'glass') -> None:
        self.cut(center, sill, width, spring, rise, depth)
        self.rect(center - width - 1, center + width + 1, sill - 1, sill - 1, -1, 1, PALE)
        self.mould(center, sill, width, spring, rise, 1, 0, 1, CARVED)
        for u in range(-width, width + 1):
            top = arch_top(u, width, spring, rise)
            for y in range(sill, top + 1):
                if kind == 'glass':
                    block = lancet_glass(u, y - sill, width, seed)
                elif kind == 'blind':
                    block = DARK if y > sill + 1 else TUFF
                elif kind == 'louver':
                    if (y - sill) % 3 != 0 and u != 0:
                        continue
                    block = BLACK if u else BASE
                else:
                    continue
                self.put(center + u, y, -1, block)

    def rose(self, center: int, yc: int, radius: int, depth: int) -> None:
        for u in range(-radius - 2, radius + 3):
            for v in range(-radius - 2, radius + 3):
                r = math.hypot(u, v)
                if r <= radius:
                    self.rect(center + u, center + u, yc + v, yc + v, -depth, 0, AIR)
                    self.put(center + u, yc + v, -1, rose_glass(u, v, radius))
                elif r <= radius + 2:
                    self.put(center + u, yc + v, 0, BASE)
                    self.put(center + u, yc + v, 1, PALE if r > radius + 1 else CARVED)


def lancet_glass(u: int, v: int, width: int, seed: int) -> int:
    """Leaded geometry and an inlaid jewel pattern (not random confetti)."""
    a = abs(u)
    if a == width:
        return GLASS['blue']
    if width >= 3 and a == 0 and v % 12 not in (4, 5, 6, 7, 8):
        return BASE
    t = (v + seed) % 12
    if abs(t - 6) + a <= 1:
        return GLASS['yellow']
    if abs(t - 6) + a <= 3:
        return GLASS['red'] if (v + seed) // 12 % 2 == 0 else GLASS['purple']
    if v < 2 or t == 0:
        return GLASS['cyan']
    return GLASS['light_blue'] if (a + v // 4) % 4 < 2 else GLASS['blue']


def rose_glass(u: int, v: int, radius: int) -> int:
    r = math.hypot(u, v)
    theta = math.atan2(v, u)
    sector = math.cos(theta * 12)
    if r < 2 or abs(r - radius * 0.34) <= 0.48:
        return CARVED
    if r < radius * 0.33:
        return GLASS['yellow'] if abs(u) + abs(v) <= 3 else GLASS['orange']
    if abs(r - (radius * 0.72 + sector * radius * 0.19)) < 0.65 or (sector < -0.86 and r > radius * 0.65):
        return CARVED
    if r > radius * 0.83:
        return GLASS['blue'] if sector < 0.25 else GLASS['light_blue']
    if sector > 0.35:
        return GLASS['red'] if r > radius * 0.54 else GLASS['yellow']
    return GLASS['purple'] if r > radius * 0.61 else GLASS['cyan']


def pedestal(g: Grid, x: int, z: int, y: int, radius: int, high: bool = False) -> None:
    """Layered octagonal pinnacle with a fleuron, anchored at y."""
    sections = ((0, 0, radius + 1, BASE), (1, 2, radius, PALE), (3, 7 if high else 5, radius, WALL),
                (8 if high else 6, 8 if high else 6, radius + 1, CARVED))
    for a, b, r, material in sections:
        for h in range(a, b + 1):
            g.oct(x, z, y + h, r, material)
    start = 9 if high else 7
    for j in range(radius * 2 + 2):
        r = max(0, radius - j // 2)
        g.oct(x, z, y + start + j, r, TEAL if j % 3 == 1 else DARK, edge=CARVED)
    g.put(x, y + start + radius * 2 + 2, z, JADE)
    g.put(x, y + start + radius * 2 + 3, z, GOLD)


def floor_pattern(x: int, z: int) -> int:
    a = abs(x)
    dc = abs(z - CROSS)
    if a + dc <= 19:
        r = math.hypot(x, dc)
        if 12.4 <= r <= 14.0 or a + dc in (16, 17):
            return DARK
        if a + dc <= 15 and (min(a, dc) * 3 <= max(a, dc) or abs(a - dc) <= 1):
            return JADE if a + dc > 3 else BRONZE
        return CARVED if (a + dc) % 4 == 0 else PALE
    if (a <= 6 and z < 194) or (dc <= 5 and a > 19):
        u, v = (a, z) if a <= 6 else (dc, x)
        if u in (4, 6):
            return DARK if v % 8 else CARVED
        if u <= 2 and (abs(v % 12 - 6) + u) <= 2:
            return JADE
        return PALE
    if (a - 8) % 9 == 0 or z % 9 == 0:
        return BASE
    return CARVED if (a // 9 + z // 9) % 2 == 0 else PALE


def foundations(g: Grid) -> None:
    def contains(x: int, z: int) -> bool:
        a = abs(x)
        return ((a <= 18 and -7 <= z <= 23) or octagon(a - 31, z - 9, 15)
                or (20 <= z <= 190 and a <= 38)
                or (102 <= z <= 138 and a <= 76)
                or (190 < z <= 223 and apse_ratio(x, z, LOW_APSE) <= 1.065)
                or (36 <= a <= 46 and any(abs(z - j) <= 4 for j in NAVE[1:-1] + CHOIR[1:])))

    for z in range(-9, 224):
        for x in range(-76, 77):
            if contains(x, z):
                edge = not all(contains(x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                g.column(x, z, 0, 2, DARK if edge else TUFF)
                g.put(x, 3, z, BASE if edge else STONE)
                g.put(x, 4, z, ORNATE if edge else floor_pattern(x, z))
    for z in range(-31, -5):
        y = min(4, (z + 31) // 5)
        w = 21 if z >= -26 else 20
        for x in range(-w, w + 1):
            g.column(x, z, 0, y, TUFF)
            g.put(x, y, z, floor_pattern(x, z) if abs(x) < w - 2 else DARK)
            if z in (-26, -21, -16, -11) and abs(x) <= w - 2:
                g.put(x, y, z, stairs('stone_brick', 'south'))
    for side in (-1, 1):
        for a in range(75, 85):
            for z in range(CROSS - 12, CROSS + 13):
                y = (85 - a) // 2
                g.column(side * a, z, 0, y, TUFF)
                g.put(side * a, y, z, floor_pattern(a, z))
                if a % 2 == 1 and a != 75:
                    g.put(side * a, y, z, stairs('stone_brick', 'east' if side == -1 else 'west'))
        for z in (-25, -15):
            x = side * 17
            y = min(4, (z + 31) // 5)
            g.box(x - 1, x + 1, y + 1, y + 1, z - 1, z + 1, BASE)
            g.column(x, z, y + 2, y + 5, PALE)
            g.box(x - 1, x + 1, y + 5, y + 5, z - 1, z + 1, ORNATE)
            g.put(x, y + 6, z, LANTERN)


def facade(g: Grid) -> None:
    p = Plane(g, 0, -6, 0, -1)
    p.rect(-19, 19, 5, 66, -4, 0, WALL)
    for y in (8, 11, 34, 38, 66):
        p.rect(-18, 18, y, y, 0, 1, BASE)
    p.portal(0, 7, 17, 11, 4, grand=True)
    # Outer triangular porch hood and sculptural niches above the door.
    for u in range(-13, 14):
        h = 39 - abs(u)
        p.rect(u, u, h - 1, h, 1, 4, CARVED)
        p.rect(u, u, h + 1, h + 1, 3, 4, DARK)
        if abs(u) % 3 == 0:
            p.put(u, h + 2, 3, PALE)
    p.put(0, 42, 3, JADE)
    for u in (-15, 15):
        p.lancet(u, 14, 1, 25, 3, 3, kind='blind')
        p.lancet(u, 43, 1, 54, 4, 4, seed=3)
        for dx in (-2, 2):
            p.rect(u + dx, u + dx, 9, 60, 1, 1, PALE)
            for y in (12, 31, 41, 59):
                p.put(u + dx, y, 2, ORNATE)
    p.rose(0, 52, 11, 4)
    p.rect(-19, 19, 65, 66, -1, 2, PALE)
    p.rect(-19, 19, 67, 74, -3, 0, WALL)
    for u in range(-15, 16, 5):
        p.lancet(u, 68, 1, 70, 2, 1, kind='blind')
    p.rect(-20, 20, 74, 75, -1, 2, BASE)
    for u in range(-21, 22):
        h = 96 - round(21 * abs(u) / 21)
        p.rect(u, u, 74, h, -3, 0, WALL)
        p.rect(u, u, h - 1, h, 0, 2, CARVED)
        p.put(u, h + 1, 1, DARK)
        if u % 3 == 0:
            p.put(u, h + 2, 1, CARVED)
    p.lancet(0, 77, 2, 85, 4, 3, 4)
    pedestal(g, 0, -7, 98, 1)


def spiral(g: Grid, cx: int, cz: int) -> None:
    # Quarter turns have flat landings; a walkable spiral loops around a solid pier.
    for y in range(5, 89):
        g.oct(cx, cz, y, 3, TUFF, edge=BASE)
    directions = ((1, 0, 'east'), (0, 1, 'south'), (-1, 0, 'west'), (0, -1, 'north'))
    for rise in range(72):
        turn, tread = divmod(rise, 7)
        dx, dz, facing = directions[turn % 4]
        i, y = tread - 3, 5 + rise
        x, z = cx + dx * i + dz * 6, cz + dz * i - dx * 6
        for t in range(3):
            g.put(x - t * dz, y, z + t * dx, stairs('dark_oak', facing))
            g.put(x - t * dz, y - 1, z + t * dx, WOOD)
        if tread == 6:
            # This landing fills the 3x3 square between adjoining stair flights.
            x, z = cx + dx * 5 + dz * 5, cz + dz * 5 - dx * 5
            g.box(x - 1, x + 1, y, y, z - 1, z + 1, WOOD)
    # A landing opens into the ring gallery below the top of the belfry arches.
    g.oct(cx, cz, 76, 9, BASE, 3, edge=PALE)
    g.box(cx, cx + 1, 76, 76, cz + 4, cz + 6, WOOD)


def spire(g: Grid, cx: int, cz: int, base: int, height: int, radius: int, copper: bool = False) -> None:
    prev = radius
    for dy in range(height):
        t = dy / (height - 1)
        r = max(1, round(radius * (1 - t) ** 1.24))
        primary = TEAL if copper else ROOF
        if dy in (0, 1, 7) or dy > height - 10:
            primary = DARK
        if dy in (3, 4, height - 16, height - 15):
            primary = JADE
        g.oct(cx, cz, base + dy, r, primary, None if r <= 2 else max(2, prev - r + 1), CARVED if dy % 6 == 0 else (TEAL if not copper else DARK))
        for dx in range(-r, r + 1):
            if (dy + abs(dx) * 2) % 15 in (5, 6) and abs(dx) <= r * 3 // 5:
                for side in (-1, 1):
                    g.put(cx + dx, base + dy, cz + side * r, JADE if copper else TEAL)
                    g.put(cx + side * r, base + dy, cz + dx, JADE if copper else TEAL)
        prev = r
    y = base + height
    g.column(cx, cz, y, y + 6, JADE)
    g.box(cx - 2, cx + 2, y + 3, y + 3, cz, cz, BRONZE)
    g.box(cx, cx, y + 3, y + 3, cz - 2, cz + 2, BRONZE)
    for dx, dz in ((0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)):
        g.put(cx + dx, y + (6 if dx == dz == 0 else 3), cz + dz, GOLD)


def towers(g: Grid) -> None:
    for sign in (-1, 1):
        cx, cz = sign * 31, 9
        for y in range(5, 96):
            r = 14 if y <= 25 else 13 if y <= 61 else 12
            block = WALL
            if y in (5, 6, 11, 23, 24, 26, 52, 55, 61, 62, 63, 64, 85, 86, 89, 90, 94, 95):
                r += 1 if y in (5, 23, 24, 61, 62, 86, 89, 90) else 0
                block = PALE if y % 3 else BASE
            if y >= 87 and y in (89, 90, 93, 94, 95):
                g.oct(cx, cz, y, r, block if y != 93 else DARK)
            else:
                g.oct(cx, cz, y, r, block, 3, edge=CARVED)
        for nx, nz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            p = Plane(g, cx + nx * 14, cz + nz * 14, nx, nz)
            p.portal(0, 3 if nz else 2, 14, 6, 3)
            for u in (-6, 6):
                if nz == -1 or nx == sign:
                    p.lancet(u, 12, 1, 17, 2, 2, kind='blind')
            p = Plane(g, cx + nx * 13, cz + nz * 13, nx, nz)
            for u in (-5, 0, 5):
                p.lancet(u, 30 if u == 0 else 31, 1, 43, 5, 3, abs(u))
            for u in (-7, 7):
                p.rect(u, u, 26, 55, 0, 1, CARVED)
                p.rect(u - 1, u + 1, 48, 49, 0, 1, ORNATE)
            for u in (-6, -2, 2, 6):
                p.lancet(u, 56, 1, 57, 1, 1, kind='blind')
            p = Plane(g, cx + nx * 12, cz + nz * 12, nx, nz)
            for u in (-4, 4):
                p.lancet(u, 66, 2, 78, 4, 2, kind='louver')
            for u in (-7, 0, 7):
                p.rect(u, u, 65, 84, 0, 1, CARVED)
                p.rect(u - 1, u + 1, 67, 67, 0, 1, ORNATE)
            for u in range(-6, 7, 3):
                p.put(u, 91, 1, ORNATE)
                p.put(u, 92, 1, PALE)
            p.rect(-7, 7, 93, 93, 0, 1, PALE)
        for dx in (-1, 1):
            for dz in (-1, 1):
                x, z = cx + dx * 9, cz + dz * 9
                for y in range(5, 58):
                    r = 2 if y < 12 else 1
                    g.box(x - r, x + r, y, y, z - r, z + r, BASE if y in (7, 8, 12, 25, 54, 55) else WALL)
                    g.put(x + dx * r, y, z + dz * r, PALE)
                pedestal(g, x, z, 92, 2, high=True)
        spiral(g, cx, cz)
        spire(g, cx, cz, 96, 56, 10)


def nave_and_choir(g: Grid) -> None:
    for sign in (-1, 1):
        outer = Plane(g, sign * 37, 0, sign, 0)
        upper = Plane(g, sign * 20, 0, sign, 0)
        inside = Plane(g, sign * 17, 0, -sign, 0)
        upper.rect(-4, 20, 23, 62, -3, 0, WALL)
        for z0, z1 in BAYS:
            m = (z0 + z1) // 2
            outer.rect(z0, z1, 5, 30, -2, 0, WALL)
            upper.rect(z0, z1, 5, 62, -3, 0, WALL)
            for y, material in ((5, BASE), (8, ORNATE), (27, BASE), (30, PALE)):
                outer.rect(z0, z1, y, y, 0, 1, material)
            for y, material in ((39, TUFF), (43, BASE), (60, BASE), (62, PALE)):
                upper.rect(z0, z1, y, y, 0, 1, material)
            outer.lancet(m, 11, 4, 20, 6, 2, z0 % 12)
            for off in (-6, 6):
                outer.rect(m + off, m + off, 9, 25, 0, 1, PALE)
            inside.cut(m, 5, (z1 - z0) // 2 - 3, 20, 11, 3)
            inside.mould(m, 5, (z1 - z0) // 2 - 3, 20, 11, 2, 0, 1, CARVED)
            for off in (-5, 0, 5):
                upper.lancet(m + off, 46 if off else 44, 1, 52 if off else 54, 4, 3, z0 % 12)
                inside.lancet(m + off, 33, 1, 37, 2, 1, kind='blind')
            for off in (-3, 3):
                upper.rect(m + off, m + off, 44, 56, 0, 0, PALE)
            inside.rect(z0, z1, 41, 41, 0, 1, PALE)
        for z in tuple(dict.fromkeys(NAVE + CHOIR)):
            x = sign * 17
            for y in range(5, 45):
                r = 2 if y in (5, 6, 19, 20, 41, 42, 43, 44) else 1
                g.box(x - r, x + r, y, y, z - r, z + r, BASE if r == 2 else ORNATE if y == 7 else PALE)
            g.column(x - sign * 2, z, 9, 18, CARVED)
            g.put(x - sign * 2, 19, z, ORNATE)
            g.put(x - sign * 3, 19, z, ORNATE)
            g.put(x - sign * 3, 20, z, LANTERN)


def transept(g: Grid) -> None:
    for sign in (-1, 1):
        for dz in (-1, 1):
            z = CROSS + dz * 15
            p = Plane(g, 0, z, 0, dz)
            u1, u2 = sorted((sign * 19, sign * 73))
            p.rect(u1, u2, 5, 62, -3, 0, WALL)
            for y, material in ((8, BASE), (28, BASE), (31, PALE), (60, BASE), (62, PALE)):
                p.rect(u1, u2, y, y, 0, 1, material)
            for a in (28, 45, 62):
                p.lancet(sign * a, 11, 3, 20, 5, 3, a % 12)
                for dx in (-3, 3):
                    p.lancet(sign * a + dx, 34, 1, 48, 8, 3, seed=6)
                p.rect(sign * a, sign * a, 32, 53, 0, 1, CARVED)
            for a in (36, 54, 69):
                x = sign * a
                p.rect(x - 2, x + 2, 5, 9, -1, 3, BASE)
                p.rect(x - 1, x + 1, 10, 52, 0, 2, WALL)
                p.rect(x, x, 10, 53, 3, 3, PALE)
                pedestal(g, x, z + dz, 53, 1)
        p = Plane(g, sign * 73, CROSS, sign, 0)
        p.rect(-17, 17, 5, 63, -3, 0, WALL)
        for y, material in ((8, BASE), (33, BASE), (36, PALE), (62, PALE)):
            p.rect(-16, 16, y, y, 0, 1, material)
        p.portal(0, 6, 15, 10, 3, grand=True)
        for u in range(-12, 13):
            h = 35 - abs(u)
            p.rect(u, u, h - 1, h, 1, 3, CARVED)
            p.put(u, h + 1, 2, DARK)
        for u in (-13, 13):
            p.lancet(u, 13, 1, 25, 4, 2, kind='blind')
            p.lancet(u, 41, 1, 53, 4, 2, 6)
        p.rose(0, 49, 10, 3)
        for u in range(-17, 18):
            h = 94 - 31 * abs(u) // 17
            p.rect(u, u, 62, h, -3, 0, WALL)
            p.rect(u, u, h - 1, h, 0, 1, PALE)
            p.put(u, h + 1, 1, DARK)
            if u % 3 == 0:
                p.put(u, h + 2, 1, CARVED)
        for u in (-5, 0, 5):
            p.lancet(u, 65 if u else 68, 1, 72 if u else 78, 4, 2, kind='blind')
        pedestal(g, sign * 74, CROSS, 96, 1)
        for dz in (-1, 1):
            x, z = sign * 72, CROSS + dz * 14
            for y in range(5, 68):
                g.oct(x, z, y, 3 if y < 12 or y in (30, 31, 62, 63) else 2,
                      BASE if y in (5, 6, 9, 10, 29, 30, 59, 62, 67) else WALL, edge=CARVED)
            pedestal(g, x, z, 68, 3, high=True)


def chevet(g: Grid) -> None:
    for outline, floor, ceiling, sill, spring, rise, lo in (
        (LOW_APSE, 5, 30, 11, 20, 6, .915),
        (HIGH_APSE, 26, 62, 44, 52, 6, .84),
    ):
        high = outline is HIGH_APSE
        segments = tuple(zip(outline, outline[1:]))
        for z in range(191, 222):
            for x in range(-37, 38):
                u = apse_ratio(x, z, outline)
                if not (lo <= u <= 1.025):
                    continue
                # The plan's five slanted/flat facets are treated as independent window bays.
                a, d = abs(x), z - 190
                j = max(range(len(segments)), key=lambda t: (
                    (segments[t][1][1] - segments[t][0][1]) * a + (segments[t][0][0] - segments[t][1][0]) * d
                ) / (segments[t][0][0] * segments[t][1][1] - segments[t][1][0] * segments[t][0][1]))
                (a0, d0), (a1, d1) = segments[j]
                dx, dz = a1 - a0, d1 - d0
                length = math.hypot(dx, dz)
                if j == len(segments) - 1:
                    offset, w = a, 3 if high else 7
                else:
                    t = ((a - a0) * dx + (d - d0) * dz) / (length * length)
                    offset, w = round((t - .5) * length), round(length * .32)
                g.column(x, z, floor, ceiling, WALL)
                for y in ((41, 60, 62) if high else (8, 27, 30)):
                    g.put(x, y, z, PALE if u > .97 else BASE)
                if j != 0 and w > 1 and abs(offset) <= w + 1:
                    plaster_top = arch_top(offset, w + 1, spring + 1, rise)
                    g.column(x, z, sill - 1, plaster_top, CARVED if u > .97 else WALL)
                    if abs(offset) <= w:
                        top = arch_top(offset, w, spring, rise)
                        glazing = .89 <= u <= (.972 if high else .988)
                        for y in range(sill, top + 1):
                            g.put(x, y, z, lancet_glass(offset, y - sill, w, j * 3) if glazing else AIR)
        for x, dz in outline[1:-1]:
            for sign in (-1, 1):
                cx, cz = sign * x, 190 + dz
                for y in range(26 if high else 5, (62 if high else 33) + 1):
                    g.oct(cx, cz, y, 1 if high or y > 9 else 2, PALE if y % 7 else BASE)
                if not high:
                    pedestal(g, cx, cz, 33, 1)


def roof_shell(g: Grid, heights: dict[tuple[int, int], int], eave: int) -> None:
    for (x, z), y in heights.items():
        base = min(y - 1, *(heights.get((x + dx, z + dz), y) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))))
        g.column(x, z, base, y, ROOF)
        if y <= eave + 1:
            g.put(x, y, z, DARK)
        elif (z % 17 in (0, 1) and abs(x) % 11 in (1, 2)) or (x % 18 == 0 and z % 7 == 2):
            g.put(x, y, z, JADE)


def roofs(g: Grid) -> None:
    low: dict[tuple[int, int], int] = {}
    high: dict[tuple[int, int], int] = {}
    for z in range(-3, 225):
        for x in range(-74, 75):
            a = abs(x)
            u = a / 22 if z <= 190 else apse_ratio(x, z, HIGH_APSE) / 1.155
            v = abs(z - CROSS) / 18
            if u <= 1:
                high[x, z] = 62 + round(30 * (1 - u) ** 1.08)
            if v <= 1:
                high[x, z] = max(high.get((x, z), 0), 62 + round(28 * (1 - v) ** 1.08))
            u = a / 38 if z <= 190 else apse_ratio(x, z, LOW_APSE) / 1.035
            if z >= 23 and v >= .84 and 0.49 <= u <= 1:
                low[x, z] = 30 + round(14 * (1 - u) / .51)
    roof_shell(g, low, 30)
    roof_shell(g, high, 62)
    for (x, z), y in high.items():
        if (x == 0 and y >= 86) or (z == CROSS and abs(x) >= 12):
            g.put(x, y + 1, z, TEAL)
            if ((x + z) % 5) in (0, 1):
                g.put(x, y + 2, z, JADE)
            if (x + z) % 15 == 0:
                g.put(x, y + 3, z, BRONZE)
    # Small dormers repeat at the seam between pairs of clerestory bays.
    for sign in (-1, 1):
        for z in (30, 48, 65, 82, 96, 148, 166, 183):
            x = sign * 13
            y = high[x, z]
            p = Plane(g, x, z, sign, 0)
            p.rect(-2, 2, y - 2, y + 4, -3, 0, DARK)
            p.lancet(0, y, 1, y + 2, 1, 1, seed=3)
            for u in range(-3, 4):
                p.rect(u, u, y + 6 - abs(u), y + 6 - abs(u), -4, 1, TEAL)


def flying_arch(g: Grid, inner: tuple[int, int], outer: tuple[int, int], start: int = 54) -> None:
    x0, z0 = inner
    x1, z1 = outer
    dx, dz = x1 - x0, z1 - z0
    steps = max(abs(dx), abs(dz))
    nx, nz = (0, 1) if abs(dx) >= abs(dz) else (1, 0)
    previous = start
    for i in range(steps + 1):
        t = i / steps
        h = 32 + round((start - 32) * (1 - t) ** .62)
        x, z = round(x0 + dx * t), round(z0 + dz * t)
        for w in range(-1, 2):
            g.column(x + nx * w, z + nz * w, h, previous + 2, WALL if w == 0 else CARVED)
            g.put(x + nx * w, previous + 3, z + nz * w, PALE if w else DARK)
        if i % 3 == 0 and i < steps - 3:
            g.put(x, previous + 4, z, ORNATE)
        previous = h


def flanking_pier(g: Grid, x: int, z: int) -> None:
    for y in range(5, 44):
        r = 4 if y < 9 else 3 if y < 23 else 2
        g.oct(x, z, y, r, BASE if y in (5, 6, 8, 9, 22, 23, 33, 42, 43) else WALL, edge=CARVED)
    pedestal(g, x, z, 43, 2, high=True)


def buttresses(g: Grid) -> None:
    for sign in (-1, 1):
        for z in NAVE[1:-1] + CHOIR[1:]:
            g.box(min(sign * 36, sign * 42), max(sign * 36, sign * 42), 5, 11, z - 2, z + 2, BASE)
            flanking_pier(g, sign * 42, z)
            flying_arch(g, (sign * 20, z), (sign * 42, z))
        x, z = sign * 26, 210
        flanking_pier(g, x, z)
        flying_arch(g, (sign * 13, 201), (x, z), 52)
    flanking_pier(g, 0, 219)
    flying_arch(g, (0, 207), (0, 219), 53)


def crossing_tower(g: Grid) -> None:
    for y in range(87, 111):
        r = 11 if y in (87, 88, 91, 92, 107, 108, 110) else 9
        material = PALE if y in (88, 92, 107, 110) else BASE if y in (87, 91, 108) else WALL
        g.oct(0, CROSS, y, r, material, 3, edge=CARVED)
    g.oct(0, CROSS, 94, 9, BASE)
    g.oct(0, CROSS, 110, 9, DARK)
    for nx, nz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        p = Plane(g, nx * 9, CROSS + nz * 9, nx, nz)
        for u in (-4, 0, 4):
            p.lancet(u, 96, 1, 101, 3, 2, 1)
    for x in (-7, 7):
        for z in (-7, 7):
            pedestal(g, x, CROSS + z, 108, 1)
    spire(g, 0, CROSS, 111, 31, 9, True)


def ribbed_vault(g: Grid, x0: int, x1: int, z0: int, z1: int, spring: int, rise: int) -> None:
    xc, zc = (x0 + x1) / 2, (z0 + z1) / 2
    wx, wz = (x1 - x0) / 2, (z1 - z0) / 2

    def height(x: int, z: int) -> int:
        return spring + round(rise * max(pointed((x - xc) / wx), pointed((z - zc) / wz)))

    for z in range(z0, z1 + 1):
        for x in range(x0, x1 + 1):
            h = height(x, z)
            bottom = min(h, height(max(x0, x - 1), z), height(min(x1, x + 1), z),
                         height(x, max(z0, z - 1)), height(x, min(z1, z + 1)))
            a, b = abs(x - xc) / wx, abs(z - zc) / wz
            rib = abs(a - b) <= 0.9 / min(wx, wz) or x in (x0, x1) or z in (z0, z1)
            g.column(x, z, bottom, h + 1, PALE if rib else WALL)
            if rib:
                g.put(x, bottom - 1, z, CARVED if (x + z) % 4 else BASE)
            if abs(x - xc) < 1.1 and abs(z - zc) < 1.1:
                g.put(x, h - 1, z, ORNATE)
    g.put(round(xc), spring + rise - 2, round(zc), JADE)


def vaults(g: Grid) -> None:
    for z0, z1 in BAYS:
        ribbed_vault(g, -17, 17, z0, z1, 44, 17)
        for xa, xb in ((-35, -20), (20, 35)):
            ribbed_vault(g, xa, xb, z0, z1, 18, 11)
    ribbed_vault(g, -17, 17, -2, 20, 43, 18)
    for xa, xb in ((-72, -54), (-54, -36), (-36, -18), (-18, 18), (18, 36), (36, 54), (54, 72)):
        ribbed_vault(g, xa, xb, 105, 135, 44, 17)
    for x in (-54, -36, 36, 54):
        for z in (106, 134):
            for y in range(5, 45):
                r = 2 if y in (5, 6, 41, 42, 43, 44) else 1
                g.box(x - r, x + r, y, y, z - r, z + r, WALL if r == 2 else PALE)
    for x, dz in HIGH_APSE[1:-1]:
        for side in (-1, 1):
            for y in range(5, 45):
                g.oct(side * x, 190 + dz, y, 2 if y in (5, 6, 38, 44) else 1, CARVED if y % 6 else BASE)
    angles = [math.atan2(dz, x) for x, dz in HIGH_APSE[1:]]
    for z in range(191, 222):
        for x in range(-37, 38):
            hi = apse_ratio(x, z, HIGH_APSE)
            lo = apse_ratio(x, z, LOW_APSE)
            if hi <= 1:
                r = math.hypot(x, z - 190)
                ang = math.atan2(z - 190, abs(x))
                h = 44 + round(17 * max(pointed(hi), .82 * abs(math.sin(ang * 3))))
                rib = min(abs(ang - a) for a in angles) * r <= 1.1
                g.column(x, z, h - 2, h + 1, CARVED if rib else WALL)
            elif lo <= 1:
                h = 23 + round(6 * pointed((lo - .70) / .30))
                g.column(x, z, h - 1, h, PALE if (x + z) % 19 == 0 else WALL)


def chandelier(g: Grid, x: int, z: int, y: int, radius: int) -> None:
    anchor = next(h for h in range(y + 1, 65) if g.get(x, h, z) != AIR)
    g.column(x, z, y + 1, anchor - 1, CHAIN)
    g.oct(x, z, y, radius, BRONZE, 2)
    g.box(x - radius, x + radius, y, y, z, z, JADE)
    g.box(x, x, y, y, z - radius, z + radius, JADE)
    for dx, dz in ((radius, 0), (0, radius), (-radius, 0), (0, -radius), (0, 0)):
        g.put(x + dx, y - 1, z + dz, HANGING)
        g.put(x + dx, y, z + dz, GOLD if dx == dz == 0 else BRONZE)


def interiors(g: Grid) -> None:
    seat = stairs('dark_oak', 'north')
    for z in range(27, 101, 4):
        for sign in (-1, 1):
            a, b = sorted((sign * 7, sign * 13))
            g.box(a, b, 5, 5, z, z, seat)
            for x in (sign * 6, sign * 14):
                g.put(x, 5, z, WOOD_END)
                g.put(x, 6, z, slab('dark_oak'))
    for z0, z1 in BAYS:
        for side in (-1, 1):
            for x in (side * 4, side * 24, side * 32):
                for z in (z0 + 4, z1 - 4):
                    g.put(x, FLOOR, z, LIGHT)
            chandelier(g, side * 28, (z0 + z1) // 2, 18, 2)
    for z in (28, 62, 96, 145, 181):
        chandelier(g, 0, z, 37, 4)
    chandelier(g, 0, CROSS, 33, 6)
    for x in (-62, -45, -27, 27, 45, 62):
        chandelier(g, x, CROSS, 36, 3)
        for z in (CROSS - 5, CROSS + 5):
            g.put(x, FLOOR, z, LIGHT)

    # Organ loft above the entrance, with an access bridge from the east tower stairs.
    g.box(-17, 17, 29, 29, -2, 12, BASE)
    g.box(-17, 17, 30, 30, -2, 12, WOOD)
    g.box(17, 24, 29, 29, 8, 10, BASE)
    g.box(17, 23, 30, 33, 8, 10, AIR)
    g.box(-16, 16, 28, 28, 11, 12, PALE)
    g.box(-17, 17, 31, 31, 12, 12, bars('west east'))
    for x in range(-16, 17, 4):
        g.column(x, 12, 30, 32, ORNATE)
        if x % 8 == 0:
            g.put(x, 33, 12, LANTERN)
    g.box(-13, 13, 31, 33, 0, 4, WOOD)
    g.box(-13, 13, 34, 34, 0, 4, slab('dark_oak'))
    for x in range(-12, 13):
        y = 36 + (6 - abs(x % 8 - 4))
        g.column(x, 1, 34, y, BRONZE if x % 3 else GOLD)
        if x % 4 == 0:
            g.put(x, y + 1, 1, DARK)
    for x in (-13, -8, 0, 8, 13):
        g.column(x, 2, 34, 41, WOOD_END)
        g.put(x, 42, 2, TEAL)
    g.box(-3, 3, 31, 32, 5, 6, WOOD)
    g.box(-2, 2, 33, 33, 5, 5, slab('smooth_quartz'))
    g.box(-2, 2, 31, 31, 8, 8, stairs('dark_oak', 'north'))

    # Choir stalls, stepped sanctuary, altar and a carved reredos.
    g.box(-1, 1, 5, 5, 143, 163, CARPET)
    for z in range(146, 162, 3):
        for sign in (-1, 1):
            g.put(sign * 11, 5, z, stairs('dark_oak', 'west' if sign > 0 else 'east'))
            g.put(sign * 12, 5, z, WOOD_END)
    for i in range(3):
        y, z, r = 5 + i, 164 + 2 * i, 12 - i
        g.box(-r, r, y, y, z, 187 - i, QUARTZ if i % 2 == 0 else CARVED)
        g.box(-r, r, y, y, z, z, stairs('smooth_quartz', 'south'))
    g.box(-4, 4, 8, 8, 174, 178, BASE)
    for x in (-3, 3):
        g.box(x - 1, x + 1, 9, 9, 175, 177, ORNATE)
    g.box(-5, 5, 10, 10, 174, 178, slab('smooth_quartz', 'top'))
    for x in (-3, 3):
        g.box(x - 1, x + 1, 10, 10, 175, 177, QUARTZ)
    for x in (-4, 4):
        g.put(x, 11, 177, LANTERN)
    g.column(0, 177, 11, 14, BRONZE)
    g.box(-1, 1, 13, 13, 177, 177, GOLD)
    p = Plane(g, 0, 184, 0, -1)
    p.rect(-8, 8, 8, 10, -1, 1, BASE)
    p.rect(-8, 8, 11, 19, -1, 0, WALL)
    for u in (-6, -3, 0, 3, 6):
        p.lancet(u, 11, 1, 16, 2, 1, abs(u), kind='blind')
        p.put(u, 12, -1, GLASS['yellow'])
        for v in (-1, 1):
            p.put(u + v, 15, 1, CARVED)
    p.rect(-9, 9, 19, 19, -2, 1, PALE)
    for x in (-7, 0, 7):
        pedestal(g, x, 184, 20, 1)
    for x, z in ((-21, 198), (21, 198), (-12, 211), (12, 211), (0, 214)):
        g.box(x - 1, x + 1, 5, 5, z - 1, z + 1, BASE)
        g.column(x, z, 6, 7, CARVED)
        g.put(x, 8, z, LANTERN)


def texture(g: Grid) -> None:
    blocks = g.voxels
    for kind in (WALL, ROOF):
        y, z, x = np.where(blocks == kind)
        a = np.abs(x + X0)
        z = z.astype(np.int64)
        # Symmetrical colour across the centre line, broken up into small masonry patches.
        h = (a * 1367130551 ^ y * 1597334677 ^ z * 381829731) & 0xffffffff
        h = ((h ^ (h >> 15)) * 73244475) & 0xffffffff
        h = (h ^ (h >> 14)) % 100
        if kind == WALL:
            material = np.select((h < 73, h < 83, h < 90, h < 97), (
                STONE, BASE, PALE, state('cracked_stone_bricks')), TUFF)
        else:
            material = np.select((h < 76, h < 90, h < 97), (DEEP, state('deepslate_bricks'), DARK), BLACK)
        blocks[y, z, x] = material


def build() -> np.ndarray:
    g = Grid()
    for part in (foundations, facade, towers, nave_and_choir, transept, chevet, roofs, buttresses, crossing_tower, vaults, interiors, texture):
        part(g)
    return g.voxels


def pack_states(blocks: np.ndarray, bits: int) -> nbt.LongArray:
    # Litematica indexes x fastest, then z, then y, and allows entries to straddle longs.
    flat = blocks.ravel()
    active = np.flatnonzero(flat)
    where = active.astype(np.uint64) * bits
    shift = where & 63
    word = (where >> 6).astype(np.intp)
    value = flat[active].astype(np.uint64)
    packed = np.zeros((len(flat) * bits + 63) // 64, dtype=np.uint64)
    np.bitwise_or.at(packed, word, value << shift)
    carry = shift + bits > 64
    np.bitwise_or.at(packed, word[carry] + 1, value[carry] >> (64 - shift[carry]))
    return nbt.LongArray(packed.view(np.int64))


def vector(x: int, y: int, z: int) -> nbt.Compound:
    return nbt.Compound(x=nbt.Int(x), y=nbt.Int(y), z=nbt.Int(z))


def save(path: Path, blocks: np.ndarray, preview: Path | None = None, *, variant: str = 'original',
         title: str | None = None, description: str | None = None) -> None:
    ys, zs, xs = np.nonzero(blocks)
    blocks = blocks[ys.min():ys.max() + 1, zs.min():zs.max() + 1, xs.min():xs.max() + 1]
    dy, dz, dx = blocks.shape
    colorway = COLORWAYS[variant]
    # Remap only material names and keep all block properties, including stair facings.
    # Several source materials can share one entry in the new palette.
    lookup = np.zeros(len(STATES), dtype=np.int16)
    mapped = {}
    for i in np.unique(blocks):
        name, props = STATES[i]
        material = name.removeprefix('minecraft:')
        key = 'minecraft:' + colorway.materials.get(material, material), props
        lookup[i] = mapped.setdefault(key, len(mapped))
    palette = nbt.List[nbt.Compound]()
    for name, props in mapped:
        entry = nbt.Compound(Name=nbt.String(name))
        if props:
            entry['Properties'] = nbt.Compound({k: nbt.String(v) for k, v in props})
        palette.append(entry)
    size = vector(dx, dy, dz)
    count = len(xs)
    if title is None:
        title = f'{TITLE} — {colorway.label}' if colorway.label else TITLE
    if description is None:
        description = 'Готический собор с нефом, витражами и тремя шпилями. Minecraft Java 26.3.'
        if colorway.description:
            description += ' ' + colorway.description
    metadata = nbt.Compound(
        Name=nbt.String(title), Author=nbt.String('Arena'), Description=nbt.String(description),
        RegionCount=nbt.Int(1), TimeCreated=nbt.Long(1794960000000), TimeModified=nbt.Long(1794960000000),
        TotalBlocks=nbt.Int(count), TotalVolume=nbt.Int(blocks.size), EnclosingSize=size,
    )
    if preview:
        from PIL import Image

        with Image.open(preview) as image:
            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
            square = Image.new('RGB', (128, 128), (28, 33, 41))
            square.paste(image.convert('RGB'), ((128 - image.width) // 2, (128 - image.height) // 2))
            rgb = np.asarray(square, dtype=np.uint32).reshape(-1, 3)
        argb = 0xff000000 | rgb[:, 0] << 16 | rgb[:, 1] << 8 | rgb[:, 2]
        metadata['PreviewImageData'] = nbt.IntArray(argb.view(np.int32))
    region = nbt.Compound(
        Position=vector(0, 0, 0), Size=size, BlockStatePalette=palette,
        BlockStates=pack_states(lookup[blocks], max(2, (len(palette) - 1).bit_length())),
        TileEntities=nbt.List[nbt.Compound](), Entities=nbt.List[nbt.Compound](),
        PendingBlockTicks=nbt.List[nbt.Compound](), PendingFluidTicks=nbt.List[nbt.Compound](),
    )
    root = nbt.File({
        'Version': nbt.Int(7), 'SubVersion': nbt.Int(1), 'MinecraftDataVersion': nbt.Int(DATA_VERSION),
        'Metadata': metadata, 'Regions': nbt.Compound({'Cathedral': region}),
    })
    with path.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as out:
        root.write(out)
    print(f'{path}: {dx} × {dy} × {dz}, {count:,} non-air blocks, {len(palette)} block states')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant', default='original', choices=COLORWAYS, help='material palette (default: original)')
    p.add_argument('--output', type=Path, help='override the output filename for the selected variant')
    p.add_argument('--preview', type=Path, help='optional image to embed in Litematica’s schematic browser')
    args = p.parse_args()
    save(args.output or output_for(args.variant), build(), args.preview, variant=args.variant)


if __name__ == '__main__':
    main()
