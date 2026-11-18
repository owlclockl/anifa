"""Place the Seal's surface finishes without changing inherited editions or their palettes."""

from __future__ import annotations

import numpy as np

from . import build_throne_cathedral as t


c, s, r = t.c, t.s, t.r
AIR, BRICK, TRIM, CARVED, SLATE = t.AIR, t.BRICK, t.TRIM, t.CARVED, t.SLATE
MORTAR = c.state('polished_tuff')


def set_dressing(g: s.DeepGrid) -> None:
    stone_shelves(g)
    entry_apron(g)
    bridge_parapets(g)
    lodge_shelter(g)
    nave_crossings(g)


def stone_shelves(g: s.DeepGrid) -> None:
    """Gather scattered stone colors into broad beds; keep the face of the ravine dark."""
    x0, x1, y0, _, z0, z1 = g.limits
    low, high = -8, 17
    layers = g.box(x0, x1, low, high, z0, z1)
    y, z, x = np.ogrid[low:high+1, z0:z1+1, x0:x1+1]
    covered = np.any(g.blocks[high+1-y0:] != AIR, axis=0)
    old_rock = np.isin(layers, (s.COBBLE, s.BASALT, r.BLACKSTONE)) & ~covered
    slate_bed = c.state('deepslate', axis='y')
    tuff = c.state('tuff')
    fissure = np.array([r.ground_line(u) for u in range(x0, x1+1)])
    east_rift = (x > 40) & (z > 146) & (np.abs(z - fissure) < 36)
    # The seams run across slopes, not down individual columns. Stones in the stream bed stay darker.
    stratum = y - .018 * (x + 21) + .014 * z
    seams = (-2.6 <= stratum) & (stratum <= -.55)
    shoulders = ((x + 56) / 28)**2 + ((z + 28) / 22)**2 < 1
    shoulders |= ((x - 54) / 35)**2 + ((z - 60) / 38)**2 < 1
    shoulders |= ((x + 153) / 45)**2 + ((z - 96) / 27)**2 < 1
    rock = np.select((east_rift & (y < 2), seams & shoulders, y <= -4),
                     (s.BASALT, tuff, slate_bed), default=s.COBBLE)
    layers[old_rock] = rock[old_rock]

    # Keep the chapel's masonry markers; not every needle of exposed rock needs an amethyst-like tip.
    crystals = (layers[1:] == s.TEARS) & (layers[:-1] == t.BASALT) & (x < -90) & (z > 80)
    layers[1:][crystals] = r.COBBLE_CAP


