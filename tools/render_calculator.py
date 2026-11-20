"""Render the Moonspire calculator and a GIF walkthrough from its Litematica export."""
from __future__ import annotations

import argparse
from functools import cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont

from . import build_calculator as d
from . import calculator_display as screen
from . import calculator_logic as logic
from .render_universal_store import AQUA, BG, BLUE, COPPER, DIM, EDGE, FONT_DIR, GOLD, INK, MUTED, PANEL, RED
from .voxel_render import Camera, Scene, rasterizer

W, H = 1260, 930
PREVIEW = d.OUTPUT.with_name('moonspire-calculator-preview.jpg')
GIF = d.OUTPUT.with_name('moonspire-calculator.gif')
SCENARIOS = (
    (197, 19, 2, COPPER, 'Умножение', 'Пять разрядов без ручного перевода из двоичной системы.'),
    (197, 19, 3, BLUE, 'Целочисленное деление', 'Меняем только код операции — отсчёт начинается заново.'),
    (255, 255, 2, AQUA, 'Максимальное произведение', 'Табло выводит все пять цифр: 65025.'),
    (42, 87, 1, GOLD, 'Отрицательный результат', 'Минус загорается слева от числа.'),
    (197, 0, 3, RED, 'Деление на ноль', 'Цифры погашены, горит отдельный индикатор ошибки.'),
)



