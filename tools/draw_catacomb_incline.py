#!/usr/bin/env python3
"""Side elevation and operating card for the Keepers' Incline (no game capture)."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import build_catacomb_cathedral as b, catacomb_funicular as f

BG, PANEL, GRID = '#111820', '#1b242d', '#34434d'
INK, DIM = '#f1e9dd', '#adbcc6'
COPPER, TEAL, GOLD = '#e5a16d', '#89d4c7', '#efc47e'
WIDTH, HEIGHT = 1500, 1070


def draw(output: Path) -> None:
    im = Image.new('RGB', (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(im)
    small = ImageFont.truetype('DejaVuSans.ttf', 17)
    body = ImageFont.truetype('DejaVuSans.ttf', 21)
    label = ImageFont.truetype('DejaVuSans-Bold.ttf', 23)
    title = ImageFont.truetype('DejaVuSerif.ttf', 53)
    d.rectangle((33, 29, WIDTH-34, HEIGHT-30), outline=GRID, width=2)
    d.text((80, 49), 'АББАТСТВО ЛУННЫХ ШПИЛЕЙ   /   ПЕЧАТЬ ГЛУБИН', font=small, fill=COPPER)
    d.text((78, 84), 'Перевоз ключей', font=title, fill=INK)
    d.text((942, 110), 'Продольный разрез · север слева', font=body, fill=DIM)
    d.line((79, 161, 1420, 161), fill=GRID, width=2)

    def xx(z):
        return 115 + (z - 173)*19

    def yy(y):
        return 294 + (f.TOP_Y - y)*17

    for y in (f.TOP_Y, -21, -28, f.BOTTOM_Y):
        d.line((112, yy(y), 912, yy(y)), fill=GRID)
        d.text((101, yy(y)), str(y + 72), font=small, fill=DIM, anchor='rm')
    d.text((80, 220), 'Пол Y', font=small, fill=DIM)
    # The walkway and rail share a grade but are in different lanes. Separate
    # them vertically in the drawing so both are legible.
    track = [(xx(z), yy(f.floor(z)) - 7) for z in range(f.TOP_Z, f.BOTTOM_Z + 1)]
    d.line(track, fill=COPPER, width=5, joint='curve')
    for (x, y) in track:
        d.rectangle((x-1, y-4, x+1, y+4), fill=GOLD)
    stairs = []
    for z in range(f.TOP_Z, f.BOTTOM_Z + 1):
        y = yy(f.floor(z)) + 13
        if stairs:
            stairs.append((xx(z)-5, stairs[-1][1]))
        stairs.extend(((xx(z)-5, y), (xx(z)+6, y)))
    d.line(stairs, fill=TEAL, width=3)
    for i, (z, y, name) in enumerate(((f.TOP_Z, f.TOP_Y, 'Старая крипта'),
                                      (f.BOTTOM_Z, f.BOTTOM_Y, 'Семь колоколов')), 1):
        x = xx(z)
        cy = yy(y) - (68 if i == 1 else 106)
        d.line((x, cy+20, x, yy(y)-10), fill=COPPER, width=2)
        d.ellipse((x-16, cy-16, x+16, cy+16), outline=COPPER, width=2)
        d.text((x, cy), str(i), font=body, fill=INK, anchor='mm')
        d.text((x+27 if i == 1 else x-27, cy-1), name, font=label, fill=INK,
               anchor='lm' if i == 1 else 'rm')
    for _, _, z in f.DETECTORS:
        x, y = xx(z), yy(f.floor(z)) - 7
        d.polygon(((x, y-8), (x+8, y), (x, y+8), (x-8, y)), fill=INK)
    d.line((113, 705, 149, 705), fill=COPPER, width=5)
    d.text((161, 693), f'{f.BOTTOM_Z-f.TOP_Z+1} рельсов · перепад {f.TOP_Y-f.BOTTOM_Y} блок', font=small, fill=INK)
    d.line((451, 705, 487, 705), fill=TEAL, width=4)
    d.text((499, 693), 'Пеший марш за стеклом', font=small, fill=INK)
    d.polygon(((754, 698), (761, 705), (754, 712), (747, 705)), fill=INK)
    d.text((773, 693), 'Датчик звонка', font=small, fill=INK)

    d.rounded_rectangle((944, 201, 1421, 724), radius=10, fill=PANEL, outline=GRID, width=2)
    d.text((975, 229), 'Как пользоваться', font=label, fill=INK)
    instructions = (
        ('Одна вагонетка на всю линию.', 'Поставь её на крайний рельс', 'у медного упора верхней станции.'),
        ('Вагонетка на другой станции?', 'Нажми кнопку и дождись её.', 'Лампа показывает блокировку.'),
        ('Когда лампа погаснет, садись', 'и нажми кнопку с места.', 'На станции она затормозит.'),
    )
    for i, lines in enumerate(instructions):
        y = 286 + i*137
        d.text((975, y), f'0{i+1}', font=small, fill=COPPER)
        for j, line in enumerate(lines):
            d.text((1017, y+j*29), line, font=body, fill=INK if j == 0 else DIM)

    d.line((79, 756, 1420, 756), fill=GRID, width=2)
    for i, (head, lines) in enumerate((
        ('Пуск', ('Жетон уходит во второй', 'выбрасыватель. Оба крайних', 'рельса получают короткий пуск.')),
        ('Блокировка', ('Крайние рельсы тормозят.', 'Повторный вызов отсечён;', 'два колокола отмечают проезд.')),
        ('Готовность', ('Линия задержки возвращает', 'жетон. Лампы гаснут,', 'и можно ехать обратно.')),
    )):
        x = 80 + i*463
        d.text((x, 797), head, font=label, fill=COPPER)
        for j, line in enumerate(lines):
            d.text((x, 838+j*30), line, font=body, fill=DIM)
    d.line((79, 971, 1420, 971), fill=GRID, width=2)
    d.text((80, 991), 'Высоты пола даны для начала схемы на Y=29. Лампа показывает цикл, а не фактическое местоположение вагонетки.',
           font=small, fill=DIM)
    im.save(output, optimize=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=b.OUTPUT.with_name(b.OUTPUT.stem + '-incline.png'))
    draw(p.parse_args().output)


if __name__ == '__main__':
    main()
