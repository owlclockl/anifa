#!/usr/bin/env python3
"""Loop a 3D orbit of the exported warehouse, with a sorting-layer cutaway."""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont

from . import build_universal_store as u
from . import catacomb_logistics as l
from .render_universal_store import (
    AQUA, BG, BLUE, COPPER, DIM, EDGE, FONT_DIR, GOLD, INK, MUTED, PANEL, RED, center, storage_mask,
)
from .voxel_render import Camera, Scene, rasterizer

W, H = 1160, 824
VIEW = (28, 125, 844, 759)
VX, VY, VW, VH = VIEW[0], VIEW[1], VIEW[2]-VIEW[0], VIEW[3]-VIEW[1]
SIDE = (860, 125, 1132, 759)
START, CUT = 29, 151
OUTPUT = u.OUTPUT.with_name('moonspire-universal-store-tour.gif')


@dataclass(frozen=True)
class Shot:
    yaw: float
    reveal: float = 0
    stage: int = -1  # 0–6 sorters, 7 overflow; -1 has no moving cue
    hop: float = 0
    ms: int = 80


def smooth(t):
    return t*t*(3-2*t)


def sweep(start, end, count, opening=False):
    # Uniform speed through most of the orbit, with short easing at each end.
    eps = 0.13
    t = np.linspace(0, 1, count+1)
    profile = np.clip(np.minimum(t, 1-t)/eps, 0, 1)
    step = (profile[:-1]+profile[1:])/2
    angles = start+(end-start)*np.r_[0., step.cumsum()/step.sum()]
    result = [Shot(float(a)) for a in angles[:-1]]
    if opening:
        result[0] = Shot(START, ms=950)
    return result


def timeline():
    yield from sweep(START, CUT, 53, opening=True)
    for i in range(1, 9):
        yield Shot(CUT, reveal=smooth(i/8))
    yield Shot(CUT, reveal=1, ms=550)
    for stage in range(7):
        for tick in range(8):
            yield Shot(CUT, reveal=1, stage=stage, hop=tick/7, ms=100)
    yield Shot(CUT, reveal=1, stage=7, ms=960)
    for i in range(7, 0, -1):
        yield Shot(CUT, reveal=smooth(i/8))
    yield from sweep(CUT, START+360, 88)


def route_segments(scene):
    """Follow one real hopper branch from each relay to its next destination."""
    segments = []
    for i, cell in enumerate(u.CELLS):
        relay = cell.relay[0]
        route = [cell.inputs[0], cell.center, relay]
        dest = u.CELLS[i+1].inputs[0] if i+1 < len(u.CELLS) else u.OVERFLOW[0]
        end = relay
        direction = 'down'  # Hopper directly under the relay chest pulls from it.
        while end != dest:
            end = l.step(end, direction)
            if end in route:
                raise ValueError(f'Loop after relay {relay}')
            route.append(end)
            if end == dest:
                break
            name, props = scene.blocks[end]
            if name != 'hopper':
                raise ValueError(f'{end} is {name}, not a hopper en route to {dest}')
            direction = props['facing']
        points = np.array([center(p, .84) for p in route])
        length = np.r_[0., np.linalg.norm(np.diff(points, axis=0), axis=1).cumsum()]
        samples = np.linspace(0, length[-1], 250)
        segments.append(np.column_stack([np.interp(samples, length, points[:, a]) for a in range(3)]))
    return segments


def text(draw, xy, body, font, color=INK, anchor=None):
    draw.text(xy, body, font=font, fill=color, anchor=anchor)


