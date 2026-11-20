"""Audit both Snake exports and the independent 72×72 movement model."""
import gzip
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

import nbtlib
import numpy as np

from tools import build_snake_live as b
from tools import snake_live_rules as g
from tools.vanilla_catacomb_test import unpack_region


def palette_entry(state):
    return (str(state.get('Name',state.get('id'))),
            tuple(sorted((str(k),str(v)) for k,v in state.get('Properties',state.get('properties',{})).items())))


class LiveSnakeExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file=nbtlib.load(b.SCHEMATIC)
        cls.region,=cls.file['Regions'].values()
        grid=unpack_region(cls.region)
        palette=list(map(palette_entry,cls.region['BlockStatePalette']))
        cls.blocks={(int(x),int(y),int(z)):palette[grid[y,z,x]] for y,z,x in np.argwhere(grid)}

    def test_full_lamp_plane_with_empty_private_backing(self):
        self.assertEqual(int(self.file['MinecraftDataVersion']),5023)
        self.assertEqual(tuple(self.region['Size'][k] for k in 'xyz'),g.SIZE)
        self.assertEqual(tuple(self.region['Position'][k] for k in 'xyz'),(0,0,0))
        self.assertEqual(int(self.file['Metadata']['TotalBlocks']),len(self.blocks))
        lamps={p for p,(name,_) in self.blocks.items() if name==b.LAMP}
        field={g.pixel(x,y) for x in range(g.SIDE) for y in range(g.SIDE)}
        indicators={p for name in g.HUD for p in b.hud_pixels(name)}
        self.assertEqual(len(field),5184)
        self.assertEqual(lamps,field | indicators)
        self.assertTrue(field.isdisjoint(indicators))
        for x,y,z in lamps:
            self.assertEqual(self.blocks[x,y,z],(b.LAMP,(('lit','false'),)))
            self.assertNotIn((x,y,z-1),self.blocks)
            self.assertNotIn((x,y,z+1),self.blocks)
        self.assertFalse(any(name==b.POWER or 'command_block' in name for name,_ in self.blocks.values()))

    def ray_clear(self, start, end):
        """Sample the view through full cubes; stairs/signs/buttons are non-full."""
        for u in np.linspace(0,1,1+math.ceil(math.dist(start,end)*25)):
            p=tuple(math.floor(a+(c-a)*u) for a,c in zip(start,end))
            state=self.blocks.get(p)
            if state and not state[0].endswith(('_button','_sign','_stairs')):
                return False,p
        return True,None

    def test_walkup_pulpit_can_reach_buttons_and_see_both_edges(self):
        self.assertEqual({p for p,(name,_) in self.blocks.items() if name=='minecraft:stone_button'},set(g.BUTTONS.values()))
        view=(g.VIEW[0],g.VIEW[1]+1.62,g.VIEW[2])
        for value in g.BUTTONS.values():
            x,y,z=value
            self.assertIn((x,y-1,z),self.blocks)
            self.assertEqual(self.blocks[value][1],(('face','floor'),('facing','north'),('powered','false')))
            touch=(x+.5,y+.10,z+.5)
            self.assertLess(math.dist(view,touch),4.5)
            self.assertEqual(self.ray_clear(view,touch),(True,None))
        for v in (0,1,18,35,52,70,71):
            for x,y in ((v,0),(v,71),(0,v),(71,v),(v,v)):
                px,py,pz=g.pixel(x,y)
                self.assertEqual(self.ray_clear(view,(px+.5,py+.5,pz+1.001)),(True,None),(x,y))
        for x in (49,50):
            for y in range(g.DECK+1):
                stair=(x,y,g.SIZE[2]-1-y)
                self.assertTrue(self.blocks[stair][0].endswith('_stairs'))
                self.assertNotIn((stair[0],stair[1]+1,stair[2]),self.blocks)

    def test_datapack_includes_both_equivalent_vanilla_templates(self):
        with ZipFile(b.PACK) as z:
            self.assertIsNone(z.testzip())
            meta=json.loads(z.read('pack.mcmeta'))
            self.assertEqual(meta['pack']['min_format'],list(b.MIN_FORMAT))
            self.assertEqual(meta['pack']['max_format'],list(b.MAX_FORMAT))
            self.assertEqual(meta['overlays']['entries'][0]['directory'],b.MODERN)
            for name,version in ((b.TEMPLATE,4671),(f'{b.MODERN}/{b.TEMPLATE}',5023)):
                native=nbtlib.File.parse(io.BytesIO(gzip.decompress(z.read(name))))
                self.assertEqual(native['DataVersion'],version)
                self.assertEqual(tuple(native['size']),g.SIZE)
                states=list(map(palette_entry,native['palette']))
                self.assertEqual(len(native['blocks']),len(self.blocks))
                self.assertEqual({tuple(entry['pos']):states[entry['state']] for entry in native['blocks']},self.blocks)
                signs={tuple(entry['pos']):entry['nbt'] for entry in native['blocks'] if 'nbt' in entry}
                self.assertEqual(signs,{tuple(t[k] for k in 'xyz'):{k:v for k,v in t.items() if k not in 'xyz'}
                                        for t in self.region['TileEntities']})
            for name,text in b.datapack_files().items():
                self.assertEqual(z.read(name).decode('utf-8'),text,name)
        with tempfile.TemporaryDirectory() as tmp:
            copy=Path(tmp)/'pack.zip'
            b.pack(copy)
            self.assertEqual(copy.read_bytes(),b.PACK.read_bytes())


