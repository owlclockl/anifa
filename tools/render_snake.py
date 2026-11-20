"""Illustrate a round using the actual lamp positions in the Snake export."""
from __future__ import annotations

import argparse
from functools import cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import build_snake as schematic
from . import snake_logic as game
from .render_calculator import gif_write
from .render_universal_store import AQUA, BG, COPPER, DIM, EDGE, FONT_DIR, GOLD, INK, MUTED, PANEL, RED
from .voxel_render import Camera, Scene, rasterizer

PREVIEW = schematic.OUTPUT.with_name('moonspire-snake-preview.jpg')
DEMO = schematic.OUTPUT.with_name('moonspire-snake.gif')
WIDTH, HEIGHT = 1240, 998
BOARD = (28, 139, 874, 868)
ARROWS = {'UP':'↑', 'LEFT':'←', 'DOWN':'↓', 'RIGHT':'→', 'RESET':'↻'}


class Art:
    def __init__(self, path, assets, fonts):
        self.fonts=fonts
        self.scene=Scene(path,assets,fonts/'DejaVuSans.ttf')
        self.draw_voxels=rasterizer()
        panel_z=schematic.screen.FRONT_Z
        self.face={p:state for p,state in self.scene.blocks.items()
                   if p[0]<schematic.WIDTH_PANEL and abs(p[2]+schematic.FRONT-panel_z)<=1 and p[1]>=schematic.FLOOR}
        x0,y0,x1,y1=BOARD
        yy,xx=np.ogrid[:y1-y0,:x1-x0]
        glow=np.exp(-4*((xx/(x1-x0)-.52)**2+(yy/(y1-y0)-.44)**2))
        self.backdrop=Image.fromarray((np.array([13,23,31])+glow[...,None]*[32,48,52]).astype('uint8'))

    @cache
    def font(self,size,kind):
        name={'serif':'DejaVuSerif','bold':'DejaVuSans-Bold','sans':'DejaVuSans','mono':'DejaVuSansMono'}[kind]
        return ImageFont.truetype(self.fonts/(name+'.ttf'),size)

    def text(self,d,p,msg,size,*,tone=INK,kind='sans',anchor=None):
        d.multiline_text(p,msg,font=self.font(size,kind),fill=tone,anchor=anchor,spacing=7)

    def render(self,round_,phase):
        ready=phase!='turn'
        showing=game.screen_lights(round_,ready)
        face=self.face.copy()
        for name in schematic.LAMP_PORTS:
            for p in map(schematic.export_point,schematic.pixels(name)):
                kind,props=face[p]
                face[p]=kind,props|{'lit':str(name in showing).lower()}
        original=self.scene.blocks
        self.scene.blocks,self.scene.parts=face,{}
        try:
            mesh=self.scene.mesh()
        finally:
            self.scene.blocks,self.scene.parts=original,{}
        x0,y0,x1,y1=BOARD
        w,h=x1-x0,y1-y0
        camera=Camera.fit(182,5,mesh.xyz.reshape(-1,3),(34,58,w-34,h-29))
        cam=Camera(camera.origin*2,camera.factor*2,camera.matrix)
        voxels=mesh.image(self.draw_voxels,cam,(2*w,2*h)).resize((w,h),Image.Resampling.LANCZOS)
        background=self.backdrop.copy()
        background.paste(voxels,mask=voxels)
        return background

    def frame(self,r,key=None,phase='ready',step=None):
        img=Image.new('RGB',(WIDTH,HEIGHT),BG)
        d=ImageDraw.Draw(img)
        d.rounded_rectangle((28,22,31,106),radius=2,fill=AQUA)
        self.text(d,(46,22),'MOONSPIRE  /  REDSTONE ARCADE',15,tone=AQUA,kind='bold')
        self.text(d,(43,43),'Лунная змейка',46,kind='serif')
        self.text(d,(48,102),'Змейка шириной в один блок · игровое поле 6 × 6',17,tone=MUTED)
        self.text(d,(1211,38),f'{schematic.BOARD_SIZE} × {schematic.BOARD_SIZE}',40,kind='mono',anchor='ra')
        self.text(d,(1211,98),'ЛАМПЫ НА ПОЛЕ  /  JAVA 26.3',14,tone=MUTED,kind='mono',anchor='ra')
        mask=Image.new('L',self.backdrop.size)
        ImageDraw.Draw(mask).rounded_rectangle((0,0,mask.width-1,mask.height-1),radius=15,fill=255)
        img.paste(self.render(r,phase),BOARD[:2],mask)
        d.rounded_rectangle(BOARD,radius=15,outline=EDGE)
        self.text(d,(48,159),'01  /  МАТРИЦА БЕЗ ПРОМЕЖУТКОВ',14,tone=AQUA,kind='bold')
        label=f'ХОД {step:02}' if step is not None else 'РЕНДЕР СХЕМЫ'
        self.text(d,(853,158),label,15,tone=MUTED,kind='mono',anchor='ra')
        d.rounded_rectangle((894,139,1212,868),radius=15,fill=PANEL,outline=EDGE)
        self.text(d,(917,159),'02  /  ПАРТИЯ',14,tone=AQUA,kind='bold')
        self.text(d,(916,192),f'{r.eaten} / 4',41,kind='mono')
        self.text(d,(918,247),'ЯБЛОК СОБРАНО',13,tone=MUTED,kind='bold')
        for i in range(4):
            x=918+i*68
            d.rounded_rectangle((x,276,x+56,291),radius=4,fill=GOLD if i<r.eaten else '#14212b',outline=EDGE)
        status,tone= ('ПОБЕДА',GOLD) if r.won else ('СТОЛКНОВЕНИЕ',RED) if r.dead else ('ХОД В ОБРАБОТКЕ',COPPER) if phase=='turn' else ('МОЖНО ХОДИТЬ',AQUA)
        d.rounded_rectangle((918,315,1189,352),radius=6,outline=tone)
        d.ellipse((928,330,937,339),fill=tone)
        self.text(d,(946,325),status,15,tone=tone,kind='bold')
        glyphs=((('.....','####.','...#.','...#.','.....'),'Змейка','Тонкая линия и на поворотах'),
                (('..+..','.....','..#.+','..#..','..#..'),'Голова','Метки сверху и справа'),
                (('.....','..#..','####.','####.','####.'),'Яблоко','Плод с черенком на поле'))
        for i,(matrix,capt,note) in enumerate(glyphs):
            y=403+92*i
            d.line((918,y-19,1189,y-19),fill=EDGE)
            d.rounded_rectangle((918,y,971,y+53),radius=7,fill=BG,outline=EDGE)
            for v,row in enumerate(matrix):
                for u,mark in enumerate(row):
                    x0,y0=925+8*u,y+7+8*v
                    fill=GOLD if mark=='#' else AQUA if mark=='+' else '#1f2c38'
                    d.rectangle((x0,y0,x0+6,y0+6),fill=fill)
            self.text(d,(985,y+1),capt,22,kind='bold')
            self.text(d,(985,y+34),note,13,tone=MUTED)
        d.line((918,672,1189,672),fill=EDGE)
        self.text(d,(918,694),'ДЛИНА ЗМЕЙКИ',13,tone=MUTED,kind='bold')
        self.text(d,(916,718),f'{len(r.body)} / 7',34,kind='mono')
        self.text(d,(918,802),'5 184 ЛАМПЫ НА ПОЛЕ',15,tone=AQUA,kind='mono')
        self.text(d,(918,827),'ВАНИЛЬНЫЙ РЕДСТОУН',13,tone=MUTED,kind='mono')
        d.rounded_rectangle((28,887,1212,957),radius=12,fill=PANEL,outline=EDGE)
        self.text(d,(51,909),'ПУЛЬТ',15,tone=AQUA,kind='bold')
        for i,k in enumerate(game.COMMANDS):
            x=154+60*i
            highlight=k==key
            d.rounded_rectangle((x,900,x+45,944),radius=7,fill=AQUA if highlight else BG,outline=AQUA if highlight else EDGE)
            self.text(d,(x+22.5,922),ARROWS[k],24,tone=BG if highlight else INK,kind='bold',anchor='mm')
        self.text(d,(485,912),'Одно нажатие — один ход.  ↻ Новая игра.',19,tone=MUTED)
        self.text(d,(29,974),'РЕНДЕР ИЗ .LITEMATIC  /  ПАУЗЫ В ДЕМО СОКРАЩЕНЫ',12,tone=DIM,kind='mono')
        self.text(d,(1212,974),'БЕЗ КОМАНДНЫХ БЛОКОВ',12,tone=DIM,kind='mono',anchor='ra')
        return img


