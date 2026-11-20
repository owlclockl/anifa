"""Place, route, and export a fully redstone, button-per-turn game of Snake."""
from __future__ import annotations

import argparse
import hashlib
import math
import random
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from nbtlib import tag as nbt

from . import build_calculator as red
from . import build_cathedral as base
from . import snake_logic as logic
from . import snake_screen as screen

OUTPUT = base.OUTPUT.with_name('moonspire-snake.litematic')
TITLE = 'Лунная змейка'
DESC = 'Экран 72 × 72 лампы, змейка шириной в одну лампу. Ванильный редстоун, Java 26.3.'
WIDTH, HEIGHT, DEPTH = 83, 36, 84
FLOOR = red.FLOOR
OPP, put_at, world = red.OPPOSITE, red.place, red.world
BED, TRIM = 'deepslate_tiles', 'waxed_weathered_cut_copper'
WIDTH_PANEL, TOP_PANEL = 88, 106
SCREEN_MIN_X = 8
SCREEN_LEVEL = 3
SCREEN_MIN_Y = red.world((0,SCREEN_LEVEL,0))[1]
BOARD_SIZE = logic.SIZE*screen.CELL_PITCH
# Budget from a routed socket through the rear drivers, including lamp
# turn-off. Isolated drivers settled within 28 sampled game ticks.
DRAW_TICKS = 40

