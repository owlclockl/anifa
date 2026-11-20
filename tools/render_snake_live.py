"""Render a real-time demo of the automatic Snake using its exported lamp wall."""
from __future__ import annotations

import argparse
from functools import cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import build_snake_live as board
from . import snake_live_rules as g
from .render_calculator import gif_write
from .render_universal_store import AQUA, BG, COPPER, DIM, EDGE, FONT_DIR, GOLD, INK, MUTED, PANEL
from .voxel_render import Camera, Scene, rasterizer

DEMO = board.ROOT/'moonspire-snake-live.gif'
W,H = 1240,1004
FACE = 44,163
SCALE = 8
ARROWS = {'up':'↑','left':'←','down':'↓','right':'→'}


def route():
    """A sample round with interior turns and two corners, no reduced timing."""
    r=g.Frame()
    yield r,None
    spawns=((69,54),(8,69),(30,24),None)
    for key,count in (('right',26),('up',8),('right',25),('down',44),('left',71),('up',10)):
        for i in range(count):
            r=g.move(r,key,spawn=spawns[r.score])
            assert r.outcome is None
            yield r,key if i==0 else None


class Art:
    def __init__(self, schematic, assets, fonts):
        self.fonts=fonts
        scene=Scene(schematic,assets,fonts/'DejaVuSans.ttf')
        raster=rasterizer()
        w,h,_=g.SIZE
        c=Camera(np.array((0,h*SCALE)),SCALE,Camera.basis(0,0))
        keep=lambda p:p[2]<=g.ZFACE+1
        size=w*SCALE,h*SCALE
        self.off=scene.mesh(keep).image(raster,c,size).convert('RGB')
        lamps={p for p,(name,_) in scene.blocks.items() if name=='redstone_lamp'}
        for p in lamps:
            scene.blocks[p]=('redstone_lamp',{'lit':'true'})
            scene.parts.pop(p,None)
        on=scene.mesh(keep).image(raster,c,size).convert('RGB')
        # Shade the unlit lamp glass as in a dim arcade, while the active
        # tiles retain the vanilla lit texture and exactly one-block footprint.
        unlit=np.array(self.off)
        lit_lut=np.round(np.arange(256)[:,None]*[.60,.66,.76]).astype(np.uint8)
        self.tiles={}
        for x,y,z in lamps:
            left,top=x*SCALE,(h-y-1)*SCALE
            rect=(left,top,left+SCALE,top+SCALE)
            self.tiles[x,y,z]=((left,top),on.crop(rect))
            cell=unlit[top:top+SCALE,left:left+SCALE]
            cell[:]=lit_lut[cell,np.arange(3)]
        self.off=Image.fromarray(unlit)
        console=scene.mesh(lambda p:p[1]>=g.DECK-1 and p[2]>=76)
        c=Camera.fit(10,46,console.xyz.reshape(-1,3),(4,9,378,138))
        hi=Camera(c.origin*2,c.factor*2,c.matrix)
        self.console=console.image(raster,hi,(764,292)).resize((382,146),Image.Resampling.LANCZOS)

    @cache
    def font(self,size,kind):
        name={'ui':'DejaVuSans','bold':'DejaVuSans-Bold','serif':'DejaVuSerif','mono':'DejaVuSansMono'}[kind]
        return ImageFont.truetype(self.fonts/(name+'.ttf'),size)

    def text(self,d,x,y,text,size,kind='ui',color=INK,anchor='lt'):
        d.text((x,y),text,fill=color,font=self.font(size,kind),anchor=anchor)

    def frame(self, r,key=None):
        img=Image.new('RGB',(W,H),BG)
        d=ImageDraw.Draw(img)
        text=lambda x,y,s,n,k='ui',c=INK,a='lt':self.text(d,x,y,s,n,k,c,a)
        def card(rect,fill=PANEL,outline=EDGE,radius=12):
            d.rounded_rectangle(rect,radius=radius,fill=fill,outline=outline)
        d.rounded_rectangle((28,23,31,106),radius=2,fill=AQUA)
        text(46,24,'MOONSPIRE  /  REDSTONE ARCADE',14,'bold',AQUA)
        text(43,46,'Лунная змейка',45,'serif')
        text(46,99,'Живой экран · каждый блок — игровая клетка',17,'ui',MUTED)
        text(1212,46,'72 × 72',43,'mono',INK,'rt')
        text(1210,100,'5 184 ИГРОВЫЕ КЛЕТКИ',15,'mono',AQUA,'rt')

        card((28,132,764,972),fill='#111c27')
        text(44,144,'01  /  ЛАМПОВОЕ ПОЛЕ',13,'bold',DIM)
        text(749,144,'ШИРИНА ЗМЕЙКИ  /  1 БЛОК',12,'mono',DIM,'rt')
        face=self.off.copy()
        lit={g.pixel(x,y) for x,y in r.lit}
        lit.update(board.hud_pixels('run'))
        for k in range(1,r.score+1):
            lit.update(board.hud_pixels(f'apple{k}'))
        for p in lit:
            offset,tile=self.tiles[p]
            face.paste(tile,offset)
        img.paste(face,FACE)

        card((784,132,1212,972))
        text(807,154,'02  /  ХОД ПАРТИИ',14,'bold',AQUA)
        x,y=r.body[0]
        text(805,186,f'X {x:02d}   Y {y:02d}',38,'mono')
        text(808,238,'Столбец и строка головы · 0–71',15,'ui',MUTED)
        card((807,274,1189,321),fill='#112a29',outline='#315d58',radius=8)
        d.ellipse((824,292,835,303),fill=AQUA)
        text(849,289,'АВТОМАТИЧЕСКОЕ ДВИЖЕНИЕ',16,'bold',AQUA)
        text(807,352,'СОБРАНО ЯБЛОК',14,'bold',MUTED)
        text(1189,342,f'{r.score} / {g.GOAL}',32,'mono',GOLD,'rt')
        for i in range(g.GOAL):
            left=807+i*98
            card((left,387,left+88,400),fill=GOLD if i<r.score else '#101b26',radius=5)
        d.line((806,432,1190,432),fill=EDGE)
        text(807,457,'0,20 с',38,'mono',INK)
        text(976,457,'1 лампа за шаг',22,'bold')
        text(977,488,'4 тика · 5 ламп/с при 20 TPS',14,'ui',MUTED)
        d.line((806,529,1190,529),fill=EDGE)
        text(807,553,'03  /  ПУЛЬТ УПРАВЛЕНИЯ',14,'bold',AQUA)
        card((806,580,1190,739),fill='#111c27',radius=8)
        img.paste(self.console,(807,586),self.console)
        labels={'left':(827,768),'up':(875,768),'down':(923,768),'right':(971,768)}
        for k,(x,y) in labels.items():
            card((x,y,x+41,y+40),fill=AQUA if key==k else BG,radius=6)
            text(x+20.5,y+20,ARROWS[k],23,'bold',BG if key==k else INK,'mm')
        text(1188,776,'НАПРАВЛЕНИЕ',13,'bold',MUTED,'rt')
        text(807,836,'Новая игра',18,'bold',COPPER)
        text(951,836,'Пауза / продолжить',18,'bold',COPPER)
        text(807,875,'Выбирай поворот, не дожидаясь шага.',16,'ui',MUTED)
        text(807,911,'Физические кнопки · ванильный датапак',15,'ui',DIM)
        text(28,984,'РЕНДЕР ИЗ СХЕМЫ  /  ДЕМО В ТЕМПЕ ИГРЫ',12,'mono',DIM)
        text(1212,984,'MINECRAFT JAVA',12,'mono',DIM,'rt')
        return img


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('assets',type=Path,help='Java 26.3 assets/minecraft')
    p.add_argument('--fonts',type=Path,default=FONT_DIR)
    p.add_argument('--schematic',type=Path,default=board.SCHEMATIC)
    p.add_argument('--preview',type=Path,default=board.POSTER)
    p.add_argument('--gif',type=Path,default=DEMO)
    a=p.parse_args()
    art=Art(a.schematic,a.assets,a.fonts)
    states=list(route())
    art.frame(*states[37]).save(a.preview,quality=94,subsampling=0,optimize=True)
    print(f'Rendered {a.preview}',flush=True)
    ms=50*g.STEP_TICKS
    frames=[(art.frame(r,k),50*g.START_TICKS if i==0 else 1200 if i==len(states)-1 else ms)
            for i,(r,k) in enumerate(states)]
    gif_write(a.gif,frames,[frames[i][0] for i in (0,37,103,167)])
    print(f'Rendered {a.gif}: {len(frames)} frames',flush=True)


if __name__=='__main__':
    main()
