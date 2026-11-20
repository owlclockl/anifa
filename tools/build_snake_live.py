"""Export the addressable display and its deterministic vanilla datapack."""
from __future__ import annotations

import argparse
import gzip
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import nbtlib
import numpy as np
from nbtlib import tag as nbt

from . import build_catacomb_cathedral as signs
from . import build_cathedral as m
from . import snake_live_rules as g

ROOT = m.OUTPUT.parent
SCHEMATIC = ROOT/'moonspire-snake-live.litematic'
PACK = ROOT/'moonspire-snake-live-datapack.zip'
POSTER = ROOT/'moonspire-snake-live-preview.jpg'
NS = 'moonspire_snake'
OBJ = 'ms_snake'
DATA = f'{NS}:game'
TAG = f'{NS}.origin'
LAMP = 'minecraft:redstone_lamp'
POWER = 'minecraft:redstone_block'
AIR = 'minecraft:air'
TEMPLATE = f'data/{NS}/structure/board.nbt'
MODERN = 'java_26_3'
MIN_FORMAT, MAX_FORMAT = (94,1), (121,0)

ALPHABET = {
    'Л': ('..###','.#..#','.#..#','.#..#','#...#'), 'У': ('#...#','#...#','.####','....#','.###.'),
    'Н': ('#...#','#...#','#####','#...#','#...#'), 'А': ('.###.','#...#','#####','#...#','#...#'),
    'Я': ('.####','#...#','.####','..#.#','##..#'), 'З': ('####.','....#','.###.','....#','####.'),
    'М': ('#...#','##.##','#.#.#','#...#','#...#'), 'Е': ('#####','#....','####.','#....','#####'),
    'Й': ('.#.#.','#.#.#','#..##','#.#.#','##..#'), 'К': ('#...#','#..#.','###..','#..#.','#...#'),
    ' ': ('.....',)*5,
}


def hud_pixels(name):
    x,y=g.HUD[name]
    return [(x+i,y+j,g.ZFACE) for j in range(3) for i in range(3)]


def geometry():
    """Build the front plane, accessible console and an empty rear power bay."""
    w,h,d=g.SIZE
    a=np.zeros((h,d,w),dtype=np.int16)
    tile={}
    dark='deepslate_tiles'
    green='waxed_weathered_cut_copper'
    gold='waxed_cut_copper'

    def put(p,material,**props):
        x,y,z=p
        a[y,z,x]=m.state(material,**props)

    def text(p,lines,color='yellow'):
        put((p[0],p[1],p[2]-1),dark)
        put(p,'dark_oak_wall_sign',facing='south',waterlogged='false')
        tile[p]=signs.text_data(lines,color)

    # A full front wall with its service bay behind each lamp, ready for
    # independent redstone sources. Solid back ribs never share the bay.
    a[0,:9,:]=m.state(dark)
    a[1:99,4,:]=m.state(dark)
    a[1:99,1,[0,2,85,87]]=m.state('deepslate_bricks')
    a[1:99,2,[0,87]]=m.state('deepslate_bricks')
    a[1:99,3,[0,87]]=m.state(green)
    a[1:99,4,[0,7,80,87]]=m.state(green)
    for y in (5,15,16,89,97,98):
        a[y,4,:]=m.state(green if y not in (16,89,98) else gold)
    a[17:89,4,8:80]=m.state('redstone_lamp',lit='false')
    for x in (0,87):
        for y in (7,16,26,38,50,62,74,86,98):
            put((x,y,4),'ochre_froglight',axis='y')
    word='ЛУННАЯ ЗМЕЙКА'
    for i,letter in enumerate(word):
        for j,line in enumerate(ALPHABET[letter]):
            for k,ch in enumerate(line):
                if ch=='#':
                    put((6+6*i+k,95-j,4),gold)
    for name in g.HUD:
        for p in hud_pixels(name):
            put(p,'redstone_lamp',lit='false')
        x,y=g.HUD[name]
        caption={'run':'Движение','loss':'Столкновение','win':'Победа'}.get(name,name[-1])
        text((x+1,y-2,5),[caption],color='light_blue')

    # Low controls at foot level leave the entire matrix visible from the
    # copper viewing tile. Raised corner piers sit outside the sight lines.
    deck=g.DECK
    a[0,76:83,35:53]=m.state(dark)
    a[deck-1,76:78,35:53]=m.state(green)
    a[deck,78:83,35:53]=m.state(dark)
    a[deck,78:83,[35,52]]=m.state(green)
    a[deck+1,76:83,[35,52]]=m.state('deepslate_bricks')
    a[deck+1,82,36:52]=m.state('deepslate_bricks')
    a[deck+1,82,49:51]=0  # entry from the double stair
    for x in (36,51):
        for z in (76,81):
            a[1:deck,z,x]=m.state('deepslate_bricks')
            a[1:deck:8,z,x]=m.state(green)
            put((x,deck+1,z),'ochre_froglight',axis='y')
    for key,(x,y,z) in g.BUTTONS.items():
        put((x,y-1,z),gold if key=='new' else green)
        put((x,y,z),'stone_button',face='floor',facing='north',powered='false')
    put((43,deck,g.VIEW_Z),gold)
    text((39,deck,77),('Новая','игра'))
    text((47,deck,77),('Пауза',),color='light_blue')
    for x in (49,50):
        for y in range(deck+1):
            z=d-1-y
            put((x,y,z),'polished_blackstone_brick_stairs',facing='north',half='bottom',shape='straight',waterlogged='false')
            if y%8==1:
                a[:y,z,x]=m.state('deepslate_bricks')
    for p,kind in g.MARKS.items():
        put(p,kind)
    return a,tile


