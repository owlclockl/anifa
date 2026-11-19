#!/usr/bin/env python3
"""Render annotated 3D plates from the exported universal warehouse.

Requires the Java 26.3 assets/minecraft directory (not the server JAR), a C
compiler for the CPU renderer, and the repository's Python requirements.
"""
from __future__ import annotations

import argparse
import math
from functools import cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

from . import build_universal_store as u
from . import catacomb_logistics as l
from .voxel_render import Camera, Scene, rasterizer

W, H = 2200, 1540
LEFT, RIGHT = (54, 229, 1594, 1425), (1621, 229, 2146, 1425)
FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')
BG, PANEL, EDGE = '#101a24', '#172532', '#314653'
INK, MUTED, DIM = '#eef4ee', '#adc1cd', '#85a1af'
AQUA, COPPER, BLUE, RED, GOLD = '#79e2cc', '#ffb887', '#8fcaff', '#ff9c91', '#f3d279'


class Plate:
    def __init__(self, fonts, index, title, subtitle, metric, metric_note):
        self.fonts = fonts
        self.image = Image.new('RGB', (W, H), BG)
        self.d = ImageDraw.Draw(self.image)
        self.d.line((55, 203, W-55, 203), fill=EDGE, width=2)
        self.d.rounded_rectangle((54, 48, 58, 181), radius=2, fill=AQUA)
        self.track((77, 46), f'MOONSPIRE   /   ВИЗУАЛИЗАЦИЯ {index} ИЗ 03', color=AQUA)
        self.text((72, 71), title, 70, mode='serif')
        self.text((77, 154), subtitle, 25, color=MUTED)
        self.text((2144, 75), metric, 49, mode='mono', anchor='ra')
        self.text((2142, 141), metric_note, 19, color=MUTED, mode='mono', anchor='ra')

    @cache
    def font(self, size, mode):
        fn = {'normal': 'DejaVuSans', 'bold': 'DejaVuSans-Bold', 'serif': 'DejaVuSerif', 'mono': 'DejaVuSansMono'}[mode]
        return ImageFont.truetype(self.fonts / (fn+'.ttf'), size)

    def text(self, xy, body, size=22, *, color=INK, mode='normal', anchor=None, spacing=8):
        self.d.multiline_text(xy, body, font=self.font(size, mode), fill=color, anchor=anchor, spacing=spacing)

    def track(self, xy, body, *, color=DIM, size=17):
        x, y = xy
        f = self.font(size, 'bold')
        for char in body:
            self.d.text((x, y), char, font=f, fill=color)
            x += f.getlength(char) + 1.4

    def panel(self, rect):
        self.d.rounded_rectangle(rect, radius=18, fill=PANEL, outline=EDGE, width=2)

    def rule(self, y, x1=1653, x2=2114):
        self.d.line((x1, y, x2, y), fill=EDGE, width=2)

    def badge(self, point, key, tone, *, capsule=False):
        x, y = point
        r = 20
        width = (self.font(19, 'bold').getlength(key)+22)/2 if capsule else r
        self.d.rounded_rectangle((x-width-2, y-r-2, x+width+2, y+r+2), radius=r, fill=BG)
        self.d.rounded_rectangle((x-width, y-r, x+width, y+r), radius=r, fill=tone)
        self.text((x, y), key, 19, color=BG, mode='bold', anchor='mm')

    def leader(self, camera, pos, delta, key, tone):
        x, y, _ = camera.project(pos)
        dx, dy = delta
        # Route round the point with a short horizontal tail into the badge.
        end = (x+dx, y+dy)
        elbow = (end[0]-math.copysign(26, dx), end[1])
        coords = [(float(x), float(y)), elbow, end]
        self.d.line(coords, fill='#121d29', width=7, joint='curve')
        self.d.line(coords, fill=tone, width=2, joint='curve')
        self.d.ellipse((x-6, y-6, x+6, y+6), fill=BG)
        self.d.ellipse((x-4, y-4, x+4, y+4), fill=tone)
        self.badge(end, key, tone, capsule=len(key)>2)

    def tag(self, xy, label):
        x, y = xy
        font = self.font(17, 'mono')
        width = font.getlength(label)+25
        self.d.rounded_rectangle((x-width, y, x, y+32), radius=6, fill='#13232e', outline=EDGE)
        self.text((x-12, y+16), label, 17, color=MUTED, mode='mono', anchor='rm')

    def axes(self, camera, origin):
        x, y = origin
        self.d.ellipse((x-3, y-3, x+3, y+3), fill=MUTED)
        for i, name, tone in [(0, 'X', COPPER), (1, 'Y', AQUA), (2, 'Z', BLUE)]:
            dx, dy = camera.matrix[:2, i]*47
            dest = (x+dx, y+dy)
            self.d.line((origin, dest), fill=tone, width=2)
            self.d.ellipse((dest[0]-3, dest[1]-3, dest[0]+3, dest[1]+3), fill=tone)
            length = math.hypot(dx, dy)
            self.text((dest[0]+13*dx/length, dest[1]+13*dy/length), name, 16, color=tone, mode='mono', anchor='mm')

    def footer(self, left, right):
        self.d.line((55, 1454, 2145, 1454), fill=EDGE, width=2)
        self.text((55, 1481), left, 20, color=MUTED)
        self.text((2144, 1481), right, 20, color=DIM, mode='mono', anchor='ra')

    def save(self, path):
        self.image.save(path, quality=95, subsampling=0, optimize=True)


