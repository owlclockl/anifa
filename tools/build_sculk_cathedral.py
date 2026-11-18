#!/usr/bin/env python3
"""Grow a Deep Dark outbreak through the original Moonspire Cathedral."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from . import build_cathedral as c


TITLE = f'{c.TITLE} — Эхо глубин'
DESCRIPTION = 'Разлом под алтарём, заражённая крипта и наросты скалка от фундамента до шпиля. Minecraft Java 26.3.'
OUTPUT = c.OUTPUT.with_stem('moonspire-cathedral-sculk')
X0, X1, Y0, Y1, Z0, Z1 = -89, 89, -14, 163, -34, 239
SHAPE = (Y1 - Y0 + 1, Z1 - Z0 + 1, X1 - X0 + 1)  # y, z, x

AIR = c.AIR
SCULK = c.state('sculk')
COBBLE = c.state('cobbled_deepslate')
FRACTURE = c.state('cracked_deepslate_bricks')
CRACKED_ROOF = c.state('cracked_deepslate_tiles')
BASALT = c.state('smooth_basalt')
OBSIDIAN = c.state('obsidian')
TEARS = c.state('crying_obsidian')
DARK_TEAL = c.state('dark_prismarine')
AQUA = c.state('cyan_concrete')
RESIN = c.GLASS['cyan']
LIT_RESIN = c.GLASS['light_blue']
LUMEN = c.state('sea_lantern')
BONE = c.state('bone_block', axis='y')
CALCITE = c.state('calcite')
SOUL = c.state('soul_lantern', hanging='false', waterlogged='false')
SOUL_HANGING = c.state('soul_lantern', hanging='true', waterlogged='false')
CATALYST = c.state('sculk_catalyst', bloom='false')
SENSOR = c.state('sculk_sensor', power='0', sculk_sensor_phase='inactive', waterlogged='false')
SHRIEKER = c.state('sculk_shrieker', can_summon='false', shrieking='false', waterlogged='false')


class DeepGrid:
    limits = (X0, X1, Y0, Y1, Z0, Z1)

    def __init__(self) -> None:
        self.blocks = np.zeros(SHAPE, dtype=np.int16)
        old = c.build()
        self.box(c.X0, c.X1, 0, c.Y1, c.Z0, c.Z1)[:] = old

    @classmethod
    def coord(cls, x: int, y: int, z: int) -> tuple[int, int, int]:
        x0, _, y0, _, z0, _ = cls.limits
        return y - y0, z - z0, x - x0

    def put(self, x: int, y: int, z: int, block: int) -> None:
        self.blocks[self.coord(x, y, z)] = block

    def get(self, x: int, y: int, z: int) -> int:
        return int(self.blocks[self.coord(x, y, z)])

    def box(self, x1: int, x2: int, y1: int, y2: int, z1: int, z2: int) -> np.ndarray:
        x0, xmax, y0, ymax, z0, zmax = self.limits
        assert x0 <= x1 <= x2 <= xmax and y0 <= y1 <= y2 <= ymax and z0 <= z1 <= z2 <= zmax
        return self.blocks[y1 - y0:y2 - y0 + 1, z1 - z0:z2 - z0 + 1, x1 - x0:x2 - x0 + 1]


def patch(x: float, y: float, z: float) -> float:
    """Low-frequency variation for connected, ragged patches instead of speckle."""
    return (math.sin(x * .26 + math.sin(z * .31) * 1.65 - y * .21) * .51
            + math.cos(z * .41 + x * .29 + y * .38) * .32
            + math.sin((x - z) * .63 + y * .72) * .17)


def local(cx: float, cy: float, cz: float, rx: float, ry: float, rz: float, *, limits=DeepGrid.limits):
    """A bounded voxel window and its broadcast coordinate axes (x, y, z)."""
    x0, x1, y0, y1, z0, z1 = limits
    a, b = max(x0, math.floor(cx - rx)), min(x1, math.ceil(cx + rx))
    d, e = max(y0, math.floor(cy - ry)), min(y1, math.ceil(cy + ry))
    f, g = max(z0, math.floor(cz - rz)), min(z1, math.ceil(cz + rz))
    idx = (slice(d - y0, e - y0 + 1), slice(f - z0, g - z0 + 1), slice(a - x0, b - x0 + 1))
    yy, zz, xx = np.ogrid[d:e + 1, f:g + 1, a:b + 1]
    return idx, xx, yy, zz


def crypt(g: DeepGrid) -> None:
    """A vaulted chamber below the choir, with stairs from the west aisle."""
    for z in range(147, 205):
        for x in range(-17, 36):
            r = math.hypot((x - 9) / 26, (z - 175) / 29) + .035 * patch(x, -8, z)
            if r > 1:
                continue
            g.box(x, x, -14, -13, z, z)[:] = BASALT if r > .89 else c.TUFF
            g.put(x, -12, z, COBBLE if r > .77 else c.DARK if (x + z) % 7 < 2 else c.BASE)
            if r > .84:
                g.box(x, x, -11, 0, z, z)[:] = BASALT if r > .90 else FRACTURE
            else:
                # The surviving roof follows the undercroft walls up to the choir floor.
                low = -1 if r < .66 else -2 if r < .76 else -4
                g.box(x, x, low, 0, z, z)[:] = COBBLE if r > .72 else c.TUFF
    for z in (156, 164, 187, 194):
        for x in (-5, 22):
            g.box(x - 1, x + 1, -11, -1, z - 1, z + 1)[:] = c.TUFF
            for h in (-11, -5, -2):
                g.box(x - 1, x + 1, h, h, z - 1, z + 1)[:] = c.BASE
            g.put(x - 2, -8, z, c.BASE)
            g.put(x - 2, -7, z, SOUL)
    # Descend south, turn east, then break through the west wall into the vault.
    stair = c.stairs('polished_blackstone_brick', 'north')
    for z in range(146, 169):
        y = max(-12, 4 - (z - 145))
        g.box(-32, -25, -14, y, z, z)[:] = BASALT
        g.box(-31, -26, y, y, z, z)[:] = stair if z <= 161 else c.DARK
        g.box(-31, -26, y + 1, min(5, y + 5), z, z)[:] = AIR
        for x in (-32, -25):
            top = 5 if y > 0 else min(4, y + 4)
            g.box(x, x, y + 1, top, z, z)[:] = c.BASE if y > 0 else c.TUFF
            if z in (146, 151, 156, 161, 166):
                g.put(x, top + 1, z, SOUL)
    g.box(-33, -9, -14, -12, 163, 171)[:] = BASALT
    g.box(-31, -9, -12, -12, 164, 169)[:] = c.DARK
    g.box(-31, -9, -11, -7, 164, 169)[:] = AIR
    g.box(-25, -17, -11, -5, 163, 163)[:] = c.TUFF
    g.box(-32, -17, -11, -5, 170, 170)[:] = c.TUFF
    g.box(-32, -17, -6, -5, 163, 170)[:] = c.TUFF
    for x in (-24, -19, -14):
        g.put(x, -9, 169, c.BASE)
        g.put(x, -8, 169, SOUL)


def ruptures(g: DeepGrid) -> None:
    # The fault runs off-centre so the choir still opens into a passable western ambulatory.
    for z in range(160, 198):
        for x in range(1, 34):
            r = math.hypot((x - 15) / 16.0, (z - 178) / 18.0) + .12 * patch(x, 2, z)
            if r > 1 or x <= 3:
                continue
            notch = x < 14 and abs(z - 175) <= 3
            top = -12 if r < .63 or notch else min(3, -9 + round((r - .63) * 28))
            if top >= -11:
                g.box(x, x, -11, top, z, z)[:] = BASALT if r > .86 else COBBLE
            g.box(x, x, top + 1, 13 if x > 5 else 8, z, z)[:] = AIR
            g.put(x, top, z, SCULK if r < .86 else FRACTURE)
    # The first breach follows the root through the aisle. Smaller tears expose the roof ribs.
    for centre, radii in (
        ((36, 17, 174), (5.5, 12, 12.5)), ((31, 34, 165), (9, 6.8, 10)),
        ((19, 62, 167), (6, 11, 10)), ((25, 64, 141), (5, 3.5, 6)),
        ((16, 30, 183), (3.2, 6.2, 5.5)), ((34, 23, 191), (4, 6, 3.3)),
    ):
        cx, cy, cz = centre
        rx, ry, rz = radii
        idx, x, y, z = local(cx, cy, cz, rx * 1.3, ry * 1.3, rz * 1.3)
        field = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 + ((z - cz) / rz) ** 2
        kink = .20 * np.sin(x * .78 + z * .51 + y * .30) + .14 * np.cos(z * .76 - y * .65)
        g.blocks[idx][field < 1 + kink] = AIR


def ground(g: DeepGrid) -> None:
    """A low scree fan below the outer roots rather than a rectangular baseplate."""
    for z in range(138, 235):
        for x in range(19, 79):
            r = min(math.hypot((x - cx) / a, (z - cz) / b) for cx, cz, a, b in (
                (44, 173, 27, 31), (53, 194, 26, 25), (35, 213, 28, 20),
            ))
            wobble = patch(x, 0, z)
            if r + wobble * .15 >= 1:
                continue
            y = min(5, 1 + round(3 * (1 - r) + 1.5 * wobble))
            for h in range(-1, y + 1):
                if g.get(x, h, z) == AIR:
                    g.put(x, h, z, SCULK if h == y and r + wobble * .28 < .68 else COBBLE if h < y or wobble > .03 else BASALT)


# Each knot is x, y, z, radius. The paths start at the rupture, follow buttresses
# and split towards the spire and the scree. Short paths attach to earlier ones.
ROOTS = (
    ((13,-10,177,5.3), (21,-4,176,6.4), (28,2,174,7.2), (35,12,171,7.6), (43,25,172,6.9),
     (41,35,171,6.4), (32,43,174,5.8), (23,53,174,5.8), (21,64,168,5.4), (16,74,164,4.7),
     (9,82,162,4.0), (9,92,156,2.9), (15,103,152,1.85), (18,111,145,.9)),
    ((31,7,174,5.3), (43,3,180,5.6), (54,3,189,5.4), (61,6,197,4.5), (67,4,205,3.1),
     (73,1,215,1.6), (76,0,223,.8)),
    ((41,4,180,4.5), (40,4,195,4.1), (39,4,209,3.3), (33,6,220,2.6), (28,5,229,1.9), (20,2,232,1.25)),
    ((36,7,174,4.8), (41,4,163,4.0), (45,6,155,2.9), (47,10,151,2.), (49,4,145,1.25), (55,2,139,.8)),
    ((55,4,189,4.4), (62,13,184,4.1), (67,26,180,4.0), (66,37,175,3.5), (61,45,170,3.5),
     (53,49,168,3.3), (46,46,168,3.4), (39,39,172,4.3)),
    ((26,49,174,4.3), (32,47,163,4.0), (35,49,154,4.1), (32,56,146,3.9), (25,65,139,4.4),
     (27,77,131,3.6), (23,85,124,3.5), (15,92,125,3.7), (12,101,123,3.4),
     (11,113,122,2.8), (7,124,118,2.2), (8,134,113,1.6), (10,143,113,.85)),
    ((38,33,171,4.1), (45,38,181,3.7), (44,49,189,3.0), (38,59,190,2.9), (33,66,189,2.4),
     (30,75,184,1.6), (33,85,180,.8)),
    ((22,64,168,4.1), (27,70,173,3.3), (32,79,169,2.35), (35,92,163,1.65), (41,97,165,.85)),
    ((12,85,161,3.9), (1,90,167,3.75), (-9,86,173,2.75), (-15,80,181,2.0), (-18,71,190,1.25), (-22,64,194,.78)),
    ((23,86,124,3.4), (40,83,122,2.8), (53,86,119,2.05), (57,96,115,1.55), (62,105,116,.8)),
    ((12,111,122,2.55), (18,118,126,2.1), (19,126,130,1.45), (20,133,129,.75)),
    ((20,-7,175,5.), (13,-9,165,3.45), (5,-9,161,2.4), (-4,-10,164,1.55), (-8,-11,169,.8)),
    ((13,-10,177,4.5), (15,-3,179,4.85), (12,5,179,5.5), (15,11,178,6.1), (15,17,180,4.75), (16,23,180,2.15)),
    ((12,-9,179,4), (19,-10,187,3.1), (27,-10,189,2.4), (30,-7,192,1.3), (29,-3,196,.85)),
)


def samples(knots):
    """Sample a continuous Catmull–Rom centreline with a linearly tapering radius."""
    p = np.asarray(knots, dtype=float)
    for i in range(len(p) - 1):
        a, b, d, e = p[max(0, i - 1)], p[i], p[i + 1], p[min(i + 2, len(p) - 1)]
        steps = max(1, math.ceil(np.linalg.norm(d[:3] - b[:3]) * 1.35))
        for j in range(steps):
            t = j / steps
            v = .5 * ((2 * b) + (-a + d) * t + (2*a - 5*b + 4*d - e) * t*t + (-a + 3*b - 3*d + e) * t*t*t)
            yield v[0], v[1], v[2], b[3] + (d[3] - b[3]) * t
    yield tuple(p[-1])


def stroke(field: np.ndarray, knots, vertical: float = 1., *, limits=DeepGrid.limits) -> None:
    for cx, cy, cz, r in samples(knots):
        idx, x, y, z = local(cx, cy, cz, r + 1, (r + 1) * vertical, r + 1, limits=limits)
        distance = np.sqrt((cx - x) ** 2 + ((cy - y) / vertical) ** 2 + (cz - z) ** 2)
        tooth = .19 * np.sin(x * .37 + z * .46 + y * .76) + .14 * np.cos(x * .74 - z * .52 + y * .39)
        np.maximum(field[idx], (r - distance + tooth), out=field[idx])


def heart_petals():
    # Asymmetric ribs around the aperture; the front gap looks out into the nave.
    for a, top in ((.2, 25), (1.06, 32), (1.83, 30), (2.55, 23), (3.29, 21), (5.67, 28)):
        ca, sa = math.cos(a), math.sin(a)
        yield ((14 + ca * 2, -5, 178 + sa * 2, 2.7), (14 + ca * 6, 3, 178 + sa * 5, 2.9),
               (14 + ca * 9, 11, 178 + sa * 8, 2.6), (14 + ca * 10, 18, 178 + sa * 10, 2.2),
               (14 + ca * 7.5, top - 3, 178 + sa * 7, 1.45), (14 + ca * 5, top, 178 + sa * 6, .78))


# A single high-pressure focus and successively weaker satellite colonies along the paths.
FOCI = (
    (16, 9, 177, 24, 23, 29, 1.15), (38, 20, 171, 25, 36, 33, 1.12),
    (51, 5, 192, 27, 19, 39, 1.04), (23, 58, 172, 23, 31, 30, 1.09),
    (24, 58, 143, 25, 29, 25, .99), (9, 91, 125, 27, 33, 25, 1.04),
    (35, 12, 213, 38, 20, 25, .93), (-15, 17, 204, 23, 25, 25, .76),
    (61, 29, 132, 34, 29, 29, .76), (33, 5, 125, 21, 12, 43, .78),
    (35, 3, 79, 16, 11, 24, .70), (38, 12, 56, 12, 13, 10, .55),
)


def pressure(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    value = np.zeros_like(x, dtype=np.float64)
    for cx, cy, cz, sx, sy, sz, w in FOCI:
        field = ((x - cx) / sx)**2 + ((y - cy) / sy)**2 + ((z - cz) / sz)**2
        np.maximum(value, w * np.exp(-field), out=value)
    return value


def encrust(g: DeepGrid) -> None:
    v = g.blocks
    yy, zz, xx = np.where(v)
    x, y, z = xx + X0, yy + Y0, zz + Z0
    ids = v[yy, zz, xx]
    old_stone = (c.STONE, c.BASE, c.PALE, c.CARVED, c.QUARTZ, c.ORNATE, c.TUFF, c.DARK, c.DEEP, c.BLACK,
                 c.state('cracked_stone_bricks'), c.state('deepslate_bricks'))
    decay = pressure(x, y, z)
    ripple = (.12 * np.sin(x * .23 - y * .31 + np.sin(z * .32) * 1.6)
              + .085 * np.cos(x * .14 + z * .39 + y * .27) + .05 * np.sin(y * .46 - z * .71))
    exposed = np.zeros_like(ids, dtype=bool)
    occupied = np.pad(v != AIR, 1, constant_values=False)
    for dy, dz, dx in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        exposed |= ~occupied[yy + 1 + dy, zz + 1 + dz, xx + 1 + dx]
    mineral = np.isin(ids, old_stone + (c.WOOD, c.WOOD_END))
    affected = mineral & (decay + ripple > .43) & (exposed | (decay + ripple > .79))
    crust = affected & (decay + ripple > .67)
    worn = affected & ~crust
    old_tiles = np.isin(ids, (c.DARK, c.DEEP, c.BLACK, c.state('deepslate_bricks')))
    v[yy[worn], zz[worn], xx[worn]] = np.where(old_tiles[worn], CRACKED_ROOF, FRACTURE)
    v[yy[crust], zz[crust], xx[crust]] = np.where(ripple[crust] < -.065, COBBLE, SCULK)
    glass = np.isin(ids, tuple(c.GLASS.values())) & (decay + ripple > .58)
    # The windows dim where the crust first appears; later the broken edge is overgrown.
    v[yy[glass], zz[glass], xx[glass]] = np.where(decay[glass] + ripple[glass] > .85, DARK_TEAL, RESIN)
    for before, after in ((c.LANTERN, SOUL), (c.HANGING, SOUL_HANGING), (c.LIGHT, LUMEN)):
        cool = (ids == before) & (decay > .46)
        v[yy[cool], zz[cool], xx[cool]] = after


def outgrowth(g: DeepGrid) -> None:
    petals = tuple(heart_petals())
    flesh = np.full(SHAPE, -2, dtype=np.float32)
    filaments = flesh.copy()
    for i, path in enumerate(ROOTS + petals):
        stroke(flesh, path, vertical=.80 if i in (1, 2, 3) else 1.)
        if i in (0, 1, 2, 4, 5, 6, 7, 8, 9, 10) or i >= len(ROOTS):
            # Thin offset veins follow exposed bends instead of filling the root with lights.
            sign = -1 if i % 3 == 2 or i >= len(ROOTS) else 1
            stripe = [(x + r * .74, y + .17 * r + .27 * math.sin(j * 2), z + sign * r * .48,
                       min(.94, .32 + r * .125)) for j, (x, y, z, r) in enumerate(path)]
            stroke(filaments, stripe)
    yy, zz, xx = np.where(flesh >= 0)
    x, y, z = xx + X0, yy + Y0, zz + Z0
    skin = flesh[yy, zz, xx] < 1.1
    wave = np.sin(x * .55 + z * .21 - y * .63) + .57 * np.cos(x * .33 + y * .35 + z * .49)
    mass = np.full_like(xx, SCULK)
    mass[wave < -.79] = COBBLE
    mass[wave > 1.15] = OBSIDIAN
    mass[skin & (wave > .58) & (wave < .90)] = DARK_TEAL
    mass[skin & (wave < -1.43)] = TEARS
    vein = skin & (filaments[yy, zz, xx] >= 0)
    pulse = np.cos(z * .41 + x * .27 - y * .55)
    mass[vein] = np.select((pulse[vein] > .77, pulse[vein] > -.42), (LUMEN, AQUA), DARK_TEAL)
    g.blocks[yy, zz, xx] = mass

    # The ends of the petals expose pale ribs above the dark flesh.
    for path in petals + (ROOTS[4], ROOTS[7], ROOTS[9]):
        cx, cy, cz, _ = path[-1]
        idx, x, y, z = local(cx, cy, cz, 4.5, 5, 4.5)
        caps = (flesh[idx] >= 0) & ((x - cx)**2 + (z - cz)**2 + .33 * (y - cy)**2 < 12) & (y > cy - 5)
        g.blocks[idx][caps] = np.where((np.broadcast_to(y, caps.shape)[caps] + round(cz)) % 4 == 0, BONE, CALCITE)


def luminous_heart(g: DeepGrid) -> None:
    # Three cracks in the tilted shell face the nave. Glass caps their sea-lantern cores.
    cx, cy, cz = 14, 14, 177
    idx, x, y, z = local(cx, cy, cz, 8, 8, 7)
    xx, yy, zz = x - cx - .18 * (y - cy), y - cy, z - cz
    u, w = .93 * xx - .367 * zz, .367 * xx + .93 * zz
    r = (u / 5.8)**2 + (yy / 7.6)**2 + (w / 5.5)**2
    pulse = u + .26 * np.sin(yy * .85) + .06 * yy
    slit = (np.abs(pulse) < 1.14) & (np.abs(yy) <= 6)
    veins = (np.abs(np.abs(pulse) - (2.55 + .24 * np.cos(yy * .78))) < .55) & (np.abs(yy) <= 4.1)
    front = (r <= 1) & (w < -.9)
    v = g.blocks[idx]
    capsule = r <= 1
    v[capsule] = np.where(np.sin(u * 1.3 - yy * .64) > .15, DARK_TEAL, SCULK)[capsule]
    v[front & (slit | veins)] = LUMEN
    v[front & (r > .66) & slit] = LIT_RESIN
    v[front & (r > .63) & veins] = RESIN
    v[front & slit & (np.abs(yy) <= 1) & (np.abs(pulse) < .70)] = LUMEN


def rubble_and_colonies(g: DeepGrid) -> None:
    for x, z, radius, height in (
        (22, 163, 3, 3), (27, 166, 3, 4), (35, 180, 4, 4), (38, 169, 4, 4), (43, 171, 3, 5),
        (47, 176, 4, 6), (52, 174, 3, 5), (53, 181, 3, 4), (48, 190, 4, 3), (34, 192, 3, 4),
        (16, 193, 4, 3), (10, 197, 2, 3), (57, 199, 3, 4), (62, 205, 3, 3), (43, 219, 3, 3),
        (35, 219, 2, 2), (31, 154, 2, 2), (31, 157, 2, 2), (33, 150, 2, 3),
    ):
        for dz in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                a, b = x + dx, z + dz
                r = math.hypot(dx, dz) / max(1, radius) + .29 * patch(a, 0, b)
                if r >= 1:
                    continue
                h = next((y for y in range(4, -2, -1) if g.get(a, y, b) not in (AIR, c.CARPET)), None)
                if h is None:
                    continue
                for y in range(h + 1, h + 2 + round(max(0, height * (1 - r)))):
                    if g.get(a, y, b) == AIR:
                        g.put(a, y, b, FRACTURE if r < .5 else COBBLE if (dx + dz + y) % 3 else c.STONE)
    for x, z, top, b in (
        (-8, 165, -11, SHRIEKER), (-4, 168, -11, SENSOR), (1, 171, -10, CATALYST),
        (-1, 180, -11, SENSOR), (4, 178, 4, SHRIEKER), (2, 172, 6, SENSOR),
        (8, 164, 4, CATALYST), (20, 157, 5, SENSOR), (30, 160, 6, CATALYST), (35, 182, 5, SHRIEKER),
        (53, 167, 5, SHRIEKER), (60, 201, 5, SENSOR), (51, 198, 6, CATALYST),
        (30, 217, 5, SENSOR), (38, 207, 6, SHRIEKER), (64, 186, 5, CATALYST),
    ):
        y = next((h for h in range(top, Y0, -1) if g.get(x, h, z) in (SCULK, BASALT, FRACTURE, COBBLE, c.DARK, c.BASE, c.TUFF)), None)
        if y is not None and g.get(x, y + 1, z) == AIR:
            g.put(x, y + 1, z, b)


FACES = (('down', 1, 0, 0), ('up', -1, 0, 0), ('north', 0, 1, 0),
         ('south', 0, -1, 0), ('west', 0, 0, 1), ('east', 0, 0, -1))


def multiface(g: DeepGrid, name: str, supports: tuple[int, ...]) -> None:
    v = g.blocks
    yy, zz, xx = np.where(np.isin(v, supports))
    marks = np.zeros(SHAPE, dtype=np.uint8)
    air = v == AIR
    for i, (_, dy, dz, dx) in enumerate(FACES):
        y, z, x = yy + dy, zz + dz, xx + dx
        ok = (y >= 0) & (y < SHAPE[0]) & (z >= 0) & (z < SHAPE[1]) & (x >= 0) & (x < SHAPE[2])
        ix = y[ok], z[ok], x[ok]
        marks[ix] |= air[ix].astype(np.uint8) << i
    yy, zz, xx = np.where(marks)
    x, y, z = xx + X0, yy + Y0, zz + Z0
    spores = pressure(x, y, z)
    strands = np.sin(x * .48 + z * .22 - y * .66) + np.cos(z * .81 - x * .31 + y * .65)
    variation = ((x * 77 ^ z * 21 ^ y * 57) % 127) / 127
    if name == 'sculk_vein':
        covered = (spores > .35) & (spores < 1.13) & (strands > .86 + variation * 1.66 - spores * 1.16)
    else:
        covered = (spores > .63) & (strands > 1.24 + variation * .82) & (variation < .15)
    # Do not extend the region with a decorative layer under the foundations.
    covered &= (y > Y0) & ((y > 0) | ((x < 33) & (z > 148) & (z < 201)))
    yy, zz, xx = yy[covered], zz[covered], xx[covered]
    shape = marks[yy, zz, xx]
    for mask in np.unique(shape):
        properties = {face: str(bool(int(mask) & (1 << i))).lower() for i, (face, *_) in enumerate(FACES)}
        b = c.state(name, waterlogged='false', **properties)
        select = shape == mask
        v[yy[select], zz[select], xx[select]] = b


def clean_fixtures(g: DeepGrid) -> None:
    # Shattered interior fittings can't hang from a missing block.
    v = g.blocks
    loose = (AIR, c.CARPET, c.LANTERN, SOUL, c.HANGING, SOUL_HANGING, SHRIEKER, SENSOR)
    for src, offset in ((c.LANTERN, -1), (SOUL, -1), (c.HANGING, 1), (SOUL_HANGING, 1)):
        yy, zz, xx = np.where(v == src)
        invalid = np.isin(v[yy + offset, zz, xx], loose)
        v[yy[invalid], zz[invalid], xx[invalid]] = AIR
    # Ignore one-voxel slivers left in midair by the excavated fractures.
    full = np.pad(v != AIR, 1)
    joined = (full[:-2, 1:-1, 1:-1] | full[2:, 1:-1, 1:-1] | full[1:-1, :-2, 1:-1]
              | full[1:-1, 2:, 1:-1] | full[1:-1, 1:-1, :-2] | full[1:-1, 1:-1, 2:])
    v[~joined] = AIR


def build() -> np.ndarray:
    g = DeepGrid()
    for part in (crypt, ruptures, ground, encrust, outgrowth, luminous_heart, rubble_and_colonies, clean_fixtures):
        part(g)
    multiface(g, 'sculk_vein', (c.STONE, c.BASE, c.CARVED, c.DARK, FRACTURE, COBBLE, BASALT, CRACKED_ROOF))
    multiface(g, 'glow_lichen', (SCULK, COBBLE, DARK_TEAL))
    return g.blocks


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=OUTPUT)
    p.add_argument('--preview', type=Path, help='optional thumbnail for the in-game schematic browser')
    args = p.parse_args()
    c.save(args.output, build(), args.preview, title=TITLE, description=DESCRIPTION)


if __name__ == '__main__':
    main()
