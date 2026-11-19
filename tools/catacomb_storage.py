"""The Keepers' Store: two banks of preset, overflow-protected Java item filters."""

from __future__ import annotations

from dataclasses import dataclass

from nbtlib import tag as nbt

from . import build_throne_cathedral as t

c, s, a = t.c, t.s, t.a
FLOOR = -35  # Same level as the west arm of the catacomb ring.
FILTER_Y = FLOOR + 4
BUS_Y = FILTER_Y + 1
NORTH_Z, SOUTH_Z = 144, 156
WEST, EAST = -59, -40
GAPS = (-53, -46)
WALL_W, WALL_E = -65, -37
WALL_N, WALL_S = NORTH_Z - 5, SOUTH_Z + 5
ENGINE_BOUNDS = ((-72, FLOOR - 2, WALL_N), (-36, FLOOR + 11, WALL_S))
RING_TURN = (-74, FLOOR, 149)
ENTRY = (-65, FLOOR, 149)
RECEIVING = (-62, FLOOR + 3, 146)  # Floor coordinates for the walking audit.
AISLE = (-56, FLOOR, 150)
FAR_AISLE = (-42, FLOOR, 150)
INTAKE = ((-62, BUS_Y + 1, NORTH_Z), (-61, BUS_Y + 1, NORTH_Z))
OVERFLOW_X = -62
OVERFLOW = tuple((x, y, SOUTH_Z - 1) for y in (FLOOR + 3, FLOOR + 1) for x in (-62, -61))
OVERFLOW_LAMP = (-64, FLOOR + 1, SOUTH_Z - 1)
OVERFLOW_COMPARE = (-63, FLOOR + 1, SOUTH_Z - 1)
OVERFLOW_SINK = ((OVERFLOW_X, BUS_Y - 1, SOUTH_Z), (OVERFLOW_X, FLOOR + 3, SOUTH_Z),
                 (OVERFLOW_X, FLOOR + 2, SOUTH_Z - 1))
FILLER_NAME = 'Метка кладовой'
FILLER_ID = 'minecraft:paper'
SEED = 41
RESERVE = 5 * 64

AIR, BRICK, TRIM = t.AIR, t.BRICK, t.TRIM
BED = c.state('polished_deepslate')
TILE = c.state('deepslate_tiles')
RELAY = c.state('deepslate_bricks')
PIER = c.state('chiseled_tuff_bricks')
METAL = a.BRASS
PATINA = a.VERDIGRIS
GLASS = c.state('glass')
PLANKS, BEAM = c.WOOD, c.WOOD_END
LANTERN = s.SOUL_HANGING
RUNNER = c.state('gray_carpet')
BORDER = c.state('brown_carpet')


# The sequence is also the order of the hopper bus. Only 64-stack, ordinary
# (unmodified) versions of these items match. Paper tests the named spacers.
GROUPS = (
    ('Кладка', (
        ('cobblestone', 'Булыжник'), ('stone', 'Камень'), ('stone_bricks', 'Каменные', 'кирпичи'),
        ('cobbled_deepslate', 'Дроблёный', 'глуб. сланец'), ('deepslate_bricks', 'Сланцевые', 'кирпичи'),
        ('deepslate_tiles', 'Сланцевые', 'плитки'),
    )),
    ('Камень глубин', (
        ('tuff', 'Туф'), ('tuff_bricks', 'Туфовые', 'кирпичи'), ('polished_tuff', 'Полир.', 'туф'),
        ('blackstone', 'Чернит'), ('polished_blackstone_bricks', 'Чернитные', 'кирпичи'), ('basalt', 'Базальт'),
    )),
    ('Земля и стекло', (
        ('dirt', 'Земля'), ('gravel', 'Гравий'), ('sand', 'Песок'), ('glass', 'Стекло'),
        ('calcite', 'Кальцит'), ('sculk', 'Скалк'),
    )),
    ('Плавильня', (
        ('iron_ingot', 'Железный', 'слиток'), ('copper_ingot', 'Медный', 'слиток'), ('gold_ingot', 'Золотой', 'слиток'),
        ('raw_iron', 'Рудное', 'железо'), ('raw_copper', 'Рудная', 'медь'), ('coal', 'Уголь'),
    )),
    ('Редкие запасы', (
        ('redstone', 'Редстоун'), ('lapis_lazuli', 'Лазурит'), ('diamond', 'Алмаз'),
        ('emerald', 'Изумруд'), ('quartz', 'Кварц'), ('amethyst_shard', 'Осколок', 'аметиста'),
    )),
    ('Припасы', (
        ('oak_log', 'Дубовое', 'бревно'), ('dark_oak_log', 'Тёмный дуб', 'бревно'), ('spruce_log', 'Еловое', 'бревно'),
        ('dark_oak_planks', 'Тёмный дуб', 'доски'), ('paper', 'Бумага'), ('bone', 'Кость'),
    )),
)


