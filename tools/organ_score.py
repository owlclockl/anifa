"""Original score for the Moonspire note-block organ.

All times are integer Minecraft game ticks at 20 TPS. A pulse travels down
one row per bar, so the final two subdivisions leave room for two diodes at
an elbow without adding any time to the bar. Pitched lanes are written in MIDI
notes, then converted to the 25 vanilla pitches of their own instrument.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import accumulate

TITLE = 'Лунный орган'
SONG = 'Сердце машины'
TPS, STEPS_PER_BAR = 20, 16
STEP_TICKS = (4, 2)*7 + (2, 4)
BPM = 4*60*TPS//sum(STEP_TICKS)
PULSE_TICKS = 20  # stone button


@dataclass(frozen=True)
class Voice:
    name: str
    instrument: str
    material: str
    sample: str
    middle: int | None  # MIDI number at note_block[note=12]
    color: str
    gain: float
    pan: float


VOICES = (
    Voice('Флейта',     'flute',    'clay',            'flute',      78, '#8be7d8', .39, -.13),
    Voice('Контрмотив', 'pling',    'glowstone',       'pling',      66, '#f9bb79', .19,  .42),
    Voice('Арфа',       'harp',     'coarse_dirt',     'harp2',      66, '#f2d18d', .27,  .21),
    Voice('Гитара',     'guitar',   'gray_wool',       'guitar',     54, '#b9b7ef', .24, -.37),
    Voice('Бас',        'bass',     'dark_oak_planks', 'bassattack', 42, '#e28c67', .40,  .00),
    Voice('Бочка',      'basedrum', 'smooth_stone',    'bd',       None, '#e37c80', .37,  .00),
    Voice('Малый',      'snare',    'sand',            'snare',    None, '#e09ebe', .27, -.07),
    Voice('Хэт',        'hat',      'glass',           'hat',      None, '#97bad2', .16,  .35),
)


@dataclass(frozen=True)
class Note:
    voice: int
    pitch: int       # note block state, 0..24
    accent: float    # for the stereo mix only; the physical block has fixed volume


@dataclass(frozen=True)
class Bar:
    chord: str
    bass: int
    arpeggio: tuple[int, ...]
    guitar: tuple[int, ...]


F_SHARP = Bar('F♯m9', 42, (54,57,61,64,68,73), (54,57,61,64))
D = Bar('Dmaj7', 38, (57,61,62,66,69,73), (50,54,57,61))
A = Bar('Aadd9', 33, (57,59,61,64,69,71), (45,52,57,61))
E = Bar('Esus4', 40, (56,59,61,64,66,69), (52,56,59,64))
B = Bar('Bm7', 35, (54,57,59,62,66,69), (47,50,54,57))
C_SHARP = Bar('C♯7', 37, (56,59,61,65,68,71), (49,53,56,59))
INVERSION = Bar('E/G♯', 32, (56,59,64,66,68,71), (44,52,56,59))
BARS = (F_SHARP,D,A,E, F_SHARP,D,B,C_SHARP, A,INVERSION,D,B,
        F_SHARP,D,A,E, F_SHARP,B,C_SHARP,F_SHARP)
SECTIONS = ((0,'Пробуждение'), (2,'Ход шестерён'), (8,'В свете луны'),
            (12,'Второй ход'), (16,'Кульминация'), (19,'Кода'))

# Two independent melodic parts, not a unison doubled at the octave.
LEAD = (
    (),
    ((8,73),(12,76),(14,78)),
    ((0,81),(3,80),(4,76),(6,73),(8,76),(11,78),(13,80),(15,81)),
    ((0,83),(4,81),(6,80),(8,76),(12,78),(14,80)),
    ((0,78),(3,73),(4,76),(6,78),(8,81),(11,80),(12,78),(14,73)),
    ((0,76),(3,73),(4,74),(6,78),(8,81),(12,78),(14,76)),
    ((0,74),(2,78),(4,83),(8,81),(10,78),(12,74),(15,73)),
    ((0,73),(4,77),(6,80),(8,83),(10,80),(12,77),(14,80),(15,85)),
    ((0,85),(6,83),(8,81),(12,80)),
    ((0,83),(4,80),(8,76),(14,78)),
    ((0,81),(4,78),(8,76),(12,74),(14,73)),
    ((0,78),(4,74),(8,71),(12,74),(14,76),(15,77)),
    ((0,78),(2,81),(3,80),(4,78),(6,76),(8,73),(10,76),(12,78),(14,81)),
    ((0,85),(3,83),(4,81),(6,78),(8,74),(12,78),(14,81)),
    ((0,88),(4,85),(7,83),(8,81),(10,83),(12,85),(14,88)),
    ((0,86),(3,85),(4,83),(6,80),(8,83),(10,80),(12,76),(14,77)),
    ((0,78),(2,81),(4,85),(6,83),(8,81),(10,80),(12,78),(13,76),(15,73)),
    ((0,74),(2,78),(4,83),(6,81),(8,86),(10,85),(12,83),(14,78)),
    ((0,85),(3,83),(4,80),(6,77),(8,80),(10,83),(12,85),(14,89),(15,85)),
    ((0,90),(4,85),(8,78)),
)
ANSWER = (
    (), ((5,69),(13,66)), ((5,69),(10,73),(14,76)), ((2,68),(7,71),(13,69)),
    ((2,69),(5,68),(9,64),(13,61),(15,64)), ((2,66),(5,69),(10,73),(13,69)),
    ((1,66),(6,69),(11,71),(14,74)), ((2,65),(5,68),(9,71),(13,68),(15,65)),
    ((2,69),(5,73),(10,76),(14,73)), ((2,68),(6,71),(11,73),(15,76)),
    ((3,69),(7,66),(11,69),(15,73)), ((2,66),(6,69),(10,71),(13,74)),
    ((1,61),(5,64),(7,68),(9,69),(13,76),(15,73)), ((2,66),(6,69),(10,73),(15,74)),
    ((2,73),(5,76),(9,71),(13,69)), ((1,68),(5,71),(7,76),(11,74),(15,71)),
    ((0,73),(1,76),(5,68),(7,69),(11,73),(13,76),(15,78)),
    ((2,66),(5,71),(7,74),(9,78),(13,74),(15,71)),
    ((0,71),(1,65),(5,68),(7,71),(9,77),(11,76),(13,71),(15,77)),
    ((0,73),(4,69),(8,68),(12,66)),
)


def arrange():
    frames = [dict() for _ in range(len(BARS)*STEPS_PER_BAR)]
    for i, bar in enumerate(BARS):
        def put(part, time, key, accent=1.0):
            voice = VOICES[part]
            pitch = key if voice.middle is None else key-voice.middle+12
            frame = frames[i*STEPS_PER_BAR+time]
            if part in frame or not 0 <= time < STEPS_PER_BAR or not 0 <= pitch <= 24:
                raise ValueError(f'Invalid note: bar {i+1}, step {time}, {voice.name}, {key}')
            frame[part] = Note(part, pitch, accent)

        for time,key in LEAD[i]:
            put(0,time,key, 1.0 if time%4==0 else .86)
        for time,key in ANSWER[i]:
            put(1,time,key, .78 if time%2 else .96)

        quiet = 8 <= i < 12
        finale = i == len(BARS)-1
        if finale:
            for time,hi,lo in ((0,73,57),(4,69,61),(8,68,54),(12,66,54)):
                put(2,time,hi); put(3,time,lo,.91)
            put(4,0,42); put(4,8,42,.8); put(5,0,4,.95)
            continue

        # The bowed-sounding high notes ride above broken, interlocking chords.
        if i == 0:
            arps = (0,2,4,6,8,10,12,14)
        elif quiet:
            arps = (0,4,7,8,12,15)
        elif i >= 16:
            arps = (0,1,2,3,4,6,7,8,9,10,11,12,14,15)
        else:
            arps = (0,2,3,6,8,10,11,14) if i%2 else (0,2,4,5,7,8,10,12,13,15)
        order = (0,2,4,1,3,5,2,4,1,5,3,4,2,5)
        for j,time in enumerate(arps):
            put(2,time,bar.arpeggio[order[(j+i%2)%len(order)]], .94 if time%4==0 else .73)
        for j,time in enumerate((0,8,12) if quiet or i<2 else (0,4,7,10,12,15)):
            put(3,time,bar.guitar[(j+(time==15))%4], .91 if time%4==0 else .64)

        # Bass stays low and sets up the next chord with a lead-in one step early.
        nxt = BARS[i+1].bass
        for time,key in ((0,bar.bass),(8,bar.bass+12)) if i<2 or quiet else (
                (0,bar.bass),(6,bar.bass+7),(8,bar.bass),(11,bar.bass+12),(14,nxt+12)):
            put(4,time,key, 1.0 if time%4==0 else .78)
        if i == 0:
            continue
        kicks = (0,8) if quiet or i==1 else ((0,6,8,10,15) if i%2==0 else (0,3,8,11))
        snares = (8,) if quiet else ((0,4,12,14,15) if i in (16,18) else (4,12,15) if i%4==3 else (4,12))
        hats = (2,6,10,14) if quiet or i==1 else tuple(range(0,16,2)) + ((7,11,15) if i>=12 else (15,))
        for time in kicks:
            put(5,time,5 if time%4==0 else 9, 1.0 if time%4==0 else .74)
        for time in snares:
            put(6,time,12 if time%4==0 else 17, .94 if time%4==0 else .58)
        for time in hats:
            put(7,time,14 if time%4==2 else 19, .83 if time%4==2 else .47)
    return tuple(tuple(notes[i] for i in sorted(notes)) for notes in frames)


FRAMES = arrange()
ONSET_TICKS = tuple(accumulate(STEP_TICKS*len(BARS), initial=0))
TOTAL_TICKS = ONSET_TICKS[-1]


def section(bar):
    return next(name for start,name in reversed(SECTIONS) if start <= bar)