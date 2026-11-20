import unittest
from collections import Counter

import nbtlib
import numpy as np

from tools import build_calculator as d, calculator_display as screen, calculator_logic as logic
from tools.vanilla_catacomb_test import unpack_region


class CalculatorLogicTests(unittest.TestCase):
    def test_every_operand_pair_and_opcode(self):
        # Eight 256×256 arrays check 524,288 input triples against Python.
        grid = np.arange(256, dtype=np.int32)
        a,b = np.meshgrid(grid, grid)
        nonzero = np.maximum(1,b)
        errors = b == 0
        expected = (a+b, a-b, a*b, np.where(errors,0,a//nonzero), np.where(errors,0,a%nonzero), a&b, a|b, a^b)
        network = logic.design()
        for code, result in enumerate(expected):
            with self.subTest(op=logic.MODES[code]):
                raw = {'A': a, 'B': b, 'M': np.int32(code)}
                values = network.evaluate({name: (raw[name[0]] >> int(name[1:]) & 1).astype(bool)
                                           for name in logic.INPUTS})
                out = network.outputs
                magnitude = sum(values[out[f'R{i}']].astype(np.int32) << i for i in range(16))
                negative = values[out['NEG']]
                np.testing.assert_array_equal(magnitude, np.abs(result))
                np.testing.assert_array_equal(negative, result<0)
                np.testing.assert_array_equal(values[out['ERR']], errors & (code in (3,4)))

    def test_netlist_uses_only_live_physical_gates(self):
        net = logic.design()
        active = net.live()
        self.assertTrue(set(net.inputs.values()) <= active)
        self.assertTrue(set(net.outputs.values()) <= active)
        self.assertTrue(active.isdisjoint((0,1)))
        self.assertEqual({net.gates[n].op for n in active}, {'INPUT','NOT','OR','DIFF'})
        self.assertTrue(all(all(i<n for i in net.gates[n].args) for n in active))
        self.assertEqual(len(active)-len(logic.INPUTS), 1186)


class DecimalDisplayTests(unittest.TestCase):
    def test_all_unsigned_words_render_five_decimal_digits_at_most(self):
        # Separate the converter from arithmetic; check every possible 16-bit word.
        c = logic.Circuit()
        word = list(c.inputs.values())[:16]
        outputs = screen.display(c, word, negative=0, error=0, ready=1)
        n = np.arange(65536, dtype=np.int32)
        values = c.evaluate({k: (n >> i & 1).astype(bool) if i<16 else False for i,k in enumerate(c.inputs)})
        for i in range(5):
            decade = 10**i
            digit = n//decade%10
            enabled = n>=decade if i else True
            for segment in screen.SEGMENTS:
                expected = np.isin(digit, [number for number,glyph in enumerate(screen.DIGITS) if segment in glyph])
                np.testing.assert_array_equal(values[outputs[f'D{i}{segment}']], expected & enabled)

    def test_timer_gates_decimal_output_until_ready(self):
        c = screen.design()
        for a,b,op in ((0,0,0),(255,255,2),(42,87,1),(197,19,3),(255,0,3),(255,0,4)):
            value,err = logic.reference(a,b,op)
            for hold in (False,True):
                inputs = logic.inputs_for(a,b,op) | {'HOLD': hold}
                signals = c.evaluate(inputs)
                actual = {k for k in d.SEGMENT_PADS if signals[c.outputs[k]]}
                self.assertEqual(actual, screen.glyphs(value,err,ready=not hold))
                self.assertEqual([signals[c.outputs[k]] for k in d.BAR_PADS], [not hold]*screen.STAGES)


class CalculatorExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = nbtlib.load(d.OUTPUT)
        cls.region, = cls.data['Regions'].values()
        cls.palette = [(str(b['Name']).removeprefix('minecraft:'), dict(b.get('Properties',{})))
                       for b in cls.region['BlockStatePalette']]
        cls.volume = unpack_region(cls.region)

    def at(self, p):
        x,y,z = p
        return self.palette[self.volume[y,z,x]]

    def test_port_positions_and_stable_zero_state(self):
        self.assertEqual(self.data['MinecraftDataVersion'], 5023)
        self.assertTrue(all(self.region['Position'][a]==0 for a in 'xyz'))
        self.assertEqual(np.count_nonzero(self.volume), self.data['Metadata']['TotalBlocks'])
        for k,p in d.LEVERS.items():
            self.assertEqual(self.at(p), ('lever', {'face':'floor','facing':'north','powered':'false'}), k)
            self.assertEqual(self.at(d.place(p,'south'))[1]['facing'], 'north', k)
            self.assertEqual(self.at(d.place(p,'down')), ('observer', {'facing':'up','powered':'false'}), k)
        for k,p in d.LAMPS.items():
            self.assertEqual(self.at(p), ('redstone_lamp', {'lit':'false'}), k)
            self.assertEqual(self.at(d.place(p,'south'))[1]['facing'], 'south', k)
        # Standing in front (Z < 7), the most significant bit is on the left.
        self.assertGreater(d.LEVERS['A7'][0],d.LEVERS['A0'][0])
        self.assertGreater(d.LEVERS['B7'][0],d.LEVERS['B0'][0])
        self.assertGreater(d.LAMPS['R15'][0],d.LAMPS['R0'][0])

    def test_export_has_real_supported_gates(self):
        counts = Counter()
        for j,count in enumerate(np.bincount(self.volume.ravel())):
            if count:
                counts[self.palette[j][0]] += count
        self.assertEqual(counts['lever'],19)
        self.assertEqual(counts['observer'],19)
        self.assertEqual(counts['redstone_lamp'],len(d.LAMPS)+sum(len(d.display_pixels(k)) for k in d.DISPLAY_CENTERS))
        network = screen.design()
        live_ops = Counter(network.gates[n].op for n in network.live())
        self.assertEqual(counts['comparator'],live_ops['DIFF'])
        self.assertEqual(counts['redstone_wall_torch'],live_ops['NOT'])
        self.assertEqual(len(self.region['Entities']),0)
        self.assertTrue(set(counts).isdisjoint({'command_block','chain_command_block','repeating_command_block','redstone_block'}))
        for i,(name,_) in enumerate(self.palette):
            if name in ('redstone_wire','repeater','comparator','lever'):
                ys,zs,xs = np.nonzero(self.volume==i)
                self.assertTrue((ys>0).all())
                for n in np.unique(self.volume[ys-1,zs,xs]):
                    self.assertNotIn(self.palette[n][0], {'air', *d.NON_SOLID})

    def test_comparator_outputs_are_baked_in_nbt(self):
        comparators = {tuple(int(e[a]) for a in 'xyz'): int(e['OutputSignal'])
                       for e in self.region['TileEntities'] if e['id'] == 'minecraft:comparator'}
        network = screen.design()
        self.assertEqual(len(comparators), sum(network.gates[n].op=='DIFF' for n in network.live()))
        for p, signal in comparators.items():
            self.assertIn(signal, (0,15))
            name, props = self.at(p)
            self.assertEqual(name, 'comparator')
            self.assertEqual(props['mode'], 'subtract')
            self.assertEqual(props['powered'], 'true' if signal else 'false')

    def test_screen_pixels_and_progress_bar_have_distinct_drivers(self):
        lit = screen.glyphs(0) | set(d.BAR_PADS)
        occupied = set()
        for k in d.DISPLAY_CENTERS:
            pixels = d.display_pixels(k)
            for p in pixels:
                self.assertNotIn(p, occupied)
                occupied.add(p)
                self.assertEqual(self.at(p), ('redstone_lamp', {'lit':str(k in lit).lower()}))
            # Each segment has two directly driven pixels. Adjacent pixels
            # see the strong signal without ever touching other segments.
            x,y,z = d.DISPLAY_CENTERS[k]
            for j in (-1,1):
                p = (x,y+j,z+1) if d.vertical_segment(k) else (x+j,y,z+1)
                name, props = self.at(p)
                self.assertEqual((name, props['facing']), ('repeater','south'))
        order = [d.DISPLAY_CENTERS[k][0] for k in d.BAR_PADS]
        self.assertEqual(order, sorted(set(order), reverse=True))
