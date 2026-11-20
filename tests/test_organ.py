"""Reconstruct the actual exported organ, including its 3D wire links."""
import unittest
from collections import Counter, defaultdict, deque
import math

import nbtlib
import numpy as np

from tools import build_organ as d
from tools import organ_score as s
from tools.vanilla_catacomb_test import unpack_region

DIR = {'north': (0,0,-1), 'south': (0,0,1), 'west': (-1,0,0), 'east': (1,0,0),
       'up': (0,1,0), 'down': (0,-1,0)}
OPPOSITE = dict(zip(DIR, ('south','north','east','west','down','up')))
NON_CONDUCTORS = {'air','redstone_wire','stone_button','repeater','dark_oak_wall_sign','glass',
                  'polished_blackstone_brick_stairs'}


def at(p,direction):
    return tuple(a+b for a,b in zip(p,DIR[direction]))


class OrganExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file = nbtlib.load(d.OUTPUT)
        cls.region, = cls.file['Regions'].values()
        palette = [(str(p['Name']).removeprefix('minecraft:'),dict(p.get('Properties',{})))
                   for p in cls.region['BlockStatePalette']]
        grid = unpack_region(cls.region)
        cls.blocks = {(int(x),int(y),int(z)):palette[int(grid[y,z,x])] for y,z,x in np.argwhere(grid)}
        cls.wires = {p:props for p,(kind,props) in cls.blocks.items() if kind=='redstone_wire'}

    def kind(self,p):
        return self.blocks.get(p,('air',{}))[0]

    def wire_neighbors(self,p):
        ceiling = self.kind(at(p,'up')) not in NON_CONDUCTORS
        for direction in ('north','south','east','west'):
            q = at(p,direction)
            up, down = at(q,'up'), at(q,'down')
            solid = self.kind(q) not in NON_CONDUCTORS
            if q in self.wires:
                yield q
            elif solid and not ceiling and up in self.wires:
                self.assertEqual(self.wires[p][direction],'up')
                yield up
            elif not solid and down in self.wires:
                self.assertEqual(self.wires[p][direction],'side')
                yield down

    def timing_graph(self):
        # Read links and repeater directions from NBT instead of using the
        # generator's recorded nets; a bad short changes this reconstruction.
        graph = {p:set(self.wire_neighbors(p)) for p in self.wires}
        stamps, seen, live = {}, {}, {}
        cursor, tick = d.BUTTON, 0
        repeaters = defaultdict(list)
        for p,(kind,pr) in self.blocks.items():
            if kind=='repeater':
                self.assertEqual(pr['powered'],'false')
                self.assertEqual(pr['locked'],'false')
                side = str(pr['facing'])
                repeaters[at(p,side)].append((at(p,OPPOSITE[side]),2*int(pr['delay'])))
        while repeaters[cursor]:
            self.assertEqual(len(repeaters[cursor]),1)
            start, delay = repeaters[cursor].pop()
            self.assertNotIn(start,seen)
            tick += delay
            q = deque([(start,15)])
            exits = []
            while q:
                p,strength = q.popleft()
                if p in stamps:
                    self.assertEqual(stamps[p],tick)
                    continue
                self.assertGreater(strength,0,p)
                seen[p] = start
                stamps[p] = tick
                live[p] = strength
                if repeaters[p]:
                    exits.append(p)
                for neighbor in graph[p]:
                    self.assertIn(p,graph[neighbor])
                    q.append((neighbor,strength-1))
            if not exits:
                break
            self.assertEqual(len(exits),1)
            cursor, = exits
        self.assertEqual(set(stamps),set(self.wires))
        self.assertFalse(any(repeaters.values()))
        self.assertTrue(all(int(self.wires[p]['power'])==0 for p in live))
        return stamps

    def test_reconstruct_every_timed_note_and_light_from_export(self):
        tick = self.timing_graph()
        # Dust can power a device next to an opaque support: either from
        # above the support, or from a direction the wire points into.
        def inputs(p):
            for direct in DIR:
                q = at(p,direct)
                if q in tick and (direct=='up' or direct!='down' and self.wires[q][OPPOSITE[direct]]!='none'):
                    yield tick[q]
                if self.kind(q) in NON_CONDUCTORS:
                    continue
                if at(q,'up') in tick:
                    yield tick[at(q,'up')]
                for side in ('south','north','west','east'):
                    u = at(q,side)
                    if u in tick and self.wires[u][OPPOSITE[side]]!='none':
                        yield tick[u]

        notes = {}
        lamps = {}
        for p,(kind,pr) in self.blocks.items():
            if kind in ('note_block','redstone_lamp'):
                self.assertEqual(self.kind(at(p,'up')),'air')
                times = set(inputs(p))
                self.assertEqual(len(times),1,(p,times))
                t, = times
                if kind=='note_block':
                    self.assertEqual(pr['powered'],'false')
                    notes[t,p] = str(pr['instrument']),int(pr['note']),self.kind(at(p,'down'))
                else:
                    self.assertEqual(pr['lit'],'false')
                    lamps[t,p] = True

        launch = 12
        expected_notes,expected_lamps = {},{}
        for i,(t,frame) in enumerate(zip(s.ONSET_TICKS,s.FRAMES)):
            expected_lamps[t+launch,d.lamp_at(i)] = True
            for n in frame:
                v = s.VOICES[n.voice]
                expected_notes[t+launch,d.note_at(i,n.voice)] = v.instrument,n.pitch,v.material
        self.assertEqual(lamps,expected_lamps)
        self.assertEqual(notes,expected_notes)

    def test_standalone_scheme_has_a_walk_in_listening_point(self):
        self.assertEqual(int(self.file['MinecraftDataVersion']),5023)
        self.assertEqual(tuple(self.region['Size'][k] for k in 'xyz'),(56,39,59))
        self.assertEqual(len(self.blocks),int(self.file['Metadata']['TotalBlocks']))
        self.assertFalse(self.region['Entities'])
        self.assertFalse(any('command_block' in kind for kind,_ in self.blocks.values()))
        self.assertEqual(Counter(k for k,_ in self.blocks.values())['stone_button'],1)
        self.assertEqual(self.kind(d.BUTTON),'stone_button')
        # All sounding cells are within the note-block hearing radius from
        # the platform, with room for ears at ordinary player height.
        listener = tuple(map(math.floor,d.LISTEN))
        self.assertEqual(self.kind(listener),'air')
        self.assertEqual(self.kind((listener[0],listener[1]-2,listener[2])),d.TRIM)
        for p,(kind,_) in self.blocks.items():
            if kind=='note_block':
                self.assertLess(math.dist(tuple(a+.5 for a in p),d.LISTEN),40)

    def test_composition_varies_across_twenty_bars_and_eight_lanes(self):
        self.assertEqual(s.TOTAL_TICKS,20*48)
        self.assertEqual(len(s.FRAMES),320)
        self.assertEqual(len(s.SECTIONS),6)
        self.assertEqual(sum(map(len,s.FRAMES)),829)
        self.assertEqual(max(map(len,s.FRAMES)),8)
        for frame in s.FRAMES:
            self.assertEqual(len(frame),len({n.voice for n in frame}))
            self.assertTrue(all(0<=n.pitch<=24 for n in frame))