@dataclass(frozen=True)
class Cell:
    x: int
    z: int
    item: str
    label: tuple[str, ...]

    @property
    def direction(self) -> int:
        return -1 if self.z == NORTH_Z else 1

    @property
    def back(self) -> str:
        return 'north' if self.direction < 0 else 'south'

    @property
    def front(self) -> str:
        return 'south' if self.direction < 0 else 'north'

    def at(self, dy: int = 0, dz: int = 0) -> tuple[int, int, int]:
        return self.x, FILTER_Y + dy, self.z + dz * self.direction

    @property
    def barrels(self) -> tuple[tuple[int, int, int], ...]:
        return self.at(-1, -1), self.at(-3, -1)

    @property
    def delivery(self) -> tuple[tuple[int, int, int], ...]:
        return self.at(-1), self.at(-2, -1)

    @property
    def label_pos(self) -> tuple[int, int, int]:
        return self.at(0, -2)


COLUMNS = tuple(x for x in range(WEST, EAST + 1) if x not in GAPS)
CELLS = tuple(Cell(x, z, item[0], tuple(item[1:]))
              for groups, z, xs in ((GROUPS[:3], NORTH_Z, COLUMNS), (GROUPS[3:], SOUTH_Z, COLUMNS[::-1]))
              for x, item in zip(xs, (entry for _, items in groups for entry in items)))
BEND = EAST + 2
PATH = (
    *((x, BUS_Y, NORTH_Z) for x in range(INTAKE[0][0], BEND + 1)),
    *((BEND, BUS_Y, z) for z in range(NORTH_Z + 1, SOUTH_Z + 1)),
    *((x, BUS_Y, SOUTH_Z) for x in range(BEND - 1, OVERFLOW_X - 1, -1)),
)


def hopper(facing: str, *, enabled: bool = True) -> int:
    return c.state('hopper', facing=facing, enabled=str(enabled).lower())


def chest(facing: str, half: str) -> int:
    return c.state('chest', facing=facing, type=half, waterlogged='false')


def barrel(facing: str) -> int:
    return c.state('barrel', facing=facing, open='false')


def item(slot: int, name: str, count: int, *, spacer: bool = False) -> nbt.Compound:
    data = nbt.Compound(Slot=nbt.Byte(slot), id=nbt.String(name), count=nbt.Int(count))
    if spacer:
        data['components'] = nbt.Compound({'minecraft:custom_name': nbt.String(FILLER_NAME),
                                           'minecraft:custom_data': nbt.Compound(moonspire_spacer=nbt.Byte(1))})
    return data


def inventory(kind: str, items=()) -> nbt.Compound:
    return nbt.Compound(id=nbt.String(f'minecraft:{kind}'), Items=nbt.List[nbt.Compound](items))


def inventory_data() -> dict[tuple[int, int, int], nbt.Compound]:
    result = {p: inventory('hopper') for p in (*PATH, *OVERFLOW_SINK)}
    for p in (*INTAKE, *OVERFLOW):
        result[p] = inventory('chest')
    for cell in CELLS:
        result[cell.at()] = inventory('hopper', (item(0, 'minecraft:' + cell.item, SEED),
                                                  *(item(i, FILLER_ID, 1, spacer=True) for i in range(1, 5))))
        result[cell.delivery[0]] = inventory('hopper', (item(i, 'minecraft:' + cell.item, 64) for i in range(5)))
        result[cell.delivery[1]] = inventory('hopper')
        result[cell.at(0, 1)] = nbt.Compound(id=nbt.String('minecraft:comparator'), OutputSignal=nbt.Int(2))
        for p in cell.barrels:
            result[p] = inventory('barrel')
    result[OVERFLOW_COMPARE] = nbt.Compound(id=nbt.String('minecraft:comparator'), OutputSignal=nbt.Int(0))
    return result


