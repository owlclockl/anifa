"""Secondary circulation carved into the existing shell; no new exterior roofs."""

from . import build_throne_cathedral as t

c, a, s = t.c, t.a, t.s
AIR = 0
ROOF_WALK = (0, 62, 82)
ROOF_LOBBY = (0, 62, 13)
ROOF_END = (0, 62, 99)
ROOF_ENTRIES = ((-23, 62, 13), (23, 62, 13))
TRIFORIUM = (-27, 30, 63)
CHAPEL_LOGGIA = (-173, 20, 160)


def roof_walk(g, plaque) -> None:
    # A tie gallery between two equal points on the existing helical stairs.
    # Both entries are on the roof side of the towers, well behind the facade.
    for x in range(-23, 24):
        g.box(x, x, 62, 62, 12, 14)[:] = c.WOOD if x % 5 else c.WOOD_END
        g.box(x, x, 63, 65, 12, 14)[:] = AIR
        if abs(x) > 17:
            g.box(x, x, 63, 65, 11, 11)[:] = t.BRICK
            g.box(x, x, 63, 65, 15, 15)[:] = t.BRICK
            continue
        g.put(x, 62, 11, t.TRIM)
        g.put(x, 62, 15, t.TRIM)
        if abs(x) >= 3:
            g.put(x, 63, 15, t.FENCE)
        g.put(x, 63, 11, t.FENCE)
        if x in (-16, -9, 0, 9, 16):
            for z in (11, 15):
                if z == 15 and x == 0:
                    continue
                g.put(x, 63, z, c.WOOD_END)
                g.put(x, 64, z, c.LANTERN)
    for x, y, z in ROOF_ENTRIES:
        # Keep the original treads and headroom immediately outside the doorway.
        g.box(x, x, y + 3, y + 3, 12, 14)[:] = t.CARVED
        plaque(g, (x, y + 2, 15), 'north', 'Сводовая тропа', 'К другой башне', color='orange')
        g.put(x, y + 1, 15, t.BASALT)

    # A narrow walk on the top of the stone vaults, not a second floor across
    # the whole nave. Preserve the original masonry ribs and external roof.
    for z in range(15, 101):
        wide = z in range(37, 44) or z in range(73, 81) or z >= 94
        width = 4 if wide else 2
        for x in range(-width, width + 1):
            g.put(x, 62, z, c.WOOD_END if abs(x) == width or z % 12 == 0 else c.WOOD)
            g.box(x, x, 63, 65, z, z)[:] = AIR
            if abs(x) == width:
                g.put(x, 63, z, t.FENCE)
                if z % 12 == 5 or (wide and z in (37, 43, 73, 80, 94, 100)):
                    g.put(x, 63, z, c.WOOD_END)
                    g.put(x, 64, z, c.LANTERN)
        if z in (37, 43, 73, 80, 94):
            for x in (-3, 3):
                g.put(x, 63, z, t.FENCE)
    for x in range(-3, 4):
        g.put(x, 63, 100, t.FENCE)
    for x, z in ((-3, 40), (3, 39), (-3, 76), (3, 78), (-3, 97)):
        g.put(x, 63, z, c.state('barrel', facing='up', open='false'))
        g.put(x, 64, z, c.WOOD_END if x < 0 else c.slab('dark_oak'))
    g.box(3, 3, 63, 63, 96, 98)[:] = c.slab('dark_oak')
    plaque(g, (-2, 64, 98), 'north', 'Конец настила', 'Осмотр сводов', color='light_gray', post=True)
    plaque(g, (-1, 64, 15), 'north', 'Над сводами нефа', 'К рёбрам нефа', color='orange', post=True)


