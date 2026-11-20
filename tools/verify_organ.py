"""Check the released organ on a disposable vanilla Minecraft server."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
from pathlib import Path
import shutil
import tempfile
import time

import nbtlib
import numpy as np
from nbtlib import tag as nbt

from . import build_organ as d
from . import organ_score as s
from .vanilla_catacomb_test import OFFICIAL, Server, place_many, unpack_region, xyz

# The 1.21.11 server can also exercise the same block layout, with only a
# template-format conversion. The shipped Litematica file stays at 5023.
VERSION = {OFFICIAL:5023, '64bb6d763bed0a9f1d632ec347938594144943ed':4671}


def write_template(schematic,target,version):
    f = nbtlib.load(schematic)
    if f['MinecraftDataVersion']!=5023:
        raise ValueError('Expected the Java 26.3 Litematica export')
    region, = f['Regions'].values()
    assert not any(region['Position'][k] for k in 'xyz')
    grid = unpack_region(region)
    size = tuple(int(region['Size'][k]) for k in 'xyz')
    palette = region['BlockStatePalette']
    if version==5023:
        palette = nbt.List[nbt.Compound](
            nbt.Compound(id=p['Name'],**({'properties':p['Properties']} if 'Properties' in p else {})) for p in palette)
    tiles = {tuple(int(t[k]) for k in 'xyz'):nbt.Compound({k:v for k,v in t.items() if k not in 'xyz'})
             for t in region['TileEntities']}
    blocks = nbt.List[nbt.Compound]()
    for y,z,x in np.argwhere(grid):
        pos = int(x),int(y),int(z)
        block = nbt.Compound(pos=nbt.List[nbt.Int](pos),state=nbt.Int(int(grid[y,z,x])))
        if pos in tiles:
            block['nbt'] = tiles[pos]
        blocks.append(block)
    target.parent.mkdir(parents=True,exist_ok=True)
    nbtlib.File({'DataVersion':nbt.Int(version),'size':nbt.List[nbt.Int](size),'palette':palette,
                 'blocks':blocks,'entities':nbt.List[nbt.Compound]()},gzipped=True).save(target)
    return (0,0,0),tuple(n-1 for n in size)


class Bench(Server):
    java_options = ('-Xms320M','-Xmx1350M','-XX:ActiveProcessorCount=2')

    def step(self,n):
        goal = self.now()+n
        self.commands(f'tick step {n}t')
        limit = time.monotonic()+15
        while (t:=self.now())<goal:
            if time.monotonic()>limit:
                raise TimeoutError(f'Tick step did not reach {goal}')
            time.sleep(.004)
        if t!=goal:
            raise AssertionError(f'Stepped to {t}, expected {goal}')


def play(mc):
    launch = 12
    by_tick = defaultdict(list)
    end = launch+s.TOTAL_TICKS+s.PULSE_TICKS+8
    by_tick[s.PULSE_TICKS] = []

    def expect(t,p,kind,props):
        info = ','.join(f'{k}={v}' for k,v in props.items())
        by_tick[t].append(f'execute unless block {xyz(p)} minecraft:{kind}[{info}] run say ORGAN_BAD {t} {p} {info}')

    for i,(t,frame) in enumerate(zip(s.ONSET_TICKS,s.FRAMES)):
        t += launch
        for check in (t-1,t,end):
            lit = str(check==t).lower()
            expect(check,d.lamp_at(i),'redstone_lamp',{'lit':lit})
            for n in frame:
                expect(check,d.note_at(i,n.voice),'note_block',
                       {'instrument':s.VOICES[n.voice].instrument,'note':n.pitch,'powered':lit})

    def button(down):
        flag = str(down).lower()
        out = mc.commands(f'setblock {xyz(d.BUTTON)} minecraft:stone_button[face=floor,facing=north,powered={flag}]')
        if 'Changed the block' not in out:
            raise RuntimeError(out)

    button(True)
    previous = 0
    for t,checks in sorted(by_tick.items()):
        mc.step(t-previous)
        previous = t
        if t==s.PULSE_TICKS:
            button(False)
        for i in range(0,len(checks),576):
            out = mc.commands(*checks[i:i+576])
            bad = [line for line in out.splitlines() if '] ORGAN_BAD ' in line]
            if bad:
                raise AssertionError(f'Tick {t}: {len(bad)} mismatched blocks\n'+'\n'.join(bad[:16]))
        if t>=launch and t!=end and (t-launch)%(4*sum(s.STEP_TICKS))==0:
            print(f'PASS music deck {(t-launch)//(4*sum(s.STEP_TICKS))+1} at tick {t}',flush=True)
    print(f'PASS exact onset and end reset for {sum(map(len,s.FRAMES))} notes and {len(s.FRAMES)} lamps',flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--java',default='java')
    p.add_argument('--server',required=True,type=Path)
    p.add_argument('--schematic',default=d.OUTPUT,type=Path)
    p.add_argument('--log',type=Path)
    p.add_argument('--accept-minecraft-eula',action='store_true')
    args = p.parse_args()
    if not args.accept_minecraft_eula:
        p.error('Read https://aka.ms/MinecraftEULA before using the acceptance option')
    version = VERSION.get(hashlib.sha1(args.server.read_bytes()).hexdigest())
    if not version:
        p.error('Use the official unmodified Java 26.3 or 1.21.11 server.jar')
    print(f'Native check, DataVersion {version}',flush=True)
    with tempfile.TemporaryDirectory(prefix='moonspire-organ-vanilla-') as tmp:
        root = Path(tmp)
        folder = 'structure' if version==5023 else 'structures'
        target = root/'world/generated/minecraft'/folder/'organ.nbt'
        bounds = write_template(args.schematic,target,version)
        (root/'eula.txt').write_text('eula=true\n',encoding='utf-8')
        (root/'server.properties').write_text(
            'server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nmax-players=0\n'
            'enable-status=false\nlevel-type=minecraft:flat\nview-distance=3\nsimulation-distance=3\n'
            'spawn-protection=0\npause-when-empty-seconds=0\nmax-tick-time=-1\n',encoding='utf-8')
        mc = Bench(args.java,args.server.resolve(),root,rate=650)
        try:
            mc.start()
            place_many(mc,(('organ',bounds),),strict=False)
            mc.step(40)
            play(mc)
        finally:
            mc.stop()
            if args.log and (root/'logs/latest.log').is_file():
                shutil.copyfile(root/'logs/latest.log',args.log)


if __name__=='__main__':
    main()