ROSTER = (
    (2, ('MOVES','CONTROL')),
    (6, ('MEMORY',)),
    (8, ('EDGE_Y',)),
    (10, ('COORDS',)),
    (12, ('EDGE_X',)),
    (14, ('ROW5','LINE5','FRUIT')),
    *[(29-3*y, (f'ROW{y}',f'LINE{y}')) for y in reversed(range(5))],
)
# Hardware timing rails, below the first routing plane. Each tap is separated
# by one repeater at delay=4, or eight game ticks.
CTRL_X, CTRL_IN_Z = 27, 24
MASTER_TAPS = range(34, 48)
SLAVE_TAPS = range(58, 65)
BUSY_TAPS = range(120)
REQUEST_TAPS = range(71)
EDGE_TICKS = 14
REQUEST_OUT = 152
DIVE, RISE, LEFT_RISE = 3,0,1
KEY_PORTS = {k:(gx,0,3) for k,gx in zip(logic.COMMANDS,(18,15,12,9,4))}
FRONT = -100
BUTTON_Z = FRONT+7
KEYS = {k:(x,10,BUTTON_Z) for k,x in zip(logic.COMMANDS,(47,45,43,41,39))}
REQ_PINS = {k:(5+4*i,0,6) for i,k in enumerate(logic.COMMANDS)}
REQ_PORTS = {k:(x+1,0,REQUEST_OUT//4) for k,(x,_,_) in REQ_PINS.items()}
CLOCK_PIN = (CTRL_X,0,CTRL_IN_Z//4)


# Socket locations stay fixed if the timing rails below them are tuned.
CLOCK_PORTS = {'PHASE_M':(CTRL_X-1,0,30), 'PHASE_S':(CTRL_X-1,0,44), 'BUSY':(CTRL_X+1,0,49)}


def export_point(p):
    x,y,z=p
    return x,y,z-FRONT


def display_pads():
    def gx(x):
        return 18-3*x

    def lv(y):
        return 19-3*y

    z=screen.SOCKET_Z
    pads={f'B{x}{y}':(gx(x),lv(y),z) for y in range(logic.SIZE) for x in range(logic.SIZE)}
    for key,(x,y),_ in logic.board_edges():
        pads[key]=(gx(x)-2,lv(y),z) if key.startswith('E') else (gx(x),lv(y)-2,z)
    pads.update({f'F{i}':(gx(x)-1,lv(y)+1,z) for i,(x,y) in enumerate(logic.APPLES)})
    pads.update({f'X{x}':(gx(x),22,z) for x in range(logic.SIZE)})
    pads.update({f'Y{y}':(1,lv(y),z) for y in range(logic.SIZE)})
    pads.update({f'G{i}':(18-2*i,1,z) for i in range(len(logic.APPLES))})
    return pads | {'READY':(9,1,z), 'LOSE':(6,1,z), 'WIN':(3,1,z)}


LAMP_PORTS = display_pads()


def pixels(key):
    return screen.pixels(key,LAMP_PORTS[key])


def field_pixels():
    for y in range(SCREEN_MIN_Y,SCREEN_MIN_Y+BOARD_SIZE):
        for x in range(SCREEN_MIN_X,SCREEN_MIN_X+BOARD_SIZE):
            yield x,y,screen.FRONT_Z


def display_lamps():
    """Yield driven channels and the unconnected dark lamps between them."""
    active=set()
    for key in LAMP_PORTS:
        for p in pixels(key):
            if p in active:
                raise ValueError(f'Two display channels share lamp {p}')
            active.add(p)
            yield key,p
    for p in field_pixels():
        if p not in active:
            yield None,p


def screen_sockets(network):
    return [(network.screen[key],pad) for key,pad in LAMP_PORTS.items()]


def state_pins(p):
    return tuple(put_at(p,d) for d in ('west','north','south'))


def fixed_sites(network):
    sites={network.inputs[name]:(4+5*(i%10)+2*((i//10)%2),1,18+6*(i//10)) for i,name in enumerate(logic.STATE)}
    sites.update({network.inputs[f'KEY_{key}']:p for key,p in KEY_PORTS.items()})
    sites.update({network.inputs[f'REQ_{key}']:p for key,p in REQ_PORTS.items()})
    return sites | {network.inputs[key]:p for key,p in CLOCK_PORTS.items()}


def optimize(network):
    """Anneal the tiers using both wire length and estimated critical paths."""
    sites=fixed_sites(network)
    tiers=[]
    live=network.live()
    for lv,banks in ROSTER:
        # Five track pitches leave room for the high-fanout edge decoders.
        slots=[(4+5*x,lv,10+5*z) for z in range(14) for x in range(16)]
        nodes=sorted(i for i in live if network.gates[i].bank in banks)
        assert len(nodes)<=len(slots),(banks,len(nodes))
        sites.update(zip(nodes,slots))
        tiers.append((slots,nodes+[None]*(len(slots)-len(nodes))))
    assert set(sites)==live,(len(sites),len(live))

    def root(i):
        return sites[i] if network.gates[i].op=='INPUT' and i not in register else put_at(sites[i],'east')

    connections=[]
    register={network.inputs[key] for key in logic.STATE}
    incident=defaultdict(set)

    def connect(n,node=None,side=None,terminal=None):
        j=len(connections)
        incident[n].add(j)
        if node is not None:
            incident[node].add(j)
        connections.append((n,node,side,terminal))

    for i in sorted(live):
        for j,arg in enumerate(network.gates[i].args):
            connect(arg,i,('west','north')[j])
    for key,n in network.next.items():
        to=network.inputs[key]
        connect(n,to,'west')
        connect(network.locks[0],to,'north')
        connect(network.locks[1],to,'south')
    for key,n in network.commands.items():
        connect(n,terminal=REQ_PINS[key])
    connect(network.clock,terminal=CLOCK_PIN)
    sockets={p for _,p in screen_sockets(network)}
    for n,p in screen_sockets(network):
        connect(n,terminal=p)
    fans=defaultdict(int)
    for src,_,_,_ in connections:
        fans[src]+=1
    weights=[1/math.sqrt(fans[src]) for src,_,_,_ in connections]

    def length(j):
        src,to,side,terminal=connections[j]
        a,_,b=root(src)
        x,_,z=put_at(sites[to],side) if to is not None else terminal
        return weights[j]*(abs(x-a)+abs(z-b))

    base_weights=weights[:]
    gate_edges=defaultdict(list)
    data_sinks=[]
    lamp_sinks=[]
    for j,(_, dst, side, term) in enumerate(connections):
        if dst in register:
            if side=='west':
                data_sinks.append(j)
        elif dst is not None:
            gate_edges[dst].append(j)
        elif term in sockets and term!=LAMP_PORTS['READY']:
            lamp_sinks.append(j)

    def criticality(starts, ends, gain):
        # Weight arcs close to the slowest input→register or register→lamp
        # path. Estimate transverse and lift costs before the real routing.
        time={n:(14 if n in starts else -math.inf) for n in network.inputs.values()}
        arc={}
        for j,(u,v,side,term) in enumerate(connections):
            a,y,z=root(u)
            b,w,x=put_at(sites[v],side) if v is not None else term
            arc[j]=4+0.62*(abs(a-b)+abs(z-x))+0.9*abs(y-w)
        for n,edges in sorted(gate_edges.items()):
            time[n]=max(time[connections[j][0]]+arc[j] for j in edges)
        end_time=max(time[connections[j][0]]+arc[j] for j in ends)
        tail=defaultdict(lambda:-math.inf)
        imp=[0.0]*len(connections)
        for j in ends:
            u=connections[j][0]
            tail[u]=max(tail[u],arc[j])
            imp[j]=gain*math.exp(-(end_time-time[u]-arc[j])/36)
        for n,edges in sorted(gate_edges.items(),reverse=True):
            for j in edges:
                u=connections[j][0]
                tail[u]=max(tail[u],tail[n]+arc[j])
                imp[j]=gain*math.exp(-(end_time-time[u]-arc[j]-tail[n])/36)
        return imp

    rng=random.Random(62354)
    for epoch in range(14):
        if epoch>=2:
            sw=criticality({network.inputs[f'REQ_{k}'] for k in logic.COMMANDS},data_sinks,8)
            pw=criticality(register,lamp_sinks,8)
            weights[:]=[b+0.60*(s+p)+0.40*max(0,o-b) for b,s,p,o in zip(base_weights,sw,pw,weights)]
        for slots,nodes in (tiers if epoch%2==0 else reversed(tiers)):
            for k in range(4300):
                a,b=rng.randrange(len(slots)),rng.randrange(len(slots))
                i,j=nodes[a],nodes[b]
                if i==j:
                    continue
                wires=incident[i]|incident[j]
                old=sum(length(w) for w in wires)
                if i is not None:
                    sites[i]=slots[b]
                if j is not None:
                    sites[j]=slots[a]
                cost=sum(length(w) for w in wires)-old
                temp=(5.5-0.37*epoch)*(1-k/4300)+0.18
                if cost<=0 or rng.random()<math.exp(-cost/temp):
                    nodes[a],nodes[b]=j,i
                else:
                    if i is not None:
                        sites[i]=slots[a]
                    if j is not None:
                        sites[j]=slots[b]
    return sites


@dataclass
class Plan:
    network: logic.Network
    sites: dict
    roots: dict
    pins: dict
    required: dict
    edges: list


def plan_routes(router=None,cache=None):
    c=logic.design()
    sites=optimize(c)
    pads,roots,pins,required={}, {}, defaultdict(list), {}

    def encode(p):
        x,y,z=p
        assert 0<=x<WIDTH and 0<=y<HEIGHT and 0<=z<DEPTH,p
        return (y*DEPTH+z)*WIDTH+x

    def decode(v):
        yz,x=divmod(v,WIDTH)
        y,z=divmod(yz,DEPTH)
        return x,y,z

    def add(p,n,side=None,rotation=None):
        q=encode(p)
        if q in pads:
            raise ValueError(f'pad overlap {p}: {pads[q][0]} vs {n}')
        mask=red.HORIZONTAL_BIT.get(side,0) if rotation is None else 1<<(8+rotation)
        pads[q]=n,mask

    def pin(p,n,side=None,rotation=None,need=3):
        pins[n].append(p)
        required[n,p]=need
        add(p,n,side,rotation)

    def source(p,n,side=None,rotation=None):
        roots[n]=p
        add(p,n,side,rotation)

    for y in range(HEIGHT):
        for z in range(3 if y==0 else screen.SOCKET_Z):
            for x in range(WIDTH):
                add((x,y,z),-2)
    names={i:key for key,i in c.inputs.items()}
    for n,p in sorted(sites.items()):
        g=c.gates[n]
        if n in names:
            name=names[n]
            if name in logic.STATE:
                add(p,-2)
                source(put_at(p,'east'),n,'west')
                data,m,s=state_pins(p)
                pin(data,c.next[name],'east')
                pin(m,c.locks[0],'south')
                pin(s,c.locks[1],'north',need=4)
            elif name.startswith('KEY_'):
                source(p,n,'north')
            else:
                source(p,n,rotation=LEFT_RISE if name.startswith('PHASE_') else RISE)
        else:
            add(p,-2)
            source(put_at(p,'east'),n,'west')
            for i,a in enumerate(g.args):
                pin(put_at(p,('west','north')[i]),a,('east','south')[i])
    for n,p in screen_sockets(c):
        pin(p,n,'north',need=4)
    for name,p in REQ_PINS.items():
        pin(p,c.commands[name],rotation=DIVE,need=5)
    pin(CLOCK_PIN,c.clock,rotation=DIVE,need=5)
    if roots.keys()!=pins.keys():
        raise ValueError(f'Orphan nets: {roots.keys() ^ pins.keys()}')
    lines=[f'{WIDTH} {HEIGHT} {DEPTH} {len(pads)} {len(roots)}']
    lines.extend(f'{p} {n} {m}' for p,(n,m) in sorted(pads.items()))
    lines.extend(' '.join(map(str,(n,encode(p),len(pins[n]),*map(encode,pins[n])))) for n,p in roots.items())
    text='\n'.join(lines)+'\n'
    source=Path(__file__).with_name('calculator_router.cpp')
    digest=hashlib.sha256(source.read_bytes()+text.encode()).hexdigest()
    cached=cache.read_text() if cache is not None and cache.is_file() else ''
    if cached.startswith(digest+'\n'):
        routes=cached.split('\n',1)[1]
    else:
        with tempfile.TemporaryDirectory(prefix='snake-router-') as tmp:
            if router is None:
                router=Path(tmp)/'router'
                subprocess.run(['c++','-std=c++17','-O3',str(source),'-o',str(router)],check=True)
            routes=subprocess.run([str(router)],text=True,input=text,stdout=subprocess.PIPE,check=True).stdout
        if cache is not None:
            cache.write_text(digest+'\n'+routes)
    edges=[(n,decode(a),decode(b),r) for n,a,b,r in (map(int,line.split()) for line in routes.splitlines())]
    return Plan(c,sites,roots,dict(pins),required,edges)


def buffer_routes(edges, strength, required):
    need=dict(required)
    strength=dict(strength)
    for n,a,b,_ in reversed(edges):
        out=need.get((n,b),1)
        threshold=2 if a[1]==b[1] and out<=14 else out+4
        need[n,a]=max(need.get((n,a),1),threshold)
    buffered=set()
    for n,a,b,_ in edges:
        x=strength[n,a]
        if x<need[n,a]:
            raise ValueError(f'Cannot power cable on net {n}, {a}')
        req=need.get((n,b),1)
        if x-4>=req:
            strength[n,b]=x-4
        elif a[1]==b[1] and req<=14:
            strength[n,b]=14
            buffered.add((n,a,b))
        else:
            raise ValueError(f'Cannot buffer {a} to {b} on net {n}')
    if any(strength.get(q,0)<v for q,v in required.items()):
        raise ValueError('A route does not deliver enough signal to its input')
    return buffered


def buffer_tracks(plan):
    c=plan.network
    lifted={c.inputs[k] for k in CLOCK_PORTS}|{c.inputs[f'REQ_{k}'] for k in logic.COMMANDS}
    storage={c.inputs[k] for k in logic.STATE}
    strength={(n,p): 11 if n in lifted else 13 if n in storage or c.gates[n].op in ('OR','NOT') else 12
              for n,p in plan.roots.items()}
    return buffer_routes(plan.edges,strength,plan.required)


def rail(pad, taps, out):
    """Return the two diode-isolated branches of a pulse collector."""
    first=world(pad)[2]+2
    end=world(out)[2]
    z=[first+2*i for i in taps]
    # Both halves are oriented towards the output. All taps and the output
    # are at even Z; the buffer positions are odd and never eject a tap.
    low=range(min(z[0],end),end)
    high=range(max(z[-1],end),end,-1)
    return z,end,low,high


def tap_times(pad, taps, out):
    z,end,low,high=rail(pad,taps,out)
    buffers={u for branch in (low,high) for i,u in enumerate(branch) if i%10==9}
    return [8*(i+1)+4+2*sum(min(v,end)<u<max(v,end) for u in buffers) for i,v in zip(taps,z)]


def clock_check(plan, buffered):
    """Audit settle time, minimum pulse width and non-overlapping latches.

    All figures are in game ticks at the routing sockets. A simultaneous
    chord has the same KEY launch time (cable delays are balanced).
    """
    c=plan.network
    legs={(n,p):0 for n,p in plan.roots.items()}
    for n,a,b,_ in plan.edges:
        legs[n,b]=legs[n,a]+2*int((n,a,b) in buffered)

    def arrival(seeds):
        times={}
        for n,p in sorted(plan.sites.items()):
            gate=c.gates[n]
            if n in seeds or gate.op=='INPUT':
                times[n]=seeds.get(n,-math.inf)
            else:
                times[n]=max(times[u]+legs[u,put_at(p,side)] for u,side in zip(gate.args,('west','north')))+4
        return times

    def interval(pad,taps,port):
        times=tap_times(pad,taps,port)
        assert all(0<b-a<=EDGE_TICKS-2 for a,b in zip(times,times[1:]))
        return times[0], times[-1]+EDGE_TICKS

    request, clock = {}, []
    release = []
    for k,i in c.commands.items():
        key=c.inputs[f'KEY_{k}']
        start=legs[key,put_at(plan.sites[i],'west')]+4
        clock.append(arrival({i:start})[c.clock]+legs[c.clock,CLOCK_PIN])
        on,off=interval(REQ_PINS[k],REQUEST_TAPS,REQ_PORTS[k])
        start+=legs[i,REQ_PINS[k]]
        request[c.inputs[f'REQ_{k}']]=start+on
        release.append(start+off)

    nxt=arrival(request)
    # Include the repeater at the input to the master latch and six ticks
    # of assembly/update slack on either side of a sampling edge.
    updates={k:nxt[c.next[k]]+legs[c.next[k],state_pins(plan.sites[c.inputs[k]])[0]]+4 for k in logic.STATE}
    phases=[]
    bit_edges=[]
    for j,n in enumerate(c.locks,1):
        key=f'PHASE_{"MS"[j-1]}'
        times=arrival({c.inputs[key]:0})
        travel={k:times[n]+legs[n,state_pins(plan.sites[c.inputs[k]])[j]]+2 for k in logic.STATE}
        first,last=interval(CLOCK_PIN,(MASTER_TAPS,SLAVE_TAPS)[j-1],CLOCK_PORTS[key])
        bit_edges.append({k:(max(clock)+first+t,min(clock)+last+t) for k,t in travel.items()})
        phases.append((min(clock)+first+min(travel.values()),max(clock)+first+max(travel.values()),
                       min(clock)+last+min(travel.values()),max(clock)+last+max(travel.values())))
    master,slave=phases
    data=min(close-max(on,updates[k]) for k,(on,close) in bit_edges[0].items())
    separation=slave[0]-master[3]
    hold=min(release)-master[3]
    a,b=interval(CLOCK_PIN,SLAVE_TAPS,CLOCK_PORTS['PHASE_S'])
    sample=b-a  # skew shifts both edges on each individual bit equally
    margins=(data,separation,hold,sample)
    if min(margins)<8:
        raise ValueError(f'Unsafe capture windows (data, separation, hold, sample): {margins}')
    pixels_time=arrival({c.inputs[k]:on+4 for k,(on,_) in bit_edges[1].items()})
    screen_time=max(pixels_time[n]+legs[n,p]+DRAW_TICKS for n,p in screen_sockets(c) if p!=LAMP_PORTS['READY'])
    busy_on,busy_off=interval(CLOCK_PIN,BUSY_TAPS,CLOCK_PORTS['BUSY'])
    if min(clock)+busy_off<screen_time+18:
        raise ValueError(f'Busy falls at {min(clock)+busy_off}; screen needs {screen_time+18}')
    assert min(clock)+busy_off>=max(release)+10, 'READY can return while requests are held'
    ready=c.outputs['READY']
    ready_delay=arrival({c.inputs['BUSY']:0})[ready]+legs[ready,LAMP_PORTS['READY']]+DRAW_TICKS
    return {'data':max(updates.values()), 'master':master, 'slave':slave, 'screen':screen_time,
            'busy':(min(clock)+busy_on,max(clock)+busy_off),
            'ready':max(clock)+busy_off+ready_delay, 'margins':margins}


class Geometry(red.Geometry):
    def __init__(self,plan):
        self.plan=plan
        self.values=dict(enumerate(plan.network.evaluate(plan.network.sources())))
        self.buffered=buffer_tracks(plan)
        self.blocks,self.wires,self.data={}, {}, {}
        self.links,self.feed=defaultdict(set),defaultdict(set)

    def solid(self,p):
        return super().solid(p) and self.blocks[p][0] not in ('stone_button','red_stained_glass')

    def toggle_rep(self,p,toward,signal,lock):
        self.support(put_at(p,'down'),TRIM)
        self.put(p,'repeater',facing=OPP[toward],locked=str(self.values[lock]).lower(),delay='1',
                 powered=str(self.values[signal]).lower())
        self.feed[put_at(p,toward)].add(signal)

    def register(self,name,n,point):
        # Two non-overlapping transparent latches form a single state bit.
        c=self.plan.network
        x,y,z=world(point)
        data,lock_m,lock_s=c.next[name],*c.locks
        self.dust_line(data,[(u,y,z) for u in range(x-4,x-1)])
        self.rep((x-1,y,z),'east',data)
        self.toggle_rep((x,y,z),'east',n,lock_m)
        self.toggle_rep((x+1,y,z),'east',n,lock_s)
        self.dust_line(n,[(u,y,z) for u in range(x+2,x+5)])
        self.dust_line(lock_m,[(x,y,z-i) for i in (4,3,2)])
        self.rep((x,y,z-1),'south',lock_m)
        self.dust_line(lock_s,[(x,y,z+i) for i in (4,3,2)]+[(x+1,y,z+2)])
        self.rep((x+1,y,z+1),'north',lock_s)

    @staticmethod
    def buffers(points):
        """Refresh an isolated path on a flat straight stretch, not a stair."""
        last=-1
        for i in range(1,len(points)-1):
            a,p,b=points[i-1:i+2]
            if i-last>=9 and a[1]==p[1]==b[1] and red.direction(a,p)==red.direction(p,b):
                last=i
                yield i

    def carry(self, net, points, buffers, extra=0):
        start=0
        for i in buffers:
            self.dust_line(net,points[start:i])
            dose=min(3,extra)
            delta=red.direction(points[i],points[i+1])
            self.rep(points[i],delta,net,delay=1+dose)
            extra-=dose
            start=i+1
        self.dust_line(net,points[start:])
        assert not extra

    def controls(self):
        c=self.plan.network
        cables={}
        for k,turn in zip(logic.COMMANDS,(-45,-40,-35,-40,-45)):
            cx,y,z=KEYS[k]
            x,_,_=world(KEY_PORTS[k])
            u=1 if x>cx else -1
            # The first dust is level with the driver; then descend by one
            # block per step from Y=10 to the buried Y=8 cable tray.
            raw=[(cx,y-i,z+2+i) for i in range(3)]
            raw.extend((cx,8,v) for v in range(z+5,turn+1))
            raw.extend((a,8,turn) for a in range(cx+u,x+u,u))
            raw.extend((x,8,v) for v in range(turn+1,-16))
            pulse=[(x,8,v) for v in range(-14,-5)]+[(x,9,-5)]+[(x,10,v) for v in range(-4,8)]
            rb,pb=tuple(self.buffers(raw)),tuple(self.buffers(pulse))
            cables[k]=(raw,rb,pulse,pb)
        total=max(len(rb)+len(pb) for _,rb,_,pb in cables.values())
        for key,(raw,rb,pulse,pb) in cables.items():
            x,y,z=KEYS[key]
            net=c.inputs[f'KEY_{key}']
            raw_net=f'BUTTON_{key}'
            self.values[raw_net]=False
            self.support((x,y-1,z),'waxed_cut_copper')
            self.put((x,y,z),'stone_button',face='floor',facing='north',powered='false')
            self.rep((x,y,z+1),'south',raw_net)
            self.carry(raw_net,raw,rb,total-len(rb)-len(pb))
            x=raw[-1][0]
            # Subtract a delayed copy of the button level. Only a rising
            # edge yields a pulse; a held button cannot replay or restart.
            self.rep((x,8,-16),'south',raw_net)
            self.dust_line(raw_net,[(x,8,-17),(x+1,8,-17),(x+2,8,-17)])
            self.rep((x+2,8,-16),'south',raw_net,delay=4)
            self.wire((x+2,8,-15),raw_net)
            self.rep((x+1,8,-15),'west',raw_net,delay=4)
            compare=(x,8,-15)
            self.support((x,7,-15),TRIM)
            self.put(compare,'comparator',facing='north',mode='subtract',powered='false')
            self.data[compare]=nbt.Compound(id=nbt.String('minecraft:comparator'),OutputSignal=nbt.Int(0))
            self.feed[(x,8,-14)].add(net)
            self.carry(net,pulse,pb)
            self.rep((x,10,8),'south',net)
            self.dust_line(net,[(x,10,v) for v in range(9,13)])

    def console(self):
        self.controls()
        c=self.plan.network
        for key,pad in LAMP_PORTS.items():
            screen.drive(self,key,pad,c.screen[key])
        for key,p in display_lamps():
            if key is None:
                self.put(p,'redstone_lamp',lit='false')

    def chain(self,net,pad,taps):
        self.trace(net,put_at(pad,'down'),pad,DIVE)
        x,y,z=world(put_at(pad,'down'))
        self.rep((x,y,z+1),'south',net,delay=4)
        for i in range(taps):
            u=z+2+2*i
            self.wire((x,y,u),net)
            if i+1<taps:
                self.rep((x,y,u+1),'south',net,delay=4)

    def collector(self,net,pad,taps,out,side,rot):
        # Diodes isolate each tap, so the gathered pulse cannot travel
        # backward into the timing chain. Two one-way buses meet at the via.
        x,y,_=world(put_at(pad,'down'))
        z,end,low,high=rail(pad,taps,out)
        for v in z:
            self.rep((x+side,y,v),'east' if side==1 else 'west',net)
        points=((x+2*side,y,end),)
        for branch in (low,high):
            path=[(x+2*side,y,v) for v in branch]+list(points)
            self.carry(net,path,range(9,len(path)-1,10))
        self.rep((x+3*side,y,end),'east' if side==1 else 'west',net)
        self.trace(net,put_at(out,'down'),out,rot)

    def timing(self):
        c=self.plan.network
        for key,p in REQ_PINS.items():
            self.chain(c.commands[key],p,len(REQUEST_TAPS))
            self.collector(c.inputs[f'REQ_{key}'],p,REQUEST_TAPS,REQ_PORTS[key],1,RISE)
        self.chain(c.clock,CLOCK_PIN,len(BUSY_TAPS))
        for key,taps in (('PHASE_M',MASTER_TAPS),('PHASE_S',SLAVE_TAPS),('BUSY',BUSY_TAPS)):
            east=key=='BUSY'
            self.collector(c.inputs[key],CLOCK_PIN,taps,CLOCK_PORTS[key],1 if east else -1,RISE if east else LEFT_RISE)

    def facade(self):
        front=screen.FRONT_Z
        for x in (0,WIDTH_PANEL-1):
            for y in range(FLOOR):
                self.support((x,y,front),'deepslate_bricks')
        # A single, uninterrupted lamp plane surrounded by a copper bezel.
        for x in range(WIDTH_PANEL):
            for y in range(FLOOR,TOP_PANEL+1):
                if (x,y,front) in self.blocks:
                    continue
                if (x in (0,WIDTH_PANEL-1,SCREEN_MIN_X-1,SCREEN_MIN_X+BOARD_SIZE)
                    or y in (FLOOR,SCREEN_MIN_Y-1,SCREEN_MIN_Y+BOARD_SIZE,TOP_PANEL)):
                    kind=TRIM
                else:
                    kind='deepslate_bricks' if y<SCREEN_MIN_Y else 'deepslate_tiles'
                self.support((x,y,front),kind)
        for x in range(4,WIDTH_PANEL-3,6):
            self.support((x,TOP_PANEL,front-1),'ochre_froglight')
        for x in range(34,53):
            for z in range(FRONT,BUTTON_Z+7):
                kind='ochre_froglight' if (x in (35,51) and z%3==0) else TRIM if x in (34,52) or z==FRONT else BED
                if (x,8,z) not in self.wires:
                    self.support((x,8,z),kind)
            for z in (BUTTON_Z-1,BUTTON_Z,BUTTON_Z+1):
                self.support((x,9,z),TRIM if z==BUTTON_Z-1 else BED)
            self.support((x,11,BUTTON_Z+1),'waxed_cut_copper')
        for x in range(35,52):
            for y in range(8):
                if x in (35,51) or y<2:
                    self.support((x,y,FRONT+1),BED)
        for key,caption in zip(logic.COMMANDS,('↑ Вверх','← Влево','↓ Вниз','→ Вправо','Новая игра')):
            x,y,z=KEYS[key]
            self.sign((x,y+1,z),caption,color='orange' if key=='RESET' else 'aqua')
        for x in (35,51):
            self.support((x,10,BUTTON_Z),'ochre_froglight')
        for key,caption in (('READY','Готово'),('WIN','Победа'),('LOSE','Столкновение')):
            x,y,_=world(LAMP_PORTS[key])
            self.sign((x,y-1,front-1),caption,color='red' if key=='LOSE' else 'aqua')
        for i in range(len(logic.APPLES)):
            x,y,_=world(LAMP_PORTS[f'G{i}'])
            self.sign((x,y-1,front-1),str(i+1),color='orange')
        self.sign((78,104,front-1),'Лунная','змейка',color='aqua')
        self.sign((5,104,front-1),'Голова','строка / столбец',color='orange')

    def build(self):
        c=self.plan.network
        names={c.inputs[key]:key for key in logic.STATE}
        for n,p in sorted(self.plan.sites.items()):
            if n in names:
                self.register(names[n],n,p)
            elif c.gates[n].op!='INPUT':
                self.gate(n,p)
        self.console()
        self.timing()
        for n,a,b,rot in self.plan.edges:
            self.trace(n,a,b,rot)
        self.facade()
        self.bake()
        return self

    def save(self,path,preview=None):
        x,y,z=np.array(tuple(map(export_point,self.blocks)),dtype=np.int32).T
        assert (x.min(),y.min(),z.min())==(0,0,0)
        grid=np.zeros((y.max()+1,z.max()+1,x.max()+1),dtype=np.int16)
        grid[y,z,x]=[base.state(kind,**dict(props)) for kind,props in self.blocks.values()]
        base.save(path,grid,preview,title=TITLE,description=DESC,block_entities={export_point(p):v for p,v in self.data.items()})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--preview',type=Path)
    parser.add_argument('--router',type=Path)
    parser.add_argument('--routing-cache',type=Path)
    args=parser.parse_args()
    p=plan_routes(args.router,args.routing_cache)
    g=Geometry(p)
    print(f'Sequential timing (data, master, slave, screen): {clock_check(p,g.buffered)} game ticks',flush=True)
    g.build().save(args.output,args.preview)


if __name__=='__main__':
    main()