def rooms(g, plaque) -> None:
    # Reclaim solid overburden between the west corridor, the names gallery
    # and the old crypt stair. Neither the vaults nor the incline share a wall.
    y = FLOOR
    g.box(WALL_W, WALL_E, y - 2, y, WALL_N, WALL_S)[:] = BRICK
    g.box(WALL_W + 1, WALL_E - 1, y + 1, y + 9, WALL_N + 1, WALL_S - 1)[:] = AIR
    g.box(WALL_W, WALL_E, y + 10, y + 10, WALL_N, WALL_S)[:] = BRICK
    for x in (WALL_W, WALL_E):
        g.box(x, x, y + 1, y + 9, WALL_N, WALL_S)[:] = BRICK
    for z in (WALL_N, WALL_S):
        g.box(WALL_W + 1, WALL_E - 1, y + 1, y + 9, z, z)[:] = BRICK

    # Entry level with the loop, straight into the barrel aisle. Layered
    # pointed bays echo the two adjacent vaults without exposing redstone.
    g.box(-71, WALL_W, y, y, 147, 151)[:] = BED
    for z in range(147, 152):
        h = 5 + (2 - abs(z - 149))
        g.box(-71, WALL_W, y + 1, y + h - 1, z, z)[:] = AIR
        g.box(-70, WALL_W, y + h, y + h, z, z)[:] = TRIM
    for x in (-69, WALL_W):
        for z in (146, 152):
            g.box(x, x, y + 1, y + 5, z, z)[:] = PIER
            g.put(x, y + 2, z, BED)
            g.put(x, y + 4, z, METAL)
        g.put(x, y + 6, 149, LANTERN)
    plaque(g, (-70, y + 3, 146), 'west', 'Автосклад', 'Кладовая', 'хранителей', color='orange')
    plaque(g, (-66, y + 3, 152), 'west', 'Бочки прямо', 'Приёмка слева', color='white')

    g.box(WALL_W + 1, EAST, y, y, NORTH_Z + 1, SOUTH_Z - 1)[:] = TILE
    g.box(WALL_W + 1, EAST, y + 1, y + 1, 149, 149)[:] = RUNNER
    for z in (148, 150):
        g.box(WALL_W + 1, EAST, y + 1, y + 1, z, z)[:] = BORDER
    for j, x in enumerate((-60, *GAPS, -39)):
        for z, side in ((146, 'north'), (154, 'south')):
            g.box(x, x, y + 1, y + 7, z, z)[:] = BRICK
            g.put(x, y + 1, z, PIER)
            g.put(x, y + 5, z, METAL if j % 2 else PATINA)
            dz = 1 if z == 146 else -1
            g.put(x, y + 6, z + dz, t.stair('tuff_brick', side, 'top'))
            g.put(x, y + 7, z + 2*dz, PIER)
            g.put(x, y + 8, z + 3*dz, TRIM)
        g.box(x, x, y + 9, y + 9, 146, 154)[:] = TRIM
        g.put(x, y + 8, 150, LANTERN)
    for x in (-64, -57, -50, -43):
        g.put(x, y + 9, 149, PIER)
        g.put(x, y + 8, 149, LANTERN)

    # Keep the filter stacks behind the cabinet glazing. Only the collector
    # chests and the two barrels in each bay are used in normal operation.
    for z in (NORTH_Z + 1, SOUTH_Z - 1):
        g.box(WALL_W + 1, WALL_E - 1, y + 1, y + 9, z, z)[:] = BRICK
        g.box(WEST, EAST, y + 6, y + 6, z, z)[:] = BEAM
        g.box(WEST, EAST, y + 7, y + 7, z, z)[:] = TRIM
    for j, (group, _) in enumerate(GROUPS):
        side = j < 3
        xs = COLUMNS if side else COLUMNS[::-1]
        plaque(g, (xs[j % 3 * 6 + 2], y + 6, 146 if side else 154),
               'south' if side else 'north', group, color='orange')

    # A short stair to a separate, railed intake platform. The main aisle
    # continues at ring level past its foot.
    for z in range(148, 151):
        h = 151 - z
        g.box(-63, -62, y + 1, y + h, z, z)[:] = PLANKS
        g.box(-63, -62, y + h, y + h, z, z)[:] = t.stair('dark_oak', 'north')
    g.box(-64, -61, y + 3, y + 3, 145, 147)[:] = BEAM
    g.box(-64, -61, y + 4, y + 8, 145, 147)[:] = AIR
    for z in (145, 146):
        for x in (-64, -61):
            g.put(x, y + 4, z, t.FENCE)
    for x in (-64, -61):
        g.put(x, y + 4, 147, BEAM)
        g.put(x, y + 5, 147, c.LANTERN)
    g.put(-63, y + 4, 147, BORDER)
    g.box(-64, -60, y + 1, y + 8, NORTH_Z, NORTH_Z)[:] = BRICK
    g.box(-64, -60, y + 4, y + 4, NORTH_Z, NORTH_Z)[:] = PIER
    g.box(-62, -61, BUS_Y + 1, y + 8, NORTH_Z, NORTH_Z)[:] = AIR
    g.put(-62, y + 8, NORTH_Z, BEAM)
    plaque(g, (-62, y + 8, NORTH_Z + 1), 'south', 'Приёмка', 'Вещи сюда', color='orange')
    plaque(g, (-60, y + 3, 146), 'east', 'В бочках', 'свой предмет', color='white', post=True)

    # Overflow collected by two joined chests, with a stock indicator.
    g.box(-63, -61, y + 5, y + 5, 155, 155)[:] = BEAM
    g.box(-62, -61, y + 4, y + 4, 155, 155)[:] = AIR  # lid clearance on both halves
    g.put(-61, y + 2, 155, AIR)  # the other half has a non-occluding hopper above it
    g.put(-63, y + 2, 155, GLASS)  # keep the comparator from becoming an exposed shelf
    plaque(g, (-62, y + 5, 154), 'north', 'Остаток', 'Лампа: есть вещи', color='orange')

    # Glazed sightline onto the U-turn. The end wall secures the hopper bus.
    end = BEND - 1
    g.box(end, end, y + 1, y + 9, 147, 153)[:] = BRICK
    g.box(end, end, y + 3, y + 6, 148, 152)[:] = GLASS
    g.box(end, end, y + 2, y + 2, 148, 152)[:] = PATINA
    g.put(end, y + 7, 150, PIER)
    plaque(g, (end - 1, y + 7, 150), 'west', 'Поворот линии', 'Подача в бочки', color='orange')