def entry_apron(g: s.DeepGrid) -> None:
    """Follow the grade of each landing. The steps are left as actual climbable stairs."""
    for z in range(-64, -9):
        y = min(0, -5 + (z+68)//7) if z < -31 else min(4, (z+31)//5)
        for x in range(-11, 12):
            old = g.get(x, y, z)
            if c.STATES[old][0].endswith('_stairs') or old == AIR:
                continue
            # Three long, dressed bands rather than alternating points of light.
            material = TRIM if abs(x) in (6, 11) else c.DEEP if abs(x) >= 7 else SLATE
            if z in (-53, -38, -29, -19) and abs(x) <= 6:
                material = t.TRIM
            g.put(x, y, z, material)
    # A retreating solid base makes the walls look built into the stair, not set on its nosing.
    for side in (-1, 1):
        for z in range(-30, -10):
            y = min(4, (z+31)//5)
            x = side*20
            if z in (-29, -26, -21, -16, -11):
                rail = CARVED
            else:
                rail = t.WALL
            g.put(x, y, z, TRIM)
            g.put(x, y+1, z, rail)
            if rail == CARVED and g.get(x, y+2, z) == AIR:
                g.put(x, y+2, z, t.STEP)
            if g.get(x+side, y-1, z) == AIR and g.get(x, y-1, z) != AIR:
                g.put(x+side, y-1, z, t.stair('polished_blackstone_brick', t.direction(side, 0), 'top'))


RIDGE_RISES = (202, 207, 212, 217)
LOOKOUT = (72, 183, 8)


def east_bridge_footprint() -> dict[tuple[int, int], int]:
    """The union of both decks and the belvedere; their internal junction is not an edge."""
    deck = {}
    for z in range(120, 222):
        width = 4 if z < 195 else 6
        level = sum(z >= turn for turn in RIDGE_RISES)
        x = r.road_x(z)
        for offset in range(-width, width+1):
            deck[x+offset, z] = level
    cx, cz, radius = LOOKOUT
    for z in range(cz-radius, cz+radius+1):
        for x in range(cx-radius, cx+radius+1):
            if c.octagon(x-cx, z-cz, radius):
                deck[x, z] = 2
    for x in range(78, r.road_x(176)):
        z = 176 + (96-x)//3
        level = int(x <= 92) + int(x <= 85)
        for offset in range(-2, 3):
            deck[x, z+offset] = level
    return deck


def bridge_parapets(g: s.DeepGrid) -> None:
    """Wall returns at elbows and newels at changes of height. No gate across the lookout turn."""
    deck = east_bridge_footprint()
    for (x, z), y in deck.items():
        if z < 154 or z > 218:
            continue  # Open shoulders at the approach and the forecourt before the Nether arch.
        near = [(x+dx, z+dz) for _, dx, dz in t.CARDINAL]
        edge = any(pos not in deck for pos in near)
        before = g.get(x, y+1, z)
        if not edge:
            # The old slab curbs wandered into the branch where two independent decks overlapped.
            if x >= 78 and 173 <= z <= 185 and before == r.DARK_STEP:
                g.put(x, y+1, z, AIR)
            continue
        name = c.STATES[before][0]
        if not (before in (AIR, CARVED, BRICK) or name.endswith(('_wall', '_slab'))):
            continue  # A lantern pier is already a solid, purpose-built part of the guard.
        if g.get(x, y, z) == AIR:
            continue  # The inherited terrain can hide or replace some peripheral verge cells.
        post = (before in (CARVED, BRICK) and x > 80 or
                z in (154, 168, 194, 195, 218) or any(deck.get(pos, y) < y for pos in near))
        g.put(x, y, z, TRIM)
        g.put(x, y+1, z, CARVED if post else t.TILE_WALL if x < 90 else t.WALL)
        if post and g.get(x, y+2, z) == AIR:
            g.put(x, y+2, z, r.ROOF_CAP)
        elif not post and g.get(x, y+2, z) == r.DARK_STEP:
            g.put(x, y+2, z, AIR)


def lodge_shelter(g: s.DeepGrid) -> None:
    """An off-axis wood store and a bench on a small terrace, not on the lodge route."""
    # The east end joins the lodge path and the west end meets the service lane at the same grade.
    moss = c.state('moss_carpet')
    for z in range(57, 66):
        setback = 2 if z in (57, 65) else 1 if z in (58, 64) else 0
        for x in range(-140+setback, -122):
            g.box(x, x, -8, -1, z, z)[:] = BRICK
            g.put(x, 0, z, TRIM if z in (57, 65) else SLATE)
    for x in (-135, -127):
        for z in (58, 62):
            g.put(x, 1, z, CARVED)
            g.put(x, 2, z, t.FENCE)
            g.put(x, 3, z, t.FENCE)
    log = c.state('dark_oak_log', axis='x')
    ridge = c.slab('deepslate_tile', 'top')
    for x in range(-136, -125):
        for z in range(57, 64):
            face = 'south' if z <= 60 else 'north'
            setback = abs(z-60)
            if setback == 3:
                g.put(x, 4, z, t.stair('deepslate_tile', face))
                continue
            g.put(x, 4, z, log if setback == 2 else c.WOOD)
            g.put(x, 5, z, t.stair('deepslate_tile', face) if setback == 2 else c.DEEP)
            if setback <= 1:
                if setback == 0:
                    g.put(x, 6, z, c.DEEP)
                    g.put(x, 7, z, r.ROOF_CAP)
                else:
                    g.put(x, 6, z, ridge)
    for x in range(-134, -127):
        g.put(x, 2, 58, t.FENCE)
        if x != -131:
            g.put(x, 1, 58, log)
        if x >= -131:
            g.put(x, 1, 59, t.stair('dark_oak', 'north'))
    for x in (-133, -129):
        g.put(x, 3, 62, c.HANGING)
    # A short fence keeps the stacked logs off the path. Its neighbor connections are set later.
    for z in range(59, 64):
        if g.get(-138, 1, z) == AIR:
            g.put(-138, 1, z, t.FENCE)  # Preserve the pre-existing lane lantern on its pier.
    for z in (58, 64):
        g.put(-138, 1, z, CARVED)
        g.put(-138, 2, z, t.OAK_STEP)
    for x, z in ((-137, 62), (-137, 63), (-136, 64), (-130, 64), (-129, 64), (-124, 58)):
        if g.get(x, 0, z) == SLATE and g.get(x, 1, z) == AIR:
            g.put(x, 1, z, moss)


def nave_crossings(g: s.DeepGrid) -> None:
    # Open two shortcuts from the center aisle towards the side windows, between pier axes.
    seat_edges = (c.WOOD_END, t.OAK_STEP, t.stair('dark_oak', 'north'))
    for z in (43, 79):
        for side in (-1, 1):
            for u in range(5, 20):
                x = u*side
                for pz in (z, z+1):
                    for y in (5, 6):
                        if g.get(x, y, pz) in seat_edges:
                            g.put(x, y, pz, AIR)
                    if g.get(x, 5, pz) == AIR and g.get(x, 4, pz) in (SLATE, TRIM, CARVED, c.DARK, c.BLACK, r.BLACK_CHISELED):
                        g.put(x, 4, pz, MORTAR if pz == z+1 else SLATE)
            # Turn the new pew ends down with a shaped armrest rather than a square tier of timber.
            for row in (z-3, z+5):
                for x in (side*6, side*14):
                    if g.get(x, 5, row) == c.WOOD_END:
                        g.put(x, 6, row, t.stair('dark_oak', 'south' if row < z else 'north'))
