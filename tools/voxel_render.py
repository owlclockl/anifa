"""Small orthographic renderer for the states in the Java 26.3 warehouse.

Read geometry and textures from the vanilla resource JSON. Block entities
and the two exported entity types have their own closed/resting meshes.
This is a static preview, not a Minecraft lighting or redstone simulation.
"""
from __future__ import annotations

import ctypes as ct
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import nbtlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .vanilla_catacomb_test import unpack_region

# Corners in texture order: upper left, lower left, lower right, upper right.
CORNERS = {
    'north': (6, 4, 0, 2), 'south': (3, 1, 5, 7),
    'west': (2, 0, 1, 3), 'east': (7, 5, 4, 6),
    'up': (2, 3, 7, 6), 'down': (1, 0, 4, 5),
}
DIR = dict(north=(0, 0, -1), east=(1, 0, 0), south=(0, 0, 1), west=(-1, 0, 0),
           up=(0, 1, 0), down=(0, -1, 0))
YAW = dict(north=0, east=90, south=180, west=270)


def uvrect(uv):
    u, v, s, t = uv
    return np.array(((u, v), (u, t), (s, t), (s, v)), dtype=float)


def unit_cross(vertices):
    a = np.cross(vertices[..., 1, :] - vertices[..., 0, :], vertices[..., 3, :] - vertices[..., 0, :])
    return a / np.maximum(1e-12, np.linalg.norm(a, axis=-1, keepdims=True))


def rotation(axis, deg):
    i = 'xyz'.index(axis)
    j, k = (i+1) % 3, (i+2) % 3
    c, s = (round(v(math.radians(deg)), 12) for v in (math.cos, math.sin))
    rot = np.eye(3)
    rot[j, j] = rot[k, k] = c
    rot[j, k], rot[k, j] = -s, s
    return rot


def corners(low, high):
    return np.array([(x, y, z) for x in (low[0], high[0]) for y in (low[1], high[1])
                     for z in (low[2], high[2])])


def sample_rects(low, high):
    a, b, c = low
    x, y, z = high
    return dict(north=(16-x, 16-y, 16-a, 16-b), south=(a, 16-y, x, 16-b),
                west=(c, 16-y, z, 16-b), east=(16-z, 16-y, 16-c, 16-b),
                up=(a, c, x, z), down=(a, 16-z, x, 16-c))


@dataclass
class Face:
    xyz: np.ndarray
    uv: np.ndarray  # texel coordinates relative to the unpadded tile
    tile: str
    cull: tuple | None = None
    tint: tuple = (1, 1, 1)
    emissive: bool = False
    flat_light: bool = False


class Atlas:
    def __init__(self):
        self.tiles = {}

    def add(self, name, image, *, translucent=False):
        self.tiles[name] = image.convert('RGBA'), translucent
        return name

    def pack(self):
        # One duplicated edge pixel keeps clamped sprite UVs away from a neighbor.
        x = y = height = 0
        width = 1024
        offsets = {}
        for name, (image, _) in self.tiles.items():
            if x + image.width + 2 > width:
                x, y, height = 0, y+height, 0
            offsets[name] = x+1, y+1
            x += image.width+2
            height = max(height, image.height+2)
        pixels = np.zeros((y+height, width, 4), dtype=np.uint8)
        for name, (image, _) in self.tiles.items():
            x, y = offsets[name]
            pixels[y-1:y+image.height+1, x-1:x+image.width+1] = np.pad(
                np.asarray(image), ((1, 1), (1, 1), (0, 0)), mode='edge')
        return pixels, offsets


