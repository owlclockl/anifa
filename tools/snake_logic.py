"""The game rules and the independent redstone next-state logic for Moonspire Snake."""
from __future__ import annotations

from dataclasses import dataclass

from .calculator_logic import Circuit, Gate

SIZE = 6
START = ((2, 2), (1, 2), (0, 2))
APPLES = ((4, 2), (4, 4), (1, 4), (1, 1))
LIMIT = len(START)+len(APPLES)
DIRECTIONS = {'UP': (0,-1), 'LEFT': (-1,0), 'DOWN': (0,1), 'RIGHT': (1,0)}
COMMANDS = (*DIRECTIONS, 'RESET')
STATE = (tuple(f'S{j}{axis}{i}' for j in range(LIMIT) for axis in 'XY' for i in range(3))
         + tuple(f'G{i}' for i in range(len(APPLES))) + ('DEAD',))
BODIES = tuple(f'B{x}{y}' for y in range(SIZE) for x in range(SIZE))
HEADS = tuple(f'H{x}{y}' for y in range(SIZE) for x in range(SIZE))
STATUS = (*[f'G{i}' for i in range(len(APPLES))], 'READY', 'LOSE', 'WIN')


def board_edges():
    for y in range(SIZE):
        for x in range(SIZE):
            if x+1 < SIZE:
                yield f'E{x}{y}', (x,y), (x+1,y)
            if y+1 < SIZE:
                yield f'V{x}{y}', (x,y), (x,y+1)


@dataclass(frozen=True)
class Round:
    body: tuple[tuple[int, int], ...] = START
    dead: bool = False

    @property
    def eaten(self):
        return len(self.body)-len(START)

    @property
    def won(self):
        return self.eaten == len(APPLES)

    @property
    def food(self):
        if not self.dead and not self.won and APPLES[self.eaten] not in self.body:
            return APPLES[self.eaten]
        return None


def play(game, command):
    if command == 'RESET':
        return Round()
    if game.dead or game.won:
        return game
    x,y = game.body[0]
    dx,dy = DIRECTIONS[command]
    target = (x+dx,y+dy)
    if target == game.body[1]:
        return game  # don't go backwards into the neck
    grows = target == game.food
    remains = game.body if grows else game.body[:-1]
    if target in remains or not all(0 <= p < SIZE for p in target):
        return Round(game.body, True)
    return Round((target,*remains))


def lights(game):
    return ({f'B{x}{y}' for x,y in game.body} | {f'H{game.body[0][0]}{game.body[0][1]}'}
            | {f'F{i}' for i,p in enumerate(APPLES) if p == game.food}
            | {f'G{i}' for i in range(game.eaten)}
            | ({'LOSE'} if game.dead else {'WIN'} if game.won else set()))


def screen_lights(game, ready=True):
    """Reference frame: light links only between consecutive segments."""
    shown = {k for k in lights(game) if not k.startswith('H')}
    for (x0,y0),(x1,y1) in zip(game.body,game.body[1:]):
        axis = 'E' if y0 == y1 else 'V'
        shown.add(f'{axis}{min(x0,x1)}{min(y0,y1)}')
    x,y = game.body[0]
    shown.update((f'X{x}', f'Y{y}'))
    if ready:
        shown.add('READY')
    return shown


def initial_bits(game=Round()):
    bits = {'DEAD': game.dead} | {f'G{i}': i<game.eaten for i in range(len(APPLES))}
    trail = game.body+((0,0),)*(LIMIT-len(game.body))
    for j, point in enumerate(trail):
        for axis, value in zip('XY', point):
            for i in range(3):
                bits[f'S{j}{axis}{i}'] = bool(value >> i & 1)
    return bits


class Network(Circuit):
    def __init__(self):
        names = (*STATE, *(f'KEY_{k}' for k in COMMANDS),
                 *(f'REQ_{k}' for k in COMMANDS), 'PHASE_M', 'PHASE_S', 'BUSY')
        self.gates = [Gate('ZERO', (), ''), Gate('ONE', (), '')]+[Gate('INPUT', (), 'PORT') for _ in names]
        self.inputs = {name:i for i,name in enumerate(names,2)}
        self.outputs = {}
        self.screen = {}
        self.inverse = {0:1, 1:0}
        self.cache = {}
        self.bank = 'PORT'
        self.next = {}
        self.commands = {}
        self.clock = 0
        self.locks = ()

    def all_(self, terms):
        return self.invert(self.any(self.invert(t) for t in terms))

    def want(self, bits, val):
        return self.invert(self.any(b if not (val >> i & 1) else self.invert(b) for i,b in enumerate(bits)))

    def match(self, a, b):
        return self.invert(self.any(self.xor(x,y) for x,y in zip(a,b,strict=True)))

    def step_axis(self, bits, positive, negative):
        one,zero=positive,negative
        result=[]
        for bit in bits:
            result.append(self.xor(bit,self.or_(one,zero)))
            one=self.and_(one,bit)
            zero=self.difference(zero,bit)
        return result

    def sources(self, game=Round(), command=None):
        return (initial_bits(game) | {f'KEY_{k}':False for k in COMMANDS}
                | {f'REQ_{k}':k==command for k in COMMANDS}
                | {'PHASE_M':False,'PHASE_S':False,'BUSY':False})

    def live(self):
        needed=set(self.screen.values()) | set(self.next.values()) | set(self.commands.values()) | set(self.locks) | {self.clock}
        for i in reversed(range(len(self.gates))):
            if i in needed:
                needed.update(self.gates[i].args)
        return needed


