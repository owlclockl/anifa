#!/usr/bin/env python3
"""Detail the Moonspire Abbey and furnish its throne hall and inhabited ward."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from nbtlib import tag as nbt

from . import build_abbey_cathedral as a
from . import build_cathedral as c
from . import build_rift_cathedral as r
from . import build_sculk_cathedral as s


TITLE = 'Аббатство Лунных Шпилей — Лунный трон'
DESCRIPTION = 'Лунный трон, резные арки, чешуйчатый купол и жилой двор с домом, мастерской и оранжереей. Java 26.3.'
OUTPUT = c.OUTPUT.with_stem('moonspire-cathedral-throne')
LODGE = (-114, 38)
FORGE = (-165, 73)
GLASSHOUSE = (-168, 35)
THRONE = (-6, 177)
PLOTS = tuple((GLASSHOUSE[0] + u, GLASSHOUSE[1] + v) for u in (-8, 8) for v in (-7, 7))

AIR = c.AIR
BRICK, TRIM, CARVED, SLATE = a.BRICK, a.TRIM, a.CARVING, a.SLATE
TILE, BASALT, STEP, SLATE_STEP = a.TILE, a.BASALT, a.STEP, a.SLATE_STEP
WOOD, OAK = c.WOOD, c.WOOD_END
TILE_STEP = r.ROOF_CAP
OAK_STEP = c.slab('dark_oak')
WALL_MAT = 'polished_blackstone_brick_wall'
TILE_WALL_MAT = 'deepslate_tile_wall'
FENCE_MAT = 'dark_oak_fence'
CARDINAL = (('north', 0, -1), ('east', 1, 0), ('south', 0, 1), ('west', -1, 0))


def wall(material: str, **arms: str) -> int:
    sides = {d: arms.get(d, 'none') for d, _, _ in CARDINAL}
    opposite = any(sides[d] == sides[e] == 'low' and all(sides[f] == 'none' for f in rest)
                   for d, e, rest in (('east', 'west', ('north', 'south')), ('north', 'south', ('east', 'west'))))
    return c.state(material, **sides, up=str(not opposite).lower(), waterlogged='false')


WALL = wall(WALL_MAT)
TILE_WALL = wall(TILE_WALL_MAT)
FENCE = c.state(FENCE_MAT, **{d: 'false' for d, _, _ in CARDINAL}, waterlogged='false')
COPPER = c.state('waxed_exposed_cut_copper')
PATINA = c.state('waxed_weathered_cut_copper')
VERDIGRIS = s.DARK_TEAL
VELVET = c.state('purple_wool')
LINING = c.state('black_wool')
PURPUR_STEP = c.slab('purpur')
ALTAR_GEM = r.AMETHYST
RUNNER = c.state('purple_carpet')
BED_RUGS = (RUNNER, c.state('gray_carpet'))
RUG_TRIM = c.state('black_carpet')
COMPOSTER = c.state('composter', level='0')
FARMLAND = c.state('farmland', moisture='7')
WATER = c.state('water', level='0')
CROPS = tuple(c.state(name, age='7') for name in ('wheat', 'carrots', 'potatoes'))


def stair(material: str, facing: str, half: str = 'bottom', shape: str = 'straight') -> int:
    return c.state(material + '_stairs', facing=facing, half=half, shape=shape, waterlogged='false')


def direction(dx: int, dz: int) -> str:
    return 'east' if dx > 0 else 'west' if dx < 0 else 'south' if dz > 0 else 'north'


def arch_moulding(p: c.Plane, center: int, width: int, spring: int, rise: int,
                  *, round_arch: bool = False, d: int = 0, bridge_back: bool = False) -> None:
    """Recessed top slabs at the crown, inverted stairs where the arch turns down."""
    for u in range(-width, width + 1):
        ratio = u / width
        arc = math.sqrt(1 - ratio**2) if round_arch else c.pointed(ratio)
        y = spring + round(rise * arc) + 1
        side = 1 if u >= 0 else -1
        turn = direction(side * abs(p.nz), side * abs(p.nx))
        detail = c.slab('polished_blackstone_brick', 'top') if abs(u) <= 1 else stair('polished_blackstone_brick', turn, 'top')
        p.put(center + u, y, d, detail)
        if bridge_back:
            p.put(center + u, y, d - 1, CARVED)
        p.put(center + u, y + 1, d, CARVED if u % 3 == 0 else TRIM)
        if abs(u) % 2 == 0:
            p.put(center + u, y + 2, d, STEP)
    if spring >= 9:
        for side in (-1, 1):
            u = center + side * (width + 1)
            for y in (spring - 2, spring - 1):
                p.put(u, y, d, WALL)
            p.put(u, spring, d, stair('polished_blackstone', direction(-p.nx, -p.nz), 'top'))


def arch_and_rail_details(g: a.Abbey) -> None:
    arch_moulding(c.Plane(g, 0, -7, 0, -1), 0, 7, 17, 11, bridge_back=True)
    arch_moulding(c.Plane(g, 0, 13, 0, 1), 0, 13, 10, 14, round_arch=True, d=2, bridge_back=True)
    arch_moulding(c.Plane(g, r.PX, r.PZ - 5, 0, -1), 0, 9, 22, 8, bridge_back=True)

    cx, cz = a.CHAPEL
    p = c.Plane(g, cx, cz - 23, 0, -1)
    arch_moulding(p, 0, 5, 11, 3, bridge_back=True)
    for side in (-1, 1):
        for y in range(5, 11):
            p.put(side * 6, y, 1, WALL)
        p.put(side * 6, 4, 1, TRIM)
        p.put(side * 6, 11, 1, stair('polished_blackstone', 'south', 'top'))

    cx, cz = a.CLOISTER
    for sign in (-1, 1):
        for p, centers, width in (
            (c.Plane(g, cx, cz + sign * 29, 0, sign), (-17, 0, 17), 7),
            (c.Plane(g, cx + sign * 26, cz, sign, 0), (-19, 0, 19), 7),
            (c.Plane(g, cx, cz + sign * 19, 0, -sign), (-11, 0, 11), 4),
            (c.Plane(g, cx + sign * 17, cz, -sign, 0), (-12, 0, 12), 5),
        ):
            for u in centers:
                arch_moulding(p, u, width, 5, 5, round_arch=True)
                for side in (-1, 1):
                    v = u + side * (width + 1)
                    p.put(v, 1, 1, CARVED)
                    p.put(v, 2, 1, WALL)
                    p.put(v, 3, 1, TILE_WALL)
                    p.put(v, 4, 1, WALL)
                    p.put(v, 5, 1, stair('polished_blackstone', direction(-p.nx, -p.nz), 'top'))
        # Low courtyard balustrades, open on axis in all four directions.
        for u in range(-15, 16):
            if abs(u) >= 4:
                g.put(cx + u, 1, cz + sign * 17, CARVED if abs(u) in (4, 10, 15) else WALL)
        for v in range(-17, 18):
            if abs(v) >= 4:
                g.put(cx + sign * 15, 1, cz + v, CARVED if abs(v) in (4, 11, 17) else WALL)

    # A slender stone parapet replaces the thick solid rim at the rift lookout.
    cx, cz, radius = 72, 183, 8
    for u in range(-radius, radius + 1):
        for v in range(-radius, radius + 1):
            if c.octagon(u, v, radius) and not c.octagon(u, v, radius - 1) and u + v & 1:
                x, z = cx + u, cz + v
                if g.get(x, 3, z) in (BRICK, CARVED) and g.get(x, 4, z) == STEP:
                    g.put(x, 3, z, WALL)
                    g.put(x, 4, z, AIR)


def sculpt_chapel_roof(g: a.Abbey) -> None:
    cx, cz = a.CHAPEL
    roof = {TILE, SLATE, VERDIGRIS}
    for v in range(-23, 24):
        for u in range(-20, 21):
            q = math.hypot(u / 18.5, v / 22) / 1.065
            if not .28 < q <= 1:
                continue
            hf = 20.5 + 16.8 * math.sqrt(1 - q*q) + 1.9 * (1 - q)**2
            y = int(hf)
            x, z = cx + u, cz + v
            block, above = g.get(x, y, z), g.get(x, y + 1, z)
            if block not in roof or above not in (AIR, STEP, TILE_STEP):
                continue  # The invaded face and the lantern are deliberately left intact.
            axis_x = abs(u) / 18.5 >= abs(v) / 22
            outward = direction(u if axis_x else 0, v if not axis_x else 0)
            inward = direction(-u if axis_x else 0, -v if not axis_x else 0)
            theta = math.atan2(v / 22, u / 18.5)
            rib = abs(math.sin(theta * 6)) * math.hypot(u, v) < .75
            if q >= .64 and (rib or y % 2 == 0 or q > .94):
                g.put(x, y, z, stair('polished_blackstone_brick' if rib else 'deepslate_tile', inward))
                if above != AIR:
                    g.put(x, y + 1, z, AIR)
            elif hf - y < .58:
                g.put(x, y, z, STEP if rib else TILE_STEP)
                if above != AIR:
                    g.put(x, y + 1, z, AIR)
            if rib and .39 < q < .86:
                g.put(x, y + 1, z, PATINA if int(q * 18) % 4 == 0 else STEP)
            if .94 < q < .996:
                # Inverted corbels form a narrow shadow line underneath the eaves.
                yb = max(20, y - 3)
                if g.get(x, yb + 1, z) not in (AIR, s.SCULK):
                    g.put(x, yb, z, stair('polished_blackstone', outward, 'top'))
    for u, v in ((5, 0), (4, 3), (0, 5), (-4, 3), (-5, 0), (-4, -3), (0, -5), (4, -3)):
        for y, block in ((48, TRIM), (49, WALL), (50, TILE_WALL), (51, STEP)):
            g.put(cx + u, y, cz + v, block)
    for y in range(51, 59):
        edge = 5.5 * (1 - (y - 49) / 10)**1.15
        for u in range(-5, 6):
            for v in range(-5, 6):
                rho = math.hypot(u, v)
                if edge - .8 < rho <= edge and g.get(cx+u, y+1, cz+v) == AIR and g.get(cx+u, y, cz+v) in roof:
                    facing = direction(-u if abs(u) >= abs(v) else 0, -v if abs(v) > abs(u) else 0)
                    g.put(cx + u, y, cz + v, stair('deepslate_tile', facing) if rho > 1 else TILE_STEP)


def moon_throne(g: a.Abbey) -> None:
    cx, cz = THRONE
    # Reuse the rounded choir steps. Only the old altar table is replaced; the scar stays open.
    g.box(cx - 4, cx + 4, 8, 14, cz - 3, cz + 3)[:] = AIR
    for v in range(-4, 5):
        for u in range(-7, 8):
            q = math.hypot(u / 7.2, v / 4.4)
            if q > 1:
                continue
            x, z = cx + u, cz + v
            g.put(x, 7, z, SLATE)
            if v == -4:
                block = stair('polished_blackstone_brick', 'south')
            else:
                block = STEP if q > .80 else CARVED if (abs(u) + abs(v)) % 3 else TRIM
            g.put(x, 8, z, block)
    # Footstool, velvet seat and sweeping arm rests.
    g.box(cx - 2, cx + 2, 9, 9, cz - 2, cz)[:] = PURPUR_STEP
    for u in (-3, 3):
        sign = 1 if u > 0 else -1
        x = cx + u
        g.box(x, x, 9, 10, cz - 2, cz + 1)[:] = CARVED
        g.put(x, 11, cz - 2, stair('polished_blackstone', 'south'))
        g.put(x, 11, cz - 1, COPPER)
        g.put(x, 11, cz, stair('polished_blackstone', 'south', 'top'))
        g.put(x, 10, cz - 3, stair('polished_blackstone_brick', 'south', 'top', 'outer_left' if sign < 0 else 'outer_right'))
        g.put(x, 9, cz - 3, CARVED)
        g.put(x + sign, 9, cz - 1, STEP)
    for u in range(-4, 5):
        h = c.arch_top(u, 4, 16, 6)
        for y in range(9, h + 1):
            if y == h and abs(u) > 1:
                g.put(cx + u, y, cz + 2, stair('polished_blackstone_brick', 'east' if u < 0 else 'west'))
            else:
                g.put(cx + u, y, cz + 2, CARVED if abs(u) == 4 or y == 9 else TRIM)
            if 10 <= y < h - 1:
                # Tapered upholstery inset, with a lit crescent stitched into the back.
                q = math.hypot(u / 2.9, (y - 16) / 3.8)
                cut = math.hypot((u - .9) / 2.35, (y - 16.5) / 3.5)
                crest = q <= 1.02 and cut >= .92
                mat = COPPER if crest else VELVET if abs(u) <= 2 and y < h - 3 else LINING if abs(u) < 4 else CARVED
                if abs(u) == 3 and y in (12, 17, 19):
                    mat = ALTAR_GEM
                g.put(cx + u, y, cz + 1, mat)
    g.put(cx, 19, cz + 1, ALTAR_GEM)
    g.put(cx, 20, cz + 1, c.GLASS['purple'])
    g.put(cx, 21, cz + 1, s.LUMEN)
    g.put(cx, 22, cz + 2, VERDIGRIS)
    g.put(cx, 23, cz + 2, WALL)
    g.put(cx, 24, cz + 2, TILE_WALL)
    g.put(cx, 25, cz + 2, STEP)

    for side in (-1, 1):
        x, z = cx + side * 5, cz + 2
        for y in range(8, 20):
            g.put(x, y, z, CARVED if y in (8, 9, 12, 18, 19) else BASALT if y <= 16 else WALL)
        g.put(x, 20, z, s.TEARS)
        g.put(x, 21, z, WALL)
        g.put(x, 22, z, STEP)
        for u, h in ((6, 13), (7, 15)):
            xx = cx + side * u
            for y in range(h - 2, h + 2):
                g.put(xx, y, z, TILE_WALL if y >= h else CARVED)
            g.put(xx, h + 2, z, STEP)
        g.put(x + side, 12, z, stair('polished_blackstone_brick', 'east' if side < 0 else 'west', 'top'))
        g.put(x + side * 2, 13, z, CARVED)
        # Cold sconces mirror the sculk glow without obscuring the dark throne.
        xx = cx + side * 5
        g.put(xx, 10, cz - 2, CARVED)
        g.put(xx, 11, cz - 2, s.SOUL)
        g.put(xx, 9, cz - 2, WALL)
        g.put(xx, 8, cz - 2, CARVED)


def inhabited_ridge(g: a.Abbey) -> None:
    shelves = ((-129, 56, 66, 49), (-164, 54, 33, 49), (-114, 85, 48, 38))
    for z in range(5, 111):
        for x in range(-202, -81):
            edge = min(math.hypot((x - cx) / rx, (z - cz) / rz) for cx, cz, rx, rz in shelves)
            p = s.patch(x, -1, z)
            if edge + .06 * p > 1:
                continue
            y = max(-6, min(3, round(-1 + 1.9 * math.sin(z * .104 + x * .054) + 1.1 * p - 2 * (edge > .94))))
            rock = g.box(x, x, -8, y, z, z)[:, 0, 0]
            empty = rock[-1] == AIR
            rock[rock == AIR] = s.BASALT if p > .09 else s.COBBLE
            if empty:
                g.put(x, y, z, r.BLACKSTONE if p > -.32 else s.COBBLE)


def terrace(g: a.Abbey, cx: int, cz: int, hx: int, hz: int) -> None:
    for z in range(cz - hz - 1, cz + hz + 2):
        for x in range(cx - hx - 1, cx + hx + 2):
            edge = abs(x - cx) >= hx or abs(z - cz) >= hz
            g.box(x, x, -8, -1, z, z)[:] = s.BASALT if edge else BRICK
            g.box(x, x, 1, 14, z, z)[:] = AIR
            light = (x - cx + 2) % 6 == 0 and (z - cz + 2) % 6 == 0 and not edge
            block = c.LIGHT if light else TRIM if edge or (x - cx) % 7 == 0 else SLATE
            g.put(x, 0, z, block)


def doors(g: a.Abbey, x: int, z: int, facing: str) -> None:
    dz = int(facing in ('east', 'west'))
    dx = 1 - dz
    hinges = ('right', 'left') if facing in ('south', 'west') else ('left', 'right')
    for u, hinge in enumerate(hinges):
        for half, y in (('lower', 1), ('upper', 2)):
            block = c.state('dark_oak_door', facing=facing, half=half, hinge=hinge, open='false', powered='false')
            g.put(x + dx * u, y, z + dz * u, block)


def roof_height(u: int, half: int, base: int, rise: int) -> int:
    return base + round(rise * max(0., 1 - abs(u) / (half + 1))**.78)


def shingled_gable(g: a.Abbey, cx: int, cz: int, hx: int, hz: int, base: int, rise: int) -> None:
    """A swept roof with half-height shingles, butt-end stairs and a scalloped eave."""
    for u in range(-hx - 1, hx + 2):
        y = roof_height(u, hx, base, rise)
        inner = roof_height(u - (1 if u > 0 else -1), hx, base, rise)
        lower = min(y - 1, roof_height(u - 1, hx, base, rise), roof_height(u + 1, hx, base, rise))
        for v in range(-hz - 1, hz + 2):
            x, z = cx + u, cz + v
            g.box(x, x, lower, y - 1, z, z)[:] = TILE if abs(v) < hz else BRICK
            if v in (-hz - 1, hz + 1) or abs(u) == hx + 1:
                mat = stair('polished_blackstone_brick', 'east' if u < 0 else 'west') if inner > y else STEP
            elif abs(u) <= 1:
                mat = VERDIGRIS if (v + hz) % 4 else PATINA
            elif inner > y and (abs(u) > hx // 2 or v % 4 != 1):
                mat = stair('deepslate_tile', 'east' if u < 0 else 'west')
            else:
                mat = TILE_STEP
            g.put(x, y, z, mat)
            if abs(u) in (hx - 1, hx + 1) and v % 4 == 0:
                g.put(x, lower - 1, z, stair('polished_blackstone', 'east' if u < 0 else 'west', 'top'))
        for sign in (-1, 1):
            for h in range(base - 2, y - 1):
                g.put(cx + u, h, cz + sign * hz, TRIM if (h + abs(u)) % 7 == 0 else BRICK)
    for v in (-hz - 1, hz + 1):
        y = roof_height(0, hx, base, rise)
        g.put(cx, y + 1, cz + v, WALL)
        g.put(cx, y + 2, cz + v, s.TEARS)
        g.put(cx, y + 3, cz + v, STEP)


def loft_dormers(g: a.Abbey, cx: int, cz: int) -> None:
    """Four glazed wall dormers break up the lodge's eaves without blocking its loft."""
    for side in (-1, 1):
        face = direction(side, 0)
        for offset in (-9, 9):
            z = cz + offset
            for v in range(-3, 4):
                h = c.arch_top(v, 3, 21, 3)
                for u in range(12, 20):
                    x = cx + side * u
                    if u <= 18:
                        g.box(x, x, 18, h - 1, z + v, z + v)[:] = AIR if abs(v) < 2 else BRICK
                    g.put(x, h, z + v, stair('deepslate_tile', 'south' if v < 0 else 'north') if v else TILE_STEP)
                    g.put(x, h - 1, z + v, SLATE)
                x = cx + side * 18
                for y in range(15, h - 1):
                    if 17 <= y <= 20 and abs(v) <= 1:
                        mat = c.GLASS['light_blue'] if y % 3 else c.GLASS['purple']
                    else:
                        mat = CARVED if y in (16, 21) else BASALT if abs(v) >= 2 else WOOD
                    g.put(x, y, z + v, mat)
                if abs(v) <= 2:
                    g.put(cx + side * 19, 16, z + v, stair('polished_blackstone', direction(-side, 0), 'top'))
                    g.put(cx + side * 19, 17, z + v, TILE_STEP)
            for v in (-3, 3):
                g.put(cx + side * 19, 17, z + v, WALL)
                g.put(cx + side * 19, 18, z + v, WALL)
                g.put(cx + side * 19, 19, z + v, stair('polished_blackstone', face, 'top'))