def viewport(plate, rect, mesh, raster, angle, pad, *, grid=None, antialias=2):
    x0, y0, x1, y1 = rect
    w, h = x1-x0, y1-y0
    lft, top, rgt, bot = pad
    cam = Camera.fit(*angle, mesh.xyz.reshape(-1, 3), (lft, top, w-rgt, h-bot))
    yy, xx = np.ogrid[:h, :w]
    glow = np.exp(-2.4*((xx/w-.49)**2/.56 + (yy/h-.37)**2/.60))
    dark = np.array(ImageColor.getrgb('#14212c'))
    lit = np.array(ImageColor.getrgb('#2a4351'))
    pixels = (dark + glow[:, :, None]*(lit-dark)).astype(np.uint8)
    im = Image.fromarray(pixels, 'RGB')
    if grid is not None:
        gx, gy, gz, tx, tz = grid
        floor = lambda x, z: tuple(cam.project((x, gy, z))[:2])
        d = ImageDraw.Draw(im)
        lines = [(floor(x, gz), floor(x, tz)) for x in range(math.ceil(gx/4)*4, tx, 4)]
        lines += [(floor(gx, z), floor(tx, z)) for z in range(math.ceil(gz/4)*4, tz, 4)]
        for a, b in lines:
            d.line((a, b), fill='#2b414d')
        outline = [floor(gx, gz), floor(gx, tz), floor(tx, tz), floor(tx, gz), floor(gx, gz)]
        d.line(outline, fill='#3b5460', width=1)
        # Shadow of the horizontal block footprint, beneath the projected model.
        shadow = Image.new('L', (w, h))
        d = ImageDraw.Draw(shadow)
        footprint = set(map(tuple, np.floor(mesh.xyz.mean(axis=1)[:, [0, 2]]).astype(int)))
        for x, z in footprint:
            d.polygon([floor(x+.1, z+.15), floor(x+1.15, z+.15),
                       floor(x+1.15, z+1.22), floor(x+.1, z+1.22)], fill=76)
        im.paste('#050b13', mask=shadow.filter(ImageFilter.GaussianBlur(13)))
    big_camera = Camera(cam.origin*antialias, cam.factor*antialias, cam.matrix)
    layer = mesh.image(raster, big_camera, (w*antialias, h*antialias))
    layer = layer.resize((w, h), Image.Resampling.LANCZOS)
    im.paste(layer, (0, 0), layer)
    stencil = Image.new('L', (w, h))
    ImageDraw.Draw(stencil).rounded_rectangle((0, 0, w-1, h-1), radius=18, fill=255)
    plate.image.paste(im, (x0, y0), stencil)
    plate.d.rounded_rectangle((x0, y0, x1-1, y1-1), radius=18, outline=EDGE, width=2)
    return Camera(cam.origin+(x0, y0), cam.factor, cam.matrix)


