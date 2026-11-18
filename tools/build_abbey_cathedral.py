#!/usr/bin/env python3
"""Moonspire Abbey: curved interiors, a cloister and a domed chapel."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from . import build_cathedral as c
from . import build_rift_cathedral as r
from . import build_sculk_cathedral as s


TITLE = 'Аббатство Лунных Шпилей'
DESCRIPTION = 'Тёмный скалковый собор с круговыми лестницами, крытым клуатром, купольной часовней и вратами в Незер. Java 26.3.'
OUTPUT = c.OUTPUT.with_stem('moonspire-cathedral-abbey')
X0, X1, Y0, Y1, Z0, Z1 = -207, r.X1, r.Y0, r.Y1, r.Z0, r.Z1
SHAPE = (Y1 - Y0 + 1, Z1 - Z0 + 1, X1 - X0 + 1)
CLOISTER = (-114, 120)
CHAPEL = (-164, 174)
TURNS = 34  # half-steps per revolution
LOFT_RISE = TURNS + TURNS // 2  # surface Y=30.5 at the east tower's bridge
BELL_RISE = 2 * (77 - 5)

AIR = c.AIR
BRICK, TRIM, CARVING = r.BLACK_BRICK, r.BLACK_TRIM, r.BLACK_CHISELED
BASALT, SLATE, TILE = r.BASALT_COLUMN, r.SLATE_BRICK, c.DEEP
BRASS = c.state('waxed_cut_copper')
VERDIGRIS = s.DARK_TEAL
MORTAR = c.state('polished_tuff')
STEP = r.DARK_STEP
SLATE_STEP = c.slab('deepslate_brick')
STONE_LIP = c.stairs('polished_blackstone_brick', 'north', 'top')
VIOLET = c.GLASS['purple']
BLUE = c.GLASS['cyan']
TEAL = c.GLASS['light_blue']


class Abbey(s.DeepGrid):
    limits = (X0, X1, Y0, Y1, Z0, Z1)

    def __init__(self, *, pure_sculk: bool = False) -> None:
        self.blocks = np.zeros(SHAPE, dtype=np.int16)
        self.box(*r.Valley.limits)[:] = r.precinct(pure_sculk=pure_sculk).blocks


def surface(g: Abbey, x: int, z: int, height: int, full: int, slab: int, backing: int = BRICK) -> int:
    """A uniform tread at a coordinate given in half-block units, with a solid backing."""
    y = (height - 1) // 2
    g.put(x, y - 1, z, backing)
    g.put(x, y, z, slab if height % 2 else full)
    return y


def circle(g: Abbey, cx: int, cz: int, y: int, radius: float, block: int, *, inner: float = 0.) -> None:
    for z in range(cz - math.ceil(radius), cz + math.ceil(radius) + 1):
        for x in range(cx - math.ceil(radius), cx + math.ceil(radius) + 1):
            if inner <= math.hypot(x - cx, z - cz) <= radius:
                g.put(x, y, z, block)


def rosette(u: int, v: int, size: int) -> int:
    d = math.hypot(u, v)
    a = math.atan2(v, u)
    if d < 1.3 or abs(d - size * .94) < .45:
        return BRASS
    if abs(d - size * .82) < .42 or abs(d - size * .48) < .6:
        return TRIM
    if d < size * .77 and abs(math.cos(a * 4)) > min(.95, .55 + d / (size * 3)):
        return VERDIGRIS if math.cos(a * 4) > 0 else s.COBBLE
    return SLATE if (u + v) % 7 else BRICK


def carved_nave(g: Abbey) -> None:
    # Burnished bundles, rounded plinths, and profiled capitals under the existing ribs.
    for side in (-1, 1):
        for z in (37, 54, 71, 88, 105, 135, 153):
            if side > 0 and z >= 135:
                continue  # Leave the choir's infected columns embedded in the fracture.
            x = side * 17
            g.box(x - 2, x + 2, 5, 19, z - 2, z + 2)[:] = AIR
            for y in range(5, 21):
                wide = y in (5, 6, 18, 19, 20)
                circle(g, x, z, y, 2.90 if wide else 2.18, TRIM if wide else BASALT)
                if y in (7, 17, 19):
                    circle(g, x, z, y, 2.9, CARVING, inner=1.5)
                for u, v in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                    if y in (7, 17):
                        g.put(x + u, y, z + v, BRASS)
                    elif 8 <= y <= 16:
                        g.put(x + u, y, z + v, MORTAR)
            g.put(x - side * 3, 19, z, TRIM)
            g.put(x - side * 3, 20, z, s.SOUL)

    # The organ remains accessible. A rounded, moulded opening under it frames the nave.
    for x in range(-17, 18):
        v = abs(x)
        inner = 10 + round(14 * math.sqrt(1 - (v / 13)**2)) if v <= 13 else 4
        for y in range(inner + 1, 29):
            material = CARVING if y == inner + 1 else TRIM if y == inner + 2 else BRICK
            g.box(x, x, y, y, 12, 14)[:] = material
        if v > 13:
            for y in (5, 10, 11):
                g.put(x, y, 15, CARVING if y == 11 else TRIM)
        if v <= 13 and inner > 10:
            g.put(x, inner + 1, 15, STONE_LIP)

    for z in range(27, 101, 4):
        for side in (-1, 1):
            seat = c.stairs('dark_oak', 'north')
            for a in range(6, 15):
                x = side * a
                g.box(x, x, 5, 6, z, z + 1)[:] = AIR
                dz = int(a in (6, 7, 13, 14))
                g.put(x, 5, z + dz, c.WOOD_END if a in (6, 14) else seat)
                if a in (6, 14):
                    g.put(x, 6, z + dz, c.slab('dark_oak'))
                elif a in (7, 13):
                    g.put(x, 5, z, c.slab('dark_oak'))

    for z in range(c.CROSS - 14, c.CROSS + 15):
        for x in range(-14, 15):
            d = math.hypot(x, z - c.CROSS)
            if d <= 14.2:
                block = rosette(x, z - c.CROSS, 14)
                if 11.9 < d < 12.8 and (abs(x) <= 1 or abs(z - c.CROSS) <= 1):
                    block = s.LUMEN
                g.put(x, c.FLOOR, z, block)


def crown_lamp(g: Abbey, x: int, z: int, y: int, radius: int) -> None:
    # Open metal ring and curved spokes. The original vertical chain is still in place.
    g.box(x - radius, x + radius, y - 1, y, z - radius, z + radius)[:] = AIR
    for v in range(-radius, radius + 1):
        for u in range(-radius, radius + 1):
            rho = math.hypot(u, v)
            phi = math.atan2(v, u)
            if radius - 1.25 <= rho <= radius + .25 or (rho < radius and abs(math.sin(phi * 2 + rho * .21)) < .27):
                g.put(x + u, y, z + v, BRASS if abs(rho - radius) < .55 else TRIM)
    circle(g, x, z, y, 1.5, BRASS)
    # Four solid spokes tie the rim into the chain even at diagonal turns in the lattice.
    for i in range(2, radius + 1):
        for u, v in ((i, 0), (0, i), (-i, 0), (0, -i)):
            if g.get(x + u, y, z + v) == AIR:
                g.put(x + u, y, z + v, VERDIGRIS)
    k = round(radius / math.sqrt(2))
    for u, v in ((radius, 0), (0, radius), (-radius, 0), (0, -radius), (k, k), (k, -k), (-k, k), (-k, -k)):
        g.put(x + u, y, z + v, BRASS)
        g.put(x + u, y - 1, z + v, s.SOUL_HANGING)
    g.put(x, y - 1, z, c.HANGING)


def choir_level(x: int, z: int) -> int:
    """Six concentric, half-block rises, offset west of the fracture."""
    if x > 3:
        return 0
    return sum(((x + 6) / (11.3 - j * 1.21))**2 + ((z - 175) / (18.8 - j * 1.60))**2 <= 1
               for j in range(6))


def rounded_choir(g: Abbey) -> None:
    # Remove the surviving rectilinear dais without closing the scar in the east aisle.
    g.box(-13, 3, 5, 10, 156, 189)[:] = AIR
    g.box(-10, 3, 11, 33, 182, 186)[:] = AIR
    g.box(-7, 3, 11, 14, 173, 179)[:] = AIR
    for z in range(156, 195):
        for x in range(-17, 4):
            rise = choir_level(x, z)
            if not rise or g.get(x, 4, z) == AIR:
                continue
            y = (10 + rise - 1) // 2
            if y > 5:
                g.box(x, x, 5, y - 1, z, z)[:] = BRICK
            exposed_rim = min(choir_level(x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))) < rise
            block = TRIM if exposed_rim else SLATE
            if rise % 2 == 0 and z % 6 == 4 and x in (-12, -8, -4, 0):
                block = s.LUMEN
            # The last backing block at Y=4 is the original floor; don't recolour it.
            g.put(x, y, z, SLATE_STEP if rise % 2 else block)
    # Rounded altar table with a recessed dark centre and a crescent of small shrine lights.
    ax, az = -6, 177
    for y, radius, block in ((8, 2.9, CARVING), (9, 2.2, BASALT), (10, 3.7, TRIM), (11, 3.55, STEP)):
        circle(g, ax, az, y, radius, block)
    circle(g, ax, az, 11, 2.25, r.AMETHYST)
    g.put(ax, 12, az, CARVING)
    g.put(ax, 13, az, s.SOUL)
    for u, v in ((-2, 2), (2, 2), (-2, -2), (2, -2)):
        g.put(ax + u, 11, az + v, CARVING)
        g.put(ax + u, 12, az + v, s.SOUL)

    # Open curved reredos: three scrolled arches rather than another solid wall.
    columns = [(-14, 184), (-10, 188), (-5, 190), (0, 188)]
    for i, (x, z) in enumerate(columns):
        base = (10 + choir_level(x, z) - 1) // 2
        g.box(x, x, base + 1, 16, z, z)[:] = BASALT
        for h, block in ((base + 1, CARVING), (13, BRASS), (16, CARVING), (17, s.TEARS), (18, STEP)):
            g.put(x, h, z, block)
        if i == 0:
            continue
        x0, z0 = columns[i - 1]
        w = x - x0
        for u in range(w + 1):
            z1 = round(z0 + (z - z0) * u / w)
            h = 13 + round(3 * math.sqrt(1 - (2 * u / w - 1)**2))
            g.box(x0 + u, x0 + u, h, h + 1, min(z1, z0) if u == 0 else z1 - 1, z1)[:] = TRIM
            g.put(x0 + u, h + 2, z1, STEP if u % 2 else VERDIGRIS)


def stair_phase(u: int, v: int, side: int) -> int:
    return round(math.atan2(v, side * u) * TURNS / math.tau) % TURNS


def helical_stairs(g: Abbey) -> None:
    for side in (-1, 1):
        cx, cz = side * 31, 9
        for v in range(-9, 10):
            for u in range(-9, 10):
                rho = math.hypot(u, v)
                x, z = cx + u, cz + v
                if rho > 9.2:
                    continue
                g.box(x, x, 5, 76, z, z)[:] = AIR
                if rho <= 3.45:
                    for y in range(5, 77):
                        g.put(x, y, z, BRASS if y % 9 == 0 and rho >= 2.3 else BASALT if rho >= 2.7 else BRICK)
                    continue
                phase = stair_phase(u, v, side)
                if rho <= 8.65:
                    for rise in range(phase, BELL_RISE, TURNS):
                        if not rise:
                            continue
                        block = s.LUMEN if rise % 6 == 0 and 3.45 < rho < 5.7 else TRIM if rho > 7.4 else SLATE
                        surface(g, x, z, 10 + rise, block, STEP if rho > 7.4 else SLATE_STEP)
                # A cutout leaves headroom at the last turn into the belfry gallery.
                if not (1 <= phase <= BELL_RISE % TURNS - 1 and rho <= 8.65):
                    g.put(x, 76, z, CARVING if rho > 8.65 else TRIM)
                # Discrete lantern shelves on the inner shaft never intrude on the outer walking lane.
                shaft_neighbor = min(math.hypot(u + dx, v + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))) <= 3.45
                if 3.45 < rho <= 4.3 and shaft_neighbor and phase % 5 == 0:
                    for rise in range(phase, BELL_RISE - 5, TURNS):
                        y = (10 + rise) // 2 + 2
                        g.put(x, y, z, CARVING)
                        g.put(x, y + 1, z, s.SOUL)
        # Lanterns and ironwork on the gallery rim. Leave the arriving flight clear.
        for u, v in ((-8, -3), (-8, 3), (8, -3), (0, -9), (0, 9)):
            x, z = cx + u, cz + v
            phase = stair_phase(u, v, side)
            if 1 <= phase <= BELL_RISE % TURNS + 1:
                continue
            g.put(x, 76, z, CARVING)
            g.put(x, 77, z, s.SOUL)

    loft_y = (10 + LOFT_RISE) // 2
    g.box(21, 23, loft_y - 1, loft_y, 8, 10)[:] = c.WOOD
    g.box(21, 23, loft_y + 1, loft_y + 4, 8, 10)[:] = AIR


def abbey_ridge(g: Abbey) -> None:
    shelves = ((-115, 112, 53, 61), (-154, 164, 47, 63), (-164, 177, 37, 43))
    for z in range(52, 232):
        for x in range(X0 + 1, -84):
            d = min(math.hypot((x - cx) / rx, (z - cz) / rz) for cx, cz, rx, rz in shelves)
            pitch = s.patch(x, -1, z)
            if d + .059 * pitch > 1:
                continue
            h = max(-6, min(5, round(-1.3 + 2 * math.sin(x * .121 + z * .074) + 1.3 * pitch - 2 * (d > .90))))
            col = g.box(x, x, -8, h, z, z)[:, 0, 0]
            empty_summit = col[-1] == AIR
            col[col == AIR] = s.BASALT if pitch > .1 else s.COBBLE
            if empty_summit:
                g.put(x, h, z, r.BLACKSTONE if pitch > -.25 else s.SCULK if z > 162 else s.COBBLE)

    # Narrow basalt needles and sculk seams below the isolated chapel terrace.
    for cx, cz, radius, high in ((-154,91,7,6),(-175,115,9,9),(-180,137,8,10),
                                  (-188,160,8,9),(-180,198,9,11),(-148,210,6,7),(-129,178,6,8),(-126,79,7,8)):
        for z in range(cz - radius, cz + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                d = math.hypot(x - cx, z - cz) / radius + .21 * s.patch(x, 0, z)
                if d >= 1 or g.get(x, -8, z) == AIR:
                    continue
                y = next(h for h in range(7, -9, -1) if g.get(x, h, z) != AIR)
                h = y + max(1, round(high * (1 - d)**1.25))
                g.box(x, x, y + 1, h, z, z)[:] = BASALT if (x + z) % 4 else s.COBBLE
                if d < .52:
                    g.put(x, h + 1, z, s.TEARS if (x - z) % 5 == 0 else r.COBBLE_CAP)


def arcade(g: Abbey, x: int, z: int, tangent: tuple[int, int], half: int, centers: tuple[int, ...], width: int) -> None:
    """Layered voussoirs over each opening; shadowed blocks between the arches form piers."""
    dx, dz = tangent
    nx, nz = dz, dx
    for u in range(-half, half + 1):
        xx, zz = x + u * dx, z + u * dz
        d = min(abs(u - m) for m in centers)
        h = 5 + round(5 * math.sqrt(1 - (d / width)**2)) if d <= width else 0
        for y in range(h + 1, 15):
            if y == h + 1 and h:
                block = CARVING
            elif y in (1, 2, 6, 12, 14):
                block = TRIM
            else:
                block = BASALT if not h and d == width + 1 else BRICK
            for n in (0, 1):
                g.put(xx - n * nx, y, zz - n * nz, block)
        if h and (d <= width - 2 or d % 2 == 0):
            g.put(xx + nx, h + 1, zz + nz, CARVING)
        if not h and d == width + 1:
            for y in range(2, 7):
                g.put(xx + nx, y, zz + nz, CARVING if y in (2, 6) else MORTAR)
            g.put(xx + nx, 7, zz + nz, BRASS)


def cloister(g: Abbey) -> None:
    cx, cz = CLOISTER
    for z in range(cz - 30, cz + 31):
        for x in range(cx - 27, cx + 28):
            u, v = abs(x - cx), abs(z - cz)
            ext = max(u - 26, v - 29)
            if ext > 1:
                continue
            h = u + v
            y = 0
            g.box(x, x, -8, y - 1, z, z)[:] = s.BASALT if ext >= 0 else BRICK
            g.box(x, x, y + 1, 13, z, z)[:] = AIR
            if u < 17 and v < 19:
                block = rosette(x - cx, z - cz, 15) if math.hypot(u, v) <= 15 else SLATE
            else:
                block = TRIM if h % 7 == 0 or u == 22 or v == 24 else BRICK
                if (u == 21 and v % 9 == 4) or (v == 23 and u % 9 == 4):
                    block = s.LUMEN
            g.put(x, y, z, block)

    for sign in (-1, 1):
        arcade(g, cx, cz + sign * 29, (1, 0), 26, (-17, 0, 17), 7)
        arcade(g, cx + sign * 26, cz, (0, 1), 29, (-19, 0, 19), 7)
        arcade(g, cx, cz + sign * 19, (1, 0), 17, (-11, 0, 11), 4)
        arcade(g, cx + sign * 17, cz, (0, 1), 19, (-12, 0, 12), 5)

    for z in range(cz - 30, cz + 31):
        for x in range(cx - 27, cx + 28):
            u, v = abs(x - cx), abs(z - cz)
            d = min(26 - u, 29 - v)
            if d < -1 or d > 10:
                continue
            h = 14 + round(7 * math.sin(math.pi * (d + 1) / 11)**.68)
            if d in (0, 9, 10):
                h = max(h, 15)
            rib = (u if 26 - u > 29 - v else v) % 9 in (0, 1)
            g.box(x, x, h - (3 if rib else 2), h, z, z)[:] = TRIM if d in (-1, 10) else TILE
            if rib:
                g.put(x, h - 3, z, CARVING)
                g.put(x, h + 1, z, STEP if d in (0, 9) else r.ROOF_CAP)
            elif d in (4, 5):
                g.put(x, h, z, VERDIGRIS)
            elif d in (-1, 10):
                g.put(x, h + 1, z, STEP)

    for u in (-24, 24):
        for v in (-27, 27):
            x, z = cx + u, cz + v
            for y in range(0, 24):
                radius = 3.8 if y in (0, 1, 6, 14, 22, 23) else 2.85
                circle(g, x, z, y, radius, CARVING if radius > 3 else BASALT)
                if y in (7, 13, 21):
                    for du, dv in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                        g.put(x + du, y, z + dv, BRASS)
            for y in range(24, 33):
                circle(g, x, z, y, 3.2 * (1 - (y - 24) / 9), VERDIGRIS if y % 3 == 0 else TILE)
            g.put(x, 33, z, s.TEARS)
            g.put(x, 34, z, SLATE_STEP)

    for u in (-25, 25):
        for v in (-18, -8, 8, 18):
            g.box(cx + u, cx + u, 12, 14, cz + v, cz + v)[:] = CARVING
            g.put(cx + u, 11, cz + v, s.SOUL_HANGING)
    for v in (-28, 28):
        for u in (-14, -7, 7, 14):
            g.box(cx + u, cx + u, 12, 14, cz + v, cz + v)[:] = TRIM
            g.put(cx + u, 11, cz + v, s.SOUL_HANGING)

    # The still basin is backlit glass, not a fluid simulation in the schematic.
    circle(g, cx, cz, 1, 7.3, TRIM)
    circle(g, cx, cz, 1, 5.45, s.LUMEN)
    for z in range(cz - 7, cz + 8):
        for x in range(cx - 7, cx + 8):
            dr = math.hypot(x - cx, z - cz)
            if dr <= 5.45:
                g.put(x, 2, z, BLUE if (x - z) % 4 else TEAL)
            elif dr <= 7.3:
                g.put(x, 2, z, STEP if dr > 6.65 else CARVING)
    for y, radius, block in ((2, 2.3, CARVING), (3, 1.5, BASALT), (4, 2.3, TRIM),
                             (5, 1.5, r.AMETHYST), (6, 1., s.TEARS)):
        circle(g, cx, cz, y, radius, block)
    g.put(cx, 7, cz, s.SOUL)


def chapel(g: Abbey) -> None:
    cx, cz = CHAPEL
    rx, rz = 18.5, 22.0

    def radius(u: int, v: int) -> float:
        return math.hypot(u / rx, v / rz)

    def dome(u: int, v: int) -> float:
        q = min(1., radius(u, v) / 1.065)
        return 20.5 + 16.8 * math.sqrt(1 - q*q) + 1.9 * (1 - q)**2

    colors = (BLUE, VIOLET, TEAL, VIOLET, BLUE, c.GLASS['magenta'], TEAL)
    angles = tuple(math.radians(deg) for deg in (-147, -33, 0, 46, 90, 134, 180))
    for z in range(cz - 24, cz + 25):
        for x in range(cx - 20, cx + 21):
            u, v = x - cx, z - cz
            d = radius(u, v)
            if d > 1.075:
                continue
            angle = math.atan2(v / rz, u / rx)
            if d <= 1.04:
                g.box(x, x, -8, 2, z, z)[:] = BRICK if d > .83 else s.BASALT
                g.put(x, 3, z, TRIM if d > .82 else rosette(u, v, 12) if math.hypot(u, v) <= 12 else SLATE)
                g.box(x, x, 4, 20, z, z)[:] = AIR
                if d >= .82:
                    distances = [abs(math.remainder(angle - a, math.tau)) * 19.3 for a in angles]
                    w = min(distances)
                    window = distances.index(w)
                    h = 13 + round(3 * c.pointed(w / 2.7)) if w <= 2.7 else 7
                    for y in range(4, 21):
                        if v < -14 and abs(u) <= 5 and y <= 11 + round(3 * c.pointed(u / 5)):
                            continue
                        if w <= 2.1 and 8 <= y <= h:
                            block = colors[window] if (y + window) % 4 else TEAL
                        elif w <= 3.1 and 7 <= y <= h + 1:
                            block = CARVING
                        elif y in (4, 7, 17, 19, 20):
                            block = TRIM if y != 19 else VERDIGRIS
                        else:
                            block = BASALT if w > 4 and (x + z) % 5 == 3 else BRICK
                        g.put(x, y, z, block)
            hf = dome(u, v)
            y = int(hf)
            h_lower = min(y - 2, *(int(dome(u + dx, v + dz)) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))))
            rib = abs(math.sin(4 * angle)) * math.hypot(u, v) < .72
            block = VERDIGRIS if rib else SLATE if (u + v) % 10 in (0, 1) else TILE
            g.box(x, x, h_lower, y, z, z)[:] = block
            if (hf - y > .43 or rib) and d > .23:
                g.put(x, y + 1, z, STEP if rib else r.ROOF_CAP)

    for degrees in (-160, -112, -68, -20, 26, 66, 113, 157):
        a = math.radians(degrees)
        x, z = cx + round(17.8 * math.cos(a)), cz + round(21.1 * math.sin(a))
        for y in range(3, 19):
            circle(g, x, z, y, 1.75 if y in (3, 4, 6, 17, 18) else 1.05, CARVING if y in (4, 6, 17, 18) else BASALT)
        g.put(x, 19, z, s.TEARS)
        g.put(x, 20, z, STEP)

    # Splayed portal facing the cloister. Ribs merge into the outer shell.
    for u in range(-7, 8):
        v = -round(rz * math.sqrt(1 - (u / rx)**2))
        h = c.arch_top(u, 5, 11, 3) if abs(u) <= 5 else 3
        for y in range(h + 1, 17):
            g.box(cx + u, cx + u, y, y, cz + v - 2, cz + v)[:] = CARVING if y - h in (1, 3) else TRIM
        if abs(u) > 5:
            g.put(cx + u, 7, cz + v - 3, TRIM)
            g.put(cx + u, 8, cz + v - 3, s.SOUL)

    # Eight-lobed lantern cupola caps the shallow stone dome.
    for y in range(39, 49):
        circle(g, cx, cz, y, 5.35 if y not in (39, 40, 47, 48) else 6., TRIM if y % 3 else CARVING, inner=2.9)
        if 41 <= y <= 46:
            for dx, dz in ((4, 0), (0, 4), (-4, 0), (0, -4)):
                g.put(cx + dx, y, cz + dz, VIOLET if y % 4 else TEAL)
                g.put(cx + round(dx * 1.25), y, cz + round(dz * 1.25), VIOLET if y % 4 else TEAL)
    for y in range(49, 59):
        circle(g, cx, cz, y, 5.5 * (1 - (y - 49) / 10)**1.15, TILE if y % 3 else VERDIGRIS)
    g.put(cx, 59, cz, s.TEARS)
    g.put(cx, 60, cz, STEP)

    for z in (cz - 9, cz - 4, cz + 1, cz + 6):
        for side in (-1, 1):
            for a in range(5, 11):
                zz = z + int(a in (5, 10))
                g.put(cx + side * a, 4, zz, c.stairs('dark_oak', 'north') if a not in (5, 10) else c.WOOD_END)
            g.put(cx + side * 10, 5, z + 1, c.slab('dark_oak'))
    for x in range(cx - 10, cx + 11):
        for z in range(cz + 8, cz + 19):
            a = math.hypot((x - cx) / 10.6, (z - cz - 13) / 6.5)
            if a <= 1 and g.get(x, 4, z) == AIR:
                g.put(x, 4, z, STEP if a > .69 else SLATE)
    for y, radius, block in ((5, 3.1, CARVING), (6, 2., BASALT), (7, 3.1, TRIM), (8, 2.05, r.AMETHYST)):
        circle(g, cx, cz + 13, y, radius, block)
    for u, v in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
        g.put(cx + u, 8, cz + 13 + v, s.SOUL)
    g.put(cx, 9, cz + 13, VIOLET)
    for x, z in ((cx - 11, cz - 12), (cx + 11, cz - 12), (cx - 13, cz + 7), (cx + 13, cz + 7)):
        r.pier_lamp(g, x, 3, z)
    for y in range(19, 38):
        if g.get(cx, y, cz) != AIR:
            break
        g.put(cx, y, cz, c.CHAIN)
    crown_lamp(g, cx, cz, 18, 6)


def abbey_walks(g: Abbey) -> None:
    # West transept -> cloister. The roof over the gateway stays in place.
    g.box(-90, -83, -3, 0, 116, 124)[:] = SLATE
    g.box(-90, -83, 1, 5, 117, 123)[:] = AIR
    for x in (-89, -85):
        for z in (118, 122):
            g.put(x, 0, z, s.LUMEN)
    for x in range(CHAPEL[0] - 2, -138):
        center = 120 + round((-139 - x) / 4.9)
        for z in range(center - 3, center + 4):
            g.box(x, x, -3, 0, z, z)[:] = TRIM if z in (center - 3, center, center + 3) else SLATE
            g.box(x, x, 1, 6, z, z)[:] = AIR
            if z in (center - 3, center + 3):
                g.put(x, 1, z, STEP)
            if x % 8 == 0 and z == center + 1:
                g.put(x, 0, z, s.LUMEN)
    for z in range(123, 155):
        h = 2 + sum(z >= stair for stair in (129, 133, 137, 141, 145, 149))
        y = (h - 1) // 2
        cx = CHAPEL[0] + 4 if z < 129 else CHAPEL[0] + max(0, (146 - z) // 5)
        half = 3 if z < 146 else 5
        for x in range(cx - half, cx + half + 1):
            g.box(x, x, -3, y - 1, z, z)[:] = BRICK
            tread = s.LUMEN if z % 7 == 3 and abs(x - cx) == 2 else TRIM if abs(x - cx) >= half - 1 else SLATE
            surface(g, x, z, h, tread, SLATE_STEP)
            g.box(x, x, y + 1, y + 5, z, z)[:] = AIR
            if abs(x - cx) == half and z < 148:
                g.put(x, y + 1, z, STEP)
    for z in (129, 142):
        y = 1 if z == 129 else 2
        cx = CHAPEL[0] + max(0, (146 - z) // 5)
        for x in (cx - 5, cx + 5):
            r.pier_lamp(g, x, y, z)


def chapel_scars(g: Abbey, *, pure_sculk: bool = False) -> None:
    # Local infection colonizes the base of the chapel; the nave and the doorway stay traversable.
    cx, cz = CHAPEL
    curves = (
        ((cx+14,2,cz+16,3.4),(cx+13,5,cz+16,2.7),(cx+11,12,cz+18,2.3),(cx+9,19,cz+21,1.9),
         (cx+5,25,cz+20,1.65),(cx-1,31,cz+17,1.4),(cx-3,36,cz+15,.85)),
        ((cx+9,19,cz+21,1.6),(cx+10,22,cz+24,1.3),(cx+13,26,cz+25,1.11),(cx+17,28,cz+24,.82)),
        ((cx+12,3,cz+16,2.4),(cx+19,3,cz+17,2.4),(cx+25,1,cz+16,2.0),(cx+30,2,cz+12,1.65),
         (cx+33,5,cz+12,1.18),(cx+37,8,cz+12,.84)),
    )
    a, b, d, e = cx - 7, cx + 42, cz + 7, cz + 28
    local_limits = (a, b, -3, 40, d, e)
    field = np.full((44, e - d + 1, b - a + 1), -1., dtype=np.float32)
    for path in curves:
        s.stroke(field, path, limits=local_limits)
    if pure_sculk:
        g.box(*local_limits)[field >= 0] = s.SCULK
        return
    yy, zz, xx = np.where(field >= 0)
    x, y, z = xx + a, yy - 3, zz + d
    switch = .66*np.sin(x*.63 + z*.51 - y*.42) + .47*np.sin(y*.92 + z*.21)
    palette = np.select((switch > .9, switch > .70, switch < -.82, switch < -.47),
                        (s.LUMEN, BLUE, s.TEARS, s.OBSIDIAN), s.SCULK)
    g.blocks[y - Y0, z - Z0, x - X0] = palette


def assemble(*, pure_sculk: bool = False) -> Abbey:
    g = Abbey(pure_sculk=pure_sculk)
    for part in (carved_nave, rounded_choir, helical_stairs, abbey_ridge, cloister, chapel, abbey_walks):
        part(g)
    chapel_scars(g, pure_sculk=pure_sculk)
    for x, z, y, radius in ((0, 28, 37, 4), (0, 62, 37, 4), (0, 96, 37, 4), (0, c.CROSS, 33, 6)):
        crown_lamp(g, x, z, y, radius)
    return g


def repair_growth(g: Abbey, *, stone_fringe: bool = False) -> None:
    """Remove unsupported faces, and optionally keep the surface growth off the sculk itself."""
    blocks = g.blocks
    support = np.array([
        name.endswith('_glass') or (r.could_support_spawn(name, props) and not name.endswith(('_stairs', '_slab')))
        for name, props in c.STATES
    ])
    if stone_fringe:
        support[s.SCULK] = False
    support = support[blocks]
    for state in np.unique(blocks):
        name, properties = c.STATES[state]
        if name not in ('minecraft:sculk_vein', 'minecraft:glow_lichen'):
            continue
        props = dict(properties)
        points = np.where(blocks == state)
        valid = np.zeros(len(points[0]), dtype=np.uint8)
        for i, (face, dy, dz, dx) in enumerate(s.FACES):
            if props[face] == 'true':
                y, z, x = points
                valid |= support[y - dy, z - dz, x - dx].astype(np.uint8) << i
        for mask in np.unique(valid):
            if mask == 0:
                fixed = AIR
            else:
                props.update({face: str(bool(int(mask) & (1 << i))).lower() for i, (face, *_) in enumerate(s.FACES)})
                fixed = c.state(name.removeprefix('minecraft:'), **props)
            keep = valid == mask
            blocks[tuple(coords[keep] for coords in points)] = fixed


def build() -> np.ndarray:
    g = assemble()
    repair_growth(g)
    r.remove_stray_voxels(g)
    r.crypt_spawn_protection(g)
    r.spawn_protection(g)
    return g.blocks


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=OUTPUT)
    p.add_argument('--preview', type=Path, help='thumbnail to embed in the schematic')
    args = p.parse_args()
    c.save(args.output, build(), args.preview, title=TITLE, description=DESCRIPTION)


if __name__ == '__main__':
    main()