def fenestrated_shell(g: a.Abbey, cx: int, cz: int, hx: int, hz: int, top: int, *, two_storeys: bool) -> None:
    for v in range(-hz, hz + 1):
        for u in range(-hx, hx + 1):
            if abs(u) != hx and abs(v) != hz:
                continue
            corner = abs(u) == hx and abs(v) == hz
            tangent = v if abs(u) == hx else u
            window = abs(tangent) > 3 and (abs(tangent) + 2) % 8 <= 2 and not corner
            for y in range(1, top + 1):
                glazing = window and (y in (3, 4, 5) or two_storeys and y in (10, 11, 12))
                if glazing:
                    block = c.GLASS['light_blue'] if y in (4, 11) else c.GLASS['purple']
                elif corner or tangent % 8 == 0:
                    block = CARVED if y in (1, 6, 8, top) else BASALT
                elif y in (1, 6, top) or two_storeys and y in (7, 8):
                    block = TRIM
                else:
                    block = WOOD if two_storeys and y >= 9 else BRICK if (u + v + y) % 6 else SLATE
                g.put(cx + u, y, cz + v, block)
            if window:
                dx = (1 if u > 0 else -1) if abs(u) == hx else 0
                dz = (1 if v > 0 else -1) if abs(v) == hz else 0
                for y in (2, 9) if two_storeys else (2,):
                    facing = direction(-dx, -dz)
                    g.put(cx + u + dx, y, cz + v + dz, stair('polished_blackstone_brick', facing, 'top'))
                    g.put(cx + u + dx, y + 4, cz + v + dz, STEP)