def board(output,preview=None):
    blocks,tiles=geometry()
    m.save(output,blocks,preview,title='Лунная змейка — живой экран',description=(
        'Каждая из 72 × 72 ламп — игровая клетка. С кнопками, требует датапак Moonspire Snake Live. Java 26.3.'),
        block_entities=tiles)


def structure(grid,tiles,version):
    # Same geometry in the vanilla /place format. Air is omitted so the
    # template does not carve an 88×99×131 cuboid out of the world.
    key,props_key=('id','properties') if version==m.DATA_VERSION else ('Name','Properties')
    palette=nbt.List[nbt.Compound]()
    index={}
    for i in sorted((int(i) for i in np.unique(grid) if i),key=m.STATES.__getitem__):
        name,props=m.STATES[i]
        index[i]=len(palette)
        state=nbt.Compound({key:nbt.String(name)})
        if props:
            state[props_key]=nbt.Compound({k:nbt.String(v) for k,v in props})
        palette.append(state)
    blocks=nbt.List[nbt.Compound]()
    for y,z,x in np.argwhere(grid):
        p=int(x),int(y),int(z)
        block=nbt.Compound(pos=nbt.List[nbt.Int](p),state=nbt.Int(index[int(grid[y,z,x])]))
        if p in tiles:
            block['nbt']=tiles[p]
        blocks.append(block)
    root=nbtlib.File({'DataVersion':nbt.Int(version),'size':nbt.List[nbt.Int](g.SIZE),
                     'palette':palette,'blocks':blocks,'entities':nbt.List[nbt.Compound]()})
    target=io.BytesIO()
    with gzip.GzipFile(fileobj=target,mode='wb',mtime=0) as compressed:
        root.write(compressed)
    return target.getvalue()


def xyz(x,y,z):
    return ' '.join('~' if v==0 else f'~{v}' for v in (x,y,z))


def rel(p):
    return xyz(*(a-b for a,b in zip(p,g.ANCHOR)))


def fn(path):
    return f'function {NS}:{path}'


def setscore(key,n):
    return f'scoreboard players set #{key} {OBJ} {n}'


def plus(key,n):
    return f'scoreboard players add #{key} {OBJ} {n}'


