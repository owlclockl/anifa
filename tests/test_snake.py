"""Check Snake game rules, all reachable netlist transitions, and the shipped file."""
import itertools
import unittest
from collections import deque

from tools import snake_logic as snake


def reachable():
    initial=snake.Round()
    seen={initial}
    queue=deque([initial])
    while queue:
        a=queue.popleft()
        yield a
        for key in snake.COMMANDS:
            b=snake.play(a,key)
            if b not in seen:
                seen.add(b)
                queue.append(b)


def walk(commands):
    r=snake.Round()
    for key in commands:
        r=snake.play(r,key)
    return r


class SnakeRules(unittest.TestCase):
    def test_growth_win_and_reset(self):
        r=snake.Round()
        for key in snake.WIN_ROUTE:
            r=snake.play(r,key)
        self.assertEqual(r.eaten,4)
        self.assertTrue(r.won)
        self.assertFalse(r.dead)
        self.assertEqual(snake.play(r,'RIGHT'),r)
        self.assertEqual(snake.play(r,'RESET'),snake.Round())

    def test_reversal_wall_body_and_departing_tail(self):
        self.assertEqual(snake.play(snake.Round(),'LEFT'),snake.Round())
        before=walk(('UP','UP'))
        lost=snake.play(before,'UP')
        self.assertTrue(lost.dead)
        self.assertEqual(lost.body,before.body)
        self.assertEqual(snake.play(lost,'DOWN'),lost)
        before=walk(('RIGHT','RIGHT','DOWN','LEFT','DOWN','RIGHT'))
        self.assertEqual(before.body[3],(4,3))
        self.assertTrue(snake.play(before,'UP').dead)
        before=walk(('RIGHT','UP','RIGHT','DOWN'))
        after=snake.play(before,'LEFT')
        self.assertEqual(before.body[-1],after.body[0])
        self.assertEqual(len(before.body),len(after.body))
        self.assertFalse(after.dead)

    def test_folded_snake_has_no_false_link_to_its_tail(self):
        r=walk(('RIGHT','UP','RIGHT','DOWN'))
        self.assertEqual(r.body,((4,2),(4,1),(3,1),(3,2)))
        lamps=snake.screen_lights(r)
        self.assertEqual({key for key in lamps if key.startswith(('E','V'))}, {'V41','E31','V31'})
        self.assertNotIn('E32',lamps)  # head and tail face each other across a dark gap

    def test_food_reappears_from_under_body(self):
        r=walk(('DOWN','DOWN','RIGHT','RIGHT','UP','UP'))
        self.assertEqual(r.eaten,1)
        self.assertIn(snake.APPLES[1],r.body)
        self.assertIsNone(r.food)
        for key in ('UP','LEFT','LEFT'):
            r=snake.play(r,key)
        self.assertEqual(r.food,snake.APPLES[1])

    def test_boolean_circuit_on_every_reachable_move(self):
        c=snake.design()
        games=list(reachable())
        self.assertEqual(len(games),8922)
        # Evaluate batches with one Python integer bit per game instead of a
        # Python loop over every gate for each of the 44,610 possible moves.
        for start in range(0,len(games),1024):
            states=games[start:start+1024]
            lines=[snake.initial_bits(r) for r in states]
            on=(1<<len(states))-1
            inputs=dict.fromkeys(c.inputs,0)
            for k in snake.STATE:
                inputs[k]=sum(int(row[k])<<i for i,row in enumerate(lines))
            frames=[snake.screen_lights(r) for r in states]
            values=c.evaluate(inputs,one=on)
            for k,g in c.screen.items():
                self.assertEqual(values[g],sum((k in frame)<<i for i,frame in enumerate(frames)),k)
            want=[snake.lights(r)|{'READY'} for r in states]
            for key in (None,*snake.COMMANDS):
                ports=inputs if key is None else inputs|{f'REQ_{key}':on}
                values=c.evaluate(ports,one=on)
                for k,g in c.outputs.items():
                    self.assertEqual(values[g],sum((k in row)<<i for i,row in enumerate(want)),k)
                after=[r if key is None else snake.play(r,key) for r in states]
                lines2=[snake.initial_bits(r) for r in after]
                for k,g in c.next.items():
                    # Inactive tail slots can hold any coordinates. Mask those
                    # until a growth step enables the newly copied segment.
                    mask=on if k[0]!='S' else sum((int(k[1])<len(r.body))<<i for i,r in enumerate(after))
                    self.assertEqual(values[g]&mask,sum(int(row[k])<<i for i,row in enumerate(lines2)),(key,k))

    def test_chord_priority_and_busy_gate(self):
        c=snake.design()
        order=('RESET',*snake.DIRECTIONS)
        r=walk(('RIGHT',))
        for width in range(len(order)+1):
            for chord in itertools.combinations(order,width):
                sources=c.sources(r)
                sources.update((f'KEY_{k}',True) for k in chord)
                sources.update((f'REQ_{k}',True) for k in chord)
                v=c.evaluate(sources)
                self.assertEqual(bool(v[c.clock]),bool(chord))
                self.assertEqual({k for k,g in c.commands.items() if v[g]},set(chord))
                key=next((k for k in order if k in chord),None)
                chosen=c.evaluate(c.sources(r,key))
                self.assertEqual([v[n] for n in c.next.values()],[chosen[n] for n in c.next.values()])
                v=c.evaluate(sources|{'BUSY':True,'PHASE_M':True})
                self.assertFalse(v[c.clock])
                self.assertFalse(v[c.outputs['READY']])
                self.assertEqual([v[n] for n in c.locks],[False,True])