def create(schematic_path, assets, fonts, preview, demo):
    art=Art(schematic_path,assets,fonts)
    r=game.Round()
    first=art.frame(r,step=0)
    frames=[(first,1400)]
    training=[first]
    for step,key in enumerate(game.WIN_ROUTE,1):
        frames.append((art.frame(r,key,phase='turn',step=step),240))
        r=game.play(r,key)
        still=art.frame(r,step=step)
        frames.append((still,2400 if r.won else 560))
        if step in (4,6,10):
            training.append(still)
        if step==4:
            art.frame(r).save(preview,quality=94,subsampling=0,optimize=True)
            print(f'Rendered {preview}',flush=True)
    frames.append((art.frame(r,'RESET',phase='turn'),320))
    gif_write(demo,frames,training)
    print(f'Rendered {demo}',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assets',type=Path,help='Java 26.3 assets/minecraft')
    parser.add_argument('--schematic',type=Path,default=schematic.OUTPUT)
    parser.add_argument('--fonts',type=Path,default=FONT_DIR)
    parser.add_argument('--preview',type=Path,default=PREVIEW)
    parser.add_argument('--gif',type=Path,default=DEMO)
    args=parser.parse_args()
    create(args.schematic,args.assets,args.fonts,args.preview,args.gif)


if __name__=='__main__':
    main()
