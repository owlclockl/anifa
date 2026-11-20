"""Independent rules for the addressable, automatic Moonspire Snake."""
from __future__ import annotations

from dataclasses import dataclass, replace

SIDE = 72
STEP_TICKS, SLOW_TICKS = 4, 8
START_TICKS = 30
SIZE = (88,99,131)
X0, Y_TOP, ZFACE = 8,88,4
ANCHOR = X0,Y_TOP,0
DECK, VIEW_Z = 48,80
VIEW = (43.5,DECK+1,VIEW_Z+.5)
BUTTON = 'minecraft:stone_button[face=floor,facing=north,powered={}]'
BUTTONS = {'new': (40,DECK+1,78), 'up': (43,DECK+1,77), 'left': (42,DECK+1,78),
           'down': (43,DECK+1,79), 'right': (44,DECK+1,78), 'pause': (46,DECK+1,78)}
DIRECTION = {'up': (0,-1), 'right': (1,0), 'down': (0,1), 'left': (-1,0)}
KEYS = tuple(DIRECTION)
START = tuple((x,35) for x in range(20,8,-1))
FIRST = (40,35)
GOAL, GAIN, RADIUS = 4, 4, 2
MAX_CENTER = SIDE-RADIUS-1
FALLBACK_START, FALLBACK_PITCH = RADIUS+1, 2*RADIUS+2
HUD = {'apple1': (10,10), 'apple2': (16,10), 'apple3': (22,10), 'apple4': (28,10),
       'run': (56,10), 'loss': (65,10), 'win': (74,10)}
MARKS = {(0,0,0):'waxed_cut_copper',(87,0,0):'chiseled_tuff_bricks'}


def pixel(x,y):
    return x+X0,Y_TOP-y,ZFACE


def fruit_pixels(center):
    if center is None:
        return set()
    x,y=center
    return {(x+i,y+j) for j in range(-RADIUS,RADIUS+1) for i in range(-RADIUS,RADIUS+1)
            if abs(i)+abs(j)<=RADIUS}


def valid_fruit(center,body):
    x,y=center
    return (RADIUS<=x<=MAX_CENTER and RADIUS<=y<=MAX_CENTER
            and fruit_pixels(center).isdisjoint(body))


def in_field(x,y):
    return 0<=x<SIDE and 0<=y<SIDE


@dataclass(frozen=True)
class Frame:
    body: tuple[tuple[int,int], ...] = START
    heading: str = 'right'
    fruit: tuple[int,int] | None = FIRST
    score: int = 0
    growth: int = 0
    outcome: str | None = None

    @property
    def lit(self):
        return set(self.body) | fruit_pixels(self.fruit)


def turn(frame, request):
    if request is None:
        return frame.heading
    return frame.heading if KEYS[(KEYS.index(frame.heading)+2)%4]==request else request


def move(frame, request=None, *, spawn=None):
    """Advance exactly one lamp; optionally supply a valid fruit after eating."""
    if frame.outcome:
        return frame
    key = turn(frame,request)
    dx,dy = DIRECTION[key]
    x,y=frame.body[0]
    nxt=x+dx,y+dy
    eats=nxt in fruit_pixels(frame.fruit)
    hold=frame.growth>0 or eats
    body=frame.body if hold else frame.body[:-1]
    if not in_field(*nxt) or nxt in body:
        return replace(frame,outcome='loss')
    body=(nxt,*body)
    score=frame.score+int(eats)
    growth=max(0,frame.growth+GAIN*eats-1)
    won=score>=GOAL
    fruit=None if won else spawn if eats else frame.fruit
    if eats and fruit is not None and not valid_fruit(fruit,body):
        raise ValueError('Fruit intersects the new trail or goes outside the field')
    return Frame(body,key,fruit,score,growth,'win' if won else None)