def minus(key,n):
    return f'scoreboard players remove #{key} {OBJ} {n}'


def op(out,operator,in_):
    return f'scoreboard players operation #{out} {OBJ} {operator} #{in_} {OBJ}'


def eq(key,n):
    return f'score #{key} {OBJ} matches {n}'


def savepos(path,x,y):
    for field,key in (('x',x),('y',y)):
        yield f'execute store result storage {DATA} {path}.{field} int 1 run scoreboard players get #{key} {OBJ}'


def fill(a,b,block):
    return f'fill {xyz(*a)} {xyz(*b)} {block}'


def hud(name,on):
    x,y=g.HUD[name]
    x,y=x-g.X0,y-g.Y_TOP
    rows=[fill((x,y,g.ZFACE-1),(x+2,y+2,g.ZFACE-1),POWER if on else AIR+' replace '+POWER)]
    if not on:
        rows.append(fill((x,y,g.ZFACE),(x+2,y+2,g.ZFACE),LAMP+'[lit=false] replace '+LAMP))
    return rows


def datapack_files():
    """Small function library; integer scores and one NBT deque describe a round."""
    files={}

    def add(path,lines):
        fnpath=f'data/{NS}/function/{path}.mcfunction'
        assert fnpath not in files
        files[fnpath]='\n'.join(lines)+'\n'

    def jsonfile(path,data):
        files[path]=json.dumps(data,ensure_ascii=False,indent=2)+'\n'

    jsonfile('pack.mcmeta',{
        'pack':{'description':'Лунная змейка — 72 × 72, автоматический ход',
                'min_format':MIN_FORMAT,'max_format':MAX_FORMAT},
        'overlays':{'entries':[{'directory':MODERN,'min_format':MAX_FORMAT,'max_format':MAX_FORMAT}]},
    })
    for hook in ('load','tick'):
        jsonfile(f'data/minecraft/tags/function/{hook}.json',{'values':[f'{NS}:{hook}']})
    locate=f'execute in minecraft:overworld at @e[type=minecraft:marker,tag={TAG},limit=1]'
    add('load',[f'scoreboard objectives add {OBJ} dummy',
                f'execute unless {eq("installed","0..1")} run {setscore("installed",0)}',
                setscore('minus_one',-1),
                f'execute unless {eq("speed","1..20")} run {setscore("speed",g.STEP_TICKS)}'])
    for key,ticks in (('normal',g.STEP_TICKS),('slow',g.SLOW_TICKS)):
        add('speed/'+key,[setscore('speed',ticks),
                          f'tellraw @s {{"text":"Лунная змейка: один шаг за {ticks} тиков.","color":"aqua"}}'])
    add('tick',[f'{locate} run {fn("live_tick")}'])
    # At arbitrary world X, the 16-block spacing covers every screen chunk.
    test_load=' '.join(f'if loaded {xyz(i,0,g.ZFACE)}' for i in (*range(0,g.SIDE,16),g.SIDE-1))
    test_load+=' '+' '.join(f'if loaded {rel(g.BUTTONS[q])}' for q in ('new','pause'))
    add('live_tick',[f'execute {test_load} run {fn("poll")}'])
    add('install',[f'execute in minecraft:overworld align xyz run {fn("check_board")}'])
    marks=' '.join(f'if block {xyz(*p)} minecraft:{kind}' for p,kind in g.MARKS.items())
    marks+=' '+f'if block {xyz(*g.pixel(0,0))} {LAMP} if block {xyz(*g.pixel(71,71))} {LAMP}'
    marks+=' '+f'if block {xyz(*g.BUTTONS["new"])} minecraft:stone_button'
    add('check_board',[f'execute if {eq("installed",1)} run return run tellraw @s {{"text":"В этом мире уже есть Лунная змейка.","color":"yellow"}}',
                       f'execute {marks} positioned {xyz(*g.ANCHOR)} {test_load} run return run {fn("bind")}',
                       'tellraw @s {"text":"Не вижу экран и пульт. Проверь начало схемы, ориентацию и загрузку чанков.","color":"red"}'])
    add('bind',[f'summon minecraft:marker ~ ~ ~ {{Tags:["{TAG}"]}}',setscore('installed',1),
                fn('round/reset'),fn('hud/ready'),
                'tellraw @s {"text":"Экран подключён. Поднимись к пульту и нажми «Новая игра».","color":"aqua"}'])
    add('uninstall',[f'{locate} {test_load} run return run {fn("unbind")}',
                     'tellraw @s {"text":"Экран не подключён или его чанки не загружены.","color":"red"}'])
    add('unbind',[fn('clear'),setscore('mode',0),setscore('installed',0),
                  f'kill @e[type=minecraft:marker,tag={TAG},distance=..0.1,limit=1]',
                  'tellraw @s {"text":"Экран отключён.","color":"aqua"}'])

    # A vanilla stone button stays pressed for 20 ticks. Release it as soon
    # as we sample it so the same arrow can be tapped again on a tight bend.
    lines=[]
    for key,p in g.BUTTONS.items():
        pos=rel(p)
        lines += [setscore('edge_'+key,0),
                  f'execute if block {pos} {g.BUTTON.format("true")} run {setscore("edge_"+key,1)}',
                  f'execute if {eq("edge_"+key,1)} run setblock {pos} {g.BUTTON.format("false")}']
    lines += [f'execute if {eq("edge_new",1)} run return run {fn("round/new")}',
              f'execute if {eq("edge_pause",1)} if {eq("mode",1)} run return run {fn("round/pause")}',
              f'execute if {eq("edge_pause",1)} if {eq("mode",2)} run return run {fn("round/resume")}']
    for key in reversed(g.KEYS):
        n=g.KEYS.index(key)
        lines.append(f'execute if {eq("mode","1..2")} if {eq("edge_"+key,1)} unless {eq("dir",(n+2)%4)} run {setscore("queued",n)}')
    lines += [f'execute if {eq("mode",1)} run {fn("round/clock")}']
    add('poll',lines)

    start_body='['+','.join(f'{{x:{x},y:{y}}}' for x,y in g.START)+']'
    a=(0,1-g.SIDE,g.ZFACE-1)
    b=(g.SIDE-1,0,g.ZFACE-1)
    add('clear',[fill(a,b,AIR)+f' replace {POWER}',
                 fill((a[0],a[1],g.ZFACE),(b[0],b[1],g.ZFACE),LAMP+'[lit=false]')+f' replace {LAMP}',
                 *(row for name in g.HUD for row in hud(name,False))])
    add('round/reset',[fn('clear'), setscore('mode',0),setscore('score',0),setscore('grow',0),
                       setscore('x',g.START[0][0]),setscore('y',g.START[0][1]),
                       setscore('dir',1),setscore('queued',1),setscore('timer',g.START_TICKS),
                       f'data modify storage {DATA} body set value {start_body}',
                       fill((g.START[-1][0],-g.START[0][1],g.ZFACE-1),(g.START[0][0],-g.START[0][1],g.ZFACE-1),POWER),
                       setscore('ax',g.FIRST[0]),setscore('ay',g.FIRST[1]),fn('fruit/accept')])
    add('round/new',[fn('round/reset'),setscore('mode',1),fn('hud/playing')])
    add('round/pause',[setscore('mode',2),*hud('run',False),fn('hud/paused')])
    add('round/resume',[setscore('mode',1),fn('hud/playing')])
    add('round/clock',[minus('timer',1),f'execute if {eq("timer","..0")} run {fn("round/step")}'])
    lines=[op('timer','=','speed'),op('nx','=','x'),op('ny','=','y')]
    for d,key in enumerate(g.KEYS):
        dx,dy=g.DIRECTION[key]
        line=plus('nx',dx) if dx>0 else minus('nx',-dx) if dx<0 else plus('ny',dy) if dy>0 else minus('ny',-dy)
        lines.append(f'execute if {eq("queued",d)} run {line}')
    lines += [f'execute unless {eq("nx","0..71")} run return run {fn("round/loss")}',
              f'execute unless {eq("ny","0..71")} run return run {fn("round/loss")}',
              *savepos('next','nx','ny'),fn('fruit/detect'),
              setscore('hold',0),f'execute if {eq("grow","1..")} run {setscore("hold",1)}',
              f'execute if {eq("eat",1)} run {setscore("hold",1)}',
              f'{fn("round/collision")} with storage {DATA} next',
              f'execute if {eq("mode",3)} run return 0',
              f'execute if {eq("hold",0)} run {fn("pixel/dark")} with storage {DATA} body[-1]',
              f'execute if {eq("hold",0)} run data remove storage {DATA} body[-1]',
              f'execute if {eq("eat",1)} run {fn("fruit/take")}',
              f'data modify storage {DATA} body prepend from storage {DATA} next',
              f'{fn("pixel/light")} with storage {DATA} next',
              op('x','=','nx'),op('y','=','ny'),op('dir','=','queued'),
              f'execute if {eq("grow","1..")} run {minus("grow",1)}',
              f'execute if {eq("score",f"{g.GOAL}..")} run return run {fn("round/win")}',
              f'execute if {eq("eat",1)} run {fn("fruit/spawn")}']
    add('round/step',lines)
    add('round/collision',[
        f'$execute unless data storage {DATA} body[{{x:$(x),y:$(y)}}] run return 0',
        f'execute if {eq("hold",1)} run return run {fn("round/loss")}',
        *(f'execute store result score #t{a} {OBJ} run data get storage {DATA} body[-1].{a} 1' for a in 'xy'),
        f'execute if score #nx {OBJ} = #tx {OBJ} if score #ny {OBJ} = #ty {OBJ} run return 0',
        fn('round/loss')])
    add('round/loss',[setscore('mode',3),*hud('run',False),*hud('loss',True),fn('hud/lost')])
    add('round/win',[setscore('mode',4),*hud('run',False),*hud('win',True),fn('hud/won')])
    add('pixel/light',[f'$setblock ~$(x) ~-$(y) ~{g.ZFACE-1} {POWER}'])
    add('pixel/dark',[f'$setblock ~$(x) ~-$(y) ~{g.ZFACE-1} {AIR}',
                      f'$setblock ~$(x) ~-$(y) ~{g.ZFACE} {LAMP}[lit=false]'])

    add('fruit/detect',[setscore('eat',0),f'execute unless {eq("fruit",1)} run return 0',
                        op('delta_x','=','nx'),op('delta_x','-=','ax'),
                        f'execute if {eq("delta_x","..-1")} run {op("delta_x","*=","minus_one")}',
                        op('delta_y','=','ny'),op('delta_y','-=','ay'),
                        f'execute if {eq("delta_y","..-1")} run {op("delta_y","*=","minus_one")}',
                        op('delta_x','+=','delta_y'),f'execute if {eq("delta_x",f"..{g.RADIUS}")} run {setscore("eat",1)}'])
    add('fruit/accept',[setscore('fruit',1),*savepos('apple','ax','ay'),
                        f'{fn("fruit/light")} with storage {DATA} apple'])
    add('fruit/take',[f'{fn("fruit/dark")} with storage {DATA} apple',setscore('fruit',0),
                      plus('score',1),plus('grow',g.GAIN),
                      *(f'execute if {eq("score",k)} run {fn(f"hud/apple{k}")}' for k in range(1,g.GOAL+1)),fn('hud/fruit')])
    for action in ('light','dark','test'):
        add('fruit/'+action,[f'$execute positioned ~$(x) ~-$(y) ~{g.ZFACE-1} run {fn("fruit/"+action+"_local")}'])
    rows=[]
    blocks=[]
    for y in range(-g.RADIUS,g.RADIUS+1):
        u=g.RADIUS-abs(y)
        rows.append(((-u,y,0),(u,y,0)))
        blocks.extend((x,y,0) for x in range(-u,u+1))
    add('fruit/light_local',[fill(a,b,POWER) for a,b in rows])
    add('fruit/dark_local',[*(fill(a,b,AIR) for a,b in rows),
                            *(fill((a[0],a[1],1),(b[0],b[1],1),LAMP+'[lit=false]') for a,b in rows)])
    add('fruit/test_local',[f'execute if block {xyz(*p)} {POWER} run return run {setscore("free",0)}' for p in blocks])
    safe_range=f'{g.RADIUS}..{g.MAX_CENTER}'
    add('fruit/spawn',[setscore('tries',16),fn('fruit/random')])
    add('fruit/candidate',[setscore('free',1),*savepos('candidate','ax','ay'),
                           f'{fn("fruit/test")} with storage {DATA} candidate'])
    add('fruit/random',[minus('tries',1),
                         *(f'execute store result score #{key} {OBJ} run random value {safe_range}' for key in ('ax','ay')),
                         fn('fruit/candidate'),f'execute if {eq("free",1)} run return run {fn("fruit/accept")}',
                         f'execute if {eq("tries","1..")} run return run {fn("fruit/random")}',
                         setscore('ax',g.FALLBACK_START),setscore('ay',g.FALLBACK_START),fn('fruit/fallback')])
    # Mutually disjoint diamonds, more candidates than the maximum length.
    add('fruit/fallback',[fn('fruit/candidate'),f'execute if {eq("free",1)} run return run {fn("fruit/accept")}',
                           plus('ax',g.FALLBACK_PITCH),
                           f'execute if {eq("ax",f"{g.MAX_CENTER+1}..")} run {plus("ay",g.FALLBACK_PITCH)}',
                           f'execute if {eq("ax",f"{g.MAX_CENTER+1}..")} run {setscore("ax",g.FALLBACK_START)}',
                           f'execute if {eq("ay",f"..{g.MAX_CENTER}")} run {fn("fruit/fallback")}'])

    audience=f'execute positioned {rel((43,37,76))} run title @a[distance=..12] actionbar '
    for mode,message,color in (('ready','Готово · нажми «Новая игра»','aqua'),
        ('playing','Змейка ползёт сама · стрелки меняют направление','aqua'),('paused','Пауза · нажми ещё раз, чтобы продолжить','yellow'),
        ('lost','Столкновение · «Новая игра», чтобы повторить','red'),('won','Четыре яблока — победа!','gold')):
        add('hud/'+mode,[*(hud('run',True) if mode=='playing' else []),
                         audience+json.dumps({'text':message,'color':color},ensure_ascii=False)])
    for i in range(1,g.GOAL+1):
        add(f'hud/apple{i}',hud(f'apple{i}',True))
    add('hud/fruit',[audience+json.dumps([{'text':'Яблоки: ','color':'gold'},
                                          {'score':{'name':'#score','objective':OBJ}},{'text':f' / {g.GOAL}'}],ensure_ascii=False)])
    return files


def pack(path):
    grid,tiles=geometry()
    files=datapack_files()
    files[TEMPLATE]=structure(grid,tiles,4671)
    files[f'{MODERN}/{TEMPLATE}']=structure(grid,tiles,m.DATA_VERSION)
    with ZipFile(path,'w') as z:
        for name,content in sorted(files.items()):
            entry=ZipInfo(name,date_time=(2026,11,18,0,0,0))
            entry.create_system=3
            entry.external_attr=0o644<<16
            z.writestr(entry,content,compress_type=ZIP_DEFLATED,compresslevel=9)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--schematic',type=Path,default=SCHEMATIC)
    p.add_argument('--pack',type=Path,default=PACK)
    p.add_argument('--preview',type=Path)
    args=p.parse_args()
    board(args.schematic,args.preview)
    pack(args.pack)


if __name__=='__main__':
    main()
