import unittest
from collections import deque

import nbtlib
import numpy as np

from tools import build_cathedral as cathedral


def unpack(region):
    """Read the serialized longs independently of the exporter's pack_states."""
    x, y, z = (int(region['Size'][axis]) for axis in 'xyz')
    n = x * y * z
    bits = max(2, (len(region['BlockStatePalette']) - 1).bit_length())
    longs = [int(word) & ((1 << 64) - 1) for word in region['BlockStates']]
    assert len(longs) == (n * bits + 63) // 64

    def indices():
        for offset in range(0, n * bits, bits):
            word, shift = divmod(offset, 64)
            value = longs[word] >> shift
            if shift + bits > 64:
                value |= longs[word + 1] << (64 - shift)
            yield value & ((1 << bits) - 1)

    return np.fromiter(indices(), dtype=np.uint16, count=n).reshape(y, z, x)


class CathedralSchematicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file = nbtlib.load(cathedral.OUTPUT)
        cls.region = cls.file['Regions']['Cathedral']
        cls.palette = cls.region['BlockStatePalette']
        cls.blocks = unpack(cls.region)

    def test_java_26_3_litematica_metadata(self):
        self.assertEqual(self.file['MinecraftDataVersion'], 5023)
        self.assertEqual((self.file['Version'], self.file['SubVersion']), (7, 1))
        self.assertEqual(self.region['Position'], {'x': 0, 'y': 0, 'z': 0})
        self.assertEqual(self.region['Size'], {'x': 169, 'y': 159, 'z': 255})
        meta = self.file['Metadata']
        self.assertEqual(meta['EnclosingSize'], self.region['Size'])
        self.assertEqual(meta['TotalVolume'], self.blocks.size)
        self.assertEqual(meta['TotalBlocks'], np.count_nonzero(self.blocks))
        self.assertEqual(self.palette[0]['Name'], 'minecraft:air')
        self.assertTrue(all(str(tag['Name']).startswith('minecraft:') for tag in self.palette))
        self.assertLess(self.blocks.max(), len(self.palette))
        self.assertEqual(len(self.region['Entities']), 0)
        self.assertEqual(len(self.region['TileEntities']), 0)

    def test_decoded_blocks_match_the_cathedral_model(self):
        drawn = cathedral.build()
        bounds = tuple(slice(a.min(), a.max() + 1) for a in np.nonzero(drawn))
        expected = drawn[bounds]
        by_state = {s: i for i, s in enumerate(cathedral.STATES)}
        mapping = [by_state[(str(tag['Name']), tuple(sorted((str(k), str(v)) for k, v in tag.get('Properties', {}).items())))]
                   for tag in self.palette]
        np.testing.assert_array_equal(np.array(mapping)[self.blocks], expected)

    def test_recolored_exports_preserve_every_block_position_and_property(self):
        def state(tag):
            props = tuple(sorted((str(k), str(v)) for k, v in tag.get('Properties', {}).items()))
            return str(tag['Name']), props

        for variant, masonry in (('dark', 'polished_blackstone_bricks'), ('light', 'quartz_bricks')):
            with self.subTest(variant=variant):
                other = nbtlib.load(cathedral.output_for(variant))
                region = other['Regions']['Cathedral']
                meta = other['Metadata']
                self.assertEqual((other['Version'], other['SubVersion'], other['MinecraftDataVersion']), (7, 1, 5023))
                self.assertEqual(region['Size'], self.region['Size'])
                self.assertEqual(region['Position'], self.region['Position'])
                self.assertEqual(meta['TotalBlocks'], self.file['Metadata']['TotalBlocks'])
                colorway = cathedral.COLORWAYS[variant]
                self.assertEqual(meta['Name'], f'{cathedral.TITLE} — {colorway.label}')
                self.assertEqual(len(meta['PreviewImageData']), 128**2)
                mapped = {state(entry): i for i, entry in enumerate(region['BlockStatePalette'])}
                self.assertEqual(mapped['minecraft:air', ()], 0)
                self.assertIn(('minecraft:' + masonry, ()), mapped)
                translated = []
                for tag in self.palette:
                    block, props = state(tag)
                    name = block.removeprefix('minecraft:')
                    translated.append(mapped['minecraft:' + colorway.materials.get(name, name), props])
                np.testing.assert_array_equal(unpack(region), np.array(translated, dtype=np.uint16)[self.blocks])

    def test_portals_nave_sanctuary_and_apse_connect(self):
        # A topology check, not a simulation of Minecraft player collision.
        # Treat carved stairs as support and check two open blocks above each tread.
        low = self.blocks[:12]
        carpet = [i for i, tag in enumerate(self.palette) if str(tag['Name']).endswith('_carpet')]
        open_space = (low == 0) | np.isin(low, carpet)
        surface = ~open_space[:-2] & open_space[1:-1] & open_space[2:]

        def point(x, y, z):
            return y, z + 31, x + 84

        front = point(0, 0, -31)
        targets = {point(-84, 0, 120), point(84, 0, 120), point(0, 4, 120),
                   point(0, 7, 169), point(0, 4, 208)}
        self.assertTrue(surface[front])
        reached, queue = {front}, deque([front])
        while queue and not targets <= reached:
            y, z, x = queue.popleft()
            for dz, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                if not (0 <= z + dz < surface.shape[1] and 0 <= x + dx < surface.shape[2]):
                    continue
                for h in range(max(0, y - 1), min(surface.shape[0], y + 2)):
                    dest = (h, z + dz, x + dx)
                    if surface[dest] and dest not in reached:
                        reached.add(dest)
                        queue.append(dest)
        self.assertFalse(targets - reached, f'Unreachable floor positions: {targets - reached}')


if __name__ == '__main__':
    unittest.main()
