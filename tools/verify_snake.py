"""Verify the real Snake redstone on a vanilla Java 26.3 server.

The harness places the schematic, simulates button presses, and reads lamps.
It never writes a register, clock, food, or screen pixel.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import cache
from pathlib import Path
import shutil
import tempfile

from . import build_snake as d
from . import snake_logic as logic
from .vanilla_catacomb_test import read_args, xyz
from .verify_calculator import CalculatorServer, sparse_template

SHORT = ('LEFT', 'RIGHT', 'RIGHT', 'RESET', 'UP', 'UP', 'UP', 'DOWN', 'RESET')
TAIL = ('RIGHT', 'UP', 'RIGHT', 'DOWN', 'LEFT')
BODY = ('RIGHT', 'RIGHT', 'DOWN', 'LEFT', 'DOWN', 'RIGHT', 'UP')
COVER = ('DOWN', 'DOWN', 'RIGHT', 'RIGHT', 'UP', 'UP', 'UP', 'LEFT', 'LEFT', 'LEFT')
PERIMETER = ('DOWN',)*3 + ('RIGHT',)*3 + ('UP',)*5 + ('LEFT',)*5 + ('DOWN',)*5


@contextmanager
def test_world(args):
    with tempfile.TemporaryDirectory(prefix='moonspire-snake-') as tmp:
        root = Path(tmp)
        (root/'eula.txt').write_text('eula=true\n', encoding='utf-8')
        (root/'server.properties').write_text(
            'server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nmax-players=0\n'
            'enable-status=false\nlevel-type=minecraft:flat\nview-distance=3\n'
            'simulation-distance=3\nspawn-protection=0\npause-when-empty-seconds=0\n'
            'max-tick-time=-1\n', encoding='utf-8')
        _, end = sparse_template(args.schematic, root/'world/generated/minecraft/structure/snake.nbt')
        mc = CalculatorServer(args.java, args.server.resolve(), root)
        try:
            mc.start()
            mc.commands('gamerule minecraft:spawn_mobs false')
            for x in range(0, end[0]+1, 128):
                out=mc.commands(f'forceload add {x} 0 {min(x+127,end[0])} {end[2]}')
                if 'force load' not in out.lower():
                    raise RuntimeError(out)
            mc.step(24)
            strict = '' if args.neighbor_updates else ' strict'
            out=mc.commands(f'place template minecraft:snake {xyz((0,0,0))} none none 1.0 0{strict}')
            if 'Loaded template' not in out:
                raise RuntimeError(out)
            print(f'Native placement: {tuple(n+1 for n in end)}; neighbor updates={args.neighbor_updates}', flush=True)
            yield mc
        finally:
            mc.stop()
            log = root/'logs/latest.log'
            if args.log and log.is_file():
                shutil.copyfile(log,args.log)


def at(p):
    return xyz(d.export_point(p))


def button(mc, key, down):
    pos=at(d.KEYS[key])
    out=mc.commands(f'setblock {pos} minecraft:stone_button[face=floor,facing=north,powered={str(down).lower()}]')
    if 'Changed the block' not in out:
        raise RuntimeError(out)


def is_ready(mc):
    checks=' '.join(f'if block {at(p)} minecraft:redstone_lamp[lit=true]' for p in d.pixels('READY'))
    return ' SNAKE_READY_TRUE' in mc.commands(f'execute {checks} run say SNAKE_READY_TRUE')


def trail_pixels(game):
    """Rasterize the rules' ordered path independently of the rear drivers."""
    pitch=d.BOARD_SIZE//logic.SIZE
    z=d.screen.FRONT_Z
    centers=[(d.SCREEN_MIN_X+(logic.SIZE-1-x)*pitch+5,
              d.SCREEN_MIN_Y+(logic.SIZE-1-y)*pitch+4) for x,y in game.body]
    lamps={(x,y,z) for x,y in centers}
    for (x0,y0),(x1,y1) in zip(centers,centers[1:]):
        dx,dy=(x1-x0)//pitch,(y1-y0)//pitch
        lamps.update((x0+dx*i,y0+dy*i,z) for i in range(1,pitch))
    return lamps


@cache
def lamp_checks():
    return tuple((p,at(p),key or 'background') for key,p in d.display_lamps())


