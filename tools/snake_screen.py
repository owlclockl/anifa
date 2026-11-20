"""Rear drivers for a one-lamp-wide snake on a continuous lamp plane.

The center sockets and the 11-lamp bridges between them are separate
channels. Visible lamps only receive weak power; they do not relay it into
the adjacent row. A vertical bridge uses two lamps per rear torch where
possible, with the upper lamp fed by the torch's opaque cap.
"""
from __future__ import annotations

from . import build_calculator as red

FRONT_Z = -30
CELL_PITCH = 12
SOCKET_Z = 4


def pixels(key, pad):
    """Physical lamps per socket: center, open-ended bridge, or icon."""
    x,y,_=red.world(pad)
    # A bridge socket lies 8 blocks from one center and 4 from the other.
    # The two center lamps are separate channels, so endpoints are omitted.
    if key.startswith('B'):
        return [(x,y,FRONT_Z)]
    if key.startswith('E'):
        return [(a,y,FRONT_Z) for a in range(x-3,x+8)]
    if key.startswith('V'):
        return [(x,b,FRONT_Z) for b in range(y-3,y+8)]
    return [(a,b,FRONT_Z) for b in range(y,y+4) for a in range(x-1,x+3)
            if not key.startswith('F') or b<y+3 or a==x]


def relative(x,y,z):
    return x,y,FRONT_Z+z


def low(g,pad,net):
    """Invert a socket at Z=16 and return the first dust point."""
    x,y,z=red.world(pad)
    assert z==16
    dark=('display_blank',pad)
    g.values[dark]=not g.values[net]
    g.dust_line(net,[(x,y,16),(x,y,15)])
    g.rep((x,y,14),'north',net)
    g.support((x,y,13))
    g.put((x,y,12),'redstone_wall_torch',facing='north',lit=str(g.values[dark]).lower())
    g.feed[x,y,11].add(dark)
    return dark


def rail(g,net,points):
    g.carry(net,points,tuple(g.buffers(points)))


def emitter(g,x,y,dark,*,cap=False,side=False):
    g.put(relative(x,y,1),'redstone_wall_torch',facing='north',lit=str(not g.values[dark]).lower())
    if cap:
        g.support(relative(x,y+1,1))
    g.support(relative(x,y,2))
    p=relative(x+1,y,2) if side else relative(x,y,3)
    g.rep(p,'west' if side else 'north',dark)


def center(g,pad,net):
    x,y,z=red.world(pad)
    g.dust_line(net,[(x,y,z),(x,y,z-1)])
    g.rep((x,y,z-2),'north',net)
    points=[(x,y,u) for u in range(z-3,8,-1)] + [(x-1,y,9),(x-2,y,9)]
    points.extend((x-2,y,u) for u in range(8,FRONT_Z+6,-1))
    rail(g,net,points)
    # Feed these blocks at a different depth from the bridge-driver taps.
    g.rep(relative(x-1,y,7),'east',net)
    for i in (7,5,3,1):
        g.support(relative(x,y,i))
    for i in (6,4,2):
        g.rep(relative(x,y,i),'north',net)


def horizontal(g,pad,net):
    x,y,_=red.world(pad)
    dark=low(g,pad,net)
    bus=FRONT_Z+4
    rail(g,dark,[(x,y,u) for u in range(11,bus+1,-1)])
    g.rep((x,y,bus+1),'north',dark)
    g.dust_line(dark,[(a,y,bus) for a in range(x-3,x+8)])
    for a in range(x-3,x+8):
        emitter(g,a,y,dark)


def vertical(g,pad,net):
    x,y,_=red.world(pad)
    dark=low(g,pad,net)
    y0=y-3
    start=FRONT_Z+21
    lead=[(x,y,u) for u in range(11,7,-1)]+[(x+1,y,8),(x+2,y,8)]
    lead.extend((x+2,y-d,8-d) for d in range(1,4))
    lead.extend((x+2,y0,u) for u in range(4,start+1,-1))
    rail(g,dark,lead)
    g.rep((x+2,y0,start+1),'north',dark)
    g.dust_line(dark,[(x+2,y0+j,start-j) for j in range(10)])
    # Pair the lamps on either side of a lone middle lamp (offset 4).
    # Neither cap at the upper end can then light the next center lamp.
    for i in (0,2,4,5,7,9):
        v,z=y0+i,start-i
        if i==5:
            # Feed the adjacent wall torch from the side: its usual rear
            # diode would occupy the support above the lone emitter.
            g.rep((x+3,v,z),'east',dark)
            bus=FRONT_Z+2
            rail(g,dark,[(x+4,v,u) for u in range(z,bus-1,-1)]+[(x+3,v,bus),(x+2,v,bus)])
            emitter(g,x,v,dark,cap=True,side=True)
            continue
        # Side taps are diodes; no upper tap can feed back into the ramp.
        g.rep((x+1,v,z),'west',dark)
        g.dust_line(dark,[(x,v,u) for u in range(z,FRONT_Z+7,-1)])
        g.rep(relative(x,v,7),'north',dark)
        g.support(relative(x,v,6))
        g.rep(relative(x,v,5),'north',dark)
        g.support(relative(x,v,4))
        emitter(g,x,v,dark,cap=i!=4)


def block_icon(g,key,pad,net):
    x,y,_=red.world(pad)
    dark=low(g,pad,net)
    bus=FRONT_Z+(7 if pad[0]%2 else 4)
    lower=[(x,y,u) for u in range(11,bus-1,-1)]
    upper=[(x,y,10),(x+1,y+1,10)] + [(x+1,y+2,u) for u in range(9,bus-1,-1)]
    rail(g,dark,lower)
    rail(g,dark,upper)
    for v in (y,y+2):
        g.dust_line(dark,[(a,v,bus) for a in range(x-1,x+3)])
        for a in range(x-1,x+3):
            emitter(g,a,v,dark,cap=not key.startswith('F') or v==y or a==x)
            for u in range(FRONT_Z+4,bus):
                g.rep((a,v,u),'north',dark)


def drive(g,key,pad,net):
    for p in pixels(key,pad):
        g.put(p,'redstone_lamp',lit=str(g.values[net]).lower())
    if key.startswith('B'):
        center(g,pad,net)
    elif key.startswith('E'):
        horizontal(g,pad,net)
    elif key.startswith('V'):
        vertical(g,pad,net)
    else:
        block_icon(g,key,pad,net)