def design():
    c=Network()
    c.bank='CONTROL'
    request={k:c.inputs[f'REQ_{k}'] for k in COMMANDS}
    armed=c.inputs['BUSY']
    c.commands={k:c.difference(c.inputs[f'KEY_{k}'],armed) for k in COMMANDS}
    c.clock=c.any(c.commands.values())
    c.locks=tuple(c.invert(c.inputs[f'PHASE_{k}']) for k in 'MS')
    c.outputs['READY']=c.invert(armed)
    trail=[[c.inputs[f'S{j}{axis}{i}'] for axis in 'XY' for i in range(3)] for j in range(LIMIT)]
    growth=[c.inputs[f'G{i}'] for i in range(len(APPLES))]
    visible=[1]*len(START)+growth
    dead=c.inputs['DEAD']
    c.outputs.update(LOSE=dead, WIN=growth[-1])
    for i,g in enumerate(growth):
        c.outputs[f'G{i}']=g

    c.bank='MOVES'
    # A chord has a fixed priority, RESET takes precedence over all arrows.
    picked={}
    prior=request['RESET']
    for k in DIRECTIONS:
        picked[k]=c.difference(request[k],prior)
        prior=c.or_(prior,request[k])
    x,y=trail[0][:3],trail[0][3:]
    new=c.step_axis(x,picked['RIGHT'],picked['LEFT']) + c.step_axis(y,picked['DOWN'],picked['UP'])
    wall=c.any(c.and_(picked[key],c.want(axis,limit)) for key,axis,limit in (
        ('UP',y,0),('DOWN',y,SIZE-1),('LEFT',x,0),('RIGHT',x,SIZE-1)))
    moving=c.difference(c.any(picked.values()),c.any((dead,growth[-1],c.match(new,trail[1]))))
    # The neck is handled separately; only a segment with another active
    # segment behind it can block entry (the final tail cell is departing).
    hit=c.any(c.and_(visible[j+1],c.match(new,trail[j])) for j in range(2,LIMIT-1))
    collision=c.or_(wall,hit)
    advance=c.difference(moving,collision)
    died=c.or_(dead,c.and_(moving,collision))

    # Decode one axis per segment, then combine the row and column at each pixel.
    c.bank='COORDS'
    xs,ys=[],[]
    for j,s in enumerate(trail):
        xs.append([c.and_(visible[j],c.want(s[:3],v)) for v in range(SIZE)])
        ys.append([c.want(s[3:],v) for v in range(SIZE)])
    for yy in range(SIZE):
        c.bank=f'ROW{yy}'
        for xx in range(SIZE):
            cells=[c.and_(a[xx],b[yy]) for a,b in zip(xs,ys)]
            c.outputs[f'B{xx}{yy}']=c.any(cells)
            c.outputs[f'H{xx}{yy}']=cells[0]

    c.bank='FRUIT'
    wins=[]
    for i,(xx,yy) in enumerate(APPLES):
        selected=c.difference(growth[i-1] if i else 1,growth[i])
        on=c.difference(selected,c.or_(dead,c.outputs[f'B{xx}{yy}']))
        c.outputs[f'F{i}']=on
        at=c.and_(c.want(new[:3],xx),c.want(new[3:],yy))
        wins.append(c.and_(on,at))
    grow=c.and_(advance,c.any(wins))
    saved=initial_bits()
    def save(name, node):
        c.next[name]=c.or_(node,request['RESET']) if saved[name] else c.difference(node,request['RESET'])

    c.bank='MEMORY'
    for j,(nxt,cur) in enumerate(zip([new,*trail[:-1]],trail)):
        for i,(a,b) in enumerate(zip(nxt,cur)):
            save(f'S{j}{"XY"[i//3]}{i%3}',c.mux(advance,a,b))
    for i,g in enumerate(growth):
        save(f'G{i}',c.or_(g,c.and_(grow,growth[i-1] if i else 1)))
    save('DEAD',died)

    c.screen.update((k,c.outputs[k]) for k in (*BODIES,*(f'F{i}' for i in range(len(APPLES))),*STATUS))
    c.screen.update((f'X{i}',n) for i,n in enumerate(xs[0]))
    c.screen.update((f'Y{i}',n) for i,n in enumerate(ys[0]))

    # Consecutive coordinates are equal or differ by one. For these pairs,
    # the low bit detects motion on the axis. At each position of min(a,b),
    # either both bits are set or a carry toggled the next higher bit.
    def anchors(offset, bank):
        c.bank=bank
        result=[]
        for j,(here,there) in enumerate(zip(trail,trail[1:])):
            a,b=here[offset:offset+3],there[offset:offset+3]
            changed=[c.xor(u,v) for u,v in zip(a,b)]
            lower=[c.or_(c.and_(a[i],b[i]),changed[i+1] if i<2 else 0) for i in range(3)]
            show=c.and_(changed[0],visible[j+1])
            result.append([c.and_(show,c.want(lower,v)) for v in range(SIZE-1)])
        return result

    left,above=anchors(0,'EDGE_X'),anchors(3,'EDGE_Y')
    for key,(x,y),_ in board_edges():
        c.bank=f'LINE{y}'
        if key.startswith('E'):
            pairs=zip((a[x] for a in left),(b[y] for b in ys))
        else:
            pairs=zip((a[x] for a in xs),(b[y] for b in above))
        c.screen[key]=c.any(c.and_(a,b) for a,b in pairs)
    return c


WIN_ROUTE = ('RIGHT','RIGHT','DOWN','DOWN','LEFT','LEFT','LEFT','UP','UP','UP')
