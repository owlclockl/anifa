"""Run the new export and a comparable baseline on an official Java 26.3 server.

Console commands only set up and observe fixtures. The schematic has no
commands, creative mode triggers, or datapack functions in its item path.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import nbtlib
from nbtlib import tag as nbt

from . import build_compact_store as old, build_universal_store as u
from . import catacomb_logistics as l, catacomb_storage as s
from .vanilla_catacomb_test import place, read_args, session, xyz
from .verify_logistics import box, send_farm, verify_recipes
from .verify_storage import Store, counts, expect, merged, stack

NAME = 'warehouse_universal'
CHESTS = tuple(p for chest in u.CABINETS for p in chest.pair)
PORTS = (*u.INTAKE, *(l.step(p, 'up') for p in u.BOX_INPUTS), u.RAW_INPUT)


def cold(t, strict, schematic):
    place(t, NAME, u.BOUNDS, strict=strict)
    # Native 26.3 structure placement does not reconstruct passengers.
    # Use the exact export's entity tags in the fixture, as with test items.
    region = nbtlib.load(schematic)['Regions']['Cathedral']
    summon = []
    for entry in region['Entities']:
        point = tuple(float(x) for x in entry['Pos'])
        tag = nbt.Compound({k: v for k, v in entry.items() if k not in ('id', 'Pos')})
        summon.append(f"summon {entry['id']} {xyz(point)} {tag.snbt()}")
    t.commands(*summon)
    t.step(60)
    expected = u.CART_COUNT * len(u.CELLS)
    for kind in ('minecart', 'copper_golem'):
        result = t.commands(f'execute if entity @e[type=minecraft:{kind}]')
        if f'count: {expected}' not in result.lower():
            raise AssertionError(f'Expected {expected} {kind}: {result}')
    t.checked('unless entity @e[type=minecraft:item]', 'No mechanism blocks dropped on load')
    for cell in u.CELLS:
        t.block(cell.center, 'rail[shape=north_south]')
        for pos in cell.inputs:
            t.block(pos, u.WAXED)
    seeded = t.inventories(CHESTS)
    for cabinet in u.CABINETS:
        expect(merged(seeded, cabinet.pair), counts(*(stack(i) for i in cabinet.items)), f'{cabinet.label}: installed seeds')
    print(f'PASS cold placement: {expected} mounted golems and all {len(u.BY_ID)} seed IDs', flush=True)
    return seeded


def expected_by_bin(payload):
    result = defaultdict(Counter)
    for item in payload:
        name = str(item['id']).removeprefix('minecraft:')
        result[u.BY_ID[name]].update(counts(item))
    return result


def wait_for_storage(t, seeded, payload, *, limit, period=200, trace=False):
    expected = expected_by_bin(payload)
    targets = tuple(p for cabinet in expected for p in cabinet.pair)
    start = t.now()
    for elapsed in range(period, limit + 1, period):
        t.step(period)
        inv = t.inventories((*targets, *u.OVERFLOW))
        progress = sum(sum((merged(inv, c.pair) - merged(seeded, c.pair)).values()) for c in expected)
        if trace and (elapsed % (5 * period) == 0 or elapsed == limit):
            print(f'  t={t.now()-start}: {progress}/{sum(counts(*payload).values())}', flush=True)
        extra = merged(inv, u.OVERFLOW)
        if extra:
            raise AssertionError(f'Cargo reached fallback with open category bins: {extra}')
        if all(merged(inv, c.pair) == merged(seeded, c.pair) + want for c, want in expected.items()):
            return t.now() - start
    for cabinet, want in expected.items():
        got = merged(inv, cabinet.pair) - merged(seeded, cabinet.pair)
        if want != got:
            print(f'{cabinet.label} {cabinet.near}: expected {want}, got {got}', flush=True)
    print('inlet/relay:', t.inventories(tuple(p for cell in u.CELLS for p in (*cell.inputs, *cell.relay))), flush=True)
    raise AssertionError(f'Not all cargo was stored by {limit} ticks')


def verify(t, strict, schematic):
    seeded = cold(t, strict, schematic)
    # Include 16-stack items, component variants, tools and a late category.
    sample = [stack(c.items[0], title='Контроль') for c in u.CABINETS]
    potion = stack('potion', title='Особое зелье')
    potion['components']['minecraft:potion_contents'] = nbt.Compound(potion=nbt.String('minecraft:healing'))
    tool = stack('diamond_pickaxe', title='Инструмент')
    tool['components']['minecraft:enchantments'] = nbt.Compound({'minecraft:efficiency': nbt.Int(2)})
    sample.extend([stack('ender_pearl', 16, title='Стак 16'), potion, tool, stack('written_book', title='Книга')])
    for i, pos in enumerate(u.INTAKE):
        # Up to 54 slots, including mixed 64-, 16- and 1-stack IDs.
        t.write({pos: sample[i:54:2]})
    farm = [stack('cobblestone', 32, title='С водоввода'), *sample[54:]]
    send_farm(t, *farm, port=u.WATER_PORT)
    taken = wait_for_storage(t, seeded, [*sample, farm[0]], limit=20000, period=400, trace=True)
    print(f'PASS ordinary, water & all {len(u.CABINETS)} categories: {taken} ticks', flush=True)
    seeded = t.inventories(CHESTS)
    for item, component in ((potion, 'minecraft:potion_contents'), (tool, 'minecraft:enchantments')):
        cabinet = u.BY_ID[str(item['id']).removeprefix('minecraft:')]
        recovered = next(v for p in cabinet.pair for v in seeded[p] if counts(v) == counts(item))
        expect(recovered['components'][component], item['components'][component], f'{cabinet.label}: component retained')

    cargo = [stack('oak_log', 32, title='Груз 1'), stack('iron_helmet', title='Груз 2')]
    boxes = [box('red_shulker_box', cargo[0], title='Первая'), box('white_shulker_box', cargo[1], title='Вторая')]
    t.write({p: [item] for p, item in zip(PORTS[2:4], boxes)})
    returns = [stack('red_shulker_box', title='Первая'), stack('white_shulker_box', title='Вторая')]
    taken = wait_for_storage(t, seeded, [*cargo, *returns], limit=12000, period=200)
    shulkers = t.inventories(u.BY_ID['shulker_box'].pair)
    for item in shulkers.values():
        for v in item:
            if str(v.get('components', {}).get('minecraft:custom_name', '')) in ('Первая', 'Вторая'):
                expect(v.get('components', {}).get('minecraft:container'), None, 'Returned box is empty')
    print(f'PASS both shulker unloaders and named empty returns: {taken} ticks', flush=True)
    seeded = t.inventories(CHESTS)

    all_ingredients = [stack(p.item, 9) for p in u.PRESSES]
    all_products = [stack(p.product) for p in u.PRESSES]
    # Products include the three ingots, also inputs to other crafters. They
    # must not occupy those crafters again. One incomplete recipe stays put.
    all_ingredients[0]['count'] = nbt.Int(10)
    off_recipe = stack('granite', 3, title='Мимо упаковки')
    t.write({u.RAW_INPUT: [*all_ingredients, off_recipe]})
    taken = wait_for_storage(t, seeded, [*all_products, off_recipe], limit=12000, period=200, trace=True)
    state = t.inventories(tuple(x for p in u.PRESSES for x in (p.origin, p.filter, p.reserve)))
    for p in u.PRESSES:
        expect(merged(state, (p.filter,)), counts(stack(p.item), stack('paper', u.SPACER_COUNT * 4, title=u.SPACER_TITLE)), p.item + ' seed')
        expect(merged(state, (p.reserve,)), counts(stack(p.item)), p.item + ' priming item')
        expect(merged(state, (p.origin,)), counts(stack('iron_ingot')) if p == u.PRESSES[0] else Counter(), p.item + ' remainder')
    print(f'PASS all 20 recipes, 1 retained ingredient, every product in its shared section: {taken} ticks', flush=True)
    t.checked('unless entity @e[type=minecraft:item]', 'All cargo accounted for; no remaining drops')
    verify_overflow(t)


def verify_overflow(t):
    destination = u.BY_ID['cobblestone'].pair
    old_items = t.inventories(CHESTS)
    t.write({p: [*old_items[p], *([stack('cobblestone', 64)] * (27-len(old_items[p])))] for p in destination})
    item = stack('cobblestone', 16, title='Контроль переполнения')
    t.write({u.INTAKE[0]: [item]})
    for _ in range(28):
        t.step(400)
        if merged(t.inventories(u.OVERFLOW), u.OVERFLOW) == counts(item):
            break
    else:
        raise AssertionError('Full destination did not release the 16 excess items into overflow')
    indicators = [l.step(p, 'east', 2) for p in u.OVERFLOW]
    assert any('] FULL' in t.commands(f'execute if block {xyz(p)} minecraft:redstone_lamp[lit=true] run say FULL') for p in indicators)
    t.empty(u.OVERFLOW)
    t.write({p: old_items[p] for p in destination} | {u.INTAKE[1]: [item]})
    wait_for_storage(t, old_items, [item], limit=4000, period=200)
    for p in indicators:
        t.block(p, 'redstone_lamp[lit=false]')
    print('PASS overflow, warning lamp, and successful refeed after freeing the cabinet', flush=True)


def benchmark(t, strict, batch, *, baseline, schematic):
    if baseline:
        place(t, NAME, old.BOUNDS, strict=strict)
        t.step(60)
        storage = {cell.item: tuple(old.raw(p) for p in cell.barrels) for cell in s.CELLS}
        seeded = None
    else:
        seeded = cold(t, strict, schematic)
    mixed = ([stack('cobblestone', 64)] * 16 + [stack('dirt', 64)] * 4 + [stack('oak_log', 64)] * 4)
    shulker = [stack('cobblestone', 64)] * 20 + [stack('oak_log', 64)] * 7
    water = [stack('cobblestone', 64)] * 8
    port = old.WATER_PORT if baseline else u.WATER_PORT
    intake = l.INTAKE if baseline else u.INTAKE
    if batch == 'loose':
        cargo = mixed
        t.write({p: cargo[i::2] for i, p in enumerate(intake)})
    elif batch == 'box':
        cargo = shulker
        p = intake[0] if baseline else PORTS[2]
        t.write({p: [box('blue_shulker_box', *cargo, title='Полный замер')]})
    else:
        cargo = water
        send_farm(t, *cargo, port=port)
    if not baseline:
        wanted = [*cargo, stack('blue_shulker_box', title='Полный замер')] if batch == 'box' else cargo
        elapsed = wait_for_storage(t, seeded, wanted, limit=26000, period=100, trace=False)
    else:
        want = counts(*cargo)
        names = {name for name, _ in want}
        target = tuple(p for name in names for p in storage[name])
        if batch == 'box':
            target += l.RETURN
            want += counts(stack('blue_shulker_box', title='Полный замер'))
        start = t.now()
        for elapsed in range(100, 90001, 100):
            t.step(100)
            state = t.inventories(target)
            if got := merged(state, target):
                if got == want:
                    elapsed = t.now() - start
                    break
            if elapsed % 10000 == 0:
                print(f'  baseline t={elapsed}: {sum(got.values())}/{sum(want.values())}', flush=True)
        else:
            raise AssertionError(f'Baseline did not complete identical load: {got}')
    n = sum(counts(*cargo).values())
    print(f'BENCH {"baseline" if baseline else "universal"} {batch}: {n} items in {elapsed} ticks; '
          f'{20*n/elapsed:.3f} items/sec at 20 TPS', flush=True)


def main():
    def flags(parser):
        parser.add_argument('--bench', choices=('loose', 'box', 'water'))
        parser.add_argument('--baseline', action='store_true')
        parser.add_argument('--rate', type=int, default=400)
    args = read_args(__doc__, configure=flags, default_schematic=u.OUTPUT)
    if args.baseline:
        if not args.bench:
            raise SystemExit('--baseline requires --bench')
        args.schematic = old.OUTPUT
    verify_recipes(args.server)
    bounds, origin = (old.BOUNDS, old.ORIGIN) if args.baseline else (u.BOUNDS, u.ORIGIN)
    with session(args, NAME, bounds, Store, rate=args.rate, schematic_min=origin) as t:
        strict = not args.neighbor_updates
        if args.bench:
            benchmark(t, strict, args.bench, baseline=args.baseline, schematic=args.schematic)
        else:
            verify(t, strict, args.schematic)


if __name__ == '__main__':
    main()