class Models:
    def __init__(self, assets, font):
        self.assets = assets
        self.font = font
        self.atlas = Atlas()

    @cache
    def image(self, name):
        return Image.open(self.assets / 'textures' / (name+'.png')).convert('RGBA')

    @cache
    def sprite(self, name):
        src = self.image(name)
        src = src.crop((0, 0, src.width, src.width)) if name.startswith('block/water_') else src
        if name.startswith('block/water_'):
            p = np.array(src)
            p[:, :, :3] = np.minimum(255, p[:, :, :3] * [0.41, 0.66, 0.99]).astype('uint8')
            p[:, :, 3] = 179
            src = Image.fromarray(p)
        self.atlas.add(name, src, translucent=name.startswith(('block/water_', 'block/glass')))
        return name, (src.width / 16, src.height / 16)

    @cache
    def model(self, name):
        if name == 'block/block':
            return {}, []
        data = json.loads((self.assets / 'models' / (name+'.json')).read_text())
        if parent := data.get('parent'):
            textures, shapes = self.model(parent.split(':')[-1])
        else:
            textures, shapes = {}, []
        return textures | data.get('textures', {}), data.get('elements', shapes)

    @staticmethod
    def applies(test, props):
        if 'OR' in test:
            return any(Models.applies(row, props) for row in test['OR'])
        if 'AND' in test:
            return all(Models.applies(row, props) for row in test['AND'])
        return all(props.get(k) in v.split('|') for k, v in test.items())

    @cache
    def block(self, name, properties):
        props = dict(properties)
        if name in {'chest', 'waxed_copper_chest'}:
            return self.chest(name, props)
        if name == 'water':
            top = (14 - int(props['level'])*2)/16
            mesh = self.box((0, 0, 0), (1, top, 1), self.sprite('block/water_still')[0], (0, 0, 16, 16))
            for face, direction in zip(mesh, CORNERS):
                if direction != 'up':
                    face.cull = DIR[direction]
            return mesh
        state = json.loads((self.assets / 'blockstates' / (name+'.json')).read_text())
        if 'variants' in state:
            matches = [val for key, val in state['variants'].items()
                       if not key or self.applies(dict(kv.split('=') for kv in key.split(',')), props)]
            if len(matches) != 1:
                raise ValueError(f'Unresolved state {name}: {properties}')
        else:
            matches = [m['apply'] for m in state['multipart'] if self.applies(m.get('when', {}), props)]
        faces = []
        for variant in matches:
            if isinstance(variant, list):
                variant = variant[0]  # choose a deterministic variant of randomized tiles
            textures, elements = self.model(variant['model'].split(':')[-1])
            rot = rotation('y', -variant.get('y', 0)) @ rotation('x', -variant.get('x', 0))
            for element in elements:
                lo, hi = element['from'], element['to']
                xyz = corners(lo, hi)
                if tilt := element.get('rotation'):
                    pivot = np.array(tilt['origin'])
                    axis, angle = tilt['axis'], tilt['angle']
                    xyz = (xyz-pivot) @ rotation(axis, angle).T
                    if tilt.get('rescale'):
                        xyz *= [1 if a == axis else 1/math.cos(math.radians(angle)) for a in 'xyz']
                    xyz += pivot
                xyz = ((xyz-8) @ rot.T + 8)/16
                for direct, face in element['faces'].items():
                    spec = face['texture']
                    while isinstance(spec, str) and spec.startswith('#'):
                        spec = textures[spec[1:]]
                    spec = spec['sprite'] if isinstance(spec, dict) else spec
                    tex, size = self.sprite(spec.split(':')[-1])
                    adjust = (1, 1, 1)
                    if name == 'redstone_wire' and 'tintindex' in face:
                        strength = int(props['power'])/15
                        adjust = (0.56 + 0.44*strength, 0.14 + .18*strength, .17)
                    cull = face.get('cullface')
                    if cull:
                        cull = tuple(np.rint(rot @ DIR[cull]).astype(int))
                    uv = uvrect(face.get('uv', sample_rects(lo, hi)[direct]))
                    uv = np.roll(uv, face.get('rotation', 0)//90, axis=0)*size
                    geom = xyz[list(CORNERS[direct])].copy()
                    # The white/opaque dust overlay is deliberately coplanar in
                    # the model. Give it a sub-pixel offset for deterministic depth.
                    if name == 'redstone_wire' and tex.endswith('_overlay'):
                        geom += unit_cross(geom)*.0002
                    faces.append(Face(geom, uv, tex, cull, adjust,
                                      name == 'ochre_froglight' or tex in {'block/redstone_torch', 'block/redstone_lamp_on'},
                                      element.get('shade_direction_override') == 'up'))
        if not faces:
            raise ValueError(f'No renderable geometry for {name}: {properties}')
        return faces

    def box(self, lo, hi, tile, uv, *, emit=False):
        xyz = corners(lo, hi)
        return [Face(xyz[list(idx)], uvrect(uv[side] if isinstance(uv, dict) else uv), tile, emissive=emit)
                for side, idx in CORNERS.items() if not isinstance(uv, dict) or side in uv]

    def chest(self, name, props):
        side = props['type']
        texture = 'entity/chest/' + ('normal' if name == 'chest' else 'copper')
        if side != 'single':
            texture += '_'+side
        if texture not in self.atlas.tiles:
            self.atlas.add(texture, self.image(texture))
        # Face north in the rest pose. The type is from the block's POV.
        lo, hi = (1 if side != 'right' else 0), (15 if side != 'left' else 16)
        w = hi-lo
        # Closed lid and body, using their respective strips in the entity atlas.
        uv = {'north': (14, 14, 14+w, 19), 'south': (28+w, 14, 28+2*w, 19),
              'up': (14+w, 0, 14+2*w, 14)}
        body = {'north': (14, 33, 14+w, 43), 'south': (28+w, 33, 28+2*w, 43),
                'down': (14+w, 19, 14+2*w, 33)}
        if side != 'right':
            uv['west'], body['west'] = (0, 14, 14, 19), (0, 33, 14, 43)
        if side != 'left':
            uv['east'], body['east'] = (14+w, 14, 28+w, 19), (14+w, 33, 28+w, 43)
        if side != 'single':
            # Double halves omit the interior side of the front/back strips.
            uv['south'], body['south'] = (14+2*w, 14, 14+3*w, 19), (14+2*w, 33, 14+3*w, 43)
            face_side = 'west' if side == 'left' else 'east'
            uv[face_side], body[face_side] = (w, 14, w+14, 19), (w, 33, w+14, 43)
            uv['north'], body['north'] = (0, 14, w, 19), (0, 33, w, 43)
            uv['up'], body['down'] = (w*2, 0, w*3, 14), (w*2, 19, w*3, 33)
        mesh = self.box(np.array((lo, 9, 1))/16, np.array((hi, 14, 15))/16, texture, uv)
        mesh += self.box(np.array((lo, 0, 1))/16, np.array((hi, 9, 15))/16, texture, body)
        a, b = {'left': (15, 16), 'right': (0, 1), 'single': (7, 9)}[side]
        mesh += self.box(np.array((a, 7, 0))/16, np.array((b, 11, 1))/16, texture, (1, 1, 3, 5))
        rot = rotation('y', -YAW[props['facing']])
        for face in mesh:
            face.xyz = (face.xyz-.5) @ rot.T+.5
        return mesh

    def sign(self, pos, data, name, props):
        wall = name == 'dark_oak_wall_sign'
        rot = YAW[props['facing']]-180 if wall else float(props['rotation'])*22.5
        rot = rotation('y', -rot)
        label = data['front_text']
        content = [str(m) for m in label['messages']]
        ink = {'orange': '#ffd091', 'white': '#f9eeca', 'red': '#ff9f8e', 'aqua': '#7adddf'}
        im = Image.new('RGBA', (192, 96))
        draw = ImageDraw.Draw(im)
        for i, line in enumerate(content):
            font_size = 20
            while True:
                font = ImageFont.truetype(self.font, font_size)
                if font.getlength(line) < 176 or font_size <= 10:
                    break
                font_size -= 1
            draw.text((96, 15+22*i), line, font=font, fill=ink.get(str(label['color']), '#f9eeca'), anchor='mm')
        tex = self.atlas.add('sign/'+','.join(map(str, pos)), im)
        z, lo = (1.68/16, 4.33333/16) if wall else (8.68/16, 9.33333/16)
        v = np.array([(0, lo+.5, z), (0, lo, z), (1, lo, z), (1, lo+.5, z)])
        return Face((v-.5) @ rot.T+.5, uvrect((0, 0, 192, 96)), tex, emissive=True)

    def entity(self, kind, nbt):
        mesh = []
        if kind == 'minecart':
            tile = 'entity/minecart/minecart'
            self.atlas.add(tile, self.image(tile))
            # Open metal cart: base and four side panels, no opaque top.
            for lo, hi, tex in [((-8, -1, -9), (8, 1, 9), (24, 12, 43, 27)),
                                ((-8, 1, -9), (-6, 6, 9), (1, 3, 17, 9)),
                                ((6, 1, -9), (8, 6, 9), (1, 3, 17, 9)),
                                ((-6, 1, -9), (6, 6, -7), (19, 3, 35, 9)),
                                ((-6, 1, 7), (6, 6, 9), (19, 3, 35, 9))]:
                mesh += self.box(np.array(lo)/16, np.array(hi)/16, tile, tex)
        elif kind == 'copper_golem':
            tile = 'entity/copper_golem/copper_golem'
            self.atlas.add(tile, self.image(tile))
            head = {'south': (18, 14, 26, 19), 'north': (28, 14, 36, 19),
                    'up': (17, 4, 25, 12), 'down': (25, 4, 33, 12),
                    'east': (26, 14, 34, 19), 'west': (10, 14, 18, 19)}
            for lo, hi, tex in [((-4, 5.6, -3), (4, 11.6, 3), (7, 24, 17, 31)),
                                ((-4, 11.6, -4), (4, 16.6, 4), head),
                                ((-1, 10.8, 3.8), (1, 13.2, 5), (46, 4, 50, 8)),
                                ((-.8, 16.6, -.8), (.8, 18, .8), (58, 5, 61, 8)),
                                ((-5.6, 4.5, -1.2), (-4, 10.6, 1.2), (40, 23, 43, 33)),
                                ((4, 4.5, -1.2), (5.6, 10.6, 1.2), (50, 23, 53, 33)),
                                ((-3.8, 1, -1.5), (-.6, 6, 1.5), (5, 33, 10, 40)),
                                ((.6, 1, -1.5), (3.8, 6, 1.5), (21, 33, 26, 40))]:
                mesh += self.box(np.array(lo)/16, np.array(hi)/16, tile, tex)
        else:
            raise ValueError(f'Unexpected warehouse entity: {kind}')
        rot = rotation('y', -float(nbt.get('Rotation', [0])[0]))
        for face in mesh:
            face.xyz = face.xyz @ rot.T
        return mesh


@dataclass
class Camera:
    origin: np.ndarray
    factor: float
    matrix: np.ndarray

    def project(self, points):
        p = np.asarray(points) @ self.matrix.T
        p[..., :2] = p[..., :2]*self.factor+self.origin
        return p

    @staticmethod
    def basis(yaw, pitch):
        yaw, pitch = map(math.radians, (yaw, pitch))
        toward = np.array((math.sin(yaw)*math.cos(pitch), math.sin(pitch), math.cos(yaw)*math.cos(pitch)))
        right = np.array((math.cos(yaw), 0., -math.sin(yaw)))
        return np.array((right, -np.cross(toward, right), toward))

    @classmethod
    def fit(cls, yaw, pitch, vertices, rect):
        matrix = cls.basis(yaw, pitch)
        xy = vertices @ matrix[:2].T
        lo, hi = xy.min(axis=0), xy.max(axis=0)
        tl, br = np.split(np.array(rect), 2)
        scale = min((br-tl)/(hi-lo))
        return cls((tl+br)/2-(lo+hi)*scale/2, scale, matrix)


SOLIDS = {'deepslate_tiles', 'deepslate_bricks', 'chiseled_tuff_bricks', 'ochre_froglight',
          'blue_ice', 'dispenser', 'redstone_lamp', 'crafter', 'barrel', 'waxed_cut_copper',
          'waxed_exposed_cut_copper', 'waxed_weathered_cut_copper', 'waxed_oxidized_cut_copper'}


class Scene:
    def __init__(self, schematic, assets, font):
        file = nbtlib.load(schematic)
        if int(file['MinecraftDataVersion']) != 5023 or len(file['Regions']) != 1:
            raise ValueError('Expected the single-region Java 26.3 warehouse')
        region, = file['Regions'].values()
        if any(region['Position'][axis] != 0 for axis in 'xyz'):
            raise ValueError('Expected warehouse origin (0, 0, 0)')
        self.grid = unpack_region(region)
        palette = [(str(p['Name']).split(':')[-1], dict((str(k), str(v)) for k, v in p.get('Properties', {}).items()))
                   for p in region['BlockStatePalette']]
        self.blocks = {(int(x), int(y), int(z)): palette[self.grid[y, z, x]] for y, z, x in np.argwhere(self.grid)}
        if len(self.blocks) != int(file['Metadata']['TotalBlocks']):
            raise ValueError('Decoded block count differs from schematic metadata')
        self.models = Models(assets, font)
        self.parts = {}
        self.tiles = {tuple(map(int, (v['x'], v['y'], v['z']))): v for v in region['TileEntities']}
        self.entities = list(self.flatten(region.get('Entities', [])))
        self.occupancy = [self.grid.shape[2], self.grid.shape[0], self.grid.shape[1]]

    @staticmethod
    def flatten(entities):
        for entity in entities:
            yield entity
            yield from Scene.flatten(entity.get('Passengers', []))

    def mesh(self, keep=lambda p: True):
        blocks = {p: state for p, state in self.blocks.items() if keep(p)}
        solid = np.zeros(self.occupancy, dtype=bool)
        faces, shifts = [], []
        def push(face, shift):
            faces.append(face)
            shifts.append(shift)

        for p, (name, props) in blocks.items():
            if p not in self.parts:
                mesh = self.models.block(name, tuple(sorted(props.items())))
                if name.endswith('_sign'):
                    mesh = [*mesh, self.models.sign(p, self.tiles[p], name, props)]
                self.parts[p] = mesh
            if name in SOLIDS:
                solid[p] = True
            for face in self.parts[p]:
                if face.cull:
                    q = tuple(a+b for a, b in zip(p, face.cull))
                    other = blocks.get(q, ('air', {}))[0]
                    if other in SOLIDS or (name in {'glass', 'water'} and other == name):
                        continue
                push(face, p)
        seen = set()
        for entity in self.entities:
            p = tuple(map(float, entity['Pos']))
            kind = str(entity['id']).split(':')[-1]
            key = (kind, p)
            # The NBT exports 8 carts and golems at exactly the same point per rail.
            if key in seen or not keep(tuple(map(math.floor, p))):
                continue
            for face in self.models.entity(kind, entity):
                push(face, p)
            seen.add(key)
        return Mesh(self.models.atlas, faces, shifts, solid)


class Mesh:
    def __init__(self, atlas, faces, shifts, solid):
        self.atlas, offsets = atlas.pack()
        self.xyz = np.array([face.xyz for face in faces]) + np.array(shifts)[:, None, :]
        self.uv = np.array([face.uv + offsets[face.tile] for face in faces])
        self.normals = unit_cross(self.xyz)
        self.lighting_normals = self.normals.copy()
        self.lighting_normals[[face.flat_light for face in faces]] = (0, 1, 0)
        self.tint = np.array([face.tint for face in faces])
        self.emissive = np.array([face.emissive for face in faces])
        self.trans = np.array([atlas.tiles[face.tile][1] for face in faces])
        center = self.xyz.mean(axis=1) + self.normals*.075
        bounds = np.array(solid.shape)
        shadows = np.zeros(len(faces))
        for v in [(.5, 1, .88), (.08, 1, .65), (.7, 1, .2)]:
            cast = np.zeros(len(faces), dtype=bool)
            for distance in (.18, .40, .68, .96, 1.26, 1.57, 2.0, 2.4, 2.85, 3.3, 3.75, 4.2, 4.65):
                p = np.floor(center + np.array(v)*distance).astype(int)
                valid = np.all((p >= 0) & (p < bounds), axis=1)
                cast[valid] |= solid[tuple(p[valid].T)]
            shadows += cast/3
        self.shadow = shadows

    def image(self, raster, camera, size):
        w, h = size
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        depth = np.full((h, w), -np.inf, dtype=np.float32)
        visible = np.flatnonzero(self.normals @ camera.matrix[2] > 1e-5)
        key = np.array((.38, .83, .41))
        direct = np.maximum(0, self.lighting_normals[visible] @ key)
        y = np.maximum(0, self.lighting_normals[visible, 1])
        brightness = .90 + (.42*direct + .19*y)*(1-.48*self.shadow[visible])
        colors = brightness[:, None]*[1.03, 1.06, 1.12]
        colors[self.emissive[visible]] = [1.24, 1.19, 1.07]
        colors *= self.tint[visible]
        transformed = np.concatenate((camera.project(self.xyz[visible]), self.uv[visible]), axis=2)
        is_trans = self.trans[visible]
        for tran in (False, True):
            use = np.flatnonzero(is_trans == tran)
            if tran:
                use = use[np.argsort(transformed[use, :, 2].mean(axis=1), kind='stable')]
            triangles = np.ascontiguousarray(transformed[use][:, [[0, 1, 2], [0, 2, 3]], :], dtype=np.float32)
            col = np.ascontiguousarray(np.repeat(colors[use], 2, axis=0), dtype=np.float32)
            th, tw = self.atlas.shape[:2]
            raster(w, h, rgba, depth, tw, th, self.atlas, len(col), triangles, col, tran)
        # PNG/Pillow alpha compositing expects straight alpha, not premultiplied.
        partial = (rgba[:, :, 3] > 0) & (rgba[:, :, 3] < 255)
        rgb = rgba[partial, :3].astype(np.float32)
        rgba[partial, :3] = np.rint(np.minimum(255, rgb * 255 / rgba[partial, 3, None])).astype(np.uint8)
        return Image.fromarray(rgba, 'RGBA')


def rasterizer():
    source = Path(__file__).with_name('voxel_raster.c')
    with tempfile.TemporaryDirectory(prefix='moonspire-raster-') as tmp:
        lib = Path(tmp) / 'voxel.so'
        subprocess.run(['cc', '-O3', '-std=c99', '-shared', '-fPIC', str(source), '-o', str(lib), '-lm'], check=True)
        raster = ct.CDLL(str(lib)).rasterize
    u8 = np.ctypeslib.ndpointer(dtype=np.uint8, flags='C_CONTIGUOUS')
    f32 = np.ctypeslib.ndpointer(dtype=np.float32, flags='C_CONTIGUOUS')
    raster.argtypes = [ct.c_int, ct.c_int, u8, f32, ct.c_int, ct.c_int, u8, ct.c_size_t, f32, f32, ct.c_int]
    raster.restype = None
    return raster