def bed(g: a.Abbey, x: int, z: int, side: int, color: str) -> None:
    facing = 'east' if side > 0 else 'west'
    for xx, part in ((x, 'foot'), (x + side, 'head')):
        g.put(xx, 9, z, c.state(color + '_bed', facing=facing, part=part, occupied='false'))


def hearth_wall(g: a.Abbey, cx: int, cz: int, hx: int, hz: int, *, floor: int) -> None:
    for side in (-1, 1):
        x = cx + side * (hx - 1)
        for v in (-hz + 3, 0, hz - 3):
            g.put(x, floor + 1, cz + v, stair('polished_blackstone', 'west' if side < 0 else 'east', 'top'))
            g.put(x, floor + 2, cz + v, TRIM)
            g.put(x, floor + 3, cz + v, c.LANTERN)


def lodge(g: a.Abbey) -> None:
    cx, cz = LODGE
    hx, hz = 18, 17
    terrace(g, cx, cz, hx, hz)
    fenestrated_shell(g, cx, cz, hx, hz, 13, two_storeys=True)
    shingled_gable(g, cx, cz, hx, hz, 15, 11)
    loft_dormers(g, cx, cz)
    doors(g, cx, cz + hz, 'south')
    arch_moulding(c.Plane(g, cx, cz + hz + 1, 0, 1), 0, 3, 4, 3)

    for z in range(cz - hz + 1, cz + hz):
        for x in range(cx - hx + 1, cx + hx):
            glow = (x - cx + 1) % 6 == 0 and (z - cz) % 6 == 0
            g.put(x, 8, z, c.LIGHT if glow else WOOD if (x - cx) % 8 else TRIM)
    for k in range(1, 9):
        z = cz + 9 - k
        for x in range(cx + 4, cx + 8):
            g.put(x, k - 1, z, OAK)
            g.put(x, k, z, stair('dark_oak', 'north'))
            g.box(x, x, k + 1, k + 3, z, z)[:] = AIR
    for u in (3, 8):
        for v in range(1, 9):
            g.put(cx + u, 9, cz + v, FENCE)
        g.put(cx + u, 10, cz + 8, STEP)

    # Ground level: kitchen, dining, general-purpose storage.
    for i, name in enumerate(('smoker', 'furnace', 'furnace')):
        g.put(cx - 12 + 2 * i, 1, cz - 13, c.state(name, facing='south', lit='false'))
    g.put(cx - 5, 1, cz - 13, c.state('crafting_table'))
    for u in (-15, -14, -13, -12, 10, 12, 14):
        g.put(cx + u, 1, cz + 14, c.state('barrel', facing='north', open='false'))
    g.put(cx - 11, 1, cz + 14, c.state('chest', facing='north', type='single', waterlogged='false'))
    for v in (-6, -5, -4, -3, -2, -1, 0, 1):
        g.put(cx - 7, 1, cz + v, FENCE)
        g.put(cx - 7, 2, cz + v, OAK_STEP)
        g.put(cx - 9, 1, cz + v, stair('dark_oak', 'west'))
        g.put(cx - 5, 1, cz + v, stair('dark_oak', 'east'))
    hearth_wall(g, cx, cz, hx, hz, floor=0)

    for v in range(-13, 14):
        for u in range(-2, 3):
            if g.get(cx + u, 8, cz + v) != c.LIGHT:
                g.put(cx + u, 9, cz + v, RUG_TRIM if abs(u) == 2 or abs(v) == 13 else RUNNER)
    for v in (-10, 0, 10):
        for side, rug, color in zip((-1, 1), BED_RUGS, ('purple', 'gray')):
            for u in range(10, 15):
                for w in range(-1, 2):
                    x, z = cx + side * u, cz + v + w
                    if g.get(x, 8, z) != c.LIGHT:
                        g.put(x, 9, z, rug)
            bed(g, cx + side * 12, cz + v, side, color)
            g.put(cx + side * 14, 9, cz + v + 2, c.state('barrel', facing='up', open='false'))
            g.put(cx + side * 15, 9, cz + v + 1, OAK)
            g.put(cx + side * 15, 10, cz + v + 1, c.LANTERN)
            g.put(cx + side * 14, 8, cz + v - 2, c.LIGHT)
    hearth_wall(g, cx, cz, hx, hz, floor=8)
    # Low canopy partitions between sleeping bays, never across the corridor.
    for v in (-6, 5):
        for side in (-1, 1):
            for u in range(11, 17):
                g.put(cx + side * u, 9, cz + v, FENCE)
                if u > 13:
                    g.put(cx + side * u, 10, cz + v, OAK_STEP)


