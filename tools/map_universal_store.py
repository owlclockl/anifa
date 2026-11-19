"""Draw the navigation sheet from the same positions as the Litematica export."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import build_universal_store as u, catacomb_logistics as l

OUTPUT = u.OUTPUT.with_name('moonspire-universal-store-map.png')
BG, PANEL, LINE = '#101820', '#182630', '#30424c'
WHITE, MUTED = '#f3f0e7', '#a7bcc7'
COPPER, AQUA, BLUE, RED = '#f3ae78', '#77ddc5', '#8dc5fd', '#ff9a8b'
FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')


def draw(path, fonts):
    im = Image.new('RGB', (1440, 1010), BG)
    d = ImageDraw.Draw(im)

    def text(p, body, size=22, *, color=WHITE, bold=False, anchor=None):
        font = ImageFont.truetype(fonts / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), size)
        d.text(p, body, font=font, fill=color, anchor=anchor)

    def box(rect, fill=PANEL, edge=None, r=16):
        d.rounded_rectangle(rect, radius=r, fill=fill, outline=edge, width=1)

    def badge(p, title, color, r=15):
        x,y=p
        d.ellipse((x-r-2,y-r-2,x+r+2,y+r+2),fill=BG)
        d.ellipse((x-r,y-r,x+r,y+r),fill=color)
        text((x,y),title,17,color=BG,bold=True,anchor='mm')

    def arrow(a,b, color=AQUA, trim=21):
        dx, dy = b[0]-a[0], b[1]-a[1]
        distance = math.hypot(dx,dy)
        ux,uy = dx/distance,dy/distance
        end=(b[0]-ux*trim,b[1]-uy*trim)
        start=(a[0]+ux*trim,a[1]+uy*trim)
        if distance > 2*trim:
            d.line((start,end),fill=color,width=3)
            d.polygon([end,(end[0]-13*ux-6*uy,end[1]-13*uy+6*ux),
                       (end[0]-13*ux+6*uy,end[1]-13*uy-6*ux)],fill=color)

    text((42,30), 'MOONSPIRE   /   JAVA 26.3', 17, color=AQUA, bold=True)
    text((40,57), 'Кладовая хранителей', 52, bold=True)
    text((43,126), 'Автосклад по категориям · план без поворота схемы', 23, color=MUTED)
    text((1395,53), ' × '.join(str(n+1) for n in u.BOUNDS[1]), 36, bold=True, anchor='ra')
    text((1395,101), f'X × Y × Z   /   {len(u.CELLS)} секций', 19, color=MUTED, anchor='ra')
    d.line(((42,173),(1397,173)), fill=LINE, width=2)

    box((40,193,850,956)); box((875,193,1400,956))
    text((67,214), '01   ВИД СВЕРХУ', 18, color=AQUA, bold=True)
    text((903,214), '02   КУДА КЛАСТЬ ПРЕДМЕТЫ', 18, color=AQUA, bold=True)
    px, pz, scale = 99, 271, 17
    extent = (u.BOUNDS[1][0]+1, u.BOUNDS[1][2]+1)

    def xy(x,z):
        return px+x*scale, pz+z*scale

    def dot(p):
        return xy(p[0]+.5,p[2]+.5)

    xx,zz=xy(*extent)
    d.rectangle((px,pz,xx,zz), fill='#1b2b34', outline=LINE)
    for x in range(0,extent[0]+1,5):
        sx,sy=xy(x,0)
        d.line((sx,sy,sx,zz),fill=LINE)
        text((sx,sy-7),str(x),13,color=MUTED,anchor='ms')
    for z in range(0,extent[1]+1,5):
        sx,sy=xy(0,z)
        d.line((sx,sy,xx,sy),fill=LINE)
        text((sx-11,sy),str(z),13,color=MUTED,anchor='rm')
    text((xx+11,pz-11),'X→',14,color=MUTED)
    text((px-18,zz+12),'Z↓',14,color=MUTED)

    box((*xy(2,0),*xy(36,22)), '#24323a', '#73523f', r=8)
    text(dot((13,0,2)), '20 СБОРОЧНЫХ ПОЗИЦИЙ', 16, color=COPPER, bold=True)
    text(dot((13,0,4)), '2 яруса · продукты уходят в секции', 15, color=MUTED)
    for (x,_,z) in {p.origin for p in u.PRESSES if p.origin[1] == 25}:
        sx,sz=xy(x-1,z-1)
        ex,ez=xy(x+2,z+1)
        box((sx,sz,ex,ez),'#795440',r=4)
    for cell in u.CELLS:
        x,y,z=cell.center
        box((*xy(x-2,z-2),*xy(x+3,z+3)), '#28514f', '#386a66', r=8)
    points = [dot(cell.center) for cell in u.CELLS]
    for a,b in zip(points,points[1:]):
        arrow(a,b)
    for i,(cell,pos) in enumerate(zip(u.CELLS,points),1):
        badge(pos,str(i),AQUA,19)
        text((pos[0],pos[1]-28),f'Y={cell.center[1]}',13,color=WHITE,bold=True,anchor='mm')
    for unit in u.UNLOADERS:
        x,_,z=unit.origin
        box((*xy(x-5,z+3),*xy(x+4,z+9)),'#3c3636','#785341',r=7)
    marks = [
        ('A', INTAKE_POINT, (30, 79), COPPER, 'Общая приёмка', 'Сундук для россыпи'),
        ('B', u.WATER_PORT, (-40, -38), BLUE, 'Водный ввод', 'Короткий открытый жёлоб'),
        ('C1', l.step(u.BOX_INPUTS[0], 'up'), (10, 93), COPPER, 'Разгрузка 1', 'Положи шалкер в бочку'),
        ('C2', l.step(u.BOX_INPUTS[1], 'up'), (30, 93), COPPER, 'Разгрузка 2', 'Положи шалкер в бочку'),
        ('D', u.RAW_INPUT, (36, -37), COPPER, 'Автоупаковка', 'Ресурсы для 20 рецептов 9 → 1'),
        ('!', u.OVERFLOW[-1], (42,72), RED, 'Переполнение', 'Две бочки под секцией 7'),
    ]
    for i,(key, point, off, tone, title, sub) in enumerate(marks):
        p=dot(point); call=(p[0]+off[0], p[1]+off[1])
        d.line((p, call),fill=tone,width=2)
        d.ellipse((p[0]-4,p[1]-4,p[0]+4,p[1]+4),fill=tone)
        badge(call,key,tone)
        yy=274+78*i
        badge((924,yy+9), key, tone)
        text((953,yy-9),title,22,bold=True)
        text((953,yy+20),sub,17,color=MUTED)
        text((1369,yy+24),'/'.join(map(str,point)),15,color=tone,anchor='ra')
        d.line((905,yy+48,1370,yy+48),fill=LINE)

    text((907,759), 'ПУТЬ ВЕЩЕЙ', 16, color=AQUA, bold=True)
    text((907,791), 'Входы и сборщики → секции 1–7', 21, bold=True)
    text((907,821), 'Шалкеры после разгрузки → «Шалкеры»', 17, color=MUTED)
    text((907,850), 'Занятая категория → бочки «!»', 17, color=MUTED)
    text((907,894), 'Координаты X/Y/Z — от минимума схемы.', 16, color=MUTED)
    text((907,918), 'Точки секций отмечают рельс големов.', 16, color=MUTED)
    text((42,978), 'Оставляй по одному образцу каждого типа в его сундуке.', 17, color=MUTED)
    im.save(path, optimize=True)


INTAKE_POINT = u.INTAKE[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--fonts', type=Path, default=FONT_DIR)
    args = parser.parse_args()
    draw(args.output, args.fonts)


if __name__ == '__main__':
    main()
