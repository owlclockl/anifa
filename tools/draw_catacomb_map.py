#!/usr/bin/env python3
"""Draw a north-up guide from the actual lower floor, with the two stairs projected onto it."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import build_catacomb_cathedral as b
from .catacomb_routes import tread_tables


LEFT, RIGHT, TOP, BOTTOM = -110, 43, 72, 238
SCALE = 5
OX, OZ = 88, 188
WIDTH, HEIGHT = 1510, 1140
INK = '#eee7db'
SUBTEXT = '#b4bdc7'
CYAN = '#89dcca'
COPPER = '#efb176'
LINE = '#394753'


def pt(x: int, z: int) -> tuple[int, int]:
    return OX + (x - LEFT) * SCALE + SCALE // 2, OZ + (z - TOP) * SCALE + SCALE // 2


def dashed(draw: ImageDraw.ImageDraw, a, z, fill: str) -> None:
    x0, y0 = pt(*a)
    x1, y1 = pt(*z)
    steps = abs(x1 - x0) + abs(y1 - y0)
    dx, dy = (x1 - x0) / steps, (y1 - y0) / steps
    for i in range(0, steps, 15):
        j = min(steps, i + 8)
        draw.line((x0 + dx*i, y0 + dy*i, x0 + dx*j, y0 + dy*j), fill=fill, width=3)


def draw_map(g: b.Catacombs, output: Path) -> None:
    wall = (22, 29, 38)
    hall = (63, 73, 84)
    clear, support, _ = tread_tables()
    floor, foot, head = g.box(LEFT, RIGHT, b.LOW, b.LOW + 2, TOP, BOTTOM)
    aisle = support[floor] & clear[foot] & clear[head]
    pixels = np.full((*floor.shape, 3), wall, dtype=np.uint8)
    pixels[aisle] = hall
    pixels[aisle & (floor == b.COPPER)] = (105, 77, 56)
    canvas = Image.new('RGB', (WIDTH, HEIGHT), '#111820')
    canvas.paste(Image.fromarray(pixels).resize((pixels.shape[1]*SCALE, pixels.shape[0]*SCALE), Image.Resampling.NEAREST), (OX, OZ))
    d = ImageDraw.Draw(canvas)
    sans = 'DejaVuSans.ttf'
    serif = 'DejaVuSerif.ttf'
    label = ImageFont.truetype(sans, 22)
    small = ImageFont.truetype(sans, 18)
    number = ImageFont.truetype(sans, 16)
    d.rectangle((34, 30, WIDTH-34, HEIGHT-30), outline=LINE, width=2)
    d.text((88, 53), 'АББАТСТВО ЛУННЫХ ШПИЛЕЙ   /   ПЕЧАТЬ ГЛУБИН', font=small, fill=COPPER)
    d.text((86, 92), 'План катакомб', font=ImageFont.truetype(serif, 50), fill=INK)
    d.text((895, 107), 'Нижнее кольцо · север вверху', font=label, fill=SUBTEXT)
    d.line((88, 164, 1420, 164), fill=LINE, width=2)
    d.line((*pt(37, 88), *pt(37, 79)), fill=COPPER, width=3)
    x, z = pt(37, 79)
    d.polygon(((x, z-5), (x-6, z+7), (x+6, z+7)), fill=COPPER)
    d.text((x, z-15), 'С', font=number, fill=COPPER, anchor='ms')

    west = (b.NW, b.NE, (19, 165), (8, 165), (8, 187), (19, 187), b.SE, b.SW, b.NW)
    east = ((19, 165), (30, 165), (30, 187), (19, 187))
    for route in (west, east, ((-31, 130), (-31, 102))):
        d.line([pt(*q) for q in route], fill=CYAN, width=3, joint='curve')
    for first, second in b.SPURS[1:]:
        d.line([pt(*first), pt(*second)], fill=COPPER, width=4)
    dashed(d, (-55, 166), (-31, 166), COPPER)
    dashed(d, (b.SERVICE_X, 115), (b.SERVICE_X, 79), COPPER)
    d.rectangle((*pt(b.HEART.x-7, b.HEART.z-8), *pt(b.HEART.x+7, b.HEART.z+8)), fill='#29484a', outline='#63afa6', width=2)

    places = (
        ((b.HUB.x, b.HUB.z), 'Распутье ключей', 'Мозаичный компас. Начало обхода.'),
        ((b.NAMES.x, b.NAMES.z), 'Галерея имён', 'Каменные гробницы хранителей.'),
        ((b.ARCHIVE.x, b.ARCHIVE.z), 'Лунный архив', 'Северная ветвь; опись древнего города.'),
        ((b.HEART.x, b.HEART.z), 'Печать глубин', 'Разлом за стеклом; обход с двух сторон.'),
        ((b.BELLS.x, b.BELLS.z), 'Семь колоколов', 'Костница в южном крыле.'),
        ((b.CRYPT_GATE[0], b.CRYPT_GATE[2]), 'Подъём в крипту', 'Из крипты — к хору и тронному залу.'),
        ((b.SERVICE_DOOR[0], b.SERVICE_DOOR[2]), 'Выход в жилой двор', 'К дому, мастерской и клуатру.'),
    )
    for i, (pos, title, note) in enumerate(places, 1):
        color = COPPER if i in (6, 7) else CYAN
        x, z = pt(*pos)
        d.ellipse((x-15, z-15, x+15, z+15), fill='#111820', outline=color, width=2)
        d.text((x, z), str(i), font=number, fill=color, anchor='mm')
        py = 233 + (i - 1)*94
        d.ellipse((911, py + 3, 943, py + 35), outline=color, width=2)
        d.text((927, py + 19), str(i), font=number, fill=color, anchor='mm')
        d.text((962, py), title, font=label, fill=INK)
        d.text((962, py+33), note, font=small, fill=SUBTEXT)
        d.line((911, py+72, 1418, py+72), fill=LINE)

    for row, (color, text) in enumerate(((CYAN, 'Кольцо и ответвление в архив'),
                                        (COPPER, 'Медные метки к выходам'),
                                        (COPPER, 'Пунктир — подъём этажом выше'))):
        y = 920 + row*31
        if row == 2:
            for x in (913, 924, 935):
                d.line((x, y+9, x+7, y+9), fill=color, width=3)
        else:
            d.line((913, y+9, 942, y+9), fill=color, width=3)
        d.text((961, y), text, font=small, fill=SUBTEXT)
    d.line((87, 1045, 1420, 1045), fill=LINE)
    d.text((88, 1063), 'При начале схемы на Y=29: пол катакомб Y=37, верхняя крипта Y=60, вход со двора Y=72.', font=small, fill=SUBTEXT)
    canvas.save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=b.OUTPUT.with_name(b.OUTPUT.stem + '-map.png'))
    args = parser.parse_args()
    draw_map(b.build_site(), args.output)


if __name__ == '__main__':
    main()
