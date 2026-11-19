#!/usr/bin/env python3
"""Synthesize an 8-bit redstone calculator and export its Litematica schematic."""
from __future__ import annotations

import argparse
import hashlib
import math
import random
import subprocess
import tempfile
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from nbtlib import tag as nbt

from . import build_catacomb_cathedral as decor
from . import build_cathedral as c
from . import calculator_display as screen
from . import calculator_logic as logic

OUTPUT = c.OUTPUT.with_name('moonspire-calculator.litematic')
TITLE = 'Лунный арифмометр'
DESCRIPTION = 'Ванильный калькулятор Java 26.3: 8 операций, десятичное ламповое табло и шкала готовности.'
Vec = tuple[int, int, int]
DIRECTIONS = ('east', 'west', 'south', 'north', 'up', 'down')
DIR = dict(zip(DIRECTIONS, ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0))))
OPPOSITE = dict(zip(DIRECTIONS, ('west', 'east', 'north', 'south', 'down', 'up')))
WIDTH, HEIGHT, DEPTH = 76, 38, 74
TRACK, LEVEL, FLOOR = 4, 4, 10  # physical pitches and Y of the first routing plane
SCREEN_LEVEL = 6
PANEL_TOP = FLOOR+LEVEL*(SCREEN_LEVEL+4)+2
HORIZONTAL = DIRECTIONS[:4]
HORIZONTAL_BIT = {d: 1 << i for i, d in enumerate(HORIZONTAL)}
HOLD_SPIRAL = 0  # east-first at the pulse collector
DELAY_SPIRAL = 3  # north-first at the delay modules
STAGE_REPS, REVEAL_REPS = 36, 30  # at delay=4: 288 and 240 game ticks
HOLD_TAPS = 60
HOLD_PAD = (2, 0, 34)
LAYERS = (
    (2, ('SUM', 'SUB', 'SELECT')),
    (6, ('MUL0', 'MUL1', 'MUL2', 'MUL3')),
    (10, ('MUL4', 'MUL5', 'MUL6')),
    (12, ('GLYPH',)),
    (14, ('MUL7', 'DIV7', 'DIV6', 'DIV5', 'DIV4', 'DIV3')),
    (18, ('DIV2', 'DIV1', 'DIV0')),
    (22, ('LOGIC', 'OUT0', 'OUT1', 'OUT2', 'OUT3')),
    (26, ('BCD0', 'BCD1', 'BCD2', 'BCD3', 'BCD4')),
    (30, ('BCD5', 'BCD6')),
    (34, ('BCD7',)),
)
BED = 'deepslate_tiles'
ADDER = 'waxed_cut_copper'
MULT = 'waxed_exposed_cut_copper'
DIVIDER = 'waxed_oxidized_cut_copper'
OUT = 'waxed_weathered_cut_copper'
NON_SOLID = {'dark_oak_wall_sign', 'lever', 'redstone_wire', 'repeater', 'comparator', 'redstone_wall_torch', 'glass'}


def place(v, d, steps=1):
    a, b, c = v
    x, y, z = DIR[d]
    return a+x*steps, b+y*steps, c+z*steps


def direction(a, b):
    delta = tuple(y-x for x, y in zip(a, b))
    return next(k for k, v in DIR.items() if v == delta)


def world(p):
    # Leave room for the sideways step of a spiral on the west boundary.
    return 1+p[0]*TRACK, FLOOR+p[1]*LEVEL, p[2]*TRACK


def lever_pads():
    # The operator faces south: decreasing world X reads left to right.
    return {f'{label}{bit}': (26-(x+n-1-bit), 0, 3)
            for label, x, n in (('A', 2, 8), ('B', 11, 8), ('M', 20, 3)) for bit in range(n)}


def lamp_pads():
    def column(bit):
        nibble, place_in_digit = divmod(15-bit, 4)
        return 26-(2+5*nibble+place_in_digit)
    return {f'R{bit}': (column(bit), 1, 3) for bit in range(16)} | {'NEG': (4, 1, 3), 'ERR': (2, 1, 3)}