class Tour:
    def __init__(self, scene, fonts, shots):
        self.fonts = fonts
        self.scene = scene
        self.full = scene.mesh()
        self.cut = scene.mesh(storage_mask(scene).__contains__)
        self.raster = rasterizer()
        self.trace = route_segments(scene)
        self.cut_vertices = np.unique(self.cut.xyz.reshape(-1, 3), axis=0)
        self.full_vertices = np.unique(self.full.xyz.reshape(-1, 3), axis=0)
        self.fit_area = (39, 62, VW-39, VH-51)
        # Keep the scale fixed throughout the full orbit to avoid zoom wobble.
        self.orbit_scale = min(self.fit(s.yaw, self.orbit_pitch(s.yaw)).factor for s in shots if not s.reveal)
        y, x = np.ogrid[:VH, :VW]
        # Ordered, static dithering softens banding without making the GIF flicker.
        bayer = np.array(((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5)))/16
        profile = np.exp(-3.0*((x/VW-.49)**2/.60+(y/VH-.40)**2/.58))
        glow = np.floor(19*profile+bayer[y%4, x%4])/19
        dark, light = np.array(ImageColor.getrgb('#16232e')), np.array(ImageColor.getrgb('#273d4c'))
        self.background = Image.fromarray(np.rint(dark+glow[..., None]*(light-dark)).astype(np.uint8))
        self.stencil = Image.new('L', (VW, VH))
        ImageDraw.Draw(self.stencil).rounded_rectangle((0, 0, VW-1, VH-1), radius=12, fill=255)
        self.chrome = self.static()

    @cache
    def font(self, size, mode='normal'):
        filename = {'normal': 'DejaVuSans', 'bold': 'DejaVuSans-Bold', 'serif': 'DejaVuSerif', 'mono': 'DejaVuSansMono'}[mode]
        return ImageFont.truetype(self.fonts / (filename+'.ttf'), size)

    def label(self, draw, xy, body, size, color=INK, mode='normal', anchor=None):
        text(draw, xy, body, self.font(size, mode), color, anchor)

    @staticmethod
    def orbit_pitch(yaw):
        return 25+7*(1-math.cos(math.radians(yaw-START)))/2

    def fit(self, yaw, pitch):
        return Camera.fit(yaw, pitch, self.full_vertices, self.fit_area)

    def camera(self, yaw, reveal=0):
        # Let the upper decks fade before zooming into the lower model.
        zoom = reveal**2.3
        pitch = (1-zoom)*self.orbit_pitch(yaw)+zoom*43
        if reveal < 1:
            full = self.fit(yaw, pitch)
            pivot = (np.array(self.fit_area[:2])+self.fit_area[2:])/2
            offset = pivot+(full.origin-pivot)*self.orbit_scale/full.factor
            if reveal == 0:
                return Camera(offset, self.orbit_scale, full.matrix)
        cut = Camera.fit(yaw, pitch, self.cut_vertices, (35, 78, VW-35, VH-58))
        if reveal == 1:
            return cut
        return Camera((1-zoom)*offset+zoom*cut.origin,
                      (1-zoom)*self.orbit_scale+zoom*cut.factor, cut.matrix)

    def static(self):
        im = Image.new('RGB', (W, H), BG)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((28, 20, 31, 100), radius=2, fill=AQUA)
        self.label(d, (42, 18), 'MOONSPIRE   /   3D-ОБЛЁТ', 13, AQUA, 'bold')
        self.label(d, (40, 31), 'Кладовая хранителей', 42, mode='serif')
        self.label(d, (43, 82), 'Универсальный автосклад · Minecraft Java 26.3', 16, MUTED)
        self.label(d, (1131, 35), ' × '.join(map(str, self.scene.occupancy)), 29, mode='mono', anchor='ra')
        self.label(d, (1130, 82), 'X × Y × Z  /  БЛОКОВ', 13, MUTED, 'mono', 'ra')
        d.line((28, 110, 1132, 110), fill=EDGE)
        d.line((28, 778, 1132, 778), fill=EDGE)
        self.label(d, (29, 795), '3 951 блок  ·  56 медных големов', 14, MUTED)
        self.label(d, (1132, 796), 'ПРЯМО ИЗ .LITEMATIC', 13, DIM, 'mono', 'ra')
        return im

    def badge(self, draw, xy, value, color, active=True):
        x, y = xy
        r = 11
        rx = max(r, math.ceil(self.font(12, 'bold').getlength(value)/2+6))
        draw.rounded_rectangle((x-rx-1, y-r-1, x+rx+1, y+r+1), radius=r+1, fill=BG)
        draw.rounded_rectangle((x-rx, y-r, x+rx, y+r), radius=r, fill=color if active else PANEL,
                               outline=None if active else color)
        self.label(draw, (x, y), value, 12, BG if active else color, 'bold', 'mm')

    def rule(self, draw, y):
        draw.line((879, y, 1113, y), fill=EDGE)

    def sidebar(self, draw, shot):
        draw.rounded_rectangle(SIDE, radius=12, fill=PANEL, outline=EDGE)
        is_cut = shot.reveal >= .52
        self.label(draw, (879, 146), '02  /  СРЕЗ СЕКЦИЙ' if is_cut else '01  /  ОБЩИЙ ВИД', 13, AQUA, 'bold')
        self.label(draw, (878, 170), 'Путь предметов' if is_cut else 'Входы склада', 26, mode='bold')
        self.rule(draw, 215)
        if is_cut:
            self.label(draw, (880, 232), 'Груз без подходящего сундука\nидёт дальше по секциям.', 14, MUTED)
            self.label(draw, (880, 294), 'Секция', 13, DIM)
            self.label(draw, (1001, 294), 'Y рельса', 13, DIM, anchor='ra')
            self.label(draw, (1112, 294), 'Сундуки', 13, DIM, anchor='ra')
            for i, cell in enumerate(u.CELLS):
                y = 318+40*i
                self.rule(draw, y)
                if shot.stage == i:
                    draw.rounded_rectangle((872, y+3, 1120, y+38), radius=6, fill='#234744')
                self.badge(draw, (893, y+20), str(i+1), AQUA, shot.stage >= i)
                self.label(draw, (1001, y+11), str(cell.center[1]), 15, AQUA if shot.stage == i else INK, 'mono', 'ra')
                self.label(draw, (1112, y+11), str(len(cell.cabinets)), 15, MUTED, 'mono', 'ra')
            self.rule(draw, 598)
            if shot.stage == 7:
                draw.rounded_rectangle((872, 602, 1120, 674), radius=6, fill='#463238')
            self.badge(draw, (893, 626), '!', RED, shot.stage == 7)
            self.label(draw, (915, 614), 'Переполнение', 16, mode='bold')
            self.label(draw, (915, 643), 'Две бочки на Y=2', 14, MUTED)
            self.rule(draw, 686)
            self.label(draw, (880, 703), 'Подсветка показывает маршрут,\nа не скорость работы.', 13, DIM)
        else:
            cells = [('A', COPPER, 'Общая приёмка', 'Предметы россыпью'),
                     ('B', BLUE, 'Водный ввод', 'Вещи из водного потока'),
                     ('C', GOLD, 'Два разгрузчика', 'Коробки с предметами'),
                     ('D', COPPER, 'Вход упаковки', 'Сырьё для автосборки')]
            for i, (mark, tone, title, desc) in enumerate(cells):
                y = 224+i*78
                self.badge(draw, (893, y+23), mark, tone)
                self.label(draw, (915, y+8), title, 16, mode='bold')
                self.label(draw, (915, y+36), desc, 13, MUTED)
                self.rule(draw, y+69)
            self.label(draw, (880, 555), '20 сборщиков', 20, RED, 'bold')
            self.label(draw, (880, 586), 'Два яруса · рецепты 9 → 1', 14, MUTED)
            self.rule(draw, 625)
            self.label(draw, (880, 648), '7 секций хранения', 20, AQUA, 'bold')
            self.label(draw, (880, 679), '53 двойных сундука', 14, MUTED)
            self.label(draw, (880, 711), 'Переполнение внизу схемы', 13, DIM)

    def leader(self, draw, cam, pos, delta, label, color, active=True):
        x, y = cam.project(pos)[:2]+(VX, VY)
        end = (x+delta[0], y+delta[1])
        elbow = (end[0]-math.copysign(13, delta[0]), end[1])
        draw.line(((x, y), elbow, end), fill=BG, width=4)
        draw.line(((x, y), elbow, end), fill=color, width=1)
        draw.ellipse((x-3, y-3, x+3, y+3), fill=color, outline=BG)
        self.badge(draw, end, label, color, active)

    def inlets(self, im, cam, yaw):
        rel = abs((yaw-START+180)%360-180)
        alpha = 1-smooth(np.clip((rel-3)/13, 0, 1))
        if alpha <= 0:
            return im
        dst = im if alpha >= 1 else im.copy()
        d = ImageDraw.Draw(dst)
        self.leader(d, cam, center(u.INTAKE[0], .61, .97), (-68, 41), 'A', COPPER)
        self.leader(d, cam, center(u.WATER_PORT, .89), (-66, -32), 'B', BLUE)
        self.leader(d, cam, center(l.step(u.BOX_INPUTS[0], 'up'), .98), (-17, -43), 'C1', GOLD)
        self.leader(d, cam, center(l.step(u.BOX_INPUTS[1], 'up'), .98), (43, -37), 'C2', GOLD)
        self.leader(d, cam, center(u.RAW_INPUT, .97), (-62, -29), 'D', COPPER)
        return Image.blend(im, dst, alpha) if alpha < 1 else dst

    def flows(self, draw, cam, shot):
        if 0 <= shot.stage < len(self.trace):
            path = cam.project(self.trace[shot.stage])[:, :2]+(VX, VY)
            trail = [tuple(p) for p in path[::4]]
            draw.line(trail, fill='#142631', width=4)
            draw.line(trail, fill='#71bfae', width=1)
            idx = round(shot.hop*(len(path)-1))
            active = [tuple(p) for p in path[max(0, idx-28):idx+1:2]]
            if len(active) > 1:
                draw.line(active, fill=AQUA, width=3)
            x, y = path[idx]
            draw.ellipse((x-5, y-5, x+5, y+5), fill=AQUA, outline=BG, width=2)
            draw.ellipse((x-2, y-2, x+2, y+2), fill=INK)
        offsets = [(48, -39), (12, -49), (-18, -49), (-58, -27), (-63, 3), (-25, 57), (59, 20)]
        for i, (cell, offset) in enumerate(zip(u.CELLS, offsets, strict=True)):
            self.leader(draw, cam, center(cell.center, 2.93), offset, str(i+1), AQUA, active=shot.stage >= i)
        self.leader(draw, cam, center(u.OVERFLOW[0], .65, .94), (46, 70), '!', RED, active=shot.stage == 7)

    def backdrop(self, cam):
        im = self.background.copy()
        d = ImageDraw.Draw(im)
        def pt(x, z):
            return tuple(cam.project((x, -.12, z))[:2])
        for x in range(0, 41, 4):
            d.line((pt(x, 0), pt(x, 40)), fill='#2b414e')
        for z in range(0, 41, 4):
            d.line((pt(0, z), pt(40, z)), fill='#2b414e')
        d.line((pt(0, 0), pt(0, 40), pt(40, 40), pt(40, 0), pt(0, 0)), fill='#3b5460')
        return im

    @lru_cache(maxsize=12)
    def model_frame(self, yaw, reveal):
        cam = self.camera(yaw, reveal)
        backdrop = self.backdrop(cam)
        big = Camera(cam.origin*2, cam.factor*2, cam.matrix)
        def painted(mesh):
            layer = mesh.image(self.raster, big, (VW*2, VH*2)).resize((VW, VH), Image.Resampling.LANCZOS)
            view = backdrop.copy()
            view.paste(layer, mask=layer)
            return view
        if reveal == 0:
            return painted(self.full)
        if reveal == 1:
            return painted(self.cut)
        return Image.blend(painted(self.full), painted(self.cut), reveal)

    def frame(self, shot):
        im = self.chrome.copy()
        cam = self.camera(shot.yaw, shot.reveal)
        im.paste(self.model_frame(shot.yaw, shot.reveal), (VX, VY), self.stencil)
        if not shot.reveal:
            im = self.inlets(im, cam, shot.yaw)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle(VIEW, radius=12, outline=EDGE)
        cut = shot.reveal >= .52
        self.label(d, (45, 143), 'СОРТИРОВКА  /  ВЕРХНИЕ УЗЛЫ СКРЫТЫ' if cut else 'ОБЛЁТ  /  ПОЛНАЯ СХЕМА', 13, MUTED, 'bold')
        if shot.reveal == 1 and shot.stage >= 0:
            self.flows(d, cam, shot)
        self.sidebar(d, shot)
        return im


