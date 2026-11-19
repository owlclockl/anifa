"""Test the exported Keepers' Store on a disposable, local vanilla Java 26.3 server.

Requires Java 25+ and the official server JAR (not downloaded by the test).
Usage: python -m tools.verify_storage --java /path/to/java --server /path/to/server.jar --accept-minecraft-eula
"""

from __future__ import annotations

from collections import Counter

import nbtlib
from nbtlib import tag as nbt

from . import catacomb_storage as s
from .vanilla_catacomb_test import Server, place, read_args, session, xyz

NAME = 'keepers_store'
FILTERS = tuple(cell.at() for cell in s.CELLS)
RESERVES = tuple(cell.delivery[0] for cell in s.CELLS)
OUTPUTS = tuple(p for cell in s.CELLS for p in cell.barrels)
TRANSIT = (*s.PATH, *s.OVERFLOW_SINK, *(cell.delivery[1] for cell in s.CELLS))
INVENTORIES = (*FILTERS, *RESERVES, *OUTPUTS, *TRANSIT, *s.INTAKE, *s.OVERFLOW)


def expect(actual, expected, where):
    if actual != expected:
        raise AssertionError(f'{where}: expected {expected!r}, got {actual!r}')


def counts(*stacks):
    result = Counter()
    for stack in stacks:
        variant = str(stack.get('components', {}).get('minecraft:custom_name', ''))
        result[str(stack['id']).removeprefix('minecraft:'), variant] += int(stack['count'])
    return result


class Store(Server):
    def read_block_entities(self, positions):
        result = {}
        positions = tuple(positions)
        prefix = 'has the following block data: '
        for i in range(0, len(positions), 60):
            batch = positions[i:i + 60]
            lines = self.commands(*(f'data get block {xyz(p)}' for p in batch)).splitlines()
            data = [line.split(prefix, 1)[1] for line in lines if prefix in line]
            if len(batch) != len(data):
                raise AssertionError(f'Missing block entities in {batch}:\n' + '\n'.join(lines[-65:]))
            result.update((p, nbtlib.parse_nbt(snbt)) for p, snbt in zip(batch, data))
        return result

    def inventories(self, positions=INVENTORIES):
        return {p: tag.get('Items', []) for p, tag in self.read_block_entities(positions).items()}

    def write(self, updates):
        commands = []
        for p, content in updates.items():
            items = nbt.List[nbt.Compound]([nbt.Compound(stack, Slot=nbt.Byte(i))
                                           for i, stack in enumerate(content)])
            commands.append(f'data modify block {xyz(p)} Items set value {items.snbt()}')
        self.commands(*commands)

    def empty(self, positions):
        # Use actual slot operations for pickup. Mutating the Items NBT can
        # silently clear a chest without notifying its neighboring comparator.
        contents = self.inventories(positions)
        self.commands(*(f'item replace block {xyz(p)} container.{i} with air'
                        for p in reversed(positions) for i in sorted({0} | {int(v['Slot']) for v in contents[p]})))

    def feed(self, *stacks):
        if len(stacks) > 54:
            raise ValueError('More than one double chest of stacks')
        # Exercise both halves; every other stack enters through the second half.
        self.write({p: stacks[i::2] for i, p in enumerate(s.INTAKE)})


def stack(name, count=1, *, title=None):
    result = nbt.Compound(id=nbt.String('minecraft:' + name), count=nbt.Int(count))
    if title is not None:
        result['components'] = nbt.Compound({'minecraft:custom_name': nbt.String(title)})
    return result


def packed(name, slots):
    return [stack(name, 64)] * slots


def verify_seeds(state, saturated=None):
    baseline = s.inventory_data()
    for cell in s.CELLS:
        desired = s.SEED if cell != saturated else 64
        items = {int(item['Slot']): item for item in state[cell.at()]}
        fillers = baseline[cell.at()]['Items'][1:]
        expect(set(items), set(range(5)), f'{cell.item}: occupied filter slots')
        expect((items[0]['id'], items[0]['count'], items[0].get('components')),
               ('minecraft:' + cell.item, desired, None), f'{cell.item}: filter stack')
        for filler in fillers:
            expect(items[int(filler['Slot'])], filler, f'{cell.item}: reserved filler')
        expect(counts(*state[cell.delivery[0]]), Counter({(cell.item, ''): s.RESERVE}),
               f'{cell.item}: preloaded transfer reserve')


def merged(state, positions):
    return counts(*(item for pos in positions for item in state[pos]))


def verify_drained(state, *, backed_up=()):
    expect({p: state[p] for p in (*TRANSIT, *s.INTAKE) if state[p] and p not in backed_up},
           {}, 'Input and transit inventories after settling')