def center(p, y=.5, z=.5):
    return p[0]+.5, p[1]+y, p[2]+z


def overview(scene, raster, output, fonts):
    plate = Plate(fonts, '01', 'Кладовая хранителей', 'Универсальный автосклад · полный вид с юго-востока',
                  ' × '.join(map(str, scene.occupancy)), 'X × Y × Z   /   JAVA 26.3')
    camera = viewport(plate, LEFT, scene.mesh(), raster, (29, 25), (120, 127, 126, 80),
                      grid=(-2, -.12, -2, 39, 40))
    plate.track((83, 257), '01  /  ОБЩИЙ ВИД')
    plate.tag((1561, 253), 'ВСЕ БЛОКИ СХЕМЫ')
    plate.axes(camera, (164, 1297))
    points = [
        ('01', center(u.INTAKE[0], .6, .97), (-122, 78), COPPER),
        ('02', center(u.WATER_PORT, .89), (-135, -60), BLUE),
        ('03', center(l.step(u.BOX_INPUTS[0], 'up'), .98), (-19, -75), GOLD),
        ('03', center(l.step(u.BOX_INPUTS[1], 'up'), .98), (66, -54), GOLD),
        ('04', center(u.RAW_INPUT, .96), (-101, -40), COPPER),
        ('05', center(u.PRESSES[4].origin, .76, .95), (186, 38), RED),
        ('06', center(u.CELLS[3].cabinets[2].far, .82), (155, 12), AQUA),
    ]
    for key, coord, offset, tone in points:
        plate.leader(camera, coord, offset, key, tone)
    plate.panel(RIGHT)
    plate.track((1653, 260), 'ПРИЁМКА → ХРАНЕНИЕ', color=AQUA)
    plate.text((1651, 296), 'Узлы склада', 36, mode='bold')
    legend = [
        ('01', COPPER, 'Общая приёмка', 'Сундук для предметов россыпью.'),
        ('02', BLUE, 'Водный ввод', 'Жёлоб подаёт предметы\nв тот же сундук.'),
        ('03', GOLD, 'Два разгрузчика', 'Каждый принимает шалкеры.\nПустые идут в сундук «Шалкеры».'),
        ('04', COPPER, 'Вход автоупаковки', 'Бочка для сырья: слитков,\nбулыжника и других ресурсов.'),
        ('05', RED, 'Два яруса сборки', '20 рецептов 9 → 1. Продукты\nуходят в общую сортировку.'),
        ('06', AQUA, 'Секции хранения', 'Семь секций спускаются\nк двум бочкам переполнения.'),
    ]
    for j, (key, tone, title, description) in enumerate(legend):
        y = 365+j*148
        plate.rule(y)
        plate.badge((1675, y+47), key, tone)
        plate.text((1711, y+23), title, 27, mode='bold')
        plate.text((1711, y+63), description, 21, color=MUTED, spacing=7)
    plate.rule(1253)
    plate.text((1653, 1291), 'Нижние секции и бочки видны\nкрупнее на листе 02.', 22, color=AQUA, spacing=9)
    plate.footer('Блоки: ' + f'{len(scene.blocks):,}'.replace(',', '\u202f') + '  ·  53 категории  ·  56 медных големов',
                 'ИСТОЧНИК: MOONSPIRE-UNIVERSAL-STORE.LITEMATIC')
    plate.save(output / 'moonspire-universal-store-3d.jpg')