def segment_pads():
    # Large seven-segment glyphs. Pad centers are 4 blocks apart; each
    # segment uses five lamps with insulated gaps around the corners.
    shape = ((0,4),(-1,3),(-1,1),(0,0),(1,1),(1,3),(0,2))
    locations = {f'D{i}{seg}': (6+4*i+dx, SCREEN_LEVEL+dy, 4)
                 for i in range(5) for seg,(dx,dy) in zip(screen.SEGMENTS,shape)}
    return locations | {'SIGN': (25, SCREEN_LEVEL+2, 4), 'WARN': (2, SCREEN_LEVEL+2, 4)}


def bar_pads():
    return {f'P{i}': (24-2*i, SCREEN_LEVEL-1, 4) for i in range(screen.STAGES)}


def panel_pads():
    return lamp_pads() | segment_pads() | bar_pads()


def delay_pad(gate):
    return 26+3*int(gate.bank.removeprefix('DELAY')), 0, 6


def gate_inputs(gate, point):
    if gate.op == 'DELAY':
        return (point,)
    return tuple(place(point, side) for side in ('west','north')[:len(gate.args)])


LEVERS = {k: place(world(v), 'north', TRACK+1) for k, v in lever_pads().items()}
LAMPS = {k: place(world(v), 'north', TRACK) for k, v in lamp_pads().items()}
SEGMENT_PADS, BAR_PADS = segment_pads(), bar_pads()
DISPLAY_CENTERS = {k: place(world(v), 'north', 2*TRACK) for k, v in (SEGMENT_PADS | BAR_PADS).items()}


def vertical_segment(name):
    return name.startswith('D') and name[-1] in 'bcef'


def display_pixels(name):
    offset = 2 if not name.startswith('P') and name != 'WARN' else 1
    x,y,z = DISPLAY_CENTERS[name]
    return [(x,y+i,z) if vertical_segment(name) else (x+i,y,z) for i in range(-offset,offset+1)]


def encode(p):
    x, y, z = p
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT and 0 <= z < DEPTH):
        raise ValueError(p)
    return (y*DEPTH+z)*WIDTH+x


def decode(i):
    row, x = divmod(i, WIDTH)
    y, z = divmod(row, DEPTH)
    return x, y, z


def material(bank):
    if bank.startswith('MUL'):
        return MULT
    if bank.startswith('DIV'):
        return DIVIDER
    if bank.startswith(('OUT', 'BCD')) or bank in ('LOGIC', 'GLYPH'):
        return OUT
    if bank == 'TIMER':
        return DIVIDER
    if bank in ('SUM', 'SUB', 'SELECT'):
        return ADDER
    return BED