def place_cell(g, cell: Cell, plaque) -> None:
    p = cell.at
    # A 1-wide impulse sorter. At rest the comparator outputs 2; at 42 target
    # items it outputs 3, releasing the extraction hopper through a torch.
    for dy, dz in ((-1, 1), (-1, 2), (-1, 3), (-2, 2), (-2, 4), (-3, 3)):
        g.put(*p(dy, dz), RELAY)
    g.put(*p(0, 4), AIR)  # clearance at the lower dust step
    g.put(*p(), hopper(cell.back))
    # Reserve hopper: vanilla pushes before pulling. Starting full, it
    # only removes a filter item if it managed to make space by depositing
    # an identical one into the output. This also handles a single item
    # and full outputs without an unlocked hopper under the locking torch.
    g.put(*p(-1), hopper(cell.front, enabled=False))
    g.put(*p(0, 1), c.state('comparator', facing=cell.front, mode='compare', powered='true'))
    g.put(*p(-2, 3), c.state('repeater', facing=cell.back, delay='1', locked='false', powered='false'))
    g.put(*p(-2, 1), c.state('redstone_wall_torch', facing=cell.front, lit='true'))
    for dy, dz, strength in ((0, 2, 2), (0, 3, 1), (-1, 4, 0)):
        arms = {'east': 'side' if cell.x + 1 in COLUMNS else 'none',
                'west': 'side' if cell.x - 1 in COLUMNS else 'none',
                cell.front: 'up' if dz == 4 else 'side', cell.back: 'none' if dz == 4 else 'side'}
        g.put(*p(dy, dz), c.state('redstone_wire', power=str(strength), **arms))

    for pos in cell.barrels:
        g.put(*pos, barrel(cell.front))
    g.put(*p(-2, -1), hopper('down'))
    g.put(*p(0, -1), BEAM)
    plaque(g, cell.label_pos, cell.front, *cell.label,
           color='orange' if cell.z == NORTH_Z else 'white')
    # Closed bays above the wood lintel, lit from the main aisle.
    g.put(*p(1, -1), GLASS)
    g.put(*p(2, -1), PATINA if cell.x % 6 == 0 else TRIM)


def build(g, plaque) -> None:
    rooms(g, plaque)
    machinery(g, plaque)


def machinery(g, plaque) -> None:
    """Install the filter chain and its output fronts without the vault shell."""
    for cell in CELLS:
        place_cell(g, cell, plaque)
    for here, after in zip(PATH, PATH[1:]):
        g.put(*here, hopper(t.direction(after[0] - here[0], after[2] - here[2])))
    g.put(*PATH[-1], hopper('down'))
    for p, half in zip(INTAKE, ('right', 'left')):
        g.put(*p, chest('south', half))
    for p, half in zip(OVERFLOW, ('left', 'right') * 2):
        g.put(*p, chest('north', half))
    for p in OVERFLOW_SINK:
        g.put(*p, hopper('north' if p[1] == FLOOR + 3 else 'down'))
    g.put(*OVERFLOW_COMPARE, c.state('comparator', facing='east', mode='compare', powered='false'))
    g.put(*OVERFLOW_LAMP, c.state('redstone_lamp', lit='false'))