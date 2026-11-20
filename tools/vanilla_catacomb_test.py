"""Native-template bridge and tick control shared by the vanilla 26.3 integration tests."""

from __future__ import annotations

import argparse
import hashlib
import queue
import re
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import nbtlib
import numpy as np
from nbtlib import tag as nbt

from . import build_catacomb_cathedral as b

OFFICIAL = '33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c'
SCHEMATIC_MIN = (-203, -43, -71)
Y_LIFT = 72  # Same physical heights as a Catacombs placement with origin Y=29.


def unpack_region(region, origin=(0, 0, 0), size=None):
    """Decode a region-local XYZ cuboid without allocating the whole abbey."""
    extent = tuple(int(region['Size'][a]) for a in 'xyz')
    size = extent if size is None else size
    if any(a < 0 or n < 1 or a + n > end for a, n, end in zip(origin, size, extent)):
        raise ValueError('Mechanism crop not contained in the schematic')
    x, y, z = (np.arange(a, a + n, dtype=np.uint64) for a, n in zip(origin, size))
    nx, _, nz = extent
    bits = max(2, (len(region['BlockStatePalette']) - 1).bit_length())
    words = np.asarray(region['BlockStates'], dtype=np.uint64)
    offsets = (x + nx * (z[:, None] + nz * y[:, None, None])) * bits
    word, bit = offsets // 64, offsets % 64
    data = words[word] >> bit
    split = bit + bits > 64
    data[split] |= words[word[split] + 1] << (64 - bit[split])
    return (data & ((1 << bits) - 1)).astype(np.uint16)


def template(schematic: Path, dst: Path, bounds, *, schematic_min=SCHEMATIC_MIN) -> None:
    lo, hi = bounds
    file = nbtlib.load(schematic)
    if file['MinecraftDataVersion'] != 5023:
        raise ValueError('Expected a 26.3 Litematica schematic')
    region = file['Regions']['Cathedral']
    palette = region['BlockStatePalette']
    tile = {tuple(int(t[a]) for a in 'xyz'): nbt.Compound({k: v for k, v in t.items() if k not in 'xyz'})
            for t in region['TileEntities']}
    low = tuple(x - a for x, a in zip(lo, schematic_min))
    dims = tuple(z - x + 1 for x, z in zip(lo, hi))
    ix, iy, iz = low
    volume = unpack_region(region, low, dims)
    types = sorted(np.unique(volume))
    local = {old: i for i, old in enumerate(types)}
    blocks = nbt.List[nbt.Compound]()
    for y, z, x in np.ndindex(volume.shape):
        entry = nbt.Compound(pos=nbt.List[nbt.Int]((x, y, z)), state=nbt.Int(local[volume[y, z, x]]))
        if data := tile.get((ix + x, iy + y, iz + z)):
            entry['nbt'] = data
        blocks.append(entry)
    dst.parent.mkdir(parents=True, exist_ok=True)
    # 26.3's native structure palette uses lowercase keys. The Litematica
    # palette intentionally keeps Name/Properties (as written by MaLiLib).
    states = nbt.List[nbt.Compound]()
    for i in types:
        entry = palette[int(i)]
        native = nbt.Compound(id=entry['Name'])
        if 'Properties' in entry:
            native['properties'] = entry['Properties']
        states.append(native)
    nbtlib.File({'DataVersion': nbt.Int(5023), 'size': nbt.List[nbt.Int](dims), 'palette': states,
                 'blocks': blocks, 'entities': nbt.List[nbt.Compound]()}, gzipped=True).save(dst)


def xyz(p) -> str:
    return f'{p[0]} {p[1] + Y_LIFT} {p[2]}'