class LiveSnakeRules(unittest.TestCase):
    def test_one_lamp_per_move_and_perpendicular_turns_at_every_coordinate(self):
        for y in range(g.SIDE):
            for x in range(g.SIDE):
                p=(x,y)
                frame=g.Frame((p,),fruit=None)
                for key in ('up','right','down'):
                    dx,dy=g.DIRECTION[key]
                    nxt=(x+dx,y+dy)
                    k=g.move(frame,key)
                    if 0<=nxt[0]<g.SIDE and 0<=nxt[1]<g.SIDE:
                        self.assertEqual(k.body,(nxt,))
                        self.assertEqual(k.outcome,None)
                        self.assertEqual(k.heading,key)
                    else:
                        self.assertEqual(k.body,(p,))
                        self.assertEqual(k.outcome,'loss')
                for key in ('down','left','up'):
                    frame=g.Frame((p,),heading='left',fruit=None)
                    k=g.move(frame,key)
                    self.assertEqual(k.outcome is None,g.in_field(x+g.DIRECTION[key][0],y+g.DIRECTION[key][1]))
        self.assertEqual(g.move(g.Frame(),'left'),g.move(g.Frame()))

    def test_serpentine_contacts_all_lamps_and_all_four_corners(self):
        frame=g.Frame(tuple((0,y) for y in range(1,13)),heading='up',fruit=None)
        arrived=set()
        for y in range(g.SIDE):
            for j in range(g.SIDE):
                x=j if y%2==0 else g.SIDE-1-j
                hx,hy=frame.body[0]
                key=next(k for k,d in g.DIRECTION.items() if d==(x-hx,y-hy))
                frame=g.move(frame,key)
                self.assertEqual(frame.body[0],(x,y))
                self.assertNotIn(frame.body[0],arrived)
                self.assertEqual(len(set(frame.body)),12)
                self.assertIsNone(frame.outcome)
                arrived.add(frame.body[0])
        self.assertEqual(len(arrived),5184)

    def test_fruit_shape_and_guaranteed_free_spawn(self):
        occupied=set()
        centers=range(g.FALLBACK_START,g.MAX_CENTER+1,g.FALLBACK_PITCH)
        for y in centers:
            for x in centers:
                shape=g.fruit_pixels((x,y))
                self.assertEqual(len(shape),13)
                self.assertTrue(occupied.isdisjoint(shape))
                self.assertTrue(all(g.in_field(a,c) for a,c in shape))
                occupied |= shape
        self.assertGreater(len(centers)**2,len(g.START)+g.GAIN*g.GOAL)

    def test_growth_and_collision_rules_at_the_departing_tail(self):
        tail=((1,1),(0,1),(0,2),(1,2))
        valid=g.move(g.Frame(tail,fruit=None),'down')
        self.assertEqual(valid.body,(tail[-1],*tail[:-1]))
        self.assertEqual(g.move(g.Frame(tail,fruit=None,growth=1),'down').outcome,'loss')
        self.assertEqual(g.move(g.Frame((*tail,(2,2)),fruit=None),'down').outcome,'loss')
        r=g.Frame(tuple((x,35) for x in range(37,25,-1)))
        for i in range(4):
            r=g.move(r,spawn=(60,60))
            self.assertEqual(len(r.body),13+i)
            self.assertEqual(r.score,1)
        self.assertEqual(r.growth,0)