def layout_gates(network):
    """Place related arithmetic stages on the same floor, then shorten tracks."""
    live = network.live()
    inputs_by_name = lever_pads() | {'HOLD': HOLD_PAD}
    positions = {i: inputs_by_name[key] for key, i in network.inputs.items()}
    positions.update((i, delay_pad(network.gates[i])) for i in live if network.gates[i].op == 'DELAY')
    timers = sorted(i for i in live if network.gates[i].bank == 'TIMER')
    positions.update((n, (26+3*i, 1, 10+2*(i%2))) for i,n in enumerate(timers))
    tiers = []
    for lv, banks in LAYERS:
        front = 7 if banks == ('GLYPH',) else 11
        slots = [(4*x+3, lv, 4*z+front) for z in range(15) for x in (range(16) if z%2 == 0 else range(15, -1, -1))]
        assigned = sorted(i for i in live if network.gates[i].bank in banks)
        assert len(assigned) <= len(slots), (banks, len(assigned))
        positions.update(zip(assigned, slots))
        tiers.append((slots, assigned+[None]*(len(slots)-len(assigned))))
    assert positions.keys() == live
    # Endpoints are (gate or operator position, X offset, Z offset).
    edges = []
    incident = defaultdict(set)
    inputs = set(network.inputs.values())
    for g in sorted(live-inputs):
        for i, a in enumerate(network.gates[g].args):
            incident[g].add(len(edges))
            incident[a].add(len(edges))
            dx, dz = (0,0) if network.gates[g].op == 'DELAY' else ((-1,0) if i == 0 else (0,-1))
            edges.append((a, g, 0 if a in inputs else 1, dx, dz))
    outputs = panel_pads()
    for i, (name, gpio) in enumerate(outputs.items(), start=-len(outputs)):
        g = network.outputs[name]
        positions[i] = gpio
        incident[g].add(len(edges))
        edges.append((g, i, 1, 0, 0))
    weight = [1/math.sqrt(max(1, sum(1 for j in incident[a] if edges[j][0] == a))) for a, *_ in edges]

    def length(e):
        u, v, src_x, dst_x, dst_z = edges[e]
        a, _, c = positions[u]
        x, _, z = positions[v]
        return weight[e]*(abs(a+src_x-x-dst_x)+abs(c-z-dst_z))

    randomizer = random.Random(2603)
    # Round-robin floors so the nearest sockets on different floors can align.
    for epoch in range(6):
        steps = 3600
        for slots, assigned in (tiers if epoch % 2 == 0 else tiers[::-1]):
            n = len(slots)
            for tick in range(steps):
                a,b = randomizer.randrange(n), randomizer.randrange(n)
                i,j = assigned[a], assigned[b]
                if i == j:
                    continue
                related = incident[i] | incident[j]
                before = sum(length(e) for e in related)
                if i is not None:
                    positions[i] = slots[b]
                if j is not None:
                    positions[j] = slots[a]
                delta = sum(length(e) for e in related)-before
                temperature = (3.8-0.55*epoch)*(1-tick/steps)+.10
                if delta <= 0 or randomizer.random() < math.exp(-delta/temperature):
                    assigned[a], assigned[b] = j,i
                else:
                    if i is not None:
                        positions[i] = slots[a]
                    if j is not None:
                        positions[j] = slots[b]
    for i in range(-len(outputs), 0):
        positions.pop(i)
    return positions


@dataclass
class Plan:
    network: logic.Circuit
    positions: dict[int, Vec]
    roots: dict[int, Vec]
    pins: dict[int, list[Vec]]
    edges: list[tuple[int, Vec, Vec, int]]


def buffer_tracks(plan):
    """Place repeaters only when the next cable branch needs more power.

    A step (horizontal or vertical) loses four levels. A buffered step
    needs two levels on entry and leaves fourteen on the far pad. Each
    terminal has its own minimum for the length of its physical lead.
    """
    needs = {(net, pin): 3 for net, pins in plan.pins.items() for pin in pins}
    for name, pin in (SEGMENT_PADS | BAR_PADS).items():
        needs[plan.network.outputs[name], pin] = 9 if vertical_segment(name) else 8
    for net, point in plan.positions.items():
        g = plan.network.gates[net]
        if g.op == 'DELAY':
            needs[g.args[0], point] = 5
    pin_needs = dict(needs)
    for net,a,b,_ in reversed(plan.edges):
        required = needs.get((net,b), 1)
        threshold = 2 if a[1] == b[1] and required <= 14 else required+4
        needs[net,a] = max(needs.get((net,a),1), threshold)

    def initial_power(net):
        op = plan.network.gates[net].op
        if op == 'DELAY' or net == plan.network.inputs['HOLD']:
            return 11  # powered pad below, then four passive steps up
        return 12 if op in ('DIFF', 'INPUT') else 13

    power = {(net,pad): initial_power(net) for net,pad in plan.roots.items()}
    buffered = set()
    for net,a,b,_ in plan.edges:
        strength = power[net,a]
        if strength < needs[net,a]:
            raise ValueError(f'Insufficient output power on net {net} at {a}')
        required = needs.get((net,b), 1)
        if strength-4 >= required:
            power[net,b] = strength-4
        elif a[1] == b[1] and required <= 14:
            buffered.add((net,a,b))
            power[net,b] = 14
        else:
            raise ValueError(f'Cannot buffer track {a} → {b} on net {net}')
    for net,pins in plan.pins.items():
        for pin in pins:
            if power.get((net,pin), 0) < pin_needs[net,pin]:
                raise ValueError(f'Unpowered input {pin} on net {net}')
    return buffered