def workshop(g: a.Abbey) -> None:
    cx, cz = FORGE
    hx, hz = 14, 13
    terrace(g, cx, cz, hx, hz)
    fenestrated_shell(g, cx, cz, hx, hz, 9, two_storeys=False)
    shingled_gable(g, cx, cz, hx, hz, 11, 9)
    doors(g, cx + hx, cz, 'east')
    arch_moulding(c.Plane(g, cx + hx + 1, cz, 1, 0), 0, 3, 4, 3)
    for side in (-1, 1):
        x, z = cx + side * 9, cz - 9
        for y in range(10, 24):
            block = CARVED if y in (10, 16, 22) else SLATE
            g.box(x - 1, x + 1, y, y, z - 1, z + 1)[:] = block
        g.put(x, 24, z, WALL)
        g.put(x, 25, z, TILE_STEP)
    for u, name in ((-10, 'furnace'), (-8, 'blast_furnace'), (-6, 'blast_furnace'), (-3, 'smoker')):
        g.put(cx + u, 1, cz - 9, c.state(name, lit='false', facing='south'))
        g.put(cx + u, 0, cz - 8, c.LIGHT)
    for u, block in ((1, c.state('crafting_table')), (3, c.state('smithing_table')),
                     (5, c.state('stonecutter', facing='south')), (7, c.state('anvil', facing='east')),
                     (9, c.state('grindstone', face='floor', facing='south'))):
        g.put(cx + u, 1, cz - 9, block)
    for v in (5, 7, 9):
        g.put(cx + 11, 1, cz + v, c.state('chest', facing='west', type='single', waterlogged='false'))
        g.put(cx + 12, 1, cz + v, c.state('barrel', facing='west', open='false'))
    hearth_wall(g, cx, cz, hx, hz, floor=0)

    # Fifteen bookshelves with a clear inner ring: a vanilla level-30 enchanting setup.
    x, z = cx - 7, cz + 7
    g.put(x, 1, z, c.state('enchanting_table'))
    for v in range(-2, 3):
        for u in range(-2, 3):
            if max(abs(u), abs(v)) == 2 and (u, v) != (0, -2):
                g.put(x + u, 1, z + v, c.state('bookshelf'))
            elif (u, v) != (0, 0):
                g.put(x + u, 0, z + v, c.LIGHT if not u or not v else SLATE)
                g.put(x + u, 1, z + v, AIR)


