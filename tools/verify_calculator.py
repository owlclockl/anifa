"""Exercise the exported redstone calculator on the official Java 26.3 server.

Console commands only place the structure, toggle user levers, and read lamps.
The calculator itself contains no commands, entities or runtime software.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re
import shutil
import tempfile

import nbtlib
import numpy as np
from nbtlib import tag as nbt

from . import build_calculator as d
from . import calculator_display as screen
from . import calculator_logic as logic
from .vanilla_catacomb_test import Server, read_args, unpack_region, xyz

CASES = (
    (0, 0, 0), (255, 255, 0), (1, 255, 0),
    (42, 87, 1), (255, 0, 1), (0, 255, 1), (128, 128, 1),
    (197, 19, 2), (255, 255, 2), (201, 0, 2),
    (197, 19, 3), (255, 1, 3), (255, 128, 3), (1, 4, 3), (255, 0, 3),
    (197, 19, 4), (255, 128, 4), (127, 0, 4),
    (0b10110101, 0b00111101, 5), (0b10110101, 0b00111101, 6), (0b10110101, 0b00111101, 7),
    (255, 1, 0),
)
QUICK = ((42, 87, 1), (197, 19, 2), (197, 19, 3), (197, 19, 4),
         (255, 0, 3), (181, 61, 7), (0, 0, 0))


def sparse_template(schematic, target):
    """Transform only the non-air blocks, so a large hollow circuit stays small."""
    file = nbtlib.load(schematic)
    assert file['MinecraftDataVersion'] == 5023 and len(file['Regions']) == 1
    region, = file['Regions'].values()
    assert all(region['Position'][a] == 0 for a in 'xyz')
    size = [int(region['Size'][ax]) for ax in 'xyz']
    volume = unpack_region(region)
    tile_entities = {tuple(int(t[a]) for a in 'xyz'): nbt.Compound({k: v for k,v in t.items() if k not in 'xyz'})
                     for t in region['TileEntities']}
    palette = nbt.List[nbt.Compound]()
    for state in region['BlockStatePalette']:
        new = nbt.Compound(id=state['Name'])
        if 'Properties' in state:
            new['properties'] = state['Properties']
        palette.append(new)
    blocks = nbt.List[nbt.Compound]()
    for y,z,x in np.argwhere(volume):
        p = (int(x), int(y), int(z))
        entry = nbt.Compound(pos=nbt.List[nbt.Int](p), state=nbt.Int(volume[y,z,x]))
        if p in tile_entities:
            entry['nbt'] = tile_entities[p]
        blocks.append(entry)
    assert len(blocks) == file['Metadata']['TotalBlocks']
    target.parent.mkdir(parents=True, exist_ok=True)
    nbtlib.File({'DataVersion': nbt.Int(5023), 'size': nbt.List[nbt.Int](size), 'palette': palette,
                 'blocks': blocks, 'entities': nbt.List[nbt.Compound]()}, gzipped=True).save(target)
    return (0,0,0), tuple(n-1 for n in size)


class CalculatorServer(Server):
    java_options = ('-Xms512M', '-Xmx1856M', '-XX:ActiveProcessorCount=2')

    def step(self, n):
        expected = self.now()+n
        log = self.commands(f'tick sprint {n}t')
        if 'Sprint completed' not in log:
            # Large operand changes can temporarily push a small server far
            # below 20 TPS. This is a wall-clock timeout, not a circuit limit.
            self.until(r'Sprint completed', timeout=max(180, 45+n/10))
        actual = self.now()
        # The tick executing the sprint command can also advance the clock.
        if not expected <= actual <= expected+1:
            raise RuntimeError(f'Tick sprint expected time {expected} (+0 or 1), got {actual}')


@contextmanager
def test_world(args):
    with tempfile.TemporaryDirectory(prefix='moonspire-calculator-') as tmp:
        world = Path(tmp)
        (world/'eula.txt').write_text('eula=true\n', encoding='utf-8')
        (world/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nmax-players=0\n'
                                             'enable-status=false\nlevel-type=minecraft:flat\nview-distance=4\n'
                                             'simulation-distance=4\nspawn-protection=0\npause-when-empty-seconds=0\n'
                                             'max-tick-time=-1\nenable-jmx-monitoring=false\n', encoding='utf-8')
        bounds = sparse_template(args.schematic, world/'world/generated/minecraft/structure/calculator.nbt')
        mc = CalculatorServer(args.java, args.server.resolve(), world)
        try:
            mc.start()
            mx, _, mz = bounds[1]
            mc.commands('gamerule minecraft:spawn_mobs false')
            for x in range(0, mx+1, 128):
                result = mc.commands(f'forceload add {x} 0 {min(x+127, mx)} {mz}')
                if 'force load' not in result.lower():
                    raise RuntimeError(result)
            mc.step(24)
            flag = '' if args.neighbor_updates else ' strict'
            result = mc.commands(f'place template minecraft:calculator {xyz((0,0,0))} none none 1.0 0{flag}')
            if 'Loaded template' not in result:
                raise RuntimeError(result)
            print(f'Native placement passed, strict={not args.neighbor_updates}; {bounds}', flush=True)
            yield mc
        finally:
            mc.stop()
            log = world/'logs/latest.log'
            if args.log is not None and log.is_file():
                shutil.copyfile(log, args.log)


def lamp_state(mc):
    commands = [f'execute if block {xyz(p)} minecraft:redstone_lamp[lit=true] run say CALC_LAMP_{k}' for k,p in d.LAMPS.items()]
    light = set(re.findall(r'\[Server\] CALC_LAMP_(\w+)', mc.commands(*commands)))
    word = sum((f'R{i}' in light) << i for i in range(16))
    return (-word if 'NEG' in light else word, 'ERR' in light), light


def display_state(mc):
    # Read every pixel, not just the driver or center of each segment.
    commands = [f'execute if block {xyz(p)} minecraft:redstone_lamp[lit=true] run say LCD_{k}_{i}'
                for k in d.DISPLAY_CENTERS for i,p in enumerate(d.display_pixels(k))]
    lights = set(re.findall(r'\[Server\] LCD_(\w+)', mc.commands(*commands)))
    cells = set()
    for k in d.DISPLAY_CENTERS:
        count = len(d.display_pixels(k))
        lit = sum(f'{k}_{i}' in lights for i in range(count))
        if lit == count:
            cells.add(k)
        elif lit:
            raise AssertionError(f'Broken segment {k}: {lit}/{count} pixels lit')
    progress = {k for k in cells if k.startswith('P')}
    if progress != {f'P{i}' for i in range(len(progress))}:
        raise AssertionError(f'Progress is not a prefix: {sorted(progress)}')
    return cells-progress, len(progress)


def assert_final(mc, a, b, op):
    value, err = logic.reference(a,b,op)
    binary, light = lamp_state(mc)
    if binary != (value, err) or ('NEG' in light) != (value<0):
        raise AssertionError(f'{a} {logic.MODES[op]} {b}: expected {(value,err)}, got {binary}; {light}')
    actual, bar = display_state(mc)
    expected = screen.glyphs(value, err)
    if (actual, bar) != (expected, screen.STAGES):
        raise AssertionError(f'Decimal {value}: missing {expected-actual}, unexpected {actual-expected}; progress {bar}')
    print(f'PASS {a:3} {logic.MODES[op]:>3} {b:<3} = {"ERR" if err else value} (decimal, binary, 10/10)', flush=True)


def assert_busy(mc, expected_range):
    shown, bar = display_state(mc)
    if shown or bar not in expected_range:
        raise AssertionError(f'While busy: screen must be blank and progress in {expected_range}; got {shown}, {bar}')
    return bar


def toggle(mc, a, b, op, current):
    goal = logic.inputs_for(a,b,op)
    cmds = [f'setblock {xyz(d.LEVERS[k])} minecraft:lever[face=floor,facing=north,powered={str(v).lower()}]'
            for k,v in goal.items() if v != current[k]]
    if cmds:
        log = mc.commands(*cmds)
        if log.count('Changed the block') != len(cmds):
            raise RuntimeError(log)
    return goal


def configure(parser):
    parser.add_argument('--ticks', type=int, default=4200, help='Game ticks allowed after the final lever change')
    parser.add_argument('--log', type=Path, help='Copy the vanilla server log before removing the test world')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--quick', action='store_true')
    group.add_argument('--smoke', action='store_true', help='Check reset, sign and error with small inputs')


def main():
    args = read_args(__doc__, configure=configure, default_schematic=d.OUTPUT)
    if args.ticks <= 1920:
        raise ValueError('Give the complete timer cycle enough ticks')
    with test_world(args) as mc:
        mc.step(args.ticks)
        assert_final(mc,0,0,0)
        current = logic.inputs_for(0,0,0)
        if args.smoke:
            current = toggle(mc,0,0,3,current)
            mc.step(400)
            assert_busy(mc, range(1))
            mc.step(args.ticks-400)
            assert_final(mc,0,0,3)
            toggle(mc,0,1,1,current)
            mc.step(args.ticks)
            assert_final(mc,0,1,1)
            print('PASS mode reset, divide-by-zero and negative display', flush=True)
            return
        # The zero bar travels through less wiring than the screen's blanking
        # signal. Sample once both paths have propagated, before the first step.
        current = toggle(mc,197,19,2,current)
        mc.step(400)
        assert_busy(mc, range(1))
        mc.step(1120)
        first = assert_busy(mc, range(1,8))
        current = toggle(mc,255,255,2,current)
        mc.step(400)
        assert_busy(mc, range(1))
        mc.step(1120)
        middle = assert_busy(mc, range(1,8))
        mc.step(400)
        later = assert_busy(mc, range(middle+1,10))
        print(f'PASS automatic restart: {first}/10 → 0/10 → {middle}/10 → {later}/10', flush=True)
        seen = {0, middle, later}
        elapsed, prev = 1920, later
        while elapsed < args.ticks:
            step = min(112, args.ticks-elapsed)
            mc.step(step)
            elapsed += step
            shown, bar = display_state(mc)
            if bar < prev or (bar < 9 and shown):
                raise AssertionError(f'Bad running state at t={elapsed}: progress {prev}→{bar}, screen {shown}')
            seen.add(bar)
            prev = bar
        if not set(range(later,screen.STAGES+1)) <= seen:
            raise AssertionError(f'Timer skipped a milestone: {sorted(seen)}')
        print(f'PASS successive milestones {later} … {screen.STAGES}/10', flush=True)
        assert_final(mc,255,255,2)
        suite = QUICK if args.quick else CASES
        for a,b,op in suite:
            current = toggle(mc, a,b,op,current)
            mc.step(args.ticks)
            assert_final(mc,a,b,op)
        mc.step(24)
        assert_final(mc,*suite[-1])  # no free-running clock or flickering output at rest
        print(f'PASS {len(suite)+2} completed results and the live progress/restart test', flush=True)


if __name__ == '__main__':
    main()
