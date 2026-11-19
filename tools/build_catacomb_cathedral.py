#!/usr/bin/env python3
"""The Seal of the Depths: extend the inhabited Abbey below ground and relight the whole site."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from nbtlib import tag as nbt

from . import build_throne_cathedral as t
from . import catacomb_access as access, catacomb_funicular as funicular, catacomb_storage as storage
from .catacomb_finishes import set_dressing
from . import catacomb_logistics as logistics


c, s, r, a = t.c, t.s, t.r, t.a
TITLE = 'Аббатство Лунных Шпилей — Печать глубин'
DESCRIPTION = 'Заражение из ванильного скалка, катакомбы, фуникулёр и единая приёмка с распаковщиком, водоводом и автосборкой. Minecraft Java 26.3.'
OUTPUT = c.OUTPUT.with_stem('moonspire-cathedral-catacombs')
X0, X1, Y0, Y1, Z0, Z1 = a.X0, a.X1, -43, a.Y1, a.Z0, a.Z1
LOW = -35  # Y of the blocks below players' feet on the catacomb ring
ROCK_ROOF = -8
MIN_LIGHT = 4
CRYPT_GATE = (-31, -12, 166)
LOW_CRYPT_GATE = (-55, LOW, 166)
SERVICE_X = -100
SERVICE_FOOT = (SERVICE_X, LOW, 115)
SERVICE_DOOR = (SERVICE_X, 0, 79)
RELIQUARY = (-26, LOW + 1, 97)

AIR, BRICK, TRIM, CARVED, SLATE = t.AIR, t.BRICK, t.TRIM, t.CARVED, t.SLATE
BASALT, STEP = t.BASALT, t.STEP
COPPER, PATINA = a.BRASS, t.PATINA
MORTAR = c.state('polished_tuff')
TOMB = c.state('chiseled_tuff_bricks')
TINT = c.state('tinted_glass')
LAMP = s.SOUL_HANGING
MOONSTONE = c.GLASS['white']
BRONZE_TILE = c.GLASS['orange']
DARK_RUG, ASH_RUG = r.DARK_CARPET, r.RUIN_CARPET
TRAIL_RUG = c.state('brown_carpet')
TUFF_STEP = c.slab('tuff_brick')
TUFF_LIP = c.slab('tuff_brick', 'top')
BELL = c.state('bell', attachment='ceiling', facing='south', powered='false')
CHEST = c.state('chest', facing='south', type='single', waterlogged='false')
VECTORS = {d: (dx, dz) for d, dx, dz in t.CARDINAL}


@dataclass(frozen=True)
class Vault:
    x: int
    z: int
    rx: int
    rz: int
    height: int
    border: int


HUB = Vault(-74, 166, 16, 15, 12, PATINA)
NAMES = Vault(-29, 130, 22, 11, 10, MOONSTONE)
BELLS = Vault(-29, 220, 24, 13, 11, COPPER)
HEART = Vault(19, 176, 18, 20, 15, TINT)
ARCHIVE = Vault(-31, 102, 13, 13, 11, r.VIOLET)
VAULTS = (HUB, NAMES, HEART, BELLS, ARCHIVE)
NW, NE, SE, SW = (-74, 130), (19, 130), (19, 220), (-74, 220)
RING = (NW, NE, SE, SW, NW)
SPURS = (((-31, 130), (-31, 102)), ((-74, 166), (-55, 166)),
         (NW, (SERVICE_X, 130)), ((SERVICE_X, 130), (SERVICE_X, 115)))


class Catacombs(s.DeepGrid):
    limits = (X0, X1, Y0, Y1, Z0, Z1)

    def __init__(self) -> None:
        self.blocks = np.zeros((Y1 - Y0 + 1, Z1 - Z0 + 1, X1 - X0 + 1), dtype=np.int16)
        self.box(*a.Abbey.limits)[:] = t.assemble(pure_sculk=True).blocks
        self.signs: dict[tuple[int, int, int], nbt.Compound] = {}
        self.logistics_tiles: dict[tuple[int, int, int], nbt.Compound] = {}


def lamp(level: int) -> int:
    return c.state('light', level=str(level), waterlogged='false')


def light_at(g: Catacombs, x: int, y: int, z: int, level: int) -> None:
    if g.get(x, y, z) == AIR and not r.frame_clearance(x, y, z):
        g.put(x, y, z, lamp(level))


def bare_rock(g: Catacombs) -> None:
    # The shaped overburden joins the existing foundation without filling the old crypt.
    zones = ((-70, 168, 47, 87), (-18, 170, 69, 92), (16, 176, 36, 56), (-100, 99, 17, 32))
    for z in range(68, 265):
        for x in range(-123, 56):
            edge = min(math.hypot((x - cx) / rx, (z - cz) / rz) for cx, cz, rx, rz in zones)
            wave = s.patch(x, -16, z)
            if edge + .04 * wave > 1:
                continue
            bottom = Y0 + min(5, max(0, round((edge - .62) * 12)))
            top = -14 if -35 <= x <= 39 and 145 <= z <= 205 else ROCK_ROOF
            layers = g.box(x, x, bottom, top, z, z)[:, 0, 0]
            for n, y in enumerate(range(bottom, top + 1)):
                if layers[n] == AIR:
                    seam = math.sin(.123*x - .067*z + .37*y) + .45 * wave
                    layers[n] = s.BASALT if seam > .22 else r.BLACKSTONE if seam < -.88 else s.COBBLE


def vault(g: Catacombs, room: Vault) -> None:
    x, z, rx, rz, height, color = room.x, room.z, room.rx, room.rz, room.height, room.border
    for v in range(-rz - 2, rz + 3):
        for u in range(-rx - 2, rx + 3):
            q = math.hypot(u / rx, v / rz)
            if q > 1.12:
                continue
            ytop = LOW + 5 + round((height - 5) * math.sqrt(max(0., 1.04 - q*q)))
            dx, dz = x + u, z + v
            g.box(dx, dx, LOW - 2, LOW - 1, dz, dz)[:] = BRICK
            if q > .985:
                for y in range(LOW, ytop + 2):
                    material = CARVED if y in (LOW, LOW + 4, ytop) else BASALT if (u + v) % 5 in (0, 1) else BRICK
                    g.put(dx, y, dz, material)
                continue
            annulus = (.72 <= q <= .79 or .90 <= q <= .95)
            block = color if annulus and color != COPPER else BRONZE_TILE if annulus else SLATE if (u-v) % 11 else TRIM
            g.put(dx, LOW, dz, block)
            g.box(dx, dx, LOW + 1, ytop - 1, dz, dz)[:] = AIR
            rib = min(abs(u % 8), abs(v % 8)) == 0
            g.put(dx, ytop, dz, TRIM if rib else c.DEEP)
            if q > .87 and rib:
                g.put(dx, ytop - 1, dz, t.stair('polished_blackstone', t.direction(u, 0) if abs(u / rx) >= abs(v / rz) else t.direction(0, v), 'top'))


def passage(g: Catacombs, first: tuple[int, int], last: tuple[int, int], *, half: int = 3,
            exit_route: bool = False) -> None:
    """A broad rounded cross-section; do not lower a vault where the corridor intersects it."""
    x, z = first
    xx, zz = last
    assert (x == xx) != (z == zz)
    step_x, step_z = (xx > x) - (xx < x), (zz > z) - (zz < z)
    steps = abs(xx - x) + abs(zz - z)
    for i in range(steps + 1):
        cx, cz = x + i * step_x, z + i * step_z
        for u in range(-half, half + 1):
            px, pz = cx + u * abs(step_z), cz + u * abs(step_x)
            ceiling = 6 + round(2 * c.pointed(u / (half + .35)))
            g.put(px, LOW, pz, COPPER if exit_route and u == 0 else MORTAR if abs(u) == half - 1 else SLATE)
            g.box(px, px, LOW + 1, LOW + ceiling - 1, pz, pz)[:] = AIR
            roof = g.get(px, LOW + ceiling, pz)
            if roof != AIR and i % 9 in (0, 1):
                g.put(px, LOW + ceiling, pz, t.stair('polished_blackstone', t.direction(u * abs(step_z), u * abs(step_x)), 'top') if abs(u) == half else CARVED)
        for side in (-1, 1):
            px, pz = cx + side * (half + 1) * abs(step_z), cz + side * (half + 1) * abs(step_x)
            if i % 9 == 0 and g.get(px, LOW + 2, pz) != AIR:
                for y in range(LOW + 1, LOW + 5):
                    g.put(px, y, pz, BASALT if y not in (LOW + 1, LOW + 4) else CARVED)
        if i % 13 == 5:
            px, pz = cx + (half - 1) * abs(step_z), cz + (half - 1) * abs(step_x)
            # Hang a guide light only in the corridor, from a verified solid cap.
            y = LOW + 6
            if g.get(px, y, pz) == AIR and r.could_support_spawn(*c.STATES[g.get(px, y + 1, pz)]):
                g.put(px, y, pz, LAMP)


def flight(g: Catacombs, low: tuple[int, int, int], direction: str, high: int, *, half: int,
           open_top: int = 0) -> None:
    """One continuous stair per block of rise, with a solid stringer and seven-block vault."""
    x, base, z = low
    dx, dz = VECTORS[direction]
    tread = c.stairs('polished_blackstone_brick', direction)
    for i in range(1, high - base + 1):
        y, cx, cz = base + i, x + dx*i, z + dz*i
        opened = i > high - base - open_top
        for u in range(-half - 1, half + 2):
            px, pz = cx + u * abs(dz), cz + u * abs(dx)
            g.box(px, px, y - 2, y - 1, pz, pz)[:] = BRICK
            if abs(u) <= half:
                g.put(px, y, pz, tread)
                g.box(px, px, y + 1, y + (8 if opened else 7), pz, pz)[:] = AIR
                if not opened:
                    g.put(px, y + 8, pz, CARVED if i % 6 == 1 else BRICK)
                    if i % 7 == 2 and abs(u) == half:
                        g.put(px, y + 7, pz, LAMP)
            else:
                g.box(px, px, y, y + (2 if opened else 8), pz, pz)[:] = BRICK
                for h in range(y + 1, y + (3 if opened else 8)):
                    if h == y + 1 or (i % 7 == 0 and h < y + 7):
                        g.put(px, h, pz, CARVED if h == y + 2 or i % 7 == 0 else BASALT)
                if opened and i < high - base:
                    g.put(px, y + 3, pz, t.WALL)


def surface_exit(g: Catacombs) -> None:
    # A masonry vestibule at the head of the service stair. The short copper walk joins the lodge path.
    x, _, z = SERVICE_DOOR
    for px in range(-114, x + 5):
        for pz in range(z - 5, z + 1):
            g.box(px, px, -8, -1, pz, pz)[:] = BRICK
            g.put(px, 0, pz, BRONZE_TILE if pz == z - 2 else SLATE)
            g.box(px, px, 1, 5, pz, pz)[:] = AIR
    for u in range(-5, 6):
        for pz in range(z, z + 11):
            h = c.arch_top(u, 5, 7, 4)
            if abs(u) == 5:
                g.box(x+u, x+u, -13, h, pz, pz)[:] = BASALT if pz % 3 == 1 else BRICK
                g.put(x+u, 3, pz, CARVED)
            else:
                g.put(x+u, h, pz, t.stair('deepslate_tile', 'east' if u < 0 else 'west') if abs(u) > 1 else r.ROOF_CAP)
                g.put(x+u, h-1, pz, TRIM)
                if pz in (z, z+10):
                    g.put(x+u, h-2, pz, CARVED)
            if pz == z and abs(u) >= 4:
                g.box(x+u, x+u, -2, 5, pz-1, pz-1)[:] = BRICK
                g.put(x+u, 5, pz-2, CARVED)
                g.put(x+u, 6, pz-2, s.SOUL)
    t.arch_moulding(c.Plane(g, x, z, 0, -1), 0, 3, 5, 3, bridge_back=True)
    for u in (-3, 3):
        g.put(x + u, 0, z, TRIM)
        g.put(x + u, 8, z + 3, c.HANGING)
        # Solid support immediately above the hanging fixtures.
        g.put(x + u, 9, z + 3, CARVED)


def text_data(lines: tuple[str, ...], color: str) -> nbt.Compound:
    assert len(lines) <= 4 and all(len(line) <= 16 for line in lines), lines
    return nbt.Compound(id=nbt.String('minecraft:sign'), is_waxed=nbt.Byte(1), front_text=nbt.Compound(
        messages=nbt.List[nbt.String]((*lines, *('' for _ in range(4 - len(lines))))),
        color=nbt.String(color), has_glowing_text=nbt.Byte(1),
    ))


def plaque(g: Catacombs, pos: tuple[int, int, int], facing: str, *lines: str,
           color: str = 'white', post: bool = False) -> None:
    x, y, z = pos
    dx, dz = VECTORS[facing]
    # The sign faces into the passage and sits one block out from its backing.
    if post:
        floor = next((h for h in range(y - 1, y - 8, -1) if g.get(x-dx, h, z-dz) != AIR), y - 5)
        g.box(x-dx, x-dx, floor + 1, y, z-dz, z-dz)[:] = CARVED
    g.put(x, y, z, c.state('dark_oak_wall_sign', facing=facing, waterlogged='false'))
    iy, iz, ix = g.coord(x, y, z)
    g.signs[ix, iy, iz] = text_data(lines, color)


def compass_floor(g: Catacombs) -> None:
    x, z = HUB.x, HUB.z
    for v in range(-10, 11):
        for u in range(-10, 11):
            q = math.hypot(u, v)
            if q > 10.1:
                continue
            length, width = max(abs(u), abs(v)), min(abs(u), abs(v))
            outer = length + .4*width
            needle = (width == 0 and length < 10) or (length < 7 and width <= 2 and width <= (8-length)//2)
            if q <= 1.1:
                floor = c.GLASS['purple']
            elif length in (7, 8) and width == 0:
                floor = BRONZE_TILE
            elif needle:
                floor = MOONSTONE
            elif 9.3 <= outer <= 10.3:
                floor = c.GLASS['cyan']
            elif abs(u) == abs(v) and q < 6:
                floor = MOONSTONE
            else:
                floor = SLATE
            g.put(x + u, LOW, z + v, floor)
    for u, v in ((-10, -9), (-10, 9), (10, -9), (10, 9)):
        g.box(x+u, x+u, LOW + 1, LOW + 3, z+v, z+v)[:] = CARVED
        g.put(x+u, LOW + 4, z+v, s.SOUL)


def memorials(g: Catacombs) -> None:
    x, z = NAMES.x, NAMES.z
    names = ('Первый звон', 'Тишина', 'Сломанный ключ', 'Последний дозор', 'Луна без тени', 'Медный свод')
    plinths = (TOMB, BRICK, SLATE, TRIM, TOMB, BASALT)
    lids = (a.SLATE_STEP, TUFF_STEP, a.SLATE_STEP, r.ROOF_CAP, TUFF_STEP, r.ROOF_CAP)
    for i, (u, side) in enumerate((u, side) for side in (-1, 1) for u in (-13, 7, 13)):
        px, pz = x + u, z + side * 6
        g.box(px-2, px+2, LOW + 1, LOW + 1, pz-1, pz+1)[:] = plinths[i]
        g.box(px-1, px+1, LOW + 2, LOW + 2, pz-1, pz+1)[:] = SLATE if i != 5 else t.PATINA
        g.box(px-1, px+1, LOW + 3, LOW + 3, pz, pz)[:] = lids[i]
        if i == 2:  # A lost corner, repaired with a dressed stair rather than a whole new coffin.
            g.put(px+1, LOW + 3, pz, AIR)
            g.put(px+1, LOW + 2, pz, t.stair('deepslate_brick', 'west'))
        elif i in (1, 4):
            g.put(px, LOW + 2, pz-side, TOMB)
        elif i == 5:
            g.put(px, LOW + 3, pz, c.slab('waxed_weathered_cut_copper'))
        for dy in range(2, 6):
            g.put(px, LOW + dy, pz+side, CARVED if dy % 2 else BASALT)
        # A shallow recessed canopy backed by the vault. Its plinth is already the tomb base.
        for offset in (-2, 2):
            g.box(px+offset, px+offset, LOW + 2, LOW + 4, pz, pz)[:] = BASALT
            g.put(px+offset, LOW + 4, pz, TOMB)
            g.put(px+offset, LOW + 5, pz, t.stair('tuff_brick', 'east' if offset < 0 else 'west', 'top'))
        for offset in (-1, 0, 1):
            g.put(px+offset, LOW + 5, pz, TUFF_LIP if offset else CARVED if i in (2, 3) else TOMB)
        plaque(g, (px, LOW + 4, pz), 'south' if side < 0 else 'north', f'Хранитель {i+1:02}', names[i], 'Лунные шпили', color='light_gray')
        g.put(px, LOW + 6, pz+side, s.SOUL)


def bell_vault(g: Catacombs) -> None:
    x, z = BELLS.x, BELLS.z
    for i, u in enumerate((-15, -10, -5, 0, 5, 10, 15)):
        px, pz = x + u, z + 6
        for dx in (-1, 1):
            for y in range(LOW + 1, LOW + 6):
                block = s.BONE if y == LOW + 2 else t.WALL if y == LOW + 4 else CARVED
                g.put(px+dx, y, pz, block)
            g.put(px+dx, LOW + 5, pz, t.stair('polished_blackstone', 'east' if dx < 0 else 'west', 'top'))
        g.put(px, LOW + 5, pz, COPPER)
        g.put(px, LOW + 4, pz, BELL)
        g.put(px, LOW + 1, pz, TOMB)
        g.put(px, LOW + 2, pz, s.BONE)
        if i == 6:
            g.put(px, LOW + 6, pz, TOMB)
            g.put(px, LOW + 7, pz, s.SOUL)
        elif i in (1, 3, 5):
            g.put(px, LOW + 6, pz, a.STEP)
    plaque(g, (x, LOW + 3, z - 7), 'south', 'Семь колоколов', 'Шесть замолкли.', 'Седьмой слушает.', color='orange', post=True)
    for u in (-12, -6, 6, 12):
        for v in (-8, -7):
            g.box(x+u-1, x+u+1, LOW + 1, LOW + 4, z+v, z+v)[:] = TOMB
        g.box(x+u-1, x+u+1, LOW + 4, LOW + 4, z-6, z-6)[:] = t.PURPUR_STEP
        for dx in (-1, 0, 1):
            g.put(x+u+dx, LOW + 3, z-6, s.BONE if dx else t.ALTAR_GEM)


def archive(g: Catacombs) -> None:
    x, z = ARCHIVE.x, ARCHIVE.z
    book = c.state('bookshelf')
    for u in (-8, -4, 4, 8):
        for v in range(-7, 5):
            if abs(u) == 8 and v == -7:
                continue
            for y in range(LOW + 1, LOW + 5):
                g.put(x+u, y, z+v, c.WOOD_END if v in (-7, 4) else t.OAK_STEP if y == LOW + 4 else book)
            if v in (0, 4):
                g.put(x+u, LOW + 5, z+v, c.LANTERN)
                g.put(x+u, LOW + 4, z+v, c.WOOD)
    g.put(*RELIQUARY, CHEST)
    plaque(g, (x+5, LOW+3, z-6), 'south', 'Опись № 5', 'Эхо в осколках.', 'Город без звука.', color='light_blue', post=True)
    g.put(x, LOW + 1, z - 7, c.state('lectern', facing='south', has_book='false', powered='false'))
    plaque(g, (x, LOW + 3, z-9), 'south', 'Лунный архив', 'Пять осколков.', 'Не буди эхо.', color='white', post=True)


OUTBREAK = (
    ((17, 8, 178, 4.7), (24, 16, 177, 5.4), (34, 22, 173, 5.25), (42, 34, 171, 5.6),
     (48, 50, 165, 5.15), (47, 63, 151, 4.5), (57, 73, 144, 4.0), (68, 85, 132, 3.1), (79, 93, 127, 2.05), (87, 103, 118, .95)),
    ((47, 47, 165, 4.15), (54, 54, 179, 4.35), (62, 66, 187, 3.5), (73, 68, 194, 2.9), (85, 64, 204, 2.0), (91, 68, 209, .95)),
    ((31, 16, 171, 4.8), (41, 18, 160, 3.8), (47, 27, 153, 3.0), (49, 33, 145, 2.15), (47, 40, 138, 1.4)),
    ((2, 142, 126, 2.5), (0, 145, 124, 2.7), (-4, 149, 121, 2.1), (-6, 153, 119, 1.65), (-6, 157.35, 117, 1.05)),
    ((-4, 149, 121, 1.7), (-7, 150, 123, 1.4), (-10, 152, 125, .9), (-11, 155, 124, .75)),
    ((66, -2, 193, 3.85), (74, 3, 200, 3.7), (77, 15, 209, 3.5), (82, 29, 220, 3.9),
     (91, 42, 226, 3.9), (98, 47, 228, 3.2), (110, 49, 233, 2.35), (123, 55, 237, 1.05)),
)
ROOT_UNDER_SEAL = (
    ((14, -15, 175, 3.35), (16, -23, 175, 3.1), (19, -27, 177, 2.65),
     (20, -31, 178, 2.4), (21, -35, 180, 1.95), (20, -38, 182, 1.5)),
    ((19, -28, 177, 1.9), (22, -29, 173, 1.65), (24, -32, 172, 1.1), (25, -35, 173, .82)),
    ((20, -31, 178, 1.8), (16, -33, 178, 1.5), (14, -35, 180, 1.3), (14, -37, 182, .84)),
    ((21, -34, 179, 1.8), (23, -34, 181, 1.12), (24, -31, 182, .91), (24, -29, 183, .70)),
)

def growth(g: Catacombs, curves: tuple, *, captive: bool = False) -> None:
    # Limit the working volume to the enclosing window of the splines, even if the schematic grows.
    knots = [k for curve in curves for k in curve]
    lo = np.floor(np.min([np.array(k[:3]) - k[3] - 6 for k in knots], axis=0)).astype(int)
    hi = np.ceil(np.max([np.array(k[:3]) + k[3] + 6 for k in knots], axis=0)).astype(int)
    x0, y0, z0 = [max(int(i), o) for i, o in zip(lo, (X0, Y0, Z0))]
    x1, y1, z1 = [min(int(i), o) for i, o in zip(hi, (X1, Y1, Z1))]
    limits = (x0, x1, y0, y1, z0, z1)
    field = np.full((y1-y0+1, z1-z0+1, x1-x0+1), -2, dtype=np.float32)
    for path in curves:
        s.stroke(field, path, limits=limits)
        # The accent here is physical relief: tapered side spurs, not a contrasting material.
        for j in range(1, len(path) - 1):
            *p, radius = path[j]
            if radius < 2.2 or j % 3 == 2:
                continue
            p = np.asarray(p)
            tangent = np.subtract(path[j+1][:3], path[j-1][:3])
            tangent = tangent / np.linalg.norm(tangent)
            side = np.cross(tangent, (0., 1., 0.))
            length = np.linalg.norm(side)
            side = side / length if length > .01 else np.array((1., 0., 0.))
            side = math.cos(j*2.3) * side + math.sin(j*2.3) * np.cross(tangent, side)
            fin = ((*tuple(p + side * (.65 * radius)), 1.05),
                   (*tuple(p + side * (radius + .6) - tangent*.8), .84),
                   (*tuple(p + side * (radius + 1.5) - tangent*2.7), .68))
            s.stroke(field, fin, limits=limits)
    yy, zz, xx = np.where(field >= 0.)
    x, y, z = xx + x0, yy + y0, zz + z0
    b = g.box(*limits)
    old = b[yy, zz, xx]
    replaceable = (old == AIR) | (old == s.SCULK)
    if captive:
        # The trunk also threads through the raw stone above the case, without opening a shaft.
        replaceable |= (y > LOW + 7) & (y < -12) & np.isin(old, (s.BASALT, s.COBBLE, r.BLACKSTONE))
        replaceable &= (abs(x-HEART.x) <= 6) & (abs(z-HEART.z) <= 7) & (y >= LOW - 4)
    else:
        # No emerging tendrils in the throne route, the portal mouth, stair heads or bridge deck.
        replaceable &= ~r.frame_clearance(x, y, z)
        replaceable &= ~((z >= 117) & (z <= 225) & (x >= 64) & (y >= -1) & (y <= 10))
        replaceable &= ~((x < 8) & (y <= 24))
    b[yy[replaceable], zz[replaceable], xx[replaceable]] = s.SCULK


def sculk_colonies(g: Catacombs) -> None:
    """Use real fixtures on the sculk; leave the branches mechanically stable and non-summoning."""
    blocks = g.blocks
    blocks[blocks == s.CATALYST] = s.SCULK
    y, z, x = np.where((blocks[:-3] == s.SCULK) & (blocks[1:-2] == AIR) & (blocks[2:-1] == AIR))
    wx, wy, wz = x + X0, y + Y0 + 1, z + Z0
    off_walkways = (wy >= 12) & (wy <= 154) & ((wx >= 9) | (wy > 33))
    seed = (x * 71 ^ y * 127 ^ z * 43) % 283
    use = off_walkways & (seed < 4) & ~r.frame_clearance(wx, wy, wz)
    blocks[y[use] + 1, z[use], x[use]] = np.where(seed[use] == 0, s.SHRIEKER, s.SENSOR)

    # A visible pair in the enclosure, on different arms of the root and below the glass lid.
    sealed = (wy <= LOW + 5) & (wy >= LOW - 2) & (abs(wx - HEART.x) <= 6) & (abs(wz - HEART.z) <= 7)
    for side, u, v, h, device in ((-1, -4, -3, 1, s.SENSOR), (1, 4, 3, 0, s.SHRIEKER)):
        candidates = np.flatnonzero(sealed & ((wx - HEART.x) * side >= 2))
        if len(candidates):
            d = ((wx[candidates] - HEART.x - u)**2 + (wz[candidates] - HEART.z - v)**2
                 + (wy[candidates] - LOW - h)**2 * 2)
            i = candidates[np.argmin(d)]
            blocks[y[i] + 1, z[i], x[i]] = device


def creep(g: Catacombs) -> None:
    """A close fringe of face-attached sculk vein on roots and the masonry they touch."""
    blocks = g.blocks
    bloom = blocks == s.SCULK
    for _ in range(3):
        e = np.pad(bloom, 1)
        bloom |= (e[2:,1:-1,1:-1] | e[:-2,1:-1,1:-1] | e[1:-1,2:,1:-1] |
                  e[1:-1,:-2,1:-1] | e[1:-1,1:-1,2:] | e[1:-1,1:-1,:-2])
    y, z, x = np.where(bloom & (blocks == AIR))
    edge = ~r.frame_clearance(x + X0, y + Y0, z + Z0)
    for axis, size in zip((y, z, x), blocks.shape):
        edge &= (axis > 0) & (axis < size - 1)
    y, z, x = y[edge], z[edge], x[edge]
    stripes = np.sin(x*.38 + z*.54 - y*.83 + .9*np.sin(z*.33 - y*.17)) + .36*np.cos(x*.83 - y*.74)
    flags = np.zeros(len(y), dtype=np.uint8)
    mortar = (BRICK, TRIM, CARVED, SLATE, BASALT, MORTAR, TOMB, c.DEEP,
              s.BASALT, s.COBBLE, s.FRACTURE, s.CRACKED_ROOF, r.BLACKSTONE, c.state('tuff'), c.state('deepslate', axis='y'))
    for i, (_, dy, dz, dx) in enumerate(s.FACES):
        surface = blocks[y-dy, z-dz, x-dx]
        # Like natural sculk growth, the fringe spreads along exposed stone, not over sculk blocks.
        vein = np.isin(surface, mortar) & (stripes > .47)
        flags[vein] |= 1 << i
    for mask in np.unique(flags[flags > 0]):
        use = flags == mask
        faces = {name: str(bool(mask & (1 << i))).lower() for i, (name, *_) in enumerate(s.FACES)}
        blocks[y[use], z[use], x[use]] = c.state('sculk_vein', **faces, waterlogged='false')


def observatory(g: Catacombs) -> None:
    x, z = HEART.x, HEART.z
    clear = c.state('glass')
    for u in range(-8, 9):
        for v in range(-9, 10):
            px, pz = x + u, z + v
            if abs(u) <= 6 and abs(v) <= 7:
                g.put(px, LOW - 4, pz, s.OBSIDIAN if (u+v) % 6 else SLATE)
                g.box(px, px, LOW - 3, LOW + 5, pz, pz)[:] = AIR
            edge = abs(u) == 7 and abs(v) <= 8 or abs(v) == 8 and abs(u) <= 7
            if edge:
                post = abs(u) == 7 and abs(v) in (0, 8) or abs(v) == 8 and abs(u) in (0, 7)
                for y in range(LOW, LOW + 8):
                    block = TOMB if y in (LOW, LOW + 7) else BASALT if post else TINT if y == LOW + 1 else clear
                    g.put(px, y, pz, block)
            if abs(u) <= 6 and abs(v) <= 7 and (abs(u) > 4 or abs(v) > 4):
                g.put(px, LOW + 7, pz, TINT)
    growth(g, ROOT_UNDER_SEAL, captive=True)
    lid = g.box(x - 6, x + 6, LOW + 7, LOW + 7, z - 7, z + 7)
    lid[lid == AIR] = clear
    # The glazing stays continuous behind the carved casing. The low walk around it stays full width.
    for sign in (-1, 1):
        for plane, width in ((c.Plane(g, x, z + sign*8, 0, sign), 7), (c.Plane(g, x + sign*7, z, sign, 0), 8)):
            for u in range(-width + 1, width):
                q = abs(u) % 4
                if q <= 1:
                    plane.put(u, LOW + 6, 1, t.stair('tuff_brick', t.direction(-plane.nx, -plane.nz), 'top'))
                else:
                    plane.put(u, LOW + 6, 1, TUFF_LIP)
                if u % 2 == 0:
                    plane.put(u, LOW + 7, 1, TUFF_STEP)
    for u, v in ((-7, -9), (7, -9), (-7, 9), (7, 9)):
        g.put(x+u, LOW + 1, z+v, CARVED)
        g.put(x+u, LOW + 2, z+v, s.SOUL)
    plaque(g, (x, LOW + 4, z-9), 'north', 'Печать глубин', 'За стеклом —', 'корень разлома.', color='light_blue')
    plaque(g, (x, LOW + 4, z+9), 'south', 'Кольцо', 'Колокола: юг', 'Имена: север', color='light_blue')


def signposts(g: Catacombs) -> None:
    notes = (
        ((-29, -9, 168), 'north', ('Катакомбы', '< Спуск на запад'), 'orange'),
        ((-57, LOW + 3, 163), 'south', ('Верхняя крипта', 'Подъём к хору'), 'orange'),
        ((-69, LOW + 3, 155), 'south', ('Кольцо', 'Имена и архив', 'Двор через север'), 'white'),
        ((-69, LOW + 3, 177), 'north', ('Кольцо', 'Семь колоколов', 'Разлом'), 'white'),
        ((-76, LOW + 3, 132), 'north', ('Развилка', '< Галерея имён', 'К жилому двору >'), 'orange'),
        ((-97, LOW + 3, 128), 'south', ('Жилой двор', 'Лестница наверх', 'Прямо за углом'), 'orange'),
        ((-31, LOW + 3, 119), 'south', ('Лунный архив', 'Северная ветвь'), 'white'),
        ((-43, LOW + 3, 128), 'south', ('Галерея имён', 'Архив на севере', 'Разлом на восток'), 'white'),
        ((16, LOW + 3, 129), 'south', ('Кольцо', 'К разлому', 'Путь на юг'), 'light_blue'),
        ((16, LOW + 3, 219), 'east', ('Кольцо', 'Зал колоколов', 'Путь на запад'), 'orange'),
        ((-73, LOW + 3, 217), 'east', ('Распутье ключей', 'Путь на север'), 'orange'),
        ((-104, 3, 78), 'north', ('Катакомбы', 'Медная тропа', 'В сторону крипты'), 'orange'),
        ((-102, 3, 74), 'west', ('Жилой двор', 'Дом и мастерская'), 'orange'),
        ((-32, 7, 144), 'east', ('Крипта', 'Катакомбы', 'Западный спуск'), 'orange'),
        ((-120, 3, 89), 'north', ('Клуатр', 'Часовня Тишины'), 'white'),
        ((-120, 3, 68), 'south', ('Жилой двор', 'Катакомбы >'), 'orange'),
        ((83, 3, 115), 'south', ('Восточный мост', 'Врата в Незер'), 'light_blue'),
    )
    for pos, facing, lines, color in notes:
        plaque(g, pos, facing, *lines, color=color, post=True)


def mend_landings(g: Catacombs) -> None:
    """Remove inherited full-block lips at the courtyard, organ and old crypt junctions."""
    for side in (-1, 1):
        step = c.stairs('polished_blackstone_brick', 'east' if side < 0 else 'west')
        for u in range(75, 86):
            x, y = side*u, min(4, (85-u)//2)
            g.box(x, x, y - 2, y - 1, 117, 123)[:] = BRICK
            g.box(x, x, y, y, 117, 123)[:] = step if u in (77, 79, 81, 83) else SLATE
            g.box(x, x, y + 1, y + 5, 117, 123)[:] = AIR
            # Provide a gradual, approach-width connection to the existing wider shoulders.
            for z in (116, 124):
                g.put(x, y, z, TRIM)
    for z in range(146, 162):
        y = 4 - (z - 146)
        g.box(-31, -26, y - 2, y - 1, z, z)[:] = BRICK
        g.box(-31, -26, y, y, z, z)[:] = c.stairs('polished_blackstone_brick', 'north')
        g.box(-31, -26, y + 1, min(6, y + 5), z, z)[:] = AIR
    g.box(17, 23, 30, 30, 8, 10)[:] = c.WOOD
    g.box(17, 23, 31, 33, 8, 10)[:] = AIR
    for x in range(17, 21):
        for z in (7, 11):
            if g.get(x, 31, z) == AIR:
                g.put(x, 30, z, CARVED)
                g.put(x, 31, z, t.WALL)


def guards(g: Catacombs) -> None:
    # Guard the surviving side of the choir, with the west aisle and throne approach clear.
    for z in range(158, 201):
        x = 3
        if g.get(x, 4, z) in (AIR, s.SHRIEKER, s.SENSOR) or g.get(x, 5, z) not in (AIR, t.STEP):
            continue
        if min(g.get(x+1, y, z) for y in (2, 3, 4)) == AIR:
            g.put(x, 5, z, CARVED if z % 7 == 2 else t.WALL)


def jamb(plane: c.Plane, u: int, y0: int, y1: int, d0: int, d1: int, block: int) -> None:
    x, z = plane.pt(u, d0)
    xx, zz = plane.pt(u, d1)
    plane.grid.box(min(x, xx), max(x, xx), y0, y1, min(z, zz), max(z, zz))[:] = block


def portal_profiles(g: Catacombs) -> None:
    """Two recessed courses, tapered piers, and sculpted spring stones, outside the clear spans."""
    portals = ((c.Plane(g, 0, -7, 0, -1), 9, 17, 12),
               (c.Plane(g, -76, c.CROSS, -1, 0), 7, 15, 10),
               (c.Plane(g, 76, c.CROSS, 1, 0), 7, 15, 10))
    for plane, width, spring, rise in portals:
        for u in range(-width, width + 1):
            y = c.arch_top(u, width, spring, rise) + 1
            bend = t.direction(u * abs(plane.nz), u * abs(plane.nx))
            plane.put(u, y, 1, TUFF_LIP if abs(u) <= 1 else t.stair('tuff_brick', bend, 'top'))
            jamb(plane, u, y + 1, y + 1, -1, 1, TOMB if u % 4 == 0 else TRIM)
            if abs(u) % 2 == 0:
                plane.put(u, y + 2, 1, STEP)
            if abs(u) <= width - 2 and (u % 3 != 1 or u == 0):
                plane.put(u, y + 1, 2, t.stair('polished_blackstone_brick', bend, 'top') if abs(u) > 1 else TUFF_LIP)
        for side in (-1, 1):
            u = side * (width + 1)
            jamb(plane, u, 3, 6, 0, 1, TOMB)
            jamb(plane, u, 7, spring - 2, 0, 1, BASALT)
            plane.put(u, 5, 2, t.stair('tuff_brick', t.direction(-plane.nx, -plane.nz), 'top'))
            for y in range(7, spring - 2):
                plane.put(u, y, 2, t.WALL if y % 4 else CARVED)
            jamb(plane, u, spring - 1, spring + 2, 0, 1, TRIM)
            plane.put(u, spring - 1, 2, t.stair('tuff_brick', t.direction(-plane.nx, -plane.nz), 'top'))
            plane.put(u, spring, 2, TOMB)
            plane.put(u, spring + 1, 2, TUFF_STEP)
            plane.put(u, spring + 3, 1, t.WALL)
            plane.put(u, spring + 4, 1, TUFF_STEP)


def pier_reliefs(g: Catacombs) -> None:
    # Pilasters stand proud of the pier; the small blind lancet is recessed into the new casing.
    backing = (BRICK, TRIM, CARVED, SLATE, BASALT, MORTAR, r.BLACKSTONE)
    for side in (-1, 1):
        for z in c.NAVE[1:-1]:
            plane = c.Plane(g, side * 45, z, side, 0)
            if not all(g.get(side * 45, y, z) in backing for y in range(10, 22)):
                continue  # Keep the break in the rhythm where the sculk has replaced the pier.
            outward = t.direction(side, 0)
            for u in range(-2, 3):
                plane.put(u, 10, 1, TOMB)
                plane.put(u, 11, 1, t.stair('tuff_brick', outward))
                plane.put(u, 20, 1, t.stair('tuff_brick', outward, 'top'))
                plane.put(u, 21, 1, CARVED)
                plane.put(u, 22, 1, TUFF_STEP)
            for u in (-1, 1):
                jamb(plane, u, 12, 18, 1, 1, MORTAR)
                plane.put(u, 18, 2, t.stair('tuff_brick', outward, 'top'))
                plane.put(u, 19, 1, TUFF_LIP)
            plane.put(0, 19, 1, TOMB)


def nave_reliefs(g: Catacombs) -> None:
    # A line of inset archivolts between the existing column capitals; never touches the aisle floor.
    backing = (BRICK, TRIM, CARVED, SLATE, MORTAR, r.BLACKSTONE, c.state('polished_deepslate'))
    for side in (-1, 1):
        for begin, end in c.BAYS:
            if begin >= c.CROSS:
                continue
            center, width = (begin + end)//2, (end - begin)//2 - 3
            for u in range(-width, width + 1):
                z = center + u
                y = c.arch_top(u, width, 20, 11) + 1
                if g.get(side*15, y, z) == AIR and g.get(side*16, y, z) in backing:
                    g.put(side*15, y, z, TOMB if u == 0 else t.stair('tuff_brick', 'south' if u > 0 else 'north', 'top'))
            for v in (-2, 0, 2):
                z = end + v
                if g.get(side*14, 18, z) == AIR and g.get(side*15, 18, z) in (TRIM, CARVED):
                    g.put(side*14, 18, z,
                          TUFF_LIP if v == 0 else t.stair('tuff_brick', t.direction(side, 0), 'top'))


def detail_masonry(g: Catacombs) -> None:
    portal_profiles(g)
    pier_reliefs(g)
    nave_reliefs(g)
    # Repeated ribs tell side chambers from connecting tunnels without lowering their walking cores.
    for room, ribs in ((NAMES, (-15, -6, 6, 15)), (BELLS, (-17, -7, 7, 17))):
        for u in ribs:
            x = room.x + u
            for v in range(-8, 9):
                z = room.z + v
                support = next((y for y in range(LOW + 7, LOW + room.height + 2)
                                if g.get(x, y, z) in (BRICK, TRIM, CARVED, c.DEEP)), None)
                if support is None or g.get(x, support - 1, z) != AIR:
                    continue
                shape = (TOMB if v == 0 else TUFF_LIP if abs(v) == 1 else
                         t.stair('tuff_brick', 'south' if v < 0 else 'north', 'top'))
                g.put(x, support - 1, z, shape)
                if abs(v) >= 6 and g.get(x, support - 2, z) == AIR:
                    g.put(x, support - 2, z, t.stair('polished_blackstone', 'south' if v < 0 else 'north', 'top'))


def catacomb_ring(g: Catacombs) -> None:
    bare_rock(g)
    for room in VAULTS:
        vault(g, room)
    for start, end in zip(RING, RING[1:]):
        passage(g, start, end)
    for idx, (start, end) in enumerate(SPURS):
        passage(g, start, end, half=2 if idx == 1 else 3, exit_route=idx > 0)
    flight(g, LOW_CRYPT_GATE, 'east', -12, half=2)
    flight(g, SERVICE_FOOT, 'north', 0, half=3, open_top=9)
    surface_exit(g)
    for detail in (compass_floor, memorials, bell_vault, archive, observatory, signposts):
        detail(g)


def soften_floors(g: Catacombs) -> None:
    """Leave lamps as route landmarks; remove most glowing checkerboard paving elsewhere."""
    y, z, x = np.where(np.isin(g.blocks, (c.LIGHT, s.LUMEN)))
    pos = (y, z, x)
    wx, wy, wz = x + X0, y + Y0, z + Z0
    floor = (g.blocks[y + 1, z, x] == AIR) & (wy >= -7) & (wy <= 8)
    cx, cz = t.GLASSHOUSE
    greenhouse = (np.abs(wx - cx) <= 18) & (np.abs(wz - cz) <= 15)
    rift = ((wx > 4) & (wz >= 153) & (wz <= 207)) | ((wx >= 61) & (wz >= 188))
    exchange = floor & ~greenhouse & ~rift & (((wx * 19 + wz * 23 + wy * 17) % 13) > 3)
    g.blocks[tuple(axis[exchange] for axis in pos)] = SLATE


def low_surface_protection(g: Catacombs) -> None:
    # Slime chunks can ignore light. Protect every low floor, including caves and hidden ledges,
    # but leave the outdoor rock (well above slime-chunk altitude at the intended placement) visible.
    below = g.blocks[:ROCK_ROOF - Y0 + 1]
    y, z, x = np.where(r.spawn_surfaces(below))
    surface = below[y, z, x]
    foot = below[y + 1, z, x]
    replace = (foot == AIR) | np.array([name == 'minecraft:sculk_vein' for name, _ in c.STATES])[foot]
    inset = ~replace
    # Half slabs show the stone paving. Keep full treads at the landings, so the first
    # ascending stair lies only half a block above them, not a whole block.
    wy, wz, wx = y + Y0, z + Z0, x + X0
    landing = ((abs(wx - LOW_CRYPT_GATE[0]) <= 3) & (abs(wz - LOW_CRYPT_GATE[2]) <= 4)) | (
        (abs(wx - SERVICE_X) <= 4) & (abs(wz - SERVICE_FOOT[2]) <= 3)
    )
    slabs = {SLATE: a.SLATE_STEP, TRIM: c.slab('polished_blackstone'), MORTAR: c.slab('polished_tuff')}
    stone = (wy == LOW) & ~landing & replace
    for full, piece in slabs.items():
        change = stone & (surface == full)
        below[y[change], z[change], x[change]] = piece
        replace &= ~change
    color = np.select((surface == COPPER, (surface == MORTAR) | (surface == TOMB)),
                      (TRAIL_RUG, ASH_RUG), default=DARK_RUG)
    below[y[replace] + 1, z[replace], x[replace]] = color[replace]
    # Thin fixtures keep their place. A full-height nonspawnable inset preserves the floor elevation.
    below[y[inset], z[inset], x[inset]] = TINT


def authored_lights(g: Catacombs) -> None:
    """Sparse moderate-level lights support existing architectural and route fixtures."""
    for (x, z), (xx, zz) in (*zip(RING, RING[1:]), *SPURS):
        dx, dz = (xx > x) - (xx < x), (zz > z) - (zz < z)
        for i in range(2, abs(xx - x) + abs(zz - z), 7):
            light_at(g, x + i*dx, LOW + 2, z + i*dz, 9)
    for foot, direction, high in ((SERVICE_FOOT, 'north', 0), (LOW_CRYPT_GATE, 'east', -12)):
        x, y, z = foot
        dx, dz = VECTORS[direction]
        for i in range(1, high - y + 1, 5):
            light_at(g, x + i*dx, y + i + 3, z + i*dz, 9)
    for u, v in ((-4, -5), (5, -5), (-4, 6), (4, 5)):
        light_at(g, HEART.x + u, LOW + 4, HEART.z + v, 9)
    for vault_ in VAULTS:
        for u in (-1, 1):
            for v in (-1, 1):
                px = vault_.x + u * (vault_.rx * 3 // 5)
                pz = vault_.z + v * (vault_.rz * 3 // 5)
                light_at(g, px, LOW + 4, pz, 8 if vault_ != HEART else 9)
    for z in range(-57, 150, 11):
        y = max(0, -5 + (z + 68) // 7) if z < -31 else c.FLOOR
        light_at(g, 0, min(7, y + 3), z, 9)
    for z in range(159, 202, 7):
        light_at(g, -11, 9, z, 8)
    for z in range(126, 219, 9):
        y = sum(z >= h for h in (202, 207, 212, 217))
        light_at(g, r.road_x(z), y + 3, z, 8)
    for z in range(62, 111, 8):
        light_at(g, a.CLOISTER[0], 3, z, 8)
    for x, z in (t.LODGE, t.FORGE):
        for u in (-7, 0, 7):
            for v in (-9, 0, 9):
                light_at(g, x + u, 3, z + v, 8)
    for h in range(12, 76, 7):
        for side in (-1, 1):
            light_at(g, side * 31, h, 3, 7)
    light_at(g, 0, 35, 9, 9)
    light_at(g, t.THRONE[0] - 1, 13, t.THRONE[1] - 6, 11)
    light_at(g, t.THRONE[0] + 1, 18, t.THRONE[1] - 5, 9)


def fill_shadows(g: Catacombs) -> None:
    """First add shared fill per sector, then repair the narrow shadows that remain."""
    b = g.blocks
    _, nz, nx = b.shape
    for step in (7, 4, 1):
        y, z, x = np.where(r.spawn_exposure(b, r.block_light(b), MIN_LIGHT))
        y += 1
        place = (b[y, z, x] == AIR) & ~r.frame_clearance(x + X0, y + Y0, z + Z0)
        y, z, x = y[place], z[place], x[place]
        if not len(y):
            break
        if step != 1:
            sector = (y // step * math.ceil(nz / step) + z // step) * math.ceil(nx / step) + x // step
            distance = sum(np.abs(axis % step - step // 2) for axis in (y, z, x))
            order = np.lexsort((distance, sector))
            order = order[np.r_[True, np.diff(sector[order]) != 0]]
            y, z, x = y[order], z[order], x[order]
        b[y, z, x] = lamp(7 if step != 1 else 5)
    # Growth should stay attached, and signs/crops should stay functional. Brighten the rare non-air foot cell from a neighbor.
    y, z, x = np.where(r.spawn_exposure(b, r.block_light(b), MIN_LIGHT))
    for iy, iz, ix in zip(y + 1, z, x):
        if r.frame_clearance(ix + X0, iy + Y0, iz + Z0):
            continue
        for dy, dz, dx in ((1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            at = (iy + dy, iz + dz, ix + dx)
            if (all(0 <= i < n for i, n in zip(at, b.shape)) and b[at] == AIR
                    and not r.frame_clearance(at[2] + X0, at[0] + Y0, at[1] + Z0)):
                b[at] = lamp(8)
                break
        else:
            # An isolated veneer in a closed pocket has nowhere to put a neighboring light.
            # Replace only that tiny cell; never turn authentic veins into glow lichen.
            if c.STATES[b[iy, iz, ix]][0] == 'minecraft:sculk_vein':
                b[iy, iz, ix] = lamp(6)
    assert not r.spawn_exposure(b, r.block_light(b), MIN_LIGHT).any(), 'A shadow remains on a candidate floor'


def data_for(g: Catacombs) -> dict[tuple[int, int, int], nbt.Compound]:
    positions = t.furnishing_data(g.blocks)
    positions.update(g.signs)
    for p, data in (funicular.inventory_data() | storage.inventory_data() | g.logistics_tiles).items():
        iy, iz, ix = g.coord(*p)
        positions[ix, iy, iz] = data
    y, z, x = g.coord(*RELIQUARY)
    positions[x, y, z]['Items'] = nbt.List[nbt.Compound](
        nbt.Compound(Slot=nbt.Byte(slot), id=nbt.String('minecraft:' + name), count=nbt.Int(count))
        for slot, name, count in ((11, 'echo_shard', 5), (13, 'music_disc_5', 1), (15, 'recovery_compass', 1))
    )
    for y, z, x in zip(*np.where(g.blocks == BELL)):
        positions[int(x), int(y), int(z)] = nbt.Compound(id=nbt.String('minecraft:bell'))
    return positions


def build_site() -> Catacombs:
    g = Catacombs()
    growth(g, OUTBREAK)
    catacomb_ring(g)
    mend_landings(g)
    guards(g)
    set_dressing(g)
    detail_masonry(g)
    sculk_colonies(g)
    access.build(g, plaque)
    funicular.build(g, plaque)
    storage.build(g, plaque)
    g.logistics_tiles = logistics.build(g, plaque)
    r.remove_stray_voxels(g)
    soften_floors(g)
    low_surface_protection(g)
    a.repair_growth(g, stone_fringe=True)
    authored_lights(g)
    creep(g)
    fill_shadows(g)
    t.connect_railings(g)
    return g


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=OUTPUT)
    p.add_argument('--preview', type=Path, help='thumbnail to embed in the schematic')
    args = p.parse_args()
    g = build_site()
    c.save(args.output, g.blocks, args.preview, title=TITLE, description=DESCRIPTION, block_entities=data_for(g))


if __name__ == '__main__':
    main()