def glasshouse(g: a.Abbey) -> None:
    cx, cz = GLASSHOUSE
    hx, hz = 17, 14
    terrace(g, cx, cz, hx, hz)
    clear = c.state('glass')
    for v in range(-hz - 1, hz + 2):
        for u in range(-hx - 1, hx + 2):
            x, z = cx + u, cz + v
            q = abs(u) / (hx + 1)
            roof = 5 + round(9 * math.sqrt(max(0, 1 - q*q)))
            edge = abs(v) >= hz
            rib = v % 5 == 0 or edge
            prev = 5 + round(9 * math.sqrt(max(0, 1 - ((abs(u) + 1) / (hx + 1))**2)))
            lower = min(roof, prev)
            sheet = r.TEAL_GLASS if (abs(u) in (5, 11, 14, 16)) else clear
            for y in range(lower, roof + 1):
                block = PATINA if rib else sheet
                if rib and y == roof and abs(u) > 5:
                    block = stair('deepslate_tile', 'west' if u > 0 else 'east')
                g.put(x, y, z, block)
            if rib and abs(u) <= 5:
                g.put(x, roof + 1, z, TILE_STEP)
            if abs(u) == hx and abs(v) <= hz or edge and abs(u) <= hx:
                for y in range(1, roof if edge else 6):
                    spine = v % 5 == 0 if not edge else u % 4 == 0
                    block = CARVED if y == 1 else TRIM if spine or y == 5 else sheet
                    g.put(x, y, z, block)
    doors(g, cx + hx, cz, 'east')
    arch_moulding(c.Plane(g, cx + hx + 1, cz, 1, 0), 0, 3, 3, 3, round_arch=True, bridge_back=True)
    # Four fully contained water sources. Nearby buried light stays sufficient at night.
    for n, (x, z) in enumerate(PLOTS):
        for v in range(-3, 4):
            for u in range(-3, 4):
                if abs(u) == abs(v) == 3:
                    g.put(x + u, 0, z + v, c.LIGHT)
                elif (u, v) == (0, 0):
                    g.put(x, 0, z, WATER)
                    g.put(x, 1, z, s.LUMEN)  # a cover over the water, not a floating lamp
                else:
                    g.put(x + u, 0, z + v, FARMLAND)
                    g.put(x + u, 1, z + v, CROPS[n % len(CROPS)])
    for u in (-14, 14):
        for v in (-10, 10):
            g.put(cx + u, 0, cz + v, c.LIGHT)
            g.put(cx + u, 1, cz + v, c.state('barrel', facing='up', open='false'))
        g.put(cx + u, 1, cz, COMPOSTER)