class SnakeSchematic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import nbtlib

        from tools import build_snake as builder
        from tools.vanilla_catacomb_test import unpack_region

        cls.d=builder
        cls.file=nbtlib.load(builder.OUTPUT)
        cls.region,=cls.file['Regions'].values()
        cls.blocks=unpack_region(cls.region)
        cls.palette=cls.region['BlockStatePalette']

    @classmethod
    def tearDownClass(cls):
        del cls.blocks

    def block(self,p):
        x,y,z=self.d.export_point(p)
        state=self.palette[int(self.blocks[y,z,x])]
        return str(state['Name']),state.get('Properties',{})

    def test_export_is_a_single_autonomous_java_26_3_structure(self):
        import numpy as np

        self.assertEqual(self.file['MinecraftDataVersion'],5023)
        self.assertEqual((self.file['Version'],self.file['SubVersion']),(7,1))
        self.assertEqual(tuple(self.region['Position'][ax] for ax in 'xyz'),(0,0,0))
        self.assertEqual(self.file['Metadata']['TotalBlocks'],np.count_nonzero(self.blocks))
        self.assertFalse(self.region['Entities'])
        self.assertFalse(self.region['PendingBlockTicks'])
        self.assertLessEqual({str(t['id']) for t in self.region['TileEntities']},{'minecraft:sign','minecraft:comparator'})
        self.assertFalse(any('command_block' in p['Name'] for p in self.palette))
        for p in self.d.KEYS.values():
            name,props=self.block(p)
            self.assertEqual(name,'minecraft:stone_button')
            self.assertEqual((props['face'],props['powered']),('floor','false'))

    def test_cold_display_and_all_47_latch_pairs(self):
        import numpy as np

        want=snake.screen_lights(snake.Round())
        seen=set()
        for k,p in self.d.display_lamps():
            self.assertNotIn(p,seen)
            seen.add(p)
            block,props=self.block(p)
            self.assertEqual(block,'minecraft:redstone_lamp')
            self.assertEqual(props['lit'],str(k in want).lower())
        self.assertEqual(len(seen),5488)
        all_lamps=sum(np.count_nonzero(self.blocks==i) for i,state in enumerate(self.palette)
                      if state['Name']=='minecraft:redstone_lamp')
        self.assertEqual(all_lamps,len(seen))
        c=snake.design()
        fixed=self.d.fixed_sites(c)
        for k,value in snake.initial_bits().items():
            p=self.d.world(fixed[c.inputs[k]])
            for q in (p,self.d.put_at(p,'east')):
                block,props=self.block(q)
                self.assertEqual(block,'minecraft:repeater')
                self.assertEqual((props['locked'],props['powered']),('true',str(value).lower()),k)

    def test_display_is_a_continuous_72_by_72_plane(self):
        d=self.d
        x0,y0,z0=d.SCREEN_MIN_X,d.SCREEN_MIN_Y,d.screen.FRONT_Z
        expected={(x,y,z0) for x in range(x0,x0+72) for y in range(y0,y0+72)}
        self.assertEqual(set(d.field_pixels()),expected)
        for p in expected:
            self.assertEqual(self.block(p)[0],'minecraft:redstone_lamp')
        driven={p for k,p in d.display_lamps() if k and k.startswith(('B','E','V','F'))}
        self.assertLess(driven,expected)
        self.assertEqual(len(driven),36+60*11+4*13)

    def test_every_reachable_display_draws_a_single_one_lamp_path(self):
        from tools.verify_snake import trail_pixels

        channels={k:set(self.d.pixels(k)) for k in self.d.LAMP_PORTS if k.startswith(('B','E','V'))}
        for r in reachable():
            dots=set().union(*(channels[k] for k in snake.screen_lights(r) if k in channels))
            self.assertEqual(dots,trail_pixels(r),r)
            self.assertEqual(len(dots),12*(len(r.body)-1)+1,r)
            degrees=[sum((x+dx,y+dy,z) in dots for dx,dy in snake.DIRECTIONS.values()) for x,y,z in dots]
            self.assertEqual(degrees.count(1),2,r)
            self.assertEqual(degrees.count(2),len(dots)-2,r)
