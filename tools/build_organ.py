"""Build the Moonspire organ: a folded, one-shot vanilla note-block score."""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import build_calculator as red
from . import build_cathedral as base
from . import organ_score as s

OUTPUT = base.OUTPUT.with_name('moonspire-organ.litematic')
ROOT = OUTPUT.parent
POSTER = ROOT/'moonspire-organ-preview.jpg'
DECKS = 5
COLUMNS = (11,22,33,44)
Y0, DECK_PITCH = 4, 8
Z0, STEP_PITCH = 8, 3
VOICE_OFFSETS = (-4, -3, -2, -1, 1, 2, 3, 4)
BUTTON = (27,18,28)
LISTEN = (27.5,19.62,26.5)  # ear above the center catwalk, exported XYZ
FRAME = 'waxed_weathered_cut_copper'
TRIM = 'waxed_cut_copper'
STONE = 'deepslate_tiles'


def position(step):
    bar, pos = divmod(step,s.STEPS_PER_BAR)
    floor, row = divmod(bar,len(COLUMNS))
    x = COLUMNS[row if floor%2==0 else len(COLUMNS)-1-row]
    z = Z0 + (pos if row%2==0 else s.STEPS_PER_BAR-1-pos)*STEP_PITCH
    return x,Y0+floor*DECK_PITCH,z


def sign(step):
    return 1 if step//s.STEPS_PER_BAR%2==0 else -1


def note_at(step, voice):
    x,y,z = position(step)
    return x+VOICE_OFFSETS[voice],y-1,z+1


def lamp_offset(step):
    return -5 if position(step)[0] < COLUMNS[2] else 5


def lamp_at(step):
    x,y,z = position(step)
    return x+lamp_offset(step),y-1,z+1


def spiral(point, rise, height, turn=1):
    x,y,z = point
    for i in range(height):
        dx,dz = ((1,0),(0,turn),(-1,0),(0,-turn))[i%4]
        x,y,z = x+dx,y+rise,z+dz
        yield x,y,z