class Server:
    java_options = ('-Xms256M', '-Xmx1200M')

    def __init__(self, java, jar, directory, rate=100):
        self.java, self.jar, self.directory = java, jar, directory
        self.process = None
        self.rate = rate

    def start(self):
        self.lines = queue.Queue()
        self.process = subprocess.Popen([self.java, *self.java_options, '-jar', str(self.jar), 'nogui'],
                                        cwd=self.directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        self.reader = threading.Thread(target=self.read, args=(self.process.stdout, self.lines), daemon=True)
        self.reader.start()
        self.until(r'\bDone \(', timeout=75)
        self.commands('tick freeze', f'tick rate {self.rate}')

    @staticmethod
    def read(stdout, lines):
        for line in stdout:
            lines.put(line.rstrip('\n'))
        lines.put(None)

    def until(self, pattern, timeout=15):
        deadline = time.monotonic() + timeout
        lines = []
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                break
            if line is None:
                break
            if re.search(pattern, line):
                return lines, line
            lines.append(line)
        raise RuntimeError(f'Server did not emit {pattern!r}:\n' + '\n'.join(lines[-25:]))

    def commands(self, *commands):
        self.process.stdin.write('\n'.join((*commands, 'say ZZ_MARKER_ZZ', '')))
        self.process.stdin.flush()
        lines, _ = self.until(r'\[Server\] ZZ_MARKER_ZZ', timeout=30)
        return '\n'.join(lines)

    def checked(self, condition, message):
        lines = self.commands(f'execute {condition} run say ZZ_OK_ZZ')
        if '] ZZ_OK_ZZ' not in lines:
            raise AssertionError(f'{message}: {condition}\n{lines}')

    def now(self):
        lines = self.commands('time query gametime')
        match = re.search(r'The (?:game )?time is (\d+)', lines)
        if match is None:
            raise RuntimeError(lines)
        return int(match[1])

    def step(self, n):
        done = self.now() + n
        self.commands(f'tick step {n}t')
        wait = time.monotonic() + 20 + n / 40
        while self.now() < done:
            if time.monotonic() > wait:
                raise TimeoutError(f'Expected game time {done}')
            time.sleep(0.05)

    def stop(self):
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    self.process.stdin.write('stop\n')
                    self.process.stdin.flush()
                self.process.wait(timeout=30)
            finally:
                if self.process.poll() is None:
                    self.process.kill()
                    self.process.wait()
                self.reader.join(timeout=2)
                self.process.stdin.close()
                self.process.stdout.close()
                self.process = None

    def block(self, p, state):
        self.checked(f'if block {xyz(p)} minecraft:{state}', 'Block state')


def read_args(description, *, configure=None, default_schematic=b.OUTPUT):
    parser = argparse.ArgumentParser(description=description)
    if configure is not None:
        configure(parser)
    parser.add_argument('--java', default='java')
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--schematic', default=default_schematic, type=Path)
    parser.add_argument('--neighbor-updates', action='store_true', help='Place with ordinary vanilla neighbor updates')
    parser.add_argument('--accept-minecraft-eula', action='store_true',
                        help='Confirm acceptance of https://aka.ms/MinecraftEULA for this local test')
    args = parser.parse_args()
    if not args.accept_minecraft_eula:
        parser.error('Read https://aka.ms/MinecraftEULA before setting --accept-minecraft-eula')
    if hashlib.sha1(args.server.read_bytes()).hexdigest() != OFFICIAL:
        parser.error('Expected a byte-identical official vanilla 26.3 server.jar')
    return args


@contextmanager
def session(args, name, bounds, server_type=Server, *, rate=100, extra=(), schematic_min=SCHEMATIC_MIN):
    """Stage the exported core and optional additional crops in a disposable world."""
    with tempfile.TemporaryDirectory(prefix='moonspire-vanilla-') as tmp:
        world = Path(tmp)
        (world / 'eula.txt').write_text('eula=true\n', encoding='utf-8')
        (world / 'server.properties').write_text(
            'server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nmax-players=0\n'
            'enable-status=false\nlevel-type=minecraft:flat\nview-distance=6\nsimulation-distance=6\n'
            'spawn-protection=0\npause-when-empty-seconds=0\n', encoding='utf-8')
        for part, volume in ((name, bounds), *extra):
            template(args.schematic, world / f'world/generated/minecraft/structure/{part}.nbt', volume,
                     schematic_min=schematic_min)
        server = server_type(args.java, args.server.resolve(), world, rate=rate)
        try:
            server.start()
            yield server
        finally:
            server.stop()


def place(server, name, bounds, *, strict=True, padding=0):
    place_many(server, ((name, bounds),), strict=strict, padding=padding)


def place_many(server, parts, *, strict=True, padding=0):
    server.commands('gamerule minecraft:spawn_mobs false')
    queue = []
    for name, ((x, y, z), (xx, _, zz)) in parts:
        loaded = server.commands(f'forceload add {x - padding} {z - padding} {xx + padding} {zz + padding}')
        if 'force load' not in loaded.lower() and 'already force loaded' not in loaded.lower():
            raise RuntimeError(loaded)
        queue.append(f'place template minecraft:{name} {xyz((x, y, z))} none none 1.0 0'
                     + (' strict' if strict else ''))
    server.step(20)
    # Keep the game frozen between overlapping pieces of the same fluid channel.
    for command in queue:
        placed = server.commands(command)
        if 'Loaded template' not in placed:
            raise RuntimeError(placed)
