"""End-to-end test of the exported single-input workshop on vanilla Java 26.3."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from io import BytesIO
import json
from zipfile import ZipFile

from nbtlib import tag as nbt

from . import catacomb_logistics as l, catacomb_storage as s
from .build_catacomb_cathedral import OUTPUT as ABBEY_OUTPUT
from .vanilla_catacomb_test import SCHEMATIC_MIN, Y_LIFT, place_many, read_args, session, xyz
from .verify_storage import INVENTORIES, Store, counts, expect, merged, packed, stack, verify_drained, verify_outputs, verify_seeds

NAME = 'keepers_workshop'
PIECES = (
    ('farm_west', ((-170, -8, 33), (-67, 3, 36))),
    ('farm_south', ((-70, -7, 37), (-68, -4, 88))),
)
COLORS = ('white', 'orange', 'magenta', 'light_blue', 'yellow', 'lime', 'pink', 'gray',
          'light_gray', 'cyan', 'purple', 'blue', 'brown', 'green', 'red', 'black')
BOXES = ('shulker_box', *(f'{color}_shulker_box' for color in COLORS))
FARM_BATCH = 'keepers_workshop_test_batch'


@dataclass(frozen=True)
class Fixture:
    parts: tuple[tuple[str, tuple[l.Vec, l.Vec]], ...]
    presses: tuple[l.Press, ...]
    bus_length: int
    water_port: l.Vec
    origin: l.Vec = SCHEMATIC_MIN
    raw_dy: int = 0

    def raw(self, p):
        return l.add(p, (0, self.raw_dy, 0))

    def raw_inventory(self, server):
        state = server.inventories(self.raw(p) for p in INVENTORIES)
        return {p: state[self.raw(p)] for p in INVENTORIES}


ABBEY = Fixture(((NAME, l.ENGINE_BOUNDS), *PIECES), l.PRESSES, len(l.PRESS_PATH), l.FARM_PORT)


def compact_fixture():
    from . import build_compact_store as compact

    fixture = Fixture(((NAME, compact.BOUNDS),), compact.PRESSES, len(compact.PRESS_FEED) + len(compact.SORTER_FEED),
                      compact.WATER_PORT, compact.ORIGIN, compact.STORE_DY)
    return fixture, compact.OUTPUT


def verify_recipes(jar):
    """Read the shipped vanilla crafting recipes, not a hard-coded reverse table."""
    with ZipFile(jar) as wrapper:
        version = next(n for n in wrapper.namelist() if n.startswith('META-INF/versions/') and n.endswith('.jar'))
        with ZipFile(BytesIO(wrapper.read(version))) as vanilla:
            recipes = [json.loads(vanilla.read(n)) for n in vanilla.namelist()
                       if n.startswith('data/minecraft/recipe/') and n.endswith('.json')]
    one_to_nine, nine_to_one = set(), set()
    for recipe in recipes:
        kind = recipe['type']
        if kind == 'minecraft:crafting_shapeless':
            items = recipe['ingredients']
        elif kind == 'minecraft:crafting_shaped':
            items = [recipe['key'][c] for row in recipe['pattern'] for c in row if c != ' ']
        else:
            continue
        if not items or not isinstance(items[0], str) or any(x != items[0] for x in items):
            continue
        result = recipe['result']
        if len(items) == 1 and result.get('count', 1) == 9:
            one_to_nine.add((result['id'], items[0]))
        elif len(items) == 9 and result.get('count', 1) == 1:
            nine_to_one.add((items[0], result['id']))
    declared = {('minecraft:' + p.item, 'minecraft:' + p.product) for p in l.PRESSES}
    expect(declared, one_to_nine & nine_to_one, 'All homogeneous vanilla 9:1 reversible recipes')


def box(name, *cargo, title=None):
    item = stack(name, title=title)
    if cargo:
        item.setdefault('components', nbt.Compound())['minecraft:container'] = nbt.List[nbt.Compound](
            nbt.Compound(slot=nbt.Int(slot), item=sample) for slot, sample in enumerate(cargo))
    return item


def feed(server, *items):
    if len(items) > 54:
        raise ValueError('The one double chest has 54 slots')
    server.write({p: items[i::2] for i, p in enumerate(l.INTAKE)})


def active(server, p, state):
    return '] HERE' in server.commands(f'execute if block {xyz(p)} minecraft:{state} run say HERE')


def await_box(server, name):
    for _ in range(28):
        if active(server, l.UNLOADER.origin, name):
            return
        server.step(30)
    server.block(l.UNLOADER.origin, name)


def send_farm(server, *items, port=l.FARM_PORT):
    x, y, z = port
    server.commands(*(f'summon item {x+.5} {y+Y_LIFT+1.25} {z+.5} '
                      f'{{Tags:["{FARM_BATCH}"],Item:{v.snbt()}}}' for v in items))


def check_press_seeds(state, presses=l.PRESSES):
    for p in presses:
        seed = sorted(state[p.filter], key=lambda n: n['Slot'])
        expect([(str(v['id']), int(v['count'])) for v in seed],
               [(f'minecraft:{p.item}', s.SEED), *[(s.FILLER_ID, 1)] * 4], p.item + ' filter seed')
        for filler in seed[1:]:
            expect(filler['components']['minecraft:custom_data']['moonspire_spacer'], 1, 'Distinct filler')
        expect(merged(state, (p.reserve,)), counts(stack(p.item, s.RESERVE)), p.item + ' reserve')


def verify(server, *, strict, fixture=ABBEY):
    place_many(server, fixture.parts, strict=strict)
    server.step(90)
    for points, halves, side in ((l.INTAKE, ('left', 'right'), 'south'),
                                 (l.RETURN, ('right', 'left'), 'north'),
                                 (l.FARM_BUFFER, ('left', 'right'), 'north')):
        for p, half in zip(points, halves):
            server.block(p, f'chest[type={half},facing={side}]')
    for p in (l.RETURN_LAMP, l.INTAKE_FULL, l.FARM_LAMP, fixture.raw(s.OVERFLOW_LAMP)):
        server.block(p, 'redstone_lamp[lit=false]')
    server.block(l.UNLOADER.origin, 'piston_head')
    server.checked('unless entity @e[type=minecraft:item]', 'No loose items created during placement')
    press_positions = tuple(p for unit in fixture.presses for p in (unit.filter, unit.reserve, unit.origin, unit.buffer, unit.output))
    check_press_seeds(server.inventories(press_positions), fixture.presses)
    print('PASS cold placement: joined chests, calibrated references and 20 intact press filters', flush=True)

    # Fill using slot operations, which notify analogue detectors. A real
    # lever shuts the meter, preserving its empty cold-start inventory.
    lever = 'lever[face=floor,facing=east,powered={}]'
    server.commands(f'setblock {xyz(l.PAUSE)} minecraft:{lever.format("true")}')
    server.commands(*(f'item replace block {xyz(p)} container.{slot} with minecraft:stone 64'
                      for p in l.INTAKE for slot in range(27)))
    server.step(40)
    server.block(l.INTAKE_FULL, 'redstone_lamp[lit=true]')
    expect(merged(server.inventories((l.ENTRY_SPLIT.meter,)), (l.ENTRY_SPLIT.meter,)), Counter(), 'Paused meter')
    print('PASS pause switch and exact full-chest warning', flush=True)

    # Keep the player inlet blocked long enough to see the real pipe queue.
    # Clearing the inlet with the lever still paused isolates the water feed
    # from the two splitters and proves that it enters the same double chest.
    # Twelve distinct stacks fill both five-slot hoppers below the buffer
    # chest, then actually reach the level monitored by its comparator.
    sample = (stack('wheat', 18), stack('carrot', 12),
              *(stack('wheat_seeds', title=f'Партия {i:02}') for i in range(10)))
    feed_queue = (*l.FARM_BUFFER, *(l.step(l.FARM_BUFFER[0], 'down', n) for n in (1, 2)))
    send_farm(server, *sample, port=fixture.water_port)
    server.step(1300)
    expect(merged(server.inventories(feed_queue), feed_queue), counts(*sample), 'Farm batch waits in receiver')
    server.block(l.FARM_LAMP, 'redstone_lamp[lit=true]')
    server.block(l.INTAKE_FULL, 'redstone_lamp[lit=true]')
    server.checked(f'unless entity @e[type=minecraft:item,tag={FARM_BATCH}]', 'A backed-up inlet catches the whole water batch')
    server.empty(l.INTAKE)
    server.step(8 * sum(counts(*sample).values()) + 50)
    server.block(l.FARM_LAMP, 'redstone_lamp[lit=false]')
    server.block(l.INTAKE_FULL, 'redstone_lamp[lit=false]')
    expect(merged(server.inventories(l.INTAKE), l.INTAKE), counts(*sample), 'Farm receiver recovers into the same chest')
    server.empty(l.INTAKE)
    server.commands(f'setblock {xyz(l.PAUSE)} minecraft:{lever.format("false")}')
    print('PASS farm queue warning and drain after clearing the shared inlet', flush=True)

    # Start with a named full box and restart the world while it is actually
    # a block. The fixture uses real 26.3 item components, not a placed box.
    cargo = (stack('cobblestone', 63), stack('iron_ingot', 9), stack('gold_ingot', 18),
             stack('diamond', 9), stack('iron_pickaxe', title='Инструмент'))
    feed(server, box('red_shulker_box', *cargo, title='Партия 01'))
    await_box(server, 'red_shulker_box')
    server.step(100)
    server.block(l.UNLOADER.origin, 'red_shulker_box')
    live = sum(counts(*server.inventories((l.UNLOADER.origin,))[l.UNLOADER.origin]).values())
    assert 0 < live < sum(counts(*cargo).values()), live
    server.stop()
    server.start()
    server.block(l.UNLOADER.origin, 'red_shulker_box')

    raw = {p.item: 9 + i % 4 for i, p in enumerate(fixture.presses)}
    farm = (stack('wheat', 18), stack('carrot', 13), stack('potato', 7))
    extras = (stack('stone', 13), stack('quartz', 8), stack('iron_ingot', 2, title='Образец'), stack('water_bucket'))
    empty_boxes = tuple(box(name) for name in BOXES if name != 'red_shulker_box')
    lime_bonus = (stack('copper_ingot', 17), stack('blue_wool', 3))
    extras_boxes = (box('lime_shulker_box', *lime_bonus, title='Партия 02'),)
    feed(server, *(stack(k, n) for k, n in raw.items()), *empty_boxes, *extras, *extras_boxes)
    send_farm(server, *farm, port=fixture.water_port)
    whole = counts(*cargo, *farm, *extras, *lime_bonus, *(stack(k, v) for k, v in raw.items()))
    expected_boxes = counts(*empty_boxes, box('red_shulker_box', title='Партия 01'), box('lime_shulker_box', title='Партия 02'))
    # Both splitters work concurrently, but each meters transactions; leave
    # time for a full trek through both banks as well as the last box return.
    server.step(42 * sum(whole.values()) + 8 * (fixture.bus_length + len(s.PATH)) + 1600)
    press = server.inventories(press_positions)
    check_press_seeds(press, fixture.presses)
    for p in fixture.presses:
        n, rest = divmod(whole[p.item, ''], 9)
        expect(merged(press, (p.output,)), counts(stack(p.product, n)), p.item + ' compressed products')
        expect(merged(press, (p.origin,)), counts(stack(p.item, rest)) if rest else Counter(), p.item + ' remainder')
        expect(press[p.buffer], [], p.item + ' drained result hopper')
    pickup = server.inventories(l.RETURN)
    expect(merged(pickup, l.RETURN), expected_boxes, 'Every box returned with correct color and name')
    for items in pickup.values():
        assert not any(it.get('components', {}).get('minecraft:container') for it in items), items
    raw_result = fixture.raw_inventory(server)
    verify_outputs(raw_result, {'cobblestone': 63, 'stone': 13, 'quartz': 8})
    verify_drained(raw_result)
    verify_seeds(raw_result)
    expect(merged(raw_result, s.OVERFLOW), counts(farm[1], farm[2], extras[2], extras[3], cargo[-1], lime_bonus[-1]),
           'Unmatched loose items and named cargo preserved')
    expect(merged(server.inventories((*l.INTAKE, *l.FARM_BUFFER)), (*l.INTAKE, *l.FARM_BUFFER)), Counter(), 'Empty common queue')
    server.block(l.FARM_LAMP, 'redstone_lamp[lit=false]')
    server.block(l.RETURN_LAMP, 'redstone_lamp[lit=true]')
    server.block(fixture.raw(s.OVERFLOW_LAMP), 'redstone_lamp[lit=true]')
    server.block(l.UNLOADER.origin, 'piston_head')
    server.checked('unless entity @e[type=minecraft:item]', 'No lost pipe, craft or piston drops')
    print('PASS all 20 recipes, mixed loose items, all 17 box colors, named cargo, restart in a live box, water inlet', flush=True)

    # Pre-fill the return conduit and a result lane; a full rack must apply
    # inventory backpressure rather than spilling entities onto the ground.
    iron, copper = fixture.presses[:2]
    old_iron = merged(press, (iron.origin,))[iron.item, '']
    old_copper = merged(press, (copper.output,))[copper.product, '']
    held = 'black_shulker_box'
    server.write({**{p: [box(held)] * 27 for p in l.RETURN},
                  **{p: [box(held)] * 5 for p in l.BOX_RETURN_PATH[:-1]},
                  iron.output: packed(iron.product, 27), iron.buffer: packed(iron.product, 5)})
    feed(server, stack(iron.item, 20), stack(copper.item, 9), box('pink_shulker_box', title='Ожидание'))
    server.step(3800)
    held_at = (l.RETURN_SPLIT.boxes, *l.BOX_RETURN_PATH)
    wait = server.inventories((*held_at, iron.origin, copper.output))
    expect(merged(wait, held_at)['pink_shulker_box', 'Ожидание'], 1, 'Return waiting safely')
    expect(merged(wait, (iron.origin,)), counts(stack(iron.item, old_iron + 20)), 'Full press holds input')
    expect(merged(wait, (copper.output,)), counts(stack(copper.product, old_copper + 1)), 'Adjacent press still working')
    server.block(l.add(iron.origin, (3, -1, 1)), 'redstone_lamp[lit=true]')
    server.checked('unless entity @e[type=minecraft:item]', 'No drops while both outputs are blocked')
    server.empty((*l.RETURN, iron.output))
    server.step(8 * 320 + 260)
    resume = server.inventories((*l.RETURN, iron.output, iron.origin))
    expect(merged(resume, l.RETURN)['pink_shulker_box', 'Ожидание'], 1, 'Return resumes on pickup')
    n, rest = divmod(old_iron + 20, 9)
    expect(merged(resume, (iron.output,)), counts(stack(iron.product, 320 + n)), 'Press resumes on pickup')
    expect(merged(resume, (iron.origin,)), counts(stack(iron.item, rest)) if rest else Counter(), 'Press remainder after recovery')
    server.block(l.add(iron.origin, (3, -1, 1)), 'redstone_lamp[lit=false]')
    print('PASS blocked return and blocked press recover automatically; no drops and no neighbour interference', flush=True)
    verify_raw_filters(server, fixture)


def verify_raw_filters(server, fixture):
    # Exercise even the old raw lanes whose ordinary inputs are now caught
    # by a press. Inject behind the presses in the test, not at a player port.
    before = fixture.raw_inventory(server)
    payload = tuple(stack(cell.item, 2 + i % 6) for i, cell in enumerate(s.CELLS))
    server.write({fixture.raw(p): payload[i::2] for i, p in enumerate(s.INTAKE)})
    server.step(8 * (sum(int(v['count']) for v in payload) + len(s.PATH)) + 200)
    after = fixture.raw_inventory(server)
    for cell, sample in zip(s.CELLS, payload):
        expect(merged(after, cell.barrels), merged(before, cell.barrels) + counts(sample), cell.item + ' raw lane')
    verify_drained(after)
    verify_seeds(after)
    expect(merged(after, s.OVERFLOW), merged(before, s.OVERFLOW), 'No new surplus from the 36 raw lanes')
    server.checked('unless entity @e[type=minecraft:item]', 'No item drops from the raw filter lanes')
    print('PASS all 36 raw lanes, with unchanged overflow and filter seeds', flush=True)


def verify_full_shulker(server, *, strict, fixture=ABBEY):
    """Conserve all 27 stacks, from one filled box to both kinds of storage."""
    place_many(server, fixture.parts, strict=strict)
    server.step(90)
    started = server.now()
    name, title = 'blue_shulker_box', 'Полная партия'
    feed(server, box(name, *packed('cobblestone', 20), *packed('iron_ingot', 7), title=title))
    server.step(1000)
    server.block(l.UNLOADER.origin, name)
    expect(merged(server.inventories(l.RETURN), l.RETURN), Counter(), 'Shulker remains until empty')
    for _ in range(22):
        server.step(4000)
        pickup = server.inventories(l.RETURN)
        if result := merged(pickup, l.RETURN):
            expect(result, counts(box(name, title=title)), 'Exact named return')
            assert not any(v.get('components', {}).get('minecraft:container') for half in pickup.values() for v in half)
            print(f'PASS full shulker returned empty by tick {server.now() - started}', flush=True)
            break
    else:
        raise AssertionError('The full shulker did not return')

    iron = fixture.presses[0]
    cobble = next(cell for cell in s.CELLS if cell.item == 'cobblestone')
    watch = (*(fixture.raw(p) for p in cobble.barrels), iron.output, iron.origin)
    products = counts(stack('cobblestone', 20*64), stack('iron_block', 49), stack('iron_ingot', 7))
    for _ in range(20):
        state = server.inventories(watch)
        if merged(state, watch) == products:
            break
        server.step(4000)
    expect(merged(server.inventories(watch), watch), products, 'All 1,728 items processed')
    state = fixture.raw_inventory(server)
    verify_outputs(state, {'cobblestone': 20*64})
    verify_drained(state)
    verify_seeds(state)
    check_press_seeds(server.inventories(p for u in fixture.presses for p in (u.filter, u.reserve)), fixture.presses)
    expect(merged(state, s.OVERFLOW), Counter(), 'No surplus from this batch')
    server.checked('unless entity @e[type=minecraft:item]', 'No lingering drops')
    elapsed = server.now() - started
    print(f'PASS 1,280 cobblestone sorted; 49 iron blocks + 7 ingots; done by tick {elapsed} '
          f'({elapsed / 1200:.1f} minutes at 20 TPS)', flush=True)


def main():
    def options(parser):
        parser.add_argument('--full-shulker', action='store_true', help='Check a 27-stack mixed payload instead of the standard run')
        parser.add_argument('--compact', action='store_true', help='Place the complete standalone module instead of the abbey crops')

    args = read_args(__doc__, configure=options, default_schematic=None)
    verify_recipes(args.server)
    fixture, default = compact_fixture() if args.compact else (ABBEY, ABBEY_OUTPUT)
    args.schematic = args.schematic or default
    scenario = verify_full_shulker if args.full_shulker else verify
    (name, bounds), *extra = fixture.parts
    with session(args, name, bounds, Store, rate=600 if args.full_shulker else 420,
                 extra=extra, schematic_min=fixture.origin) as server:
        scenario(server, strict=not args.neighbor_updates, fixture=fixture)


if __name__ == '__main__':
    main()
