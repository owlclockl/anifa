"""Play the shipped Snake datapack on a disposable vanilla Java server."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from dataclasses import replace

from . import build_snake_live as b
from . import snake_live_rules as g
from .vanilla_catacomb_test import Server
from .verify_organ import VERSION

# Deliberately offset from chunk borders; the install is not at world spawn.
ORIGIN = (11, 64, 14)
TEST = 'ms_sweep'
TNS = 'moonspire_sweep'
READY, RUN, PAUSE, LOSS, WIN = range(5)


def absolute(p):
    return ' '.join(str(a+c) for a,c in zip(ORIGIN,p))


def at_anchor(command):
    return f'execute positioned {absolute(g.ANCHOR)} run {command}'


def push(key):
    return f'setblock {absolute(g.BUTTONS[key])} {g.BUTTON.format("true")}'


class Bench(Server):
    java_options = ('-Xms350M','-Xmx1400M','-XX:ActiveProcessorCount=2')

    def score(self, key, value, objective=b.OBJ):
        self.checked(f'if score #{key} {objective} matches {value}', f'Expected #{key} = {value}')

    def action(self, key):
        self.commands(push(key))

    def button_up(self, key):
        self.checked(f'if block {absolute(g.BUTTONS[key])} {g.BUTTON.format("false")}', 'Button not re-armed')

    def fruit(self):
        line = self.commands(f'data get storage {b.DATA} apple')
        coordinates = {key:int(value) for key,value in re.findall(r'([xy]):\s*(-?\d+)',line)}
        if len(coordinates)!=2:
            raise AssertionError(line)
        return coordinates['x'],coordinates['y']

    def inspect(self, frame, mode=RUN, full=False):
        # Assert object order as well as exact lamp states. A found body compound
        # alone would not catch head/tail swaps or the wrong order after a turn.
        body = '['+','.join(f'{{x:{x},y:{y}}}' for x,y in frame.body)+']'
        checks = [f'execute unless {b.eq(key,value)} run say LIVE_BAD score {key} != {value}'
                  for key,value in {'x':frame.body[0][0], 'y':frame.body[0][1],
                                    'mode':mode, 'score':frame.score, 'grow':frame.growth,
                                    'fruit':int(frame.fruit is not None)}.items()]
        checks += [f'execute unless data storage {b.DATA} {{body:{body}}} run say LIVE_BAD missing body entry',
                   f'data get storage {b.DATA} body']
        result = self.no_errors(checks)
        seen = tuple((int(x),int(y)) for x,y in re.findall(r'\{x:\s*(-?\d+),\s*y:\s*(-?\d+)\}',result))
        if seen!=frame.body:
            raise AssertionError(f'Expected ordered trail {frame.body}; got {seen}\n{result}')
        if frame.fruit and self.fruit()!=frame.fruit:
            raise AssertionError('Wrong fruit position')
        self.lamps(frame.lit, mode, frame.score, full=full)

    def no_errors(self, checks):
        result = self.commands(*checks)
        if 'LIVE_BAD' in result:
            raise AssertionError('\n'.join(l for l in result.splitlines() if 'LIVE_BAD' in l)[:2000])
        return result

    def lamps(self, lit, mode, apples, *, full):
        def check(p,on):
            return f'execute unless block {absolute(p)} {b.LAMP}[lit={str(on).lower()}] run say LIVE_BAD lamp {p} {on}'

        points = ((x,y) for y in range(g.SIDE) for x in range(g.SIDE)) if full else sorted(lit)
        checks = [check(g.pixel(x,y),(x,y) in lit) for x,y in points]
        on = {'run':mode==RUN, 'loss':mode==LOSS, 'win':mode==WIN}
        on.update({f'apple{i}':apples>=i for i in range(1,g.GOAL+1)})
        checks += [check(p,on[key]) for key in g.HUD for p in b.hud_pixels(key)]
        for i in range(0,len(checks),720):
            self.no_errors(checks[i:i+720])

    def set_fruit(self, fruit):
        self.commands(at_anchor(f'execute if {b.eq("fruit",1)} run {b.fn("fruit/dark")} with storage {b.DATA} apple'),
                      b.setscore('fruit',0))
        if fruit is not None:
            self.commands(b.setscore('ax',fruit[0]),b.setscore('ay',fruit[1]),at_anchor(b.fn('fruit/accept')))

    def seed(self, frame):
        """Put a fixture on the same plane without using the movement code."""
        x,y=frame.body[0]
        tail = '['+','.join(f'{{x:{u},y:{v}}}' for u,v in frame.body)+']'
        state = {'x':x,'y':y,'dir':g.KEYS.index(frame.heading),'queued':g.KEYS.index(frame.heading),
                 'score':frame.score,'grow':frame.growth,'mode':RUN,'timer':g.STEP_TICKS,'fruit':0}
        self.commands(at_anchor(b.fn('clear')),
                      f'data modify storage {b.DATA} body set value {tail}',
                      *(b.setscore(k,v) for k,v in state.items()),
                      *(f'setblock {absolute((u+g.X0,g.Y_TOP-v,g.ZFACE-1))} {b.POWER}' for u,v in frame.body),
                      at_anchor(b.fn('hud/playing')))
        self.set_fruit(frame.fruit)


def install(mc):
    x,_,z=ORIGIN
    w,_,d=g.SIZE
    mc.commands(f'forceload add {x} {z} {x+w-1} {z+d-1}')
    mc.step(25)
    result=mc.commands(f'place template {b.NS}:board {absolute((0,0,0))} none none 1.0 0')
    if 'Loaded template' not in result or 'Serialization errors' in result:
        raise AssertionError(result)
    _,signs=b.geometry()
    for p,text in signs.items():
        front=text['front_text'].snbt(compact=True)
        mc.checked(f'if data block {absolute(p)} {{front_text:{front}}}', 'Sign did not retain its label')
    mc.commands(f'execute positioned {absolute((1,0,0))} run {b.fn("install")}')
    mc.score('installed',0)
    mc.commands(f'execute positioned {absolute((0,0,0))} run {b.fn("install")}')
    mc.score('installed',1)
    mc.inspect(g.Frame(),READY,full=True)
    print('Install: correct offset, start frame, all field and HUD lamps',flush=True)


def controls(mc):
    mc.action('new')
    mc.step(1)
    mc.button_up('new')
    mc.step(g.START_TICKS-1)
    r=g.Frame()
    mc.inspect(r)
    mc.step(1)
    r=g.move(r)
    mc.inspect(r)
    mc.step(g.STEP_TICKS-1)
    mc.inspect(r)
    mc.step(1)
    r=g.move(r)
    mc.inspect(r)
    for key in ('left','up','right','up'):
        mc.action(key)
        mc.step(g.STEP_TICKS)
        mc.button_up(key)
        r=g.move(r,key)
        mc.inspect(r)
    mc.action('pause')
    mc.step(1+g.STEP_TICKS*3)
    mc.button_up('pause')
    mc.inspect(r,PAUSE,full=True)
    mc.action('pause')
    mc.step(1)
    mc.inspect(r)
    mc.commands(b.fn('speed/slow'))
    mc.step(g.STEP_TICKS)
    r=g.move(r)
    mc.inspect(r)
    mc.step(g.SLOW_TICKS-1)
    mc.inspect(r)
    mc.step(1)
    mc.inspect(g.move(r),full=True)
    mc.commands(b.fn('speed/normal'))
    print('Controls: exact cadence, no reversal, repeat taps, pause/resume, slow setting',flush=True)


def apples(mc):
    mc.action('new')
    mc.step(1+g.START_TICKS)
    r=g.move(g.Frame())
    for i in range(1,g.GOAL+1):
        bite=r.fruit[0]-g.RADIUS
        while r.body[0][0]<bite-1:
            mc.step(g.STEP_TICKS)
            r=g.move(r)
        mc.step(g.STEP_TICKS)
        if i<g.GOAL:
            apple=mc.fruit()
            r=g.move(r,spawn=apple)
            mc.inspect(r,full=True)
            # Random fruit placement was verified above. Use the same renderer
            # at a known safe point to make the rest of the play reproducible.
            new_fruit=g.FIRST[0]+8*i,g.FIRST[1]
            assert g.valid_fruit(new_fruit,r.body)
            mc.set_fruit(new_fruit)
            r=replace(r,fruit=new_fruit)
            for _ in range(g.GAIN-1):
                mc.step(g.STEP_TICKS)
                r=g.move(r)
                mc.inspect(r)
            assert len(r.body)==len(g.START)+i*g.GAIN
        else:
            r=g.move(r)
            mc.inspect(r,WIN,full=True)
    mc.action('left')
    mc.step(1+g.STEP_TICKS)
    mc.inspect(r,WIN)
    print('Apples: random free positions, immediate extinguish, growth and win lock',flush=True)


def collisions(mc):
    loop=((20,20),(19,20),(19,21),(20,21))
    tests=((g.Frame(body=loop,fruit=None),'down',RUN),
           (g.Frame(body=loop,growth=1,fruit=None),'down',LOSS),
           (g.Frame(body=(*loop,(21,21)),fruit=None),'down',LOSS),
           (g.Frame(body=((71,71),(70,71),(69,71)),fruit=None),None,LOSS))
    for frame,key,mode in tests:
        mc.seed(frame)
        if key:
            mc.action(key)
        mc.step(g.STEP_TICKS)
        r=g.move(frame,key)
        mc.inspect(r,mode,full=True)
        if mode==LOSS:
            mc.action('up')
            mc.step(g.STEP_TICKS+1)
            mc.inspect(r,LOSS)
    mc.action('new')
    mc.step(1)
    mc.inspect(g.Frame(),full=True)
    print('Collisions: wall/body and growing tail freeze; departing tail is legal; reset works',flush=True)


def sweep_pack(folder):
    """Add an independent per-tick observer; leave the real tick hook untouched."""
    def write(name, body):
        path=folder/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(body+'\n',encoding='utf-8')

    def function(name, *lines):
        write(f'data/{TNS}/function/{name}.mcfunction','\n'.join(lines))

    def test(key,n):
        return f'score #{key} {TEST} matches {n}'

    def op(out,operator,src):
        return f'scoreboard players operation #{out} {TEST} {operator} #{src} {TEST}'

    store=f'{TNS}:cursor'
    write('pack.mcmeta',json.dumps({'pack':{'description':'Test observer','min_format':[94,1],'max_format':[121,0]}}))
    write('data/minecraft/tags/function/tick.json',json.dumps({'values':[TNS+':observe']}))
    function('observe',f'execute if {test("on",1)} run function {TNS}:tick')
    function('tick',f'scoreboard players add #phase {TEST} 1',
             f'execute if {test("phase",g.STEP_TICKS)} run function {TNS}:moved',
             *(f'execute unless score #{a} {TEST} = #{a} {b.OBJ} run function {TNS}:bad' for a in 'xy'),
             f'execute unless {b.eq("mode",RUN)} run function {TNS}:bad')
    function('bad',f'scoreboard players add #errors {TEST} 1')
    function('moved',f'scoreboard players set #phase {TEST} 0',
             op('y','=','index'),op('y','/=','side'),op('col','=','index'),op('col','%=','side'),
             op('odd','=','y'),op('odd','%=','two'),op('x','=','col'),
             f'execute if {test("odd",1)} run {op("x","=","last")}',
             f'execute if {test("odd",1)} run {op("x","-=","col")}',
             *(f'execute store result storage {store} head.{a} int 1 run scoreboard players get #{a} {TEST}' for a in 'xy'),
             at_anchor(f'function {TNS}:head with storage {store} head'),
             at_anchor(f'function {TNS}:tail with storage {store} tail'),
             f'data modify storage {store} tail set from storage {b.DATA} body[-1]',
             f'scoreboard players add #index {TEST} 1',
             f'execute if {test("index",g.SIDE**2)} run return run scoreboard players set #on {TEST} 0',
             f'execute if {test("col",0)} if {test("odd",0)} run {push("right")}',
             f'execute if {test("col",0)} if {test("odd",1)} run {push("left")}',
             f'execute if {test("col",g.SIDE-1)} run {push("down")}')
    function('head',f'$execute unless block ~$(x) ~-$(y) ~{g.ZFACE} {b.LAMP}[lit=true] run function {TNS}:bad',
             f'$execute unless block ~$(x) ~-$(y) ~{g.ZFACE-1} {b.POWER} run function {TNS}:bad')
    function('tail',f'$execute unless block ~$(x) ~-$(y) ~{g.ZFACE} {b.LAMP}[lit=false] run function {TNS}:bad')


def sweep(mc):
    # First move is (0,1) -> (0,0). Every subsequent row enters on the edge;
    # two consecutive one-lamp right-angle turns start the next row.
    r=g.Frame(tuple((0,y) for y in range(1,len(g.START)+1)),heading='up',fruit=None)
    mc.seed(r)
    mc.commands(f'scoreboard objectives add {TEST} dummy',
                *(f'scoreboard players set #{k} {TEST} {v}' for k,v in {
                    'on':1, 'phase':0, 'x':0, 'y':1, 'index':0, 'errors':0,
                    'side':g.SIDE, 'last':g.SIDE-1, 'two':2}.items()),
                f'data modify storage {TNS}:cursor tail set from storage {b.DATA} body[-1]')
    mc.step(g.STEP_TICKS*g.SIDE**2)
    mc.score('index',g.SIDE**2,TEST)
    mc.score('errors',0,TEST)
    for y in range(g.SIDE):
        xs=range(g.SIDE) if y%2==0 else range(g.SIDE-1,-1,-1)
        for x in xs:
            px,py=r.body[0]
            key=next(k for k,v in g.DIRECTION.items() if v==(x-px,y-py))
            r=g.move(r,key)
    mc.inspect(r,full=True)
    print(f'Sweep: {g.SIDE**2:,} successive heads checked on real lamps, at {g.STEP_TICKS} ticks per lamp',flush=True)
    mc.commands(b.fn('uninstall'))
    mc.score('installed',0)
    mc.checked(f'unless entity @e[type=minecraft:marker,tag={b.TAG}]','Uninstall left a marker')
    mc.lamps(set(),READY,0,full=True)
    print('Uninstall: marker removed and every lamp off',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--java',default='java')
    p.add_argument('--server',type=Path,required=True)
    p.add_argument('--pack',type=Path,default=b.PACK)
    p.add_argument('--log',type=Path,help='Save the vanilla server log outside the temporary world')
    p.add_argument('--accept-minecraft-eula',action='store_true',help='Accept https://aka.ms/MinecraftEULA for this test')
    a=p.parse_args()
    if not a.accept_minecraft_eula:
        p.error('Read and accept the Minecraft EULA before running a vanilla server')
    version=VERSION.get(hashlib.sha1(a.server.read_bytes()).hexdigest())
    if version is None:
        p.error('Expected a byte-identical vanilla server.jar for Java 26.3 or 1.21.11')
    print(f'Verifying unmodified datapack at DataVersion {version}',flush=True)
    with tempfile.TemporaryDirectory(prefix='moonspire-snake-live-') as tmp:
        root=Path(tmp)
        (root/'eula.txt').write_text('eula=true\n',encoding='utf-8')
        (root/'server.properties').write_text(
            'server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nmax-players=0\n'
            'enable-status=false\nlevel-type=minecraft:flat\nview-distance=3\nsimulation-distance=3\n'
            'spawn-protection=0\npause-when-empty-seconds=0\nmax-tick-time=-1\n',encoding='utf-8')
        dst=root/'world/datapacks'
        dst.mkdir(parents=True)
        shutil.copyfile(a.pack,dst/'live.zip')
        sweep_pack(dst/'zz_live_test')
        mc=Bench(a.java,a.server.resolve(),root,rate=850)
        try:
            mc.start()
            packs=mc.commands('datapack list enabled')
            if not re.search(r'file/live\.zip.*file/zz_live_test',packs):
                raise AssertionError('Observer must run after the released tick function: '+packs)
            mc.commands('gamerule minecraft:spawn_mobs false')
            install(mc)
            controls(mc)
            apples(mc)
            collisions(mc)
            sweep(mc)
        finally:
            mc.stop()
            if a.log and (root/'logs/latest.log').is_file():
                shutil.copyfile(root/'logs/latest.log',a.log)


if __name__=='__main__':
    main()