def arrival_times(plan, buffered, source=None):
    """Paths from operands (or one specified net), with delays in game ticks.

    Timer stages are cut here: their outputs are independent of the operand
    datapath and the stage-to-stage timing is checked separately.
    """
    trees = defaultdict(list)
    for n,a,b,_ in plan.edges:
        trees[n].append((a,b,2*int((n,a,b) in buffered)))
    clocks = {}
    for net,root in sorted(plan.roots.items()):
        g = plan.network.gates[net]
        if net == source:
            delay = 0
        elif g.op in ('INPUT', 'DELAY'):
            delay = 2 if source is None and g.op == 'INPUT' else -math.inf
        else:
            points = gate_inputs(g, plan.positions[net])
            delay = max(clocks[arg][p] for arg,p in zip(g.args, points))+4
        clocks[net] = arrivals = {root: delay}
        for a,b,ticks in trees[net]:
            arrivals[b] = arrivals[a]+ticks
    return clocks


def timing_checks(plan, buffered):
    def display_ticks(clocks):
        return max(clocks[plan.network.outputs[name]][p]+6 for name,p in SEGMENT_PADS.items())

    ticks = display_ticks(arrival_times(plan, buffered))
    last_delay = next(i for i,g in enumerate(plan.network.gates) if g.bank == f'DELAY{screen.STAGES}')
    ready = plan.network.gates[last_delay].args[0]
    reveal = display_ticks(arrival_times(plan, buffered, ready))
    hold = arrival_times(plan, buffered, plan.network.inputs['HOLD'])
    purge = max(hold[plan.network.gates[i].args[0]][p] for i,p in plan.positions.items()
                if plan.network.gates[i].op == 'DELAY')
    if ticks+40 >= 8*STAGE_REPS*screen.STAGES or reveal >= 8*REVEAL_REPS:
        raise ValueError(f'Timer too short for the data path ({ticks} ticks) or display reveal ({reveal} ticks)')
    # Longest gate fanout still has time to flush one stage while HOLD is high.
    if purge+8*STAGE_REPS+32 >= 8*HOLD_TAPS-26:
        raise ValueError(f'Reset pulse too short: hold fanout takes {purge} ticks')
    return int(ticks), int(reveal), int(purge)


def make_plan(router=None, cache=None):
    network = screen.design()
    gate_spots = layout_gates(network)
    pads, roots, pins = {}, {}, defaultdict(list)

    def pad(p, n, toward=None, mask=0):
        if encode(p) in pads:
            raise ValueError(f'Overlapping pad at {p}')
        pads[encode(p)] = n, mask | HORIZONTAL_BIT.get(toward, 0)

    def pin(p, net, toward=None, mask=0):
        pins[net].append(p)
        pad(p, net, toward, mask)

    for lv in range(HEIGHT):
        for z in range(3 if lv < 2 else 4):
            for x in range(WIDTH):
                pad((x, lv, z), -2)
    for node, g in sorted(gate_spots.items()):
        gate = network.gates[node]
        if gate.op == 'INPUT':
            roots[node] = g
            if node == network.inputs['HOLD']:
                pad(g, node, mask=1 << (8+HOLD_SPIRAL))
            else:
                pad(g, node, 'north')
        elif gate.op == 'DELAY':
            roots[node] = other = place(g, 'east')
            pad(other, node, mask=1 << (8+DELAY_SPIRAL))
            pin(g, gate.args[0], mask=1 << (8+DELAY_SPIRAL))
        else:
            pad(g, -2)
            roots[node] = place(g, 'east')
            pad(roots[node], node, 'west')
            for i, arg in enumerate(gate.args):
                pin(place(g, ('west','north')[i]), arg, ('east','south')[i])
    for name, p in panel_pads().items():
        pin(p, network.outputs[name], 'north')
    assert roots.keys() == pins.keys()
    data = [f'{WIDTH} {HEIGHT} {DEPTH} {len(pads)} {len(roots)}']
    data.extend(f'{pos} {n} {mask}' for pos, (n, mask) in sorted(pads.items()))
    for n, root in roots.items():
        data.append(' '.join(map(str, (n, encode(root), len(pins[n]), *map(encode, pins[n])))))
    text = '\n'.join(data)+'\n'
    source = Path(__file__).with_name('calculator_router.cpp')
    key = hashlib.sha256(text.encode()+source.read_bytes()).hexdigest()
    saved = cache.read_text() if cache is not None and cache.is_file() else ''
    if saved.startswith(key+'\n'):
        routed = saved.split('\n',1)[1]
    else:
        with tempfile.TemporaryDirectory(prefix='moonspire-router-') as tmp:
            if router is None:
                router = Path(tmp)/'route'
                subprocess.run(['c++', '-std=c++17', '-O3', str(source), '-o', str(router)], check=True)
            routed = subprocess.run([str(router)], text=True, input=text, stdout=subprocess.PIPE, check=True).stdout
        if cache is not None:
            cache.write_text(key+'\n'+routed)
    edges = [(n, decode(a), decode(b), rot) for n, a, b, rot in (map(int, s.split()) for s in routed.splitlines())]
    return Plan(network, gate_spots, roots, dict(pins), edges)