def storage_mask(scene):
    selected = set(u.storage().wire_states())
    for cell in u.CELLS:
        x, y, z = cell.center
        lx, _, lz = cell.ladder
        for p, (name, _) in scene.blocks.items():
            a, b, c = p
            if abs(a-x) <= 3 and z-4 <= c <= z+2:
                if b == y-1 or b == y and name.endswith('_sign'):
                    selected.add(p)
            if a == lx and 0 <= b <= y and lz-1 <= c <= lz:
                if name in {'chiseled_tuff_bricks', 'ladder'}:
                    selected.add(p)
    selected.update(p for p in scene.blocks if p[1] == 0 and p[2] >= 14)
    selected.add(l.step(u.OVERFLOW[-1], 'south'))
    return selected


def sections(scene, raster, output, fonts):
    plate = Plate(fonts, '02', 'Секции хранения', 'Северо-восточный ракурс · приёмка и верхние механизмы скрыты',
                  '07 / 53', 'СЕКЦИЙ   /   ДВОЙНЫХ СУНДУКОВ')
    mesh = scene.mesh(storage_mask(scene).__contains__)
    camera = viewport(plate, LEFT, mesh, raster, (151, 43), (80, 154, 71, 100), grid=(-1, -.12, 12, 36, 36))
    plate.track((83, 257), '02  /  СОРТИРОВКА')
    plate.tag((1561, 253), 'РАСПОЛОЖЕНИЕ БЛОКОВ СОХРАНЕНО')
    plate.axes(camera, (172, 1299))
    offsets = [(83, -72), (19, -88), (-31, -84), (-103, -48), (-113, 10), (-39, 103), (103, 42)]
    for i, (cell, delta) in enumerate(zip(u.CELLS, offsets, strict=True), 1):
        plate.leader(camera, center(cell.center, 2.93), delta, str(i), AQUA)
    plate.leader(camera, center(u.OVERFLOW[-1], .65, .94), (81, 128), '!', RED)
    plate.panel(RIGHT)
    plate.track((1653, 260), 'МАРШРУТ ПРЕДМЕТОВ', color=AQUA)
    plate.text((1651, 296), 'Секции 1 → 7', 36, mode='bold')
    plate.text((1654, 377), 'Секция', 20, color=DIM)
    plate.text((1940, 377), 'Y рельса', 20, color=DIM, anchor='ra')
    plate.text((2113, 377), 'Сундуки', 20, color=DIM, anchor='ra')
    for i, cell in enumerate(u.CELLS, 1):
        y = 411+(i-1)*83
        plate.rule(y)
        plate.badge((1675, y+41), str(i), AQUA)
        plate.text((1940, y+29), f'{cell.center[1]:02}', 22, color=INK, mode='mono', anchor='ra')
        plate.text((2113, y+29), str(len(cell.cabinets)), 22, color=INK, mode='mono', anchor='ra')
    plate.rule(998)
    plate.badge((1675, 1050), '!', RED)
    plate.text((1710, 1029), 'Переполнение', 27, mode='bold')
    plate.text((1653, 1093), 'Две бочки на Y=2. Лампы\nпоказывают, что в бочках\nостались предметы.', 23, color=MUTED, spacing=8)
    plate.rule(1214)
    plate.text((1653, 1251), 'В каждой секции 8 големов\nстоят в одной точке, поэтому\nих модели на виде совпадают.', 21, color=MUTED, spacing=8)
    plate.footer('Показаны секции, соединительные воронки и площадки доступа.', 'Y СЧИТАЕТСЯ ОТ НИЗА СХЕМЫ')
    plate.save(output / 'moonspire-universal-store-sections.jpg')