class Media:
    def __init__(self, schematic, assets, fonts):
        self.fonts = fonts
        self.scene = Scene(schematic, assets, fonts/'DejaVuSans.ttf')
        self.raster = rasterizer()
        self.full = self.scene.mesh()
        self.panel = {p: b for p,b in self.scene.blocks.items()
                      if p[0] <= 105 and d.FLOOR-2 <= p[1] <= d.PANEL_TOP and p[2] <= 8}
        self.blocks = len(self.scene.blocks)
        self.dimensions = ' × '.join(map(str,self.scene.occupancy))
        network = screen.design()
        self.gate_count = sum(network.gates[i].op not in ('INPUT', 'DELAY') for i in network.live())

    @cache
    def font(self, size, kind):
        names = {'normal':'DejaVuSans','bold':'DejaVuSans-Bold','serif':'DejaVuSerif','mono':'DejaVuSansMono'}
        return ImageFont.truetype(self.fonts/(names[kind]+'.ttf'),size)

    def txt(self, dr, p, label, size=20, *, color=INK, kind='normal', anchor=None, spacing=6):
        dr.multiline_text(p, label, font=self.font(size,kind), fill=color, anchor=anchor, spacing=spacing)

    def header(self, note):
        im=Image.new('RGB',(W,H),BG)
        dr=ImageDraw.Draw(im)
        dr.rounded_rectangle((28,22,31,110),radius=2,fill=AQUA)
        self.txt(dr,(44,22),'MOONSPIRE   /   REDSTONE LAB',14,color=AQUA,kind='bold')
        self.txt(dr,(41,38),d.TITLE,47,kind='serif')
        self.txt(dr,(44,96),note,16,color=MUTED)
        self.txt(dr,(1231,40),self.dimensions,30,kind='mono',anchor='ra')
        self.txt(dr,(1230,94),'X × Y × Z  /  JAVA 26.3',13,color=MUTED,kind='mono',anchor='ra')
        dr.line((27,124,1233,124),fill=EDGE)
        return im,dr

    def footer(self, dr, stage=0):
        dr.line((27,881,1233,881),fill=EDGE)
        for i,(x,title) in enumerate(((29,'ОБЩИЙ ВИД'),(218,'ПРИМЕРЫ ВЫЧИСЛЕНИЙ'))):
            dr.ellipse((x,903,x+7,910),fill=AQUA if stage==i else EDGE)
            self.txt(dr,(x+15,898),title,13,kind='bold',color=AQUA if stage==i else DIM)
        self.txt(dr,(1233,897),'РЕНДЕР ИЗ .LITEMATIC  ·  БЕЗ КОМАНДНЫХ БЛОКОВ',13,kind='mono',color=DIM,anchor='ra')

    def viewport(self, im, box, mesh, angle, padding, ground=False):
        x0,y0,x1,y1=box
        w,h=x1-x0,y1-y0
        a,b,c,e=padding
        cam=Camera.fit(*angle,mesh.xyz.reshape(-1,3),(a,b,w-c,h-e))
        yy,xx=np.ogrid[:h,:w]
        glow=np.exp(-3*((xx/w-.55)**2/.66+(yy/h-.40)**2/.53))
        dim=np.array(ImageColor.getrgb('#14222e'))
        lit=np.array(ImageColor.getrgb('#294351'))
        view=Image.fromarray((dim+glow[...,None]*(lit-dim)).astype('uint8'))
        if ground:
            dr=ImageDraw.Draw(view)
            nx,_,nz=self.scene.occupancy
            at=lambda x,z: tuple(cam.project((x,-.24,z))[:2])
            for x in range(0,nx,16):
                dr.line((at(x,0),at(x,nz)),fill='#2d4350')
            for z in range(0,nz,16):
                dr.line((at(0,z),at(nx,z)),fill='#2d4350')
        bigger=Camera(cam.origin*2,cam.factor*2,cam.matrix)
        model=mesh.image(self.raster,bigger,(2*w,2*h)).resize((w,h),Image.Resampling.LANCZOS)
        view.paste(model,mask=model)
        stencil=Image.new('L',(w,h))
        ImageDraw.Draw(stencil).rounded_rectangle((0,0,w-1,h-1),radius=14,fill=255)
        im.paste(view,(x0,y0),stencil)
        ImageDraw.Draw(im).rounded_rectangle(box,radius=14,outline=EDGE)
        return Camera(cam.origin+(x0,y0),cam.factor,cam.matrix)

    def marker(self, dr, camera, p, end, index, tone):
        x,y,_=camera.project(p)
        middle=((x+end[0])*.5,end[1])
        dr.line(((x,y),middle,end),fill=BG,width=5)
        dr.line(((x,y),middle,end),fill=tone,width=1)
        dr.ellipse((x-4,y-4,x+4,y+4),fill=tone,outline=BG)
        self.badge(dr,end,str(index),tone)

    def badge(self, dr, p, label, tone):
        x,y=p
        dr.ellipse((x-13,y-13,x+13,y+13),fill=tone,outline=BG)
        self.txt(dr,(x,y),label,13,color=BG,kind='bold',anchor='mm')

    def overview(self, angle=(221,26)):
        im,dr=self.header('Редстоун-калькулятор · десятичное табло и шкала готовности')
        cam=self.viewport(im,(28,144,911,862),self.full,angle,(37,77,34,62),ground=True)
        self.txt(dr,(48,163),'01  /  ПОЛНАЯ СХЕМА',14,color=AQUA,kind='bold')
        self.txt(dr,(890,164),f'{self.blocks:,}'.replace(',','\u202f')+' БЛОКОВ',13,color=MUTED,kind='mono',anchor='ra')
        panel=cam.project((54,d.FLOOR+20,8))[:2]
        self.marker(dr,cam,(54,d.FLOOR+20,8),tuple(panel+(68,47)),1,AQUA)
        dr.rounded_rectangle((931,144,1232,862),radius=14,fill=PANEL,outline=EDGE)
        self.txt(dr,(951,164),'АРХИТЕКТУРА',14,color=AQUA,kind='bold')
        self.txt(dr,(950,194),'8 операций',31,kind='bold')
        self.txt(dr,(951,236),f'{len(d.LAYERS)} ярусов  ·  {self.gate_count:,} логических вентилей'.replace(',','\u202f'),
                 13,color=MUTED)
        rows=((AQUA,'Ламповое табло','Пять цифр и отдельный минус.\nДвоичные лампы сохранены.'),
              (GOLD,'Шкала готовности','Десять делений. Переключил\nрычаг — шкала сбросилась.'),
              (COPPER,'Арифметика','+  −  ×  ÷  %  ·  два числа 0–255.\nДо 65 025 без переполнения.'),
              (BLUE,'Двоичный → десятичный','Сдвиги и коррекция BCD.\nОтдельная ошибка для B = 0.'),
              (AQUA,'Побитовые функции','AND, OR, XOR. Код операции\nвыбирает одну группу выходов.'))
        for i,(color,title,body) in enumerate(rows,1):
            y=263+(i-1)*100
            dr.line((951,y,1212,y),fill=EDGE)
            self.badge(dr,(965,y+30),str(i),color)
            self.txt(dr,(986,y+19),title,16,kind='bold')
            self.txt(dr,(951,y+49),body,14,color=MUTED)
        self.footer(dr)
        return im

    def panel_mesh(self,a,b,op,progress):
        # Show the actual blocks of the console, with the lamps in the
        # illustrated timer phase (not a recording of individual ticks).
        original,parts=self.scene.blocks,self.scene.parts
        try:
            visible=self.panel.copy()
            for name,on in logic.inputs_for(a,b,op).items():
                at=d.LEVERS[name]
                kind,props=visible[at]
                visible[at]=kind,props|{'powered':str(on).lower()}
                rep=d.place(at,'south')
                kind,props=visible[rep]
                visible[rep]=kind,props|{'powered':str(on).lower()}
            word,err=logic.reference(a,b,op)
            ready=progress==screen.STAGES
            binary={f'R{i}':bool(abs(word)>>i&1) and ready for i in range(16)}|{'NEG':word<0 and ready,'ERR':err and ready}
            lit={d.LAMPS[name]:on for name,on in binary.items()}
            glyph=screen.glyphs(word,err,ready)
            glyph.update(f'P{i}' for i in range(progress))
            for name in d.DISPLAY_CENTERS:
                lit.update((p,name in glyph) for p in d.display_pixels(name))
            for point,on in lit.items():
                kind,props=visible[point]
                visible[point]=kind,props|{'lit':str(on).lower()}
            self.scene.blocks,self.scene.parts=visible,{}
            return self.scene.mesh()
        finally:
            self.scene.blocks,self.scene.parts=original,parts

    def bits(self,dr,start,word,width,tone,*,pitch=28,gap=0):
        x,y=start
        for i in range(width):
            on=word>>(width-1-i)&1
            p=x+pitch*i+gap*(i//4)
            dr.rounded_rectangle((p,y,p+pitch-4,y+28),radius=5,fill=tone if on else '#14212b',
                                 outline=tone if on else EDGE)
            self.txt(dr,(p+(pitch-4)/2,y+14),str(on),15,color=BG if on else MUTED,kind='mono',anchor='mm')

    def demo(self,k,progress=screen.STAGES):
        a,b,op,tone,title,note=SCENARIOS[k]
        value,err=logic.reference(a,b,op)
        ready=progress==screen.STAGES
        im,dr=self.header(f'Пример {k+1:02} из {len(SCENARIOS):02}  /  {title}')
        cam=self.viewport(im,(28,144,1232,600),self.panel_mesh(a,b,op,progress),(180,8),(34,52,34,28))
        self.txt(dr,(49,162),'02  /  ПЯТИЗНАЧНОЕ ТАБЛО',14,color=AQUA,kind='bold')
        status=f'{progress*10:3}%  /  ' + ('ГОТОВО' if ready else 'СИГНАЛ ИДЁТ')
        self.txt(dr,(1211,162),status,15,color=GOLD if ready else MUTED,kind='mono',anchor='ra')
        for group,end,color in (('A',7,COPPER),('B',7,BLUE),('M',2,GOLD)):
            mark=[]
            for bit in (end,0):
                x,y,z=d.LEVERS[f'{group}{bit}']
                px,py,_=cam.project((x+.5,y+.25,z+.44))
                mark.append(px)
                dr.line(((px,py),(px,561)),fill=color,width=1)
                dr.ellipse((px-3,py-3,px+3,py+3),fill=color,outline=BG)
            dr.line((mark[0],561,mark[1],561),fill=color,width=1)
            self.txt(dr,(sum(mark)/2,570),f'{group}{end} → {group}0',14,color=color,kind='mono',anchor='ma')
        for i,(label,word,width,color) in enumerate((('A',a,8,COPPER),('B',b,8,BLUE),('КОД',op,3,GOLD))):
            x=28+i*405
            dr.rounded_rectangle((x,618,x+394,729),radius=12,fill=PANEL,outline=EDGE)
            self.txt(dr,(x+18,630),label,15,color=color,kind='bold')
            self.txt(dr,(x+373,627),str(word) if i!=2 else logic.MODES[word],26,kind='mono',anchor='ra')
            self.bits(dr,(x+18,683),word,width,color,gap=9)
            if i==2:
                self.txt(dr,(x+125,685),f'режим {op}',17,color=MUTED)
        dr.rounded_rectangle((28,746,1232,862),radius=14,fill=PANEL,outline=EDGE)
        self.txt(dr,(50,758),'РЕЗУЛЬТАТ' if ready else 'РАСЧЁТ',14,color=tone,kind='bold')
        if ready:
            result='ОШИБКА' if err else str(value).replace('-','−')
            formula=f'{a} {logic.MODES[op]} {b} = {result}'
        else:
            formula=f'{a} {logic.MODES[op]} {b} = …'
        self.txt(dr,(46,782),formula,40,kind='serif')
        self.txt(dr,(700,760),'ШКАЛА ГОТОВНОСТИ',13,color=AQUA,kind='bold')
        for i in range(screen.STAGES):
            x=700+48*i
            dr.rounded_rectangle((x,786,x+38,800),radius=3,fill=GOLD if i<progress else '#14212b',outline=EDGE)
        self.txt(dr,(700,819),note if ready else 'Табло погашено, пока идёт отсчёт.',15,color=MUTED)
        self.footer(dr,stage=1)
        return im


def gif_write(path, frames, stills):
    training=Image.new('RGB',(420*3,290*((len(stills)+2)//3)),BG)
    for i,frame in enumerate(stills):
        training.paste(frame.resize((420,290),Image.Resampling.LANCZOS),((i%3)*420,(i//3)*290))
    ui=(BG, PANEL, EDGE, INK, MUTED, DIM, AQUA, COPPER, GOLD, BLUE, RED, '#14212b')
    color_count=255-len(ui)
    palette=training.quantize(colors=color_count,method=Image.Quantize.MEDIANCUT).getpalette()[:color_count*3]
    palette+= [v for color in ui for v in ImageColor.getrgb(color)] + [255,0,255]
    target=Image.new('P',(1,1))
    target.putpalette(palette)
    indexed=[f.quantize(palette=target,dither=Image.Dither.NONE) for f,_ in frames]
    indexed[0].save(path,save_all=True,append_images=indexed[1:],loop=0,disposal=1,optimize=True,
                    duration=[ms for _,ms in frames],palette=bytes(palette),interlace=False)


def make_media(schematic,assets,fonts,preview,animated):
    media=Media(schematic,assets,fonts)
    first=media.overview()
    media.demo(2).save(preview,quality=94,subsampling=0,optimize=True)
    print(f'Rendered {preview}',flush=True)
    frames=[(first,1800)]
    for i in range(1,9):
        phase=i/9
        angle=221-58*(phase*phase*(3-2*phase))
        frames.append((media.overview((angle,26-4*phase)),100))
    frames.append((media.overview((163,22)),650))
    stills=[first]
    for i in range(len(SCENARIOS)):
        for progress in range(screen.STAGES+1):
            frame=media.demo(i,progress)
            frames.append((frame,2300 if progress==screen.STAGES else 155 if progress else 480))
        stills.append(frame)
    gif_write(animated,frames,stills)
    print(f'Rendered {animated}',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assets',type=Path)
    parser.add_argument('--schematic',type=Path,default=d.OUTPUT)
    parser.add_argument('--fonts',type=Path,default=FONT_DIR)
    parser.add_argument('--preview',type=Path,default=PREVIEW)
    parser.add_argument('--gif',type=Path,default=GIF)
    args=parser.parse_args()
    make_media(args.schematic,args.assets,args.fonts,args.preview,args.gif)


if __name__ == '__main__':
    main()