class Geometry:
    def __init__(self, plan, a=0, b=0, mode=0):
        self.plan = plan
        self.values = plan.network.evaluate(logic.inputs_for(a, b, mode) | {'HOLD': False})
        self.buffered = buffer_tracks(plan)
        self.blocks = {}
        self.data = {}
        self.wires = {}
        self.links = defaultdict(set)
        self.feed = defaultdict(set)

    def put(self, p, kind, **props):
        if p in self.wires:
            raise ValueError(f'{kind} overlaps dust at {p}')
        state = (kind, tuple(sorted(props.items())))
        if p in self.blocks and self.blocks[p] != state:
            raise ValueError(f'{p}: {self.blocks[p]} vs {state}')
        self.blocks[p] = state

    def solid(self, p):
        return p in self.blocks and self.blocks[p][0] not in NON_SOLID

    def support(self, p, tone=BED):
        if not self.solid(p):
            self.put(p, tone, **({'axis': 'y'} if tone == 'ochre_froglight' else {}))

    def wire(self, p, net):
        if p in self.blocks or self.wires.setdefault(p, net) != net:
            raise ValueError(f'Dust clash at {p}: {self.blocks.get(p)}, {self.wires.get(p)}, {net}')
        self.support(place(p, 'down'))

    def dust_line(self, net, points):
        for p in points:
            self.wire(p, net)
        for a,b in zip(points, points[1:]):
            self.links[a].add(b)
            self.links[b].add(a)

    def rep(self, p, to, net, delay=1):
        self.support(place(p, 'down'))
        self.put(p, 'repeater', facing=OPPOSITE[to], locked='false', delay=str(delay), powered=str(self.values[net]).lower())
        self.feed[place(p, to)].add(net)

    def trace(self, n, a, b, rot):
        d = direction(a,b)
        buffered = (n,a,b) in self.buffered
        a,b = world(a),world(b)
        if d in ('up', 'down'):
            p = a if d == 'up' else b
            points = [p]
            spiral = ('east','south','west','north')
            for step in spiral[rot:] + spiral[:rot]:
                p = place(place(p, 'up'), step)
                points.append(p)
            self.dust_line(n, points)
        elif not buffered:
            self.dust_line(n, [place(a, d, i) for i in range(TRACK+1)])
        else:
            self.dust_line(n, [a, place(a, d)])
            self.rep(place(a, d, 2), d, n)
            self.dust_line(n, [place(a, d, 3), b])

    def gate(self, i, p):
        neuron = self.plan.network.gates[i]
        p = world(p)
        skin = material(neuron.bank)
        self.support(place(p, 'down'), skin)
        for arg, pin in zip(neuron.args, ('west','north')):
            self.dust_line(arg, [place(p, pin, d) for d in range(2, TRACK+1)])
            self.rep(place(p, pin), OPPOSITE[pin], arg)
        if neuron.op == 'DIFF':
            self.put(p, 'comparator', facing='west', mode='subtract', powered=str(self.values[i]).lower())
            self.data[p] = nbt.Compound(id=nbt.String('minecraft:comparator'), OutputSignal=nbt.Int(15 if self.values[i] else 0))
            self.feed[place(p, 'east')].add(i)
            first = 1
        else:
            self.put(p, skin)
            if neuron.op == 'OR':
                self.rep(place(p, 'east'), 'east', i)
            elif neuron.op == 'NOT':
                q = place(p, 'east')
                self.support(place(q, 'down'), skin)
                self.put(q, 'redstone_wall_torch', facing='east', lit=str(self.values[i]).lower())
                self.feed[place(q, 'east')].add(i)
            else:
                raise ValueError(neuron)
            first = 2
        self.dust_line(i, [place(p, 'east', d) for d in range(first, TRACK+1)])

    def panel(self):
        for k, port in lever_pads().items():
            i, p = self.plan.network.inputs[k], LEVERS[k]
            pad = world(port)
            self.put(place(p, 'down'), 'observer', facing='up', powered='false')
            self.put(p, 'lever', face='floor', facing='north', powered=str(self.values[i]).lower())
            self.rep(place(p, 'south'), 'south', i)
            self.dust_line(i, [place(pad, 'north', n) for n in range(3, -1, -1)])
        for k, port in lamp_pads().items():
            i, p = self.plan.network.outputs[k], LAMPS[k]
            pad = world(port)
            self.put(p, 'redstone_lamp', lit=str(self.values[i]).lower())
            self.rep(place(p, 'south'), 'north', i)
            self.dust_line(i, [place(p, 'south', 2), place(p, 'south', 3), pad])

    def glyph_panel(self):
        for name, port in (SEGMENT_PADS | BAR_PADS).items():
            net = self.plan.network.outputs[name]
            center = DISPLAY_CENTERS[name]
            for p in display_pixels(name):
                self.put(p, 'redstone_lamp', lit=str(self.values[net]).lower())
            x,y,_ = center
            pad = world(port)
            stem = place(center, 'south', 6 if vertical_segment(name) else 2)
            self.dust_line(net, [(x,y,z) for z in range(stem[2],pad[2]+1)])
            if vertical_segment(name):
                # Stagger the redstone stairs to either side; power the two
                # alternate pixels directly so their neighbors also light.
                for k in (-1,1):
                    self.dust_line(net, [stem, *[(x+k,y+k,z) for z in range(14,9,-1)], (x,y+k,10)])
                    self.rep((x,y+k,9), 'north', net)
            else:
                for k in (-1,1):
                    self.dust_line(net, [stem, (x+k,y,10)])
                    self.rep((x+k,y,9), 'north', net)

    def delay_gate(self, net, point):
        gate = self.plan.network.gates[net]
        upstream, = gate.args
        other = place(point, 'east')
        a,b = place(point, 'down'),place(other, 'down')
        self.trace(upstream, a, point, DELAY_SPIRAL)
        self.trace(net, b, other, DELAY_SPIRAL)
        x,y,z = world(a)
        xx,_,_ = world(b)
        count = REVEAL_REPS if gate.bank == f'DELAY{screen.STAGES}' else STAGE_REPS
        for k in range(1, count//2+1):
            self.rep((x,y,z+k), 'south', net, delay=4)
            self.rep((xx,y,z+k), 'north', net, delay=4)
        self.dust_line(net, [(i,y,z+count//2+1) for i in range(x,xx+1)])

    def input_observers(self):
        """Merge edges, widen them, and OR delayed copies into a retriggerable HOLD."""
        hold = self.plan.network.inputs['HOLD']
        side = FLOOR-2
        x0 = 5
        for x,y,z in LEVERS.values():
            p = (x,side,z)
            self.wire(p, hold)
            self.feed[p].add(hold)  # observer facing up, output on bottom
            self.rep((x,side,z+1), 'south', hold, delay=4)
        # Diodes from the observer taps feed a one-way collector at Z=9.
        section = []
        for x in range(max(p[0] for p in LEVERS.values()), x0-1, -1):
            p = (x,side,9)
            if x % 8 == 7:
                self.dust_line(hold, section)
                section = []
                self.rep(p, 'west', hold)
            else:
                section.append(p)
        self.dust_line(hold, section)
        low = FLOOR-4
        self.dust_line(hold, [(x0,side,9),(x0,side-1,10),(x0,low,11),(x0,low,12)])
        self.rep((x0,low,13), 'south', hold, delay=4)
        for i in range(HOLD_TAPS):
            z = 14+2*i
            self.wire((x0,low,z), hold)
            self.rep((x0+1,low,z), 'east', hold, delay=4)
            if i+1 < HOLD_TAPS:
                self.rep((x0,low,z+1), 'south', hold, delay=4)
        segment = []
        last = world(HOLD_PAD)[2]
        for z in range(14,last+1):
            p = (x0+2,low,z)
            if z % 10 == 3:
                self.dust_line(hold, segment)
                segment = []
                self.rep(p, 'south', hold)
            else:
                segment.append(p)
        self.dust_line(hold, segment)
        self.rep((x0+3,low,last), 'east', hold)
        self.trace(hold, place(HOLD_PAD, 'down'), HOLD_PAD, HOLD_SPIRAL)

    def signature(self, p):
        both = {}
        neighbors = set()
        for d in HORIZONTAL:
            q = place(p, d)
            state, props = self.blocks.get(q, ('air', ()))
            props = dict(props)
            up = place(q, 'up')
            down = place(q, 'down')
            if self.solid(q) and up in self.wires and not self.solid(place(p, 'up')):
                neighbors.add(up)
                both[d] = 'up'
            elif q in self.wires:
                neighbors.add(q)
                both[d] = 'side'
            elif state in ('repeater','comparator') and props['facing'] in (d, OPPOSITE[d]):
                both[d] = 'side'
            elif state in ('redstone_wall_torch','lever'):
                both[d] = 'side'
            elif not self.solid(q) and down in self.wires:
                neighbors.add(down)
                both[d] = 'side'
            else:
                both[d] = 'none'
        for axis, other in ((('north','south'), ('east','west')), (('east','west'), ('north','south'))):
            if all(both[d] == 'none' for d in other):
                for d in axis:
                    if both[d] == 'none':
                        both[d] = 'side'
        return both, neighbors

    def bake(self):
        active = deque()
        power = defaultdict(int)
        # Validate signal strength even on nets that start off. Each dust
        # component is driven only by its own net (checked again below).
        for p, drivers in self.feed.items():
            if p in self.wires:
                if drivers != {self.wires[p]}:
                    raise ValueError(f'Mismatched driver {p}, {drivers}, {self.wires[p]}')
                power[p] = 15
                active.append(p)
        while active:
            p = active.popleft()
            if power[p] <= 1:
                continue
            for q in self.links[p]:
                if power[q] < power[p]-1:
                    power[q] = power[p]-1
                    active.append(q)
        states = {}
        for p, n in self.wires.items():
            shape, adjacent = self.signature(p)
            if adjacent != self.links[p]:
                raise ValueError(f'Physical dust adjacency mismatch at {p} ({n}, wanted {self.links[p]}, got {adjacent})')
            if not power[p]:
                raise ValueError(f'Attenuated dust at {p} on net {n}')
            shape['power'] = str(power[p] if self.values[n] else 0)
            states[p] = ('redstone_wire', tuple(sorted(shape.items())))
        self.blocks.update(states)

    def sign(self, p, *lines, color='white'):
        self.support(place(p, 'south'), BED)
        self.put(p, 'dark_oak_wall_sign', facing='north', waterlogged='false')
        self.data[p] = decor.text_data(lines, color)

    def facade(self):
        f = FLOOR
        # Keep the observer bus below the maintenance deck and all pixel
        # adapters behind the dark front surface, not embedded in it.
        for x in range(106):
            for z in range(7):
                skin = 'ochre_froglight' if z in (1,5) and x%8 == 4 else BED
                self.support((x,f-2,z), skin)
        for x in (0,105):
            for y in range(f-2):
                self.support((x,y,8), 'deepslate_bricks')
        bar_y = DISPLAY_CENTERS['P0'][1]
        for x in range(106):
            for y in range(f-1,PANEL_TOP+1):
                if (x,y,8) in self.blocks:
                    continue
                if x in (0,105) or y in (f-1,PANEL_TOP):
                    skin = OUT
                elif y in (f+5,bar_y-3):
                    skin = ADDER
                elif y >= bar_y-2:
                    skin = 'black_concrete'
                else:
                    skin = 'deepslate_bricks'
                self.support((x,y,8), skin)
        self.sign((100,f+1,7), 'Ввод A', '0 → 255', color='orange')
        self.sign((64,f+1,7), 'Ввод B', '0 → 255', color='aqua')
        self.sign((28,f+1,7), 'Операция', 'код 0–7', color='orange')
        for key,(x,y,z) in LEVERS.items():
            self.sign((x,y+1,z), key, str(1 << int(key[1])))
        for key,(x,y,z) in LAMPS.items():
            txt = {'NEG': 'Минус', 'ERR': 'Деление на 0'}.get(key, f'2^{key[1:]}')
            self.sign((x,y+1,z-1), txt, color='red' if key in ('NEG','ERR') else 'aqua')
        for x,i,symbol in zip(range(28,4,-3), range(8), logic.MODES):
            self.sign((x,f+2,7), str(i), symbol, color='orange')
        self.sign((97,PANEL_TOP-1,7), 'Лунный', 'арифмометр', color='aqua')
        self.sign((9,DISPLAY_CENTERS['WARN'][1]+2,7), 'Ошибка', 'Деление на 0', color='red')
        for i in range(screen.STAGES):
            x,y,_ = DISPLAY_CENTERS[f'P{i}']
            self.sign((x,y-1,7), f'{10*(i+1)}%', color='aqua')
        self.sign((12,bar_y,7), 'Готовность', 'по времени', color='aqua')
        for x in range(4,105,8):
            self.support((x,PANEL_TOP,7), 'ochre_froglight')

    def fill(self):
        for n, point in self.plan.positions.items():
            op = self.plan.network.gates[n].op
            if op == 'DELAY':
                self.delay_gate(n, point)
            elif op != 'INPUT':
                self.gate(n, point)
        self.panel()
        self.glyph_panel()
        self.input_observers()
        for n,a,b,rot in self.plan.edges:
            self.trace(n,a,b,rot)
        self.facade()
        self.bake()
        return self

    def save(self, path, preview=None):
        points = np.array(tuple(self.blocks), dtype=np.int32)
        if np.any(points.min(axis=0) != 0):
            raise ValueError('Next output must start at XYZ zero')
        ids = [c.state(kind, **dict(props)) for kind, props in self.blocks.values()]
        x,y,z = points.T
        grid = np.zeros((y.max()+1, z.max()+1, x.max()+1), dtype=np.int16)
        grid[y,z,x] = ids
        c.save(path, grid, preview, title=TITLE, description=DESCRIPTION, block_entities=self.data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--router', type=Path, help='Optional prebuilt solver from tools/calculator_router.cpp')
    parser.add_argument('--routing-cache', type=Path, help='Optional scratch file for reusing the solved tracks')
    args = parser.parse_args()
    plan = make_plan(args.router, args.routing_cache)
    g = Geometry(plan)
    ticks, reveal, purge = timing_checks(plan, g.buffered)
    print(f'{len(g.buffered)} track repeaters; data path {ticks}, reveal {reveal}, reset distribution {purge} game ticks', flush=True)
    g.fill()
    g.save(args.output, args.preview)


if __name__ == '__main__':
    main()