def machinery(scene, raster, output, fonts):
    plate = Plate(fonts, '03', 'Автосборка и разгрузка', 'Крупный план механизмов · секции хранения скрыты',
                  '20 / 2', 'СБОРЩИКОВ   /   РАЗГРУЗЧИКА')
    press_positions = set(u.compaction().wire_states())
    for press in u.PRESSES:
        press_positions.update(press.layout().wire_states())
    press_positions.update(p for p in scene.blocks if p[0] <= 4 and p[1] >= 28 and p[2] <= 6)
    presses = scene.mesh(press_positions.__contains__)
    cam = viewport(plate, LEFT, presses, raster, (38, 23), (100, 164, 102, 220), grid=(-1, 16.84, 0, 38, 28))
    plate.track((83, 257), '03A  /  БЛОК АВТОСБОРКИ')
    plate.tag((1561, 253), 'ДВА ЯРУСА · ПО 10 СБОРЩИКОВ')
    plate.leader(cam, center(u.RAW_INPUT, .97), (-124, -30), 'ВХОД', COPPER)
    top, bottom = u.PRESSES[9], u.PRESSES[19]
    plate.leader(cam, center(top.origin, .64, 1), (101, -57), 'Y=25', GOLD)
    plate.leader(cam, center(bottom.origin, .64, 1), (122, 56), 'Y=19', BLUE)
    plate.axes(cam, (166, 1298))
    plate.track((286, 1243), 'СЫРЬЁ → СБОРЩИКИ → СОРТИРОВКА', color=AQUA)
    plate.text((286, 1283), 'Из 9 единиц сырья сборщик делает один предмет. Продукты идут\nв общую приёмку, минуя остальные фильтры автоупаковки.', 23, color=MUTED, spacing=9)

    unit = u.UNLOADERS[0]
    box_barrel = l.step(u.BOX_INPUTS[0], 'up')
    unloader_positions = set(unit.layout().wire_states()) | {box_barrel, u.BOX_INPUTS[0]}
    example = scene.mesh(unloader_positions.__contains__)
    plate.panel(RIGHT)
    plate.track((1653, 260), '03B  /  РАЗГРУЗЧИК')
    plate.text((1651, 296), 'Узел шалкеров', 35, mode='bold')
    zoom = viewport(plate, (1645, 378, 2122, 923), example, raster, (30, 33), (22, 62, 21, 49))
    plate.leader(zoom, center(box_barrel, 1), (-62, -55), '1', GOLD)
    plate.leader(zoom, center(unit.origin, .51, .37), (72, -26), '2', RED)
    plate.leader(zoom, center(unit.drain, .63, .87), (52, 75), '3', AQUA)
    rows = [
        ('1', GOLD, 'Входная бочка для шалкеров'),
        ('2', RED, 'Камера с поршнем'),
        ('3', AQUA, 'Воронка в общую приёмку'),
    ]
    for i, (key, tone, title) in enumerate(rows):
        y = 956+i*80
        plate.badge((1673, y+20), key, tone)
        plate.text((1706, y+8), title, 22, mode='bold')
        plate.rule(y+62)
    plate.text((1653, 1222), 'На общем виде таких узлов два.\nВ каждом пустой шалкер идёт\nвместе с содержимым\nна сортировку.', 22, color=MUTED, spacing=8)
    plate.footer('Механизмы показаны в сохранённом состоянии, без проигрывания сигналов.', 'JAVA 26.3   /   СТАТИЧЕСКИЙ ВИД')
    plate.save(output / 'moonspire-universal-store-machines.jpg')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assets', type=Path, help='Path to the extracted Java 26.3 assets/minecraft directory')
    parser.add_argument('--output-dir', type=Path, default=u.OUTPUT.parent)
    parser.add_argument('--fonts', type=Path, default=FONT_DIR)
    opts = parser.parse_args()
    opts.output_dir.mkdir(parents=True, exist_ok=True)
    scene = Scene(u.OUTPUT, opts.assets, opts.fonts / 'DejaVuSans.ttf')
    raster = rasterizer()
    for draw in (overview, sections, machinery):
        draw(scene, raster, opts.output_dir, opts.fonts)


if __name__ == '__main__':
    main()