def yard_walks(g: a.Abbey) -> None:
    cx, _ = a.CLOISTER
    paving: dict[tuple[int, int], int] = {}
    for z in range(56, 92):
        w = 5 if z not in range(63, 82) else 7
        for u in range(-w, w + 1):
            paving[cx + u, z] = TRIM if abs(u) == w else SLATE
            if z % 6 == 0 and abs(u) == 2:
                paving[cx + u, z] = s.LUMEN
    for x in range(FORGE[0] + 15, cx):
        z = FORGE[1] + ((x + 150) // 12)
        for v in range(-3, 4):
            paving[x, z + v] = s.LUMEN if x % 8 == 0 and abs(v) == 2 else TRIM if abs(v) == 3 else SLATE
    for z in range(GLASSHOUSE[1], 75):
        for x in range(-146, -139):
            paving[x, z] = TRIM if x in (-146, -140) else SLATE
    for x in range(GLASSHOUSE[0] + 18, -140):
        for z in range(GLASSHOUSE[1] - 2, GLASSHOUSE[1] + 4):
            paving[x, z] = SLATE
    for (x, z), block in paving.items():
        g.box(x, x, -8, -1, z, z)[:] = BRICK
        g.put(x, 0, z, block)
        g.box(x, x, 1, 5, z, z)[:] = AIR

    for dx in (-1, 1):
        for z in range(59, 88):
            if 68 <= z <= 80:
                continue
            x = cx + dx * 6
            g.box(x, x, -8, -1, z, z)[:] = BRICK
            g.put(x, 0, z, TRIM)
            g.put(x, 1, z, CARVED if z % 7 == 0 else WALL)
        for z in (62, 83):
            r.pier_lamp(g, cx + dx * 9, 0, z)
    for z in (41, 51, 61):
        r.pier_lamp(g, -138, 0, z)
        if z == 61:
            r.pier_lamp(g, -148, 0, z)
    # Small fenced service court; an operable gate opens onto the north-south work path.
    g.box(-184, -147, -8, -1, 51, 55)[:] = s.BASALT
    g.box(-184, -147, 0, 0, 51, 55)[:] = SLATE
    g.box(-184, -147, 1, 3, 51, 55)[:] = AIR
    for x in range(-184, -153):
        for z in (51, 55):
            g.put(x, 0, z, SLATE)
            g.put(x, 1, z, FENCE)
    for z in range(52, 55):
        for x in (-184, -153):
            g.put(x, 0, z, SLATE)
            g.put(x, 1, z, FENCE)
    g.put(-153, 1, 53, c.state('dark_oak_fence_gate', facing='east', in_wall='false', open='false', powered='false'))
    for x in (-181, -170, -159):
        g.put(x, 0, 53, c.LIGHT)
        for z in (52, 54):
            g.put(x, 1, z, OAK_STEP)


def connect_railings(g: a.Abbey) -> None:
    """Encode connected arms rather than leaving columns of default, disconnected wall posts."""
    rail_materials = {f'minecraft:{name}' for name in (WALL_MAT, TILE_WALL_MAT, FENCE_MAT)}
    states = [i for i, (name, _) in enumerate(c.STATES) if name in rail_materials]

    blocks = g.blocks

    def solid_face(name: str, props: tuple, face: str) -> bool:
        if name.endswith('_slab'):
            return dict(props)['type'] in ('double', 'bottom') if face == 'down' else dict(props)['type'] == 'double'
        if name.endswith('_stairs'):
            data = dict(props)
            return data['half'] == 'bottom' if face == 'down' else data['shape'] == 'straight' and data['facing'] == face
        return r.could_support_spawn(name, props) and name != 'minecraft:farmland'

    for y, z, x in zip(*np.where(np.isin(blocks, states))):
        name = c.STATES[blocks[y, z, x]][0].removeprefix('minecraft:')
        fence = name == FENCE_MAT
        tall = not fence and solid_face(*c.STATES[blocks[y + 1, z, x]], 'down')
        arms = {}
        for d, dx, dz in CARDINAL:
            neighbor, props = c.STATES[blocks[y, z + dz, x + dx]]
            if neighbor.endswith('_fence_gate'):
                joins = (dict(props)['facing'] in ('north', 'south')) == bool(dx)
            else:
                connects_to = ('_fence',) if fence else ('_wall', ':iron_bars')
                joins = neighbor.endswith(connects_to) or solid_face(neighbor, props, direction(-dx, -dz))
            if fence:
                arms[d] = 'true' if joins else 'false'
            else:
                arms[d] = ('tall' if tall else 'low') if joins else 'none'
        blocks[y, z, x] = c.state(name, **arms, waterlogged='false') if fence else wall(name, **arms)


BLOCK_ENTITY_IDS = {
    'purple_bed': 'bed', 'gray_bed': 'bed', 'barrel': 'barrel', 'chest': 'chest', 'furnace': 'furnace',
    'blast_furnace': 'blast_furnace', 'smoker': 'smoker', 'enchanting_table': 'enchanting_table',
}
EMPTY_INVENTORIES = frozenset({'barrel', 'chest', 'furnace', 'blast_furnace', 'smoker'})


def furnishing_data(blocks: np.ndarray) -> dict[tuple[int, int, int], nbt.Compound]:
    kind_for_state = {i: BLOCK_ENTITY_IDS[name.removeprefix('minecraft:')] for i, (name, _) in enumerate(c.STATES)
                      if name.removeprefix('minecraft:') in BLOCK_ENTITY_IDS}
    result = {}
    for y, z, x in zip(*np.where(np.isin(blocks, list(kind_for_state)))):
        kind = kind_for_state[blocks[y, z, x]]
        tag = nbt.Compound(id=nbt.String(f'minecraft:{kind}'))
        if kind in EMPTY_INVENTORIES:
            tag['Items'] = nbt.List[nbt.Compound]()
        result[int(x), int(y), int(z)] = tag
    return result


def assemble(*, pure_sculk: bool = False) -> a.Abbey:
    """Reuse the complete occupied precinct before adding edition-specific spawn protection."""
    g = a.assemble(pure_sculk=pure_sculk)
    for part in (arch_and_rail_details, sculpt_chapel_roof, moon_throne, inhabited_ridge,
                 lodge, workshop, glasshouse, yard_walks):
        part(g)
    return g


def build() -> np.ndarray:
    g = assemble()
    a.repair_growth(g)
    r.remove_stray_voxels(g)
    r.crypt_spawn_protection(g)
    r.spawn_protection(g)
    connect_railings(g)
    return g.blocks


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=OUTPUT)
    p.add_argument('--preview', type=Path, help='thumbnail to embed in the schematic')
    args = p.parse_args()
    blocks = build()
    c.save(args.output, blocks, args.preview, title=TITLE, description=DESCRIPTION, block_entities=furnishing_data(blocks))


if __name__ == '__main__':
    main()