def expect(mc, game, ready=True):
    # Test the exact one-block path and all the other lamps, including the
    # dark matrix between strokes. Even one stray lit neighbor is a fault.
    want=trail_pixels(game)
    for key in logic.screen_lights(game,ready):
        if not key.startswith(('B','E','V')):
            want.update(d.pixels(key))
    commands=[f'execute unless block {pos} minecraft:redstone_lamp[lit={str(p in want).lower()}] run say SNAKE_BAD_{key}_{p}'
              for p,pos,key in lamp_checks()]
    for start in range(0,len(commands),768):
        out=mc.commands(*commands[start:start+768])
        faults=[line for line in out.splitlines() if ' SNAKE_BAD_' in line]
        if faults:
            raise AssertionError(f'{game}: {len(faults)} wrong lamps in batch {start}: {faults[:12]}')


def move(mc, game, keys, ticks, *, hold=False, test_busy=False):
    for k in keys:
        button(mc,k,True)
    key=min(keys,key=('RESET',*logic.DIRECTIONS).index)
    target=logic.play(game,key)
    started = mc.now()
    if not hold:
        mc.step(20)
        for k in keys:
            button(mc,k,False)
    if test_busy:
        mc.step(300)  # wait for the busy signal to reach the display
        if is_ready(mc):
            raise AssertionError('READY did not turn off for the move')
        # A second tap inside the busy interval must not make a second turn.
        blocked = 'LEFT' if 'DOWN' in keys else 'DOWN'
        button(mc,blocked,True)
    elapsed=mc.now()-started
    ready_at=None
    if test_busy:
        # Check the rising READY edge, then continue without an extra wait.
        # The blocked button stays down across that edge; it must not replay.
        mc.step(max(1,ticks-elapsed-160))
        while mc.now()-started<ticks and not is_ready(mc):
            mc.step(4)
        ready_at=mc.now()-started
        button(mc,blocked,False)
    else:
        mc.step(ticks-elapsed)
    expect(mc,target)
    if ready_at is not None:
        print(f'PASS READY after {ready_at} game ticks (sampled); busy press discarded',flush=True)
    if hold:
        mc.step(ticks)
        expect(mc,target)
        for k in keys:
            button(mc,k,False)
        mc.step(32)
        expect(mc,target)
    print(f'PASS {"+".join(keys):12} head={target.body[0]} length={len(target.body)} '
          f'{"WIN" if target.won else "LOSE" if target.dead else ""}', flush=True)
    return target


def configure(parser):
    parser.add_argument('--ticks',type=int,default=1230,help='Maximum expected game ticks per move')
    parser.add_argument('--log',type=Path)
    suite=parser.add_mutually_exclusive_group()
    suite.add_argument('--smoke',action='store_true',help='Check initial state and one normal move')
    suite.add_argument('--win',action='store_true',help='Check the winning route and reset')


def main():
    args=read_args(__doc__,configure=configure,default_schematic=d.OUTPUT)
    if args.ticks<=360:
        raise ValueError('Allow enough ticks for the two capture phases and the display')
    with test_world(args) as mc:
        game=logic.Round()
        mc.step(args.ticks)
        expect(mc,game)
        print('PASS ready / initial lamps',flush=True)
        if args.smoke:
            move(mc,game,('RIGHT',),args.ticks,test_busy=True)
            return
        if args.win:
            for i,key in enumerate(logic.WIN_ROUTE):
                game=move(mc,game,(key,),args.ticks,test_busy=i==0)
            move(mc,game,('RESET',),args.ticks)
            return
        for i,key in enumerate(SHORT):
            game=move(mc,game,(key,),args.ticks,test_busy=i==1)
        for path in (TAIL,BODY,COVER,PERIMETER,logic.WIN_ROUTE):
            for key in path:
                game=move(mc,game,(key,),args.ticks)
            if game.won:
                game=move(mc,game,('LEFT',),args.ticks)  # freeze after victory
            game=move(mc,game,('RESET',),args.ticks)
        move(mc,game,('RIGHT','RESET'),args.ticks)
        move(mc,game,('RIGHT',),args.ticks,hold=True)
        print('PASS all native rounds, reset priority, busy interlock and held input',flush=True)


if __name__=='__main__':
    main()