def triforium(g, plaque) -> None:
    # The broad west eaves are below the new high walk; approach from the old
    # organ landing. Leave the new south end closed at the transept masonry.
    for z in range(9, 97):
        g.box(-28, -25, 30, 30, z, z)[:] = t.SLATE if z % 6 else t.TRIM
        g.box(-28, -25, 31, 33, z, z)[:] = AIR
        if z >= 22:
            g.put(-29, 30, z, t.TRIM)
            g.put(-24, 30, z, t.TRIM)
            g.put(-29, 31, z, t.WALL)
            g.put(-24, 31, z, t.WALL)
        if z in (19, 32, 47, 63, 79, 94):
            g.put(-29, 31, z, t.CARVED)
            g.put(-29, 32, z, s.SOUL)
    for x in range(-28, -24):
        g.put(x, 31, 97, t.WALL)
    for z in (32, 47, 63, 79, 94):
        g.put(-28, 31, z, c.slab('dark_oak'))
    plaque(g, (-27, 32, 16), 'north', 'Западный обход', 'Боковой неф', color='orange', post=True)
    plaque(g, (-26, 32, 95), 'north', 'Трансепт', 'Дальше — кладка', color='light_gray', post=True)


def chapel_loggia(g, plaque) -> None:
    # One compact switchback on the uninfected side of the rotunda. Keep the
    # dome, lancets and altar untouched; the added floor hugs the west side.
    beam = c.WOOD_END
    step = t.stair('dark_oak', 'south')
    for z in range(163, 171):
        y = z - 159
        g.box(-174, -173, y, y, z, z)[:] = step
        g.box(-174, -173, y + 1, y + 3, z, z)[:] = AIR
        g.put(-172, y, z, beam)
        g.put(-172, y + 1, z, t.FENCE)
    g.box(-176, -173, 11, 11, 171, 173)[:] = c.WOOD
    g.box(-176, -173, 12, 14, 171, 173)[:] = AIR
    g.box(-177, -172, 11, 11, 174, 174)[:] = beam
    g.box(-177, -172, 12, 12, 174, 174)[:] = t.FENCE
    g.box(-177, -177, 11, 11, 171, 173)[:] = beam
    g.box(-177, -177, 12, 12, 171, 173)[:] = t.FENCE
    g.box(-172, -172, 11, 11, 171, 173)[:] = beam
    g.box(-172, -172, 12, 12, 171, 173)[:] = t.FENCE
    step = t.stair('dark_oak', 'north')
    for z in range(162, 171):
        y = 182 - z
        g.box(-176, -175, y, y, z, z)[:] = step
        g.box(-176, -175, y + 1, y + 3, z, z)[:] = AIR
        for x in (-177, -174):
            if x == -174 and z <= 165:
                continue  # the gallery itself guards this side
            g.put(x, y, z, beam)
            g.put(x, y + 1, z, t.FENCE)
    for x, z in ((-176, 171), (-173, 173), (-172, 164)):
        g.box(x, x, 4, 10 if z > 170 else 5, z, z)[:] = beam
    g.box(-177, -171, 20, 20, 159, 161)[:] = c.WOOD
    g.box(-174, -171, 20, 20, 162, 165)[:] = c.WOOD
    for x in range(-177, -170):
        for z in range(159, 166 if x >= -174 else 162):
            guard = (z == 159 or x in (-177, -171) or z == 165 or
                     (z == 161 and x == -177) or (x == -174 and z > 162))
            if guard:
                g.put(x, 21, z, t.FENCE)
            else:
                g.box(x, x, 21, 23, z, z)[:] = AIR
    g.put(-172, 21, 164, c.slab('dark_oak'))
    g.put(-173, 21, 163, c.state('lectern', facing='north', has_book='false', powered='false'))
    for x, z in ((-177, 159), (-171, 159), (-171, 165)):
        g.put(x, 21, z, beam)
        g.put(x, 22, z, c.LANTERN)
    plaque(g, (-173, 6, 162), 'north', 'Ложа певчих', 'Лестница слева', color='orange', post=True)


def build(g, plaque) -> None:
    roof_walk(g, plaque)
    triforium(g, plaque)
    chapel_loggia(g, plaque)
