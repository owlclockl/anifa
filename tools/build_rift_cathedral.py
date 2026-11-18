#!/usr/bin/env python3
"""Build the dark Moonspire precinct, with an unlit Nether gate and spawn protection."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from . import build_cathedral as c
from . import build_sculk_cathedral as s


TITLE = f'{c.TITLE} — Врата разлома'
DESCRIPTION = 'Тёмный собор, скалковый овраг и готические врата в Незер. Крипта, крыши и двор защищены от обычного спавна. Java 26.3.'
OUTPUT = c.OUTPUT.with_stem('moonspire-cathedral-rift')
X0, X1, Y0, Y1, Z0, Z1 = -142, 142, -14, 166, -73, 281
SHAPE = (Y1 - Y0 + 1, Z1 - Z0 + 1, X1 - X0 + 1)
PX, PZ, PBASE = 97, 223, 4
PWIDTH, PHEIGHT = 13, 18  # clear vanilla portal opening
PEND = PBASE + PHEIGHT + 1
MIN_LIGHT = 3

AIR = c.AIR
BLACKSTONE = c.state('blackstone')
BLACK_BRICK = c.state('polished_blackstone_bricks')
BLACK_TRIM = c.state('polished_blackstone')
BLACK_CHISELED = c.state('chiseled_polished_blackstone')
SLATE_BRICK = c.state('deepslate_bricks')
BASALT_COLUMN = c.state('polished_basalt', axis='y')
DARK_STEP = c.slab('polished_blackstone_brick')
COBBLE_CAP = c.slab('cobbled_deepslate')
ROOF_CAP = c.slab('deepslate_tile')
DARK_CARPET = c.state('black_carpet')
RUIN_CARPET = c.state('gray_carpet')
AMETHYST = c.state('amethyst_block')
VIOLET = c.state('purple_terracotta')
TEAL_GLASS = c.GLASS['cyan']
BONE = s.BONE
LICHEN = c.state('glow_lichen', down='true', up='false', north='false', south='false', east='false', west='false', waterlogged='false')


class Valley(s.DeepGrid):
    limits = (X0, X1, Y0, Y1, Z0, Z1)

    def __init__(self) -> None:
        self.blocks = np.zeros(SHAPE, dtype=np.int16)
        self.box(s.X0, s.X1, s.Y0, s.Y1, s.Z0, s.Z1)[:] = s.build()


def darken(g: Valley) -> None:
    # Keep mineral highlights and cool glass readable against an overall blackstone palette.
    mapping = dict(c.COLORWAYS['dark'].materials)
    mapping.update({
        'waxed_oxidized_cut_copper': 'dark_prismarine',
        'waxed_weathered_cut_copper': 'waxed_weathered_cut_copper',
        'waxed_exposed_cut_copper': 'waxed_exposed_cut_copper',
        'polished_blackstone_bricks': 'blackstone',
        'blue_stained_glass': 'cyan_stained_glass',
        'light_blue_stained_glass': 'light_blue_stained_glass',
        'cyan_stained_glass': 'cyan_stained_glass',
        'purple_stained_glass': 'purple_stained_glass',
        'red_stained_glass': 'purple_stained_glass',
        'orange_stained_glass': 'orange_stained_glass',
        'dark_oak_planks': 'dark_oak_planks',
        'dark_oak_stairs': 'dark_oak_stairs',
        'dark_oak_slab': 'dark_oak_slab',
        'stripped_dark_oak_log': 'stripped_dark_oak_log',
        'red_carpet': 'purple_carpet',
        'gold_block': 'waxed_exposed_cut_copper',
        'calcite': 'polished_tuff',
    })
    before = tuple(c.STATES)
    transform = np.array([c.state(mapping.get(name.removeprefix('minecraft:'), name.removeprefix('minecraft:')), **dict(props))
                          for name, props in before], dtype=np.int16)
    g.blocks[:] = transform[g.blocks]


def ground_line(x: int) -> float:
    return 180 + .57 * (x - 44) + 5.7 * math.sin((x - 48) * .115)


def landform(g: Valley) -> np.ndarray:
    # The footprint is a low ridge with two broken shelves, not a rectangular slab.
    height = np.full(SHAPE[1:], Y0, dtype=np.int8)
    fixed = np.any(g.box(X0, X1, 0, 4, Z0, Z1), axis=0)
    ellipses = ((0, 9, 74, 76), (-39, 109, 78, 142), (48, 139, 82, 126), (92, 215, 43, 46), (3, 218, 80, 52))
    for z in range(Z0, Z1 + 1):
        for x in range(X0, X1 + 1):
            za, xa = z - Z0, x - X0
            r = min(math.hypot((x - a) / w, (z - b) / l) for a, b, w, l in ellipses)
            edge = r + .048 * math.sin(x * .146 + z * .129) + .028 * math.cos(z * .273 - x * .175)
            if edge >= 1 or (-35 <= x <= 39 and 145 <= z <= 205):
                continue
            if fixed[za, xa]:
                # Tie the new terrain into the foundations without backfilling the crypt.
                column = g.box(x, x, -8, -1, z, z)
                column[column == AIR] = s.COBBLE
                continue
            w = s.patch(x, -1, z)
            h = round(-.8 + 1.7 * math.sin(.050*x + .027*z) + 1.75 * math.cos(.073*z - .030*x) + 1.25*w)
            west = abs(x + 79 + 13 * math.sin(z * .027))
            if west < 17 and 31 < z < 233:
                h += round((1 - west/17) * 6.2 * (.60 + .40 * math.cos(z * .078)))
            split = abs(z - ground_line(x))
            seam = z - ground_line(x) - 1.4 * math.sin(x * .34)
            chasm = x > 43 and z > 165 and split < 8.1 + 1.3 * w
            if chasm:
                bank = max(0., (split - 2.9) / 5.2)
                h = min(h, -7 + round(5 * bank))
            h = max(-7, min(8, h))
            if edge > .94 and not chasm:
                h = max(-7, h - 2)
            height[za, xa] = h
            stack = g.box(x, x, -8, h, z, z)[:, 0, 0]
            stack[stack == AIR] = s.BASALT if w > .2 else s.COBBLE
            near = 37 < x < 133 and 136 < z < 254 and (z > 156 or x < 78)
            crust = near and (split < 7.9 or w > .23)
            top = s.SCULK if crust else BLACKSTONE if w > .07 else s.COBBLE if w < -.31 else s.BASALT
            if chasm:
                if abs(seam) < 1.65 + .4 * w:
                    g.put(x, h - 1, z, s.LUMEN if (x + z) % 7 < 4 else s.DARK_TEAL)
                    top = TEAL_GLASS
                else:
                    top = s.TEARS if w < -.41 else s.SCULK if w > -.5 else s.OBSIDIAN
            g.put(x, h, z, top)
    return height


def buried_stones(g: Valley, ground: np.ndarray) -> None:
    # Irregular basalt reefs along the valley edges. Keep the crossing and the path clear.
    formations = (
        (-49,-26,9,5),(-61,6,7,9),(-83,21,10,8),(-87,60,13,10),(-105,112,7,8),
        (-84,139,11,9),(-87,176,12,12),(-62,227,12,8),(-39,249,8,10),(-9,254,8,8),
        (24,-31,6,5),(50,-11,9,7),(65,16,6,7),(90,55,10,10),(109,83,7,12),
        (118,153,9,9),(120,174,6,13),(119,212,7,8),(124,235,8,11),(84,254,8,11),(54,251,9,9),
    )
    for cx, cz, radius, high in formations:
        for z in range(cz - radius, cz + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                y0 = int(ground[z - Z0, x - X0])
                if y0 == Y0:
                    continue
                r = math.hypot(x - cx, (z - cz) * 1.04) / radius + .27 * s.patch(x, 1, z)
                if r >= 1:
                    continue
                y = y0 + round(max(1., high * (1-r)**1.6))
                g.box(x, x, y0 + 1, y, z, z)[:] = BASALT_COLUMN if (x*7 + z*3) % 11 > 5 else BLACKSTONE
                if (x + z) % 4 and r < .80:
                    g.put(x, y + 1, z, COBBLE_CAP if (x + z) % 3 else DARK_STEP)


def pier_lamp(g: Valley, x: int, y: int, z: int, *, tall: bool = False) -> None:
    g.box(x - 1, x + 1, y, y, z - 1, z + 1)[:] = BLACK_BRICK
    for h in range(y - 1, -9, -1):
        if g.get(x, h, z) != AIR:
            break
        g.put(x, h, z, BASALT_COLUMN)
    g.box(x, x, y + 1, y + (4 if tall else 2), z, z)[:] = BASALT_COLUMN
    cap = y + (5 if tall else 3)
    g.put(x, cap, z, BLACK_CHISELED)
    g.put(x, cap + 1, z, s.SOUL)
    for dx, dz in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        g.put(x + dx, cap, z + dz, DARK_STEP)


def road_x(z: int) -> int:
    fade = min(1., (223 - z) / 26)
    return PX + round((2.1 + 5.2 * math.sin((z - 118) * .055)) * max(0., fade))


def paths_and_bridges(g: Valley) -> None:
    # A stepped causeway on masonry piers crosses the lower basin.
    climb = {-61, -54, -47, -40, -33}
    front_step = c.stairs('polished_blackstone_brick', 'south')
    for z in range(-66, -31):
        y = min(0, -5 + (z + 68) // 7)
        half = 16 if z < -36 else 19
        for x in range(-half, half + 1):
            if abs(x) < half - 1:
                g.box(x, x, y - 2, y - 1, z, z)[:] = BLACK_BRICK
                paving = BLACK_TRIM if abs(x) in (5, 11) or (x + 2*z) % 13 == 0 else c.DARK
                g.put(x, y, z, front_step if z in climb else paving)
                g.box(x, x, y + 1, max(y + 5, 7), z, z)[:] = AIR
                if abs(x) == 7 and z % 10 == 4 and z not in climb:
                    g.put(x, y, z, s.LUMEN)
            else:
                g.box(x, x, -8, y, z, z)[:] = BLACK_BRICK if z % 11 == 0 else s.BASALT
                g.put(x, y + 1, z, DARK_STEP)
        if z % 11 in (1, 2):
            for x in (-12, 12):
                g.box(x - 1, x + 1, -8, y - 1, z, z)[:] = BLACK_BRICK
    for z, y in ((-64,-5), (-52,-3), (-41,-2), (-32,0)):
        for x in (-15, 15):
            pier_lamp(g, x, y, z, tall=z == -64)

    # The east walk connects the side transept stairs to the portal terrace.
    g.box(84, 104, -2, 0, 116, 124)[:] = BLACK_BRICK
    g.box(84, 104, 1, 7, 117, 123)[:] = AIR
    front_step = c.stairs('deepslate_brick', 'south')
    turns = {202, 207, 212, 217}
    for z in range(120, 222):
        y = sum(z >= h for h in turns)
        center = road_x(z)
        half = 4 if z < 195 else 6
        for x in range(center - half, center + half + 1):
            side = abs(x - center)
            g.box(x, x, y - 2, y - 1, z, z)[:] = BLACK_BRICK
            g.put(x, y, z, front_step if z in turns else BLACK_TRIM if side in (0, half - 2) else SLATE_BRICK)
            g.box(x, x, y + 1, y + 7, z, z)[:] = AIR
            if side == half:
                g.put(x, y + 1, z, DARK_STEP)
            elif side == half - 1 and z % 9 == 4 and z not in turns:
                g.put(x, y, z, s.LUMEN)
        if abs(z - ground_line(center)) < 11 and z % 6 in (0, 1):
            for x in (center - half, center + half):
                g.box(x, x, -8, y - 2, z, z)[:] = BLACK_BRICK
    for z in (132, 148, 166, 184, 198):
        x = road_x(z)
        pier_lamp(g, x - 5, 0, z)
        pier_lamp(g, x + 5, 0, z)


def rift_overlook(g: Valley) -> None:
    """A side stair branches off the east walk onto a small octagonal lookout."""
    cx, cz, radius, top = 72, 183, 8, 2
    for z in range(cz - radius, cz + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            u, v = x - cx, z - cz
            if not c.octagon(u, v, radius):
                continue
            pier = abs(u) in (3, 4) and abs(v) in (3, 4)
            g.box(x, x, -8 if pier else top - 2, top - 1, z, z)[:] = BLACK_BRICK
            rim = not c.octagon(u, v, radius - 1)
            ring = abs(u) + abs(v)
            paving = BLACK_TRIM if rim or ring in (4, 7) else SLATE_BRICK
            if ring == 5 and min(abs(u), abs(v)) == 0:
                paving = s.LUMEN
            g.put(x, top, z, paving)
            g.box(x, x, top + 1, top + 5, z, z)[:] = AIR
            if rim and not (u > 0 and abs(v) <= 3):
                g.put(x, top + 1, z, BLACK_CHISELED if (u + v) % 3 == 0 else BLACK_BRICK)
                g.put(x, top + 2, z, DARK_STEP)
    for x, z in ((cx - 5, cz - 5), (cx + 5, cz + 5), (cx + 5, cz - 5)):
        pier_lamp(g, x, top, z)

    tread = c.stairs('polished_blackstone_brick', 'west')
    for x in range(78, road_x(176)):
        center = 176 + (96 - x) // 3
        y = int(x <= 92) + int(x <= 85)
        for z in range(center - 2, center + 3):
            g.box(x, x, y - 2, y - 1, z, z)[:] = BLACK_BRICK
            g.put(x, y, z, tread if x in (85, 92) else BLACK_TRIM if z == center else SLATE_BRICK)
            g.box(x, x, y + 1, y + 5, z, z)[:] = AIR
            if x not in (85, 92) and abs(z - center) == 2:
                g.put(x, y + 1, z, DARK_STEP)
            elif x % 8 == 1 and z == center + 1:
                g.put(x, y, z, s.LUMEN)


def portal_square(g: Valley) -> None:
    # Terraced plinth and octagonal tracery frame an ordinary rectangular obsidian gate.
    for z in range(PZ - 11, PZ + 18):
        for x in range(PX - 21, PX + 22):
            dx, dz = abs(x - PX), abs(z - (PZ + 2))
            if dx + dz > 29:
                continue
            y = 4 if z < PZ + 13 else 3 - (z - (PZ + 13)) // 2
            g.box(x, x, -4, y - 1, z, z)[:] = BLACK_BRICK if dx >= 19 or dx + dz >= 28 else s.BASALT
            g.put(x, y, z, BLACK_TRIM if dx in (7, 14, 20) or dz in (8, 12) else SLATE_BRICK)
            g.box(x, x, y + 1, y + 5, z, z)[:] = AIR
            if (dx == 10 and dz % 3 == 2) or (dx == 4 and dz in (4, 6, 9)):
                g.put(x, y, z, s.LUMEN)
            elif (dx == 7 or dz == 8) and (x + z) % 4 == 0:
                g.put(x, y, z, VIOLET)
    # Both faces of the arch are layered, around the narrower rectangular aperture.
    for u in range(-18, 19):
        a = abs(u)
        h = c.arch_top(u, 18, 24, 15)
        inner = c.arch_top(u, 9, 22, 8) if a <= 9 else 4
        g.box(PX + u, PX + u, inner + 1, h, PZ - 2, PZ + 4)[:] = BLACK_BRICK
        g.box(PX + u, PX + u, h - 1, h, PZ - 4, PZ + 5)[:] = BLACK_TRIM
        g.put(PX + u, h + 1, PZ - 2, ROOF_CAP)
        if a % 2 == 0 and h > 27:
            g.put(PX + u, h - 2, PZ - 3, VIOLET)
        if 8 <= a <= 14:
            tip = c.arch_top(u, 14, 21, 10)
            g.box(PX + u, PX + u, 5 if a > 10 else 20, tip, PZ - 3, PZ - 2)[:] = BLACK_CHISELED
            g.put(PX + u, tip, PZ - 4, c.stairs('polished_blackstone', 'south', 'top'))
    for side in (-1, 1):
        for a, height in ((10,22), (15,28), (19,16)):
            x = PX + side * a
            for y in range(5, height + 1):
                r = 2 if y < 8 or y in (13, 14, height) else 1
                g.box(x - r, x + r, y, y, PZ - 3 - r, PZ - 3 + r)[:] = BLACK_TRIM if r == 2 else BASALT_COLUMN
            g.put(x, height + 1, PZ - 3, s.TEARS)
            g.put(x, height + 2, PZ - 3, DARK_STEP)
        x = PX + side * 11
        for y in (9, 13, 17, 21):
            g.put(x, y, PZ - 5, s.TEARS)
            g.put(x, y - 1, PZ - 5, c.stairs('polished_blackstone_brick', 'south', 'top'))
        for z in (PZ - 9, PZ + 7):
            pier_lamp(g, PX + side * 16, 4, z, tall=True)
    # Violet quatrefoil in the tympanum, set one block forward of the masonry.
    for v in range(-5, 6):
        for u in range(-5, 6):
            radius = math.hypot(u, v)
            if radius > 5.05:
                continue
            x, y = PX + u, 34 + v
            lobe = min(math.hypot(abs(u) - 2, v), math.hypot(u, abs(v) - 2))
            if radius < 1.2:
                block = s.LUMEN
            elif lobe < 1.6:
                block = AMETHYST
            elif radius <= 3.9:
                block = c.GLASS['purple'] if (u + v) % 3 else VIOLET
            else:
                block = BLACK_CHISELED
            g.put(x, y, PZ - 4, BLACK_TRIM)
            g.put(x, y, PZ - 5, block)
    for y in range(39, 46):
        r = (45 - y) // 2
        g.box(PX - r, PX + r, y, y, PZ - r, PZ + r)[:] = BLACK_CHISELED if y % 2 else BLACK_TRIM
    g.put(PX, 46, PZ, s.TEARS)
    g.put(PX, 47, PZ, DARK_STEP)


def working_frame(g: Valley) -> None:
    half = PWIDTH // 2
    g.box(PX - half, PX + half, PBASE + 1, PEND - 1, PZ - 3, PZ + 3)[:] = AIR
    g.box(PX - half - 1, PX + half + 1, PBASE, PBASE, PZ, PZ)[:] = s.OBSIDIAN
    g.box(PX - half - 1, PX + half + 1, PEND, PEND, PZ, PZ)[:] = s.OBSIDIAN
    for side in (-1, 1):
        u = PX + side * (half + 1)
        g.box(u, u, PBASE + 1, PEND - 1, PZ, PZ)[:] = s.OBSIDIAN
    for z in (PZ - 2, PZ + 2):
        for x in range(PX - half, PX + half + 1, 3):
            g.put(x, PBASE, z, s.LUMEN)


BRANCHES = (
    ((8,133,113,2.8), (4,139,122,3.0), (-8,145,131,2.8), (-19,145,140,2.5),
     (-29,140,147,1.8), (-37,146,155,1.5), (-43,155,153,.96)),
    ((-9,145,132,2.25), (-12,150,123,1.8), (-11,153,115,1.30), (-14,158,107,.86)),
    ((33,51,154,4.0), (40,61,146,4.1), (47,66,139,3.3), (54,67,132,2.7),
     (59,76,124,1.85), (66,83,112,1.35), (71,90,106,.87)),
    ((50,68,137,2.9), (56,59,143,2.7), (64,49,145,2.4), (73,49,151,1.8), (78,55,156,1.2)),
    ((56,5,188,5.1), (65,-2,191,4.8), (74,-3,200,4.3), (80,2,207,4.3), (83,12,213,4.2),
     (81,22,220,4.1), (83,31,224,3.9), (91,39,226,3.5), (98,45,227,2.95),
     (107,43,227,2.55), (115,43,231,2.), (123,49,236,1.15)),
    ((81,21,220,3.8), (73,28,220,3.0), (66,35,226,2.6), (65,44,236,1.8), (60,48,241,1.10)),
    ((71,0,204,4.2), (76,3,214,4.1), (81,1,226,3.3), (87,2,244,2.9),
     (95,7,251,2.4), (102,8,258,1.5), (109,5,264,1.05)),
    ((113,43,231,2.1), (118,37,241,2.2), (116,28,249,2.5), (119,17,251,2.8), (123,6,246,3.2),
     (129,1,240,1.65)),
    ((40,3,206,3.5), (47,2,223,3.1), (55,2,237,2.65), (53,6,247,1.9), (46,8,255,1.45), (41,5,259,1.05)),
    ((32,46,165,4.0), (24,51,156,3.7), (16,63,149,3.6), (6,74,140,3.1),
     (-6,84,132,2.9), (-17,75,131,2.55), (-25,72,133,1.8), (-33,79,138,1.0)),
)


def root_system(g: Valley) -> None:
    mass = np.full(SHAPE, -2, dtype=np.float32)
    seams = mass.copy()
    for i, path in enumerate(BRANCHES):
        s.stroke(mass, path, vertical=.8 if i in (6, 8) else 1., limits=g.limits)
        thread = [(x + r*.64, y + r*.39, z + r * (-.42 if i % 2 == 0 else .40), min(.95, .39 + r*.13))
                  for x, y, z, r in path]
        s.stroke(seams, thread, limits=g.limits)
    y, z, x = np.where(mass >= 0)
    yy, zz, xx = y + Y0, z + Z0, x + X0
    wave = np.sin(xx*.41 + yy*.79 + zz*.28) + .50*np.cos(zz*.43 - xx*.27 + yy*.37)
    materials = np.select((wave < -1.12, wave < -.58, wave > 1.15, wave > .74), (s.TEARS, s.COBBLE, s.OBSIDIAN, s.DARK_TEAL), s.SCULK)
    stripe = (seams[y, z, x] >= 0) & (mass[y, z, x] < 1.35)
    light = np.cos(xx*.30 - zz*.46 + yy*.33) + .23 * np.sin(yy*.55 + xx*.78)
    materials[stripe] = np.select((light[stripe] > .76, light[stripe] > -.44), (s.LUMEN, TEAL_GLASS), s.DARK_TEAL)
    g.blocks[y, z, x] = materials
    # Light mineral hooks make the edges readable, without bleaching the whole root.
    for i in (1, 3, 5):
        x, y, z, _ = BRANCHES[i][-1]
        idx, xx, yy, zz = s.local(x, y, z, 3.1, 5.0, 3.1, limits=g.limits)
        end = (mass[idx] >= 0) & ((xx-x)**2 + (zz-z)**2 + .35*(yy-y)**2 < 6)
        g.blocks[idx][end] = np.where(np.broadcast_to(yy, end.shape)[end] % 3 == 0, BONE, c.state('polished_tuff'))


def remove_stray_voxels(g: Valley) -> None:
    occupied = np.pad(g.blocks != AIR, 1)
    connected = (occupied[:-2,1:-1,1:-1] | occupied[2:,1:-1,1:-1] | occupied[1:-1,:-2,1:-1]
                 | occupied[1:-1,2:,1:-1] | occupied[1:-1,1:-1,:-2] | occupied[1:-1,1:-1,2:])
    g.blocks[~connected] = AIR


def block_light(blocks: np.ndarray) -> np.ndarray:
    """Conservative block-only flood; no skylight or propagation through solid shapes."""
    emission = {'sea_lantern': 15, 'ochre_froglight': 15, 'lantern': 15, 'soul_lantern': 10,
                'crying_obsidian': 10, 'glow_lichen': 7, 'sculk_catalyst': 6}
    strength = np.array([emission.get(name.removeprefix('minecraft:'), 0) for name, _ in c.STATES], dtype=np.uint8)
    light = strength[blocks]
    # Treat even stairs, glass, chains and slabs as opaque: this is a lower bound, not a skylight mock.
    through = np.array([name in ('minecraft:air', 'minecraft:sculk_vein', 'minecraft:glow_lichen')
                        for name, _ in c.STATES])[blocks]
    nxt = np.empty_like(light)
    for _ in range(14):
        nxt.fill(0)
        for axis in range(3):
            low, high = [slice(None)] * 3, [slice(None)] * 3
            low[axis], high[axis] = slice(None, -1), slice(1, None)
            lo, hi = tuple(low), tuple(high)
            np.maximum(nxt[lo], light[hi], out=nxt[lo])
            np.maximum(nxt[hi], light[lo], out=nxt[hi])
        np.maximum(nxt, 1, out=nxt)
        nxt -= 1
        nxt[~through] = 0
        np.maximum(light, nxt, out=light)
    return light


def could_support_spawn(name: str, props: tuple) -> bool:
    if name.endswith('_slab'):
        return dict(props)['type'] != 'bottom'
    if name.endswith('_stairs'):
        return dict(props)['half'] != 'bottom'
    if name.endswith(('_glass', ':glass', '_carpet', '_lantern', ':lantern', '_chain', '_bars',
                      '_vein', '_lichen', '_sensor', '_shrieker', '_wall', ':air')):
        return False
    return True


def spawn_surfaces(blocks: np.ndarray) -> np.ndarray:
    """Potential foot positions above the supplied floors, indexed by the supporting block."""
    support = np.array([could_support_spawn(*entry) for entry in c.STATES], dtype=bool)
    # Other blocks used here have collision at the spawning cell's center (including bars,
    # chains and carpets), or are the noncolliding growth considered alongside air.
    free = np.array([name in ('minecraft:air', 'minecraft:sculk_vein', 'minecraft:glow_lichen')
                     for name, _ in c.STATES], dtype=bool)
    return support[blocks[:-1]] & free[blocks[1:]]


def spawn_exposure(blocks: np.ndarray, lighting: np.ndarray, minimum: int = MIN_LIGHT) -> np.ndarray:
    """Test potential foot positions even in one-block cavities and on roof ledges."""
    return spawn_surfaces(blocks) & (lighting[1:] < minimum)


def frame_clearance(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    return (np.abs(x - PX) <= PWIDTH // 2) & (np.abs(z - PZ) <= 3) & (y > PBASE) & (y < PEND)


def crypt_spawn_protection(g: Valley) -> None:
    # Cover the buried chamber even where it is already lit. If pasted in a slime chunk
    # below Y=40, ordinary light alone cannot protect its floors.
    underground = g.box(-35, 39, g.limits[2], -1, 145, 205)
    foot = underground[1:]
    foot[spawn_surfaces(underground)] = DARK_CARPET


def spawn_protection(g: Valley) -> None:
    # First place low, cool light, then cap shadows so the build keeps its dark appearance.
    occupied = g.blocks
    x0, _, y0, _, z0, _ = g.limits
    ny, nz, nx = occupied.shape
    light = block_light(occupied)
    y, z, x = np.where(spawn_exposure(occupied, light))
    foot = y + 1
    clear = frame_clearance(x + x0, foot + y0, z + z0)
    supports = occupied[y, z, x]
    sturdy = np.array([could_support_spawn(name, props) and not name.endswith(('_slab', '_stairs'))
                       for name, props in c.STATES])[supports]
    # One deliberately spaced growth light per sector of otherwise unlit stone.
    free = np.array([name in ('minecraft:air', 'minecraft:sculk_vein') for name, _ in c.STATES])
    ok = (~clear) & sturdy & free[occupied[foot, z, x]]
    foot, z, x = foot[ok], z[ok], x[ok]
    sector = (foot // 7 * ((nz + 6) // 7) + z // 7) * ((nx + 6) // 7) + x // 7
    if len(sector):
        middle = np.abs(foot % 7 - 3) + np.abs(z % 7 - 3) + np.abs(x % 7 - 3)
        best = np.lexsort((middle, sector))
        order = best[np.r_[True, sector[best][1:] != sector[best][:-1]]]
        occupied[foot[order], z[order], x[order]] = LICHEN
    light = block_light(occupied)
    y, z, x = np.where(spawn_exposure(occupied, light))
    foot = y + 1
    assert not np.any(frame_clearance(x + x0, foot + y0, z + z0)), 'Light must reach the unlit portal opening'
    # Bottom slabs on high ledges where they won't restrict two-block passageways.
    caps = (foot + y0 >= 13)
    for offset in (1, 2):
        caps &= occupied[np.minimum(foot + offset, ny - 1), z, x] == AIR
    cap_by_state = np.array([
        ROOF_CAP if 'deepslate_tile' in name else DARK_STEP if 'blackstone' in name else COBBLE_CAP
        for name, _ in c.STATES
    ], dtype=np.int16)
    terrain = (np.abs(x + x0) > 42) | (z + z0 > 204)
    occupied[foot, z, x] = np.select((caps, terrain), (cap_by_state[occupied[y, z, x]], RUIN_CARPET), DARK_CARPET)
    # Cloth and slabs can reduce light transmission: recheck with caps in place.
    for _ in range(4):
        remaining = spawn_exposure(occupied, block_light(occupied))
        if not np.any(remaining):
            return
        y, z, x = np.where(remaining)
        assert not np.any(frame_clearance(x + x0, y + 1 + y0, z + z0))
        occupied[y+1, z, x] = DARK_CARPET
    assert not np.any(spawn_exposure(occupied, block_light(occupied))), 'A dark spawnable surface remained'


def precinct() -> Valley:
    """The unprotected geometry, reused by larger editions before their own light pass."""
    g = Valley()
    darken(g)
    surface = landform(g)
    buried_stones(g, surface)
    portal_square(g)
    root_system(g)
    paths_and_bridges(g)
    rift_overlook(g)
    working_frame(g)
    return g


def build() -> np.ndarray:
    g = precinct()
    remove_stray_voxels(g)
    crypt_spawn_protection(g)
    spawn_protection(g)
    return g.blocks


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=OUTPUT)
    p.add_argument('--preview', type=Path, help='a thumbnail to embed in the schematic')
    args = p.parse_args()
    c.save(args.output, build(), args.preview, title=TITLE, description=DESCRIPTION)


if __name__ == '__main__':
    main()