def verify_outputs(state, expected):
    for cell in s.CELLS:
        n = expected.get(cell.item, 0)
        expect(merged(state, cell.barrels), Counter({(cell.item, ''): n}) if n else Counter(),
               f'{cell.item}: two output barrels')


def verify(server, *, strict):
    place(server, NAME, s.ENGINE_BOUNDS, strict=strict)
    server.step(60)
    init = server.inventories()
    verify_seeds(init)
    verify_drained(init)
    expect(merged(init, (*s.OVERFLOW, *OUTPUTS)), Counter(), 'Empty storage on cold start')
    for p, half in zip(s.INTAKE, ('right', 'left')):
        server.block(p, f'chest[type={half},facing=south]')
    for p, half in zip(s.OVERFLOW, ('left', 'right') * 2):
        server.block(p, f'chest[type={half},facing=north]')
    server.block(s.OVERFLOW_LAMP, 'redstone_lamp[lit=false]')
    print('PASS: 36 preloaded filters, joined chests, empty outputs and passive start', flush=True)

    expected = {cell.item: 64 if i in (1, 2) else i * 5 % 7 + 1 for i, cell in enumerate(s.CELLS)}
    unknown = (stack('rotten_flesh', 37), stack('white_wool', 13), stack('iron_pickaxe'),
               stack('oak_log', 2, title='Образец'), stack('paper', 2, title=s.FILLER_NAME), stack('water_bucket'))
    mixture = [stack(name, n) for name, n in expected.items()]
    total = sum(expected.values()) + sum(counts(*unknown).values())
    server.feed(*mixture[:9], *unknown, *mixture[9:])
    server.step(160)
    in_progress = server.inventories((*s.INTAKE, *s.PATH))
    if not merged(in_progress, s.INTAKE) or not merged(in_progress, s.PATH):
        raise AssertionError('Expected some items still in intake and some already in flight at restart')
    server.stop()
    server.start()
    server.step(8 * (total + len(s.PATH)) + 240)
    mixed = server.inventories()
    verify_outputs(mixed, expected)
    verify_seeds(mixed)
    verify_drained(mixed)
    expect(merged(mixed, s.OVERFLOW), counts(*unknown), 'Overflow contents and special components')
    server.block(s.OVERFLOW_LAMP, 'redstone_lamp[lit=true]')
    print(f'PASS: {total} mixed items across all 36 lanes; unmatched intact; save/restart in transit', flush=True)

    # Pre-fill one lane so the test exercises backpressure immediately rather
    # than waiting for hours of hopper transfer in real time. Neither nearby
    # lane is filled or otherwise touched except through the intake.
    jam = s.CELLS[2]
    buffer = jam.delivery[1]
    n0, n1 = s.CELLS[1], s.CELLS[3]
    server.empty(s.OVERFLOW)
    server.write({**{p: packed(jam.item, 27) for p in jam.barrels}, buffer: packed(jam.item, 5)})
    server.step(20)
    server.block(s.OVERFLOW_LAMP, 'redstone_lamp[lit=false]')
    server.feed(stack(jam.item, 64), stack(n0.item, 9), stack(n1.item, 5))
    server.step(8 * (64 + 9 + 5 + len(s.PATH)) + 240)
    full = server.inventories()
    expected.update({jam.item: 54 * 64, n0.item: expected[n0.item] + 9, n1.item: expected[n1.item] + 5})
    verify_outputs(full, expected)
    verify_seeds(full, saturated=jam)
    verify_drained(full, backed_up=(buffer,))
    expect(merged(full, (buffer,)), counts(*packed(jam.item, 5)), 'Backed-up barrel feed')
    expect(merged(full, s.OVERFLOW), counts(stack(jam.item, s.SEED)), 'Surplus from a saturated lane')
    server.block(s.OVERFLOW_LAMP, 'redstone_lamp[lit=true]')
    print('PASS: saturated output safely bypassed; adjacent filters still sort and retain their seeds', flush=True)

    # Recover with no power cycling or access to the filter hoppers.
    server.empty(jam.barrels)
    recovered = 5 * 64 + (64 - s.SEED)
    server.step(8 * recovered + 300)
    server.feed(stack(jam.item, 7))
    server.step(8 * (len(s.PATH) + 7) + 240)
    expected[jam.item] = recovered + 7
    final = server.inventories()
    verify_seeds(final)
    verify_outputs(final, expected)
    verify_drained(final)
    expect(merged(final, s.OVERFLOW), counts(stack(jam.item, s.SEED)), 'Overflow undisturbed on recovery')
    server.checked('unless entity @e[type=minecraft:item]', 'No dropped items')
    print('PASS: loaded lane drains and resumes automatically when there is space', flush=True)


def main():
    args = read_args(__doc__)
    with session(args, NAME, s.ENGINE_BOUNDS, Store, rate=200) as server:
        verify(server, strict=not args.neighbor_updates)


if __name__ == '__main__':
    main()