def palette_for(tour, shots):
    sample = Image.new('RGB', (388*4, 272*4))
    picks = [shots[i] for i in np.linspace(0, len(shots)-1, 16, dtype=int)]
    for i, shot in enumerate(picks):
        image = tour.frame(shot)
        sample.paste(image.resize((388, 272), Image.Resampling.LANCZOS), ((i%4)*388, (i//4)*272))
    # Reserve the exact accent colours and one unused index for GIF delta pixels.
    accents = (BG, PANEL, EDGE, INK, MUTED, DIM, AQUA, BLUE, COPPER, RED, GOLD,
               '#234744', '#463238', '#2b414e', '#3b5460', '#142631', '#71bfae')
    swatches = 255-len(accents)
    colors = sample.quantize(colors=swatches, method=Image.Quantize.MEDIANCUT).getpalette()[:swatches*3]
    colors += [c for color in accents for c in ImageColor.getrgb(color)] + [255, 0, 255]
    palette = Image.new('P', (1, 1))
    palette.putpalette(colors)
    return palette


def animate(scene, fonts, output):
    shots = list(timeline())
    tour = Tour(scene, fonts, shots)
    palette = palette_for(tour, shots)
    frames = []
    for i, shot in enumerate(shots, 1):
        frames.append(tour.frame(shot).quantize(palette=palette, dither=Image.Dither.NONE))
        if i % 50 == 0:
            print(f'Rendered {i}/{len(shots)} frames', flush=True)
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=[s.ms for s in shots],
                   loop=0, disposal=1, optimize=True, palette=bytes(palette.getpalette()), interlace=False)
    with Image.open(output) as encoded:
        n_frames = encoded.n_frames  # Pillow merges consecutive identical frames.
    print(f'{output}: {n_frames} frames, {sum(s.ms for s in shots)/1000:.2f} s, {output.stat().st_size:,} bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assets', type=Path, help='Extracted Java 26.3 assets/minecraft directory')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--fonts', type=Path, default=FONT_DIR)
    opts = parser.parse_args()
    scene = Scene(u.OUTPUT, opts.assets, opts.fonts / 'DejaVuSans.ttf')
    animate(scene, opts.fonts, opts.output)


if __name__ == '__main__':
    main()