class Organ(red.Geometry):
    def __init__(self):
        self.blocks,self.data,self.wires = {},{},{}
        self.links,self.feed = defaultdict(set),defaultdict(set)
        self.values = defaultdict(bool)
        self.buses = {}   # one visible row of dust for each step
        self.diodes = {}  # position -> direction, delay, input/output net

    def solid(self,p):
        return super().solid(p) and self.blocks[p][0] not in ('stone_button','polished_blackstone_brick_stairs')

    def diode(self,p,d,t,in_net,out_net):
        self.rep(p,d,out_net,delay=t)
        self.diodes[p] = d,t,in_net,out_net

    def instrument_row(self,step,notes):
        x,y,z = position(step)
        for note in notes:
            p = note_at(step,note.voice)
            self.support(red.place(p,'down',2),STONE)
            v = s.VOICES[note.voice]
            self.put(red.place(p,'down'),v.material)
            self.put(p,'note_block',instrument=v.instrument,note=str(note.pitch),powered='false')
        self.put(lamp_at(step),'redstone_lamp',lit='false')
        offsets = [0,lamp_offset(step),*(VOICE_OFFSETS[n.voice] for n in notes)]
        points = [(u,y,z) for u in range(x+min(offsets),x+max(offsets)+1)]
        self.dust_line(step,points)
        self.buses[step] = points

    def advance(self,step):
        here,there = position(step),position(step+1)
        x,y,z = here
        u,v,w = there
        dz = sign(step)
        out,into = ('south','north') if dz==1 else ('north','south')
        delay = s.STEP_TICKS[step%s.STEPS_PER_BAR]//2
        tx = (step,'seam')
        if x==u and y==v:
            assert w-z==STEP_PITCH*dz
            self.diode((x,y,z+dz),out,delay,step,step+1)
            self.dust_line(step+1,[(x,y,z+2*dz),there])
            return
        # The final subdivision of a bar takes 4 game ticks: one repeater
        # into the fold, and another to restore its full-strength output.
        assert delay==2 and z==w
        self.diode((x,y,z+dz),out,1,step,tx)
        bend = z+2*dz
        if y==v:
            dx = 1 if u>x else -1
            if dz==1:
                # Fold one block beyond the backing of the end notes so
                # the bend cannot play the first or last note early.
                points = [(x,y,bend),*[(a,y,bend+1) for a in range(x,u+dx,dx)],(u,y,bend)]
            else:
                points = [(a,y,bend) for a in range(x,u+dx,dx)]
        else:
            assert dz==-1 and x==u and v==y+DECK_PITCH
            points = [(x,y,bend),*spiral((x,y,bend),1,DECK_PITCH,turn=-1)]
        assert points[-1]==(u,v,bend)
        self.dust_line(tx,points)
        self.diode((u,v,w+dz),into,1,tx,step+1)

    def launch(self):
        self.support(red.place(BUTTON,'down'),TRIM)
        self.put(BUTTON,'stone_button',face='floor',facing='north',powered='false')
        stages = [('start',i) for i in range(5)]
        x,y,z = BUTTON
        a = (x,y,z+2)
        self.diode((x,y,z+1),'south',1,'button',stages[0])
        self.dust_line(stages[0],[a,*spiral(a,-1,8)])
        self.diode((x,10,29),'north',1,stages[0],stages[1])
        b = (x,10,27)
        shaft = list(spiral(b,-1,9))
        assert shaft[-1]==(x+1,1,27)
        self.dust_line(stages[1],[(x,10,28),b,*shaft,*[(x+1,1,i) for i in range(26,22,-1)]])
        self.diode((x+1,1,22),'north',1,stages[1],stages[2])
        u,_,_ = position(0)
        cable = ([(x+1,1,i) for i in range(21,2,-1)]
                 + [(j,1,3) for j in range(x,u-1,-1)] + [(u,2,4),(u,3,5),(u,4,6)])
        left = 0
        for n,i in enumerate((10,24)):
            self.dust_line(stages[2+n],cable[left:i])
            self.diode(cable[i],red.direction(cable[i],cable[i+1]),1,stages[2+n],stages[3+n])
            left = i+1
        self.dust_line(stages[-1],cable[left:])
        self.diode((u,4,7),'south',1,stages[-1],0)

    def frame(self):
        # Timber and copper shelves leave air over every tuned block and
        # allow the listener to stand inside the audible radius of the score.
        for z in range(59):
            for x in range(56):
                block = FRAME if x in (0,55) or z in (0,58) else STONE
                self.support((x,0,z),block)
        for level in range(DECKS):
            y = Y0+DECK_PITCH*level-3
            for x0 in COLUMNS:
                for x in range(x0-5,x0+6):
                    if x in (27,28):
                        continue
                    for z in range(7,56):
                        p = x,y,z
                        if p not in self.wires and p not in self.blocks:
                            self.support(p,FRAME if x in (x0-5,x0+5) else STONE)
            for z in (4,56):
                for x0 in COLUMNS:
                    for x in range(x0-5,x0+6):
                        p = x,y,z
                        if p not in self.wires:
                            self.support(p,FRAME)
            for z in (2,57):
                for x in range(3,53):
                    self.support((x,y,z),FRAME)
                    if x in (*COLUMNS, 5,50):
                        self.support((x,y+1,z),'ochre_froglight')
        for z in (2,57):
            for x in (3,52):
                for y in range(1,39):
                    self.support((x,y,z),FRAME if y%8 in (1,2) else 'deepslate_bricks')
        for x in (3,52):
            for z in range(2,58):
                self.support((x,38,z),FRAME)
        for z in (2,57):
            for x in range(3,53):
                self.support((x,38,z),TRIM)
        for x in (27,28):
            for z in range(17):
                self.put((x,z+1,z),'polished_blackstone_brick_stairs',facing='south',half='bottom',shape='straight',waterlogged='false')
            for z in range(17,30):
                self.support((x,17,z),'ochre_froglight' if x==28 and z in (18,22,26) else TRIM)
        self.support((28,18,28),FRAME)
        self.sign((28,18,27),'Лунный орган','Пуск  •  ♪',color='orange')

    def audit(self):
        # Check the serial paths against the actual components, not just the
        # score. A source pad must drive precisely one next pad at its onset.
        button = self.blocks[BUTTON]
        assert button[0]=='stone_button'
        by_source = {}
        for p,(d,delay,in_net,out_net) in self.diodes.items():
            if in_net in by_source:
                raise ValueError(f'Two clock diodes on {in_net}')
            by_source[in_net] = (out_net,2*delay)
            q,r = red.place(p,red.OPPOSITE[d]),red.place(p,d)
            assert (q==BUTTON if in_net=='button' else self.wires.get(q)==in_net),(p,q,in_net)
            assert self.wires.get(r)==out_net,(p,r,out_net)
        tick,net = 0,'button'
        times = {}
        while net in by_source:
            net,dt = by_source.pop(net)
            tick += dt
            if isinstance(net,int):
                times[net] = tick
        if by_source or len(times)!=len(s.FRAMES):
            raise ValueError('The clock has a gap or an unreachable step')
        launch = times[0]
        assert tuple(times[i]-launch for i in range(len(times)))==s.ONSET_TICKS[:-1]
        # Notes must face an air block, be on their instrument substrate,
        # and hear just the weighted bus of their own step below the dust.
        for i,frame in enumerate(s.FRAMES):
            for p in [lamp_at(i),*(note_at(i,n.voice) for n in frame)]:
                x,y,z = p
                assert (x,y+1,z) not in self.blocks,(i,p,'blocked above')
                supports = {self.wires[q] for direction in ('north','south','east','west')
                            if (q:=red.place(red.place(p,direction),'up')) in self.wires}
                assert supports=={i},(i,p,supports)
        self.onset = tuple(times.values())

    def build(self):
        for i,notes in enumerate(s.FRAMES):
            self.instrument_row(i,notes)
        for i in range(len(s.FRAMES)-1):
            self.advance(i)
        self.launch()
        self.frame()
        self.bake()
        self.audit()
        return self

    def export(self,path,preview=None):
        x,y,z = np.array(tuple(self.blocks),dtype=np.int32).T
        assert (x.min(),y.min(),z.min())==(0,0,0)
        blocks = np.zeros((y.max()+1,z.max()+1,x.max()+1),dtype=np.int16)
        blocks[y,z,x] = [base.state(kind,**dict(props)) for kind,props in self.blocks.values()]
        base.save(path,blocks,preview,title=s.TITLE,
                  description=f'«{s.SONG}» — {len(s.BARS)} тактов на восьми дорожках нотных блоков. Java 26.3.',
                  block_entities=self.data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=OUTPUT)
    p.add_argument('--preview',type=Path)
    args = p.parse_args()
    organ = Organ().build()
    organ.export(args.output,args.preview)
    print(f'{sum(map(len,s.FRAMES))} notes, {len(s.FRAMES)} steps, launch={organ.onset[0]} ticks.')


if __name__=='__main__':
    main()
