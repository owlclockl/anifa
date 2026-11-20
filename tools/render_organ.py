"""Synchronize a voxel cutaway and stereo note-block mix from the same score."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from functools import cache
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

from . import build_organ as design
from . import organ_score as score
from .voxel_render import Camera, Scene, rasterizer

VIDEO = design.ROOT/'moonspire-organ.mp4'
AUDIO = design.ROOT/'moonspire-organ.mp3'
FONTS = Path('/usr/share/fonts/truetype/dejavu')
SIZE = (1440,900)
PANEL = (34,140,1007,704)
SIDEBAR = (1027,140,1406,704)
STRIP = (34,723,1406,860)
ROLL = (56,770,1384,834)
FPS, RATE = 30,48000
INTRO_FRAMES, TAIL_FRAMES = 48,36
ON = tuple(t*FPS//score.TPS for t in score.ONSET_TICKS)
DURATION = (INTRO_FRAMES+ON[-1]+TAIL_FRAMES)/FPS
PULSE = score.PULSE_TICKS*FPS//score.TPS
INK, MUTED, LIGHT = '#f5ecd9','#9caeaf','#cbd8d5'
AQUA, GOLD = '#8be7d8','#f1be79'
PANEL_BG, STROKE = '#101e25','#2c454a'
PITCH_NAMES = ('C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B')


def ffmpeg_path():
    if ff := shutil.which('ffmpeg'):
        return ff
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def audio_mix(ff,assets):
    """Use the game's actual timbres; offline panning and room reflections."""
    tones = []
    for voice in score.VOICES:
        path = assets/'sounds/note'/f'{voice.sample}.ogg'
        result = subprocess.check_output([ff,'-v','error','-i',str(path),'-vn','-ar',str(RATE),'-ac','1','-f','f32le','-'])
        a = np.frombuffer(result,dtype='<f4')
        tones.append(a/max(1e-8,np.max(np.abs(a))))

    @cache
    def instrument(voice,pitch):
        src = tones[voice]
        speed = 2**((pitch-12)/12)
        samples = np.interp(np.arange(0,len(src)-1,speed),np.arange(len(src)),src).astype(np.float32)
        # Short safety fade to remove the hard ends of a few game samples.
        samples[-256:] *= np.linspace(1,0,256,dtype=np.float32)
        v = score.VOICES[voice]
        left = math.sqrt((1-v.pan)/2)
        right = math.sqrt((1+v.pan)/2)
        return samples[:,None]*np.array([left,right],np.float32)*v.gain

    dry = np.zeros(((ON[-1]+TAIL_FRAMES)*RATE//FPS,2),np.float32)
    for tick,notes in zip(score.ONSET_TICKS,score.FRAMES):
        start = tick*RATE//score.TPS
        for n in notes:
            a = instrument(n.voice,n.pitch)*n.accent
            count = min(len(a),len(dry)-start)
            dry[start:start+count] += a[:count]
    mixed = dry.copy()
    for ms,wet,cross in ((31,.12,True),(59,.10,False),(103,.085,True),
                         (157,.060,False),(227,.044,True),(317,.038,True),(481,.022,False)):
        offset = ms*RATE//1000
        mixed[offset:] += wet*dry[:-offset,::-1] if cross else wet*dry[:-offset]
    mixed[-RATE//4:] *= np.linspace(1,0,RATE//4,dtype=np.float32)[:,None]
    mixed = np.tanh(mixed*1.12)
    mixed *= .88/max(np.max(np.abs(mixed)),1e-8)
    return mixed


def write_wav(path,mix):
    pcm = np.rint(32767*mix).astype('<i2')
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm.tobytes())


def rgba(color,a=255):
    return (*ImageColor.getrgb(color),max(0,min(255,int(a))))


def signal_strength(age,decay=13):
    return max(0,1-age/decay)**1.6


def label_for(note):
    mid = score.VOICES[note.voice].middle
    if mid is None:
        return f'• {note.pitch:02}'
    key = mid + note.pitch - 12
    return PITCH_NAMES[key%12]+str(key//12-1)


class Cutaway:
    def __init__(self,scene,raster,level):
        x0,y0,x1,y1 = PANEL
        w,h = x1-x0,y1-y0
        if level is None:
            mesh = scene.mesh()
            yaw,pitch,rect = 207,27,(80,51,w-70,h-29)
        else:
            y = design.Y0+level*design.DECK_PITCH
            rect = (33,62,w-33,h-42)
            yaw,pitch = 206+7*(level%2),34
            mesh = scene.mesh(lambda p: y-3 <= p[1] <= y and 5 <= p[2] <= 56)
        cam = Camera.fit(yaw,pitch,mesh.xyz.reshape(-1,3),rect)
        big = Camera(cam.origin*2,cam.factor*2,cam.matrix)
        voxel = mesh.image(raster,big,(2*w,2*h)).resize((w,h),Image.Resampling.LANCZOS)
        yy,xx = np.ogrid[:h,:w]
        glow = np.exp(-4.5*((xx/w-.52)**2+(yy/h-.50)**2))
        bg = np.array([13,24,31])+glow[...,None]*[17,34,37]
        lines = (yy%32==0)|(xx%32==0)
        bg[lines] += [3,5,5]
        shadow = voxel.getchannel('A').filter(ImageFilter.GaussianBlur(7))
        plate = Image.fromarray(bg.astype('uint8'),'RGB')
        plate.paste('#0e171d',(3,7,w-4,h-8),shadow.crop((0,0,w-7,h-15)))
        plate.paste(voxel,mask=voxel)
        self.bitmap,self.cam = plate,Camera(cam.origin+np.array((x0,y0)),cam.factor,cam.matrix)

    def project(self,p):
        return tuple(self.cam.project(p)[:2])

    def line(self,positions,height=.04):
        UV = self.cam.project(np.array(positions)+[.5,height,.5])
        return [tuple(p) for p in UV[:,:2]]

    def top(self,pos):
        x,y,z = pos
        return self.line([(x+a,y+1,z+b) for a,b in ((-.44,-.44),(.44,-.44),(.44,.44),(-.44,.44))])


class Film:
    def __init__(self,path,assets,fonts):
        self.fonts = fonts
        self.model = design.Organ().build()
        scene = Scene(path,assets,fonts/'DejaVuSans.ttf')
        rast = rasterizer()
        self.overview = Cutaway(scene,rast,None)
        self.levels = [Cutaway(scene,rast,i) for i in range(design.DECKS)]
        self.notes_view,self.lamps_view,self.lines_view = [],[],[]
        for i,frame in enumerate(score.FRAMES):
            cut = self.levels[self.floor(i)]
            self.notes_view.append([(n,cut.project(np.array(design.note_at(i,n.voice))+[.5,1.09,.5])) for n in frame])
            self.lamps_view.append(cut.top(design.lamp_at(i)))
            self.lines_view.append(cut.line(self.model.buses[i]))
        self.build_layout()
        self.events = [tuple((ON[i],n) for i,frame in enumerate(score.FRAMES) for n in frame if n.voice==v)
                       for v in range(len(score.VOICES))]
        self.starts = [tuple(t for t,_ in notes) for notes in self.events]

    @staticmethod
    def floor(i):
        return i//(len(design.COLUMNS)*score.STEPS_PER_BAR)

    @cache
    def font(self,size,kind):
        name = dict(serif='DejaVuSerif', mono='DejaVuSansMono', sans='DejaVuSans', bold='DejaVuSans-Bold')[kind]
        return ImageFont.truetype(str(self.fonts/(name+'.ttf')),size)

    def txt(self,d,pos,msg,size,color=INK,kind='sans',anchor=None):
        d.text(pos,msg,font=self.font(size,kind),fill=color,anchor=anchor)

    def build_layout(self):
        yy,xx = np.ogrid[:SIZE[1],:SIZE[0]]
        bloom = np.exp(-5*((xx/SIZE[0]-.46)**2 + (yy/SIZE[1]-.16)**2))
        self.shell = Image.fromarray((np.array([11,20,27])+bloom[...,None]*[6,13,13]).astype('uint8'),'RGB')
        d=ImageDraw.Draw(self.shell)
        for box in (PANEL,SIDEBAR,STRIP):
            d.rounded_rectangle(box,radius=17,fill=PANEL_BG,outline=STROKE)
        d.rounded_rectangle((35,24,38,110),radius=1,fill=AQUA)
        self.txt(d,(53,23),'MOONSPIRE   /   REDSTONE SESSIONS',15,AQUA,'bold')
        self.txt(d,(51,45),'Лунный орган',52,INK,'serif')
        self.txt(d,(54,113),'Оригинальная пьеса для нотных блоков Minecraft',16,MUTED)
        self.txt(d,(1405,39),'СЕРДЦЕ МАШИНЫ',29,INK,'mono','ra')
        self.txt(d,(1404,86),'F♯ MINOR   /   100 BPM   /   20 ТАКТОВ',15,AQUA,'mono','ra')
        self.txt(d,(1051,157),'02   /   ПАРТИИ',14,AQUA,'bold')
        d.line((1051,242,1383,242),fill=STROKE)
        self.txt(d,(55,740),'03   /   ПАРТИТУРА',14,AQUA,'bold')
        self.txt(d,(1384,739),'829 НОТ  ·  320 ШАГОВ',14,MUTED,'mono','ra')
        d.line((35,878,1406,878),fill=STROKE)
        self.txt(d,(36,887),'СИНХРОННЫЙ РЕНДЕР СХЕМЫ   /   JAVA 26.3',10,MUTED,'mono')
        self.txt(d,(1405,887),'ТОЛЬКО НОТНЫЕ БЛОКИ И РЕДСТОУН',10,MUTED,'mono','ra')
        for c in range(len(score.VOICES)+1):
            y = ROLL[1]+8*c
            d.line((ROLL[0],y,ROLL[2],y),fill='#21343b')
        for bar in range(len(score.BARS)+1):
            x = ROLL[0]+(ROLL[2]-ROLL[0])*bar/len(score.BARS)
            d.line((x,ROLL[1]-3,x,ROLL[3]),fill='#395559' if bar%4==0 else '#253a42')
            if bar%4==0:
                self.txt(d,(x+1,838),f'{bar+1:02}' if bar<len(score.BARS) else '',10,MUTED,'mono')
        for i,notes in enumerate(score.FRAMES):
            x0,x1 = (self.roll_x(ON[i]),self.roll_x(ON[i+1]))
            for n in notes:
                y = ROLL[1]+n.voice*8+2
                color = tuple(int(v*(.38+.12*n.accent)) for v in ImageColor.getrgb(score.VOICES[n.voice].color))
                d.rectangle((x0+1,y,max(x0+1,x1-1),y+4),fill=color)
        w,h = PANEL[2]-PANEL[0],PANEL[3]-PANEL[1]
        self.mask = Image.new('L',(w,h),0)
        ImageDraw.Draw(self.mask).rounded_rectangle((0,0,w-1,h-1),radius=17,fill=255)

    @staticmethod
    def roll_x(frame):
        return ROLL[0]+(ROLL[2]-ROLL[0])*min(1,max(0,frame/ON[-1]))

    def panel(self,image,frame,level):
        cut = self.levels[level]
        if frame<0:
            prev = self.overview.bitmap
            amount = min(1,max(0,(frame+12)/12))
            bitmap = Image.blend(prev,cut.bitmap,amount) if amount else prev
        elif frame>=ON[-1]:
            u = min(1,(frame-ON[-1])/16)
            bitmap = Image.blend(cut.bitmap,self.overview.bitmap,u) if u else cut.bitmap
        else:
            t0 = ON[level*len(design.COLUMNS)*score.STEPS_PER_BAR]
            bitmap = (Image.blend(self.levels[level-1].bitmap,cut.bitmap,.4+.6*(frame-t0)/9)
                      if level>0 and frame-t0<9 else cut.bitmap)
        image.paste(bitmap,PANEL[:2],self.mask)

    def frame(self,index,*,poster=False):
        elapsed = index-INTRO_FRAMES
        step = min(len(score.FRAMES)-1,max(0,bisect_right(ON,elapsed)-1))
        bar = step//score.STEPS_PER_BAR
        level = self.floor(step)
        last = step%score.STEPS_PER_BAR
        before,after = elapsed<0,elapsed>=ON[-1]
        still_wide = poster or elapsed<=-12 or (after and elapsed>ON[-1]+12)
        img = self.shell.copy()
        if poster:
            img.paste(self.overview.bitmap,PANEL[:2],self.mask)
        else:
            self.panel(img,elapsed,level)
        d = ImageDraw.Draw(img,'RGBA')
        d.rounded_rectangle(PANEL,radius=17,outline=STROKE)
        phase = 'ОБЩИЙ ВИД' if still_wide else f'ЯРУС {level+1:02} / {design.DECKS:02}'
        self.txt(d,(55,157),'01   /   НОТНЫЙ СЕКВЕНСОР',14,AQUA,'bold')
        self.txt(d,(986,157),phase,14,MUTED,'mono','ra')
        if not before and not after and not poster:
            # The leading edge clocks the notes. The same 20-tick button
            # pulse leaves a trail in the wires while the score advances.
            for i in range(max(0,bisect_right(ON,elapsed-PULSE)-1),step+1):
                if self.floor(i)!=level:
                    continue
                age=elapsed-ON[i]
                if age>=PULSE:
                    continue
                beam=.32+.68*(1-age/PULSE)**3
                d.line(self.lines_view[i],fill=rgba(GOLD,72*beam),width=14)
                d.line(self.lines_view[i],fill=rgba('#ff9e42',182*beam),width=5)
                d.line(self.lines_view[i],fill=rgba('#fff1bb',250*beam),width=2)
                d.polygon(self.lamps_view[i],fill=rgba('#ffd98a',250*beam))
                if age<17:
                    strength=signal_strength(age,17)
                    for n,(u,v) in self.notes_view[i]:
                        hue = score.VOICES[n.voice].color
                        for r,alpha in ((16,26),(9,78),(4,197)):
                            d.ellipse((u-r,v-r,u+r,v+r),fill=rgba(hue,alpha*strength))
                        ux,vy = u + math.sin((i+n.voice)*1.63)*age*.52, v-2.65*age-8
                        d.line((u,v,ux,vy),fill=rgba(hue,175*strength),width=2)
                        r = max(1,5.5*(1-age/17))
                        d.polygon(((ux-r,vy),(ux,vy-r),(ux+r,vy),(ux,vy+r)),fill=rgba(hue,255*strength))
        if elapsed>=-self.model.onset[0]*FPS//score.TPS and before and not poster:
            u,v = self.overview.project(np.array(design.BUTTON)+[.5,.27,.5])
            a = min(1,(-elapsed)/9)
            r = 14+13*(1-a)
            d.ellipse((u-r,v-r,u+r,v+r),outline=rgba(AQUA,255*a),width=2)
        footer = 'СЛУШАТЬ С ЦЕНТРАЛЬНОЙ ПЛОЩАДКИ' if poster else 'ПУСК  /  ИМПУЛЬС ВХОДИТ В ПАРТИТУРУ' if before else 'ФИНАЛ  /  МЕХАНИЗМ ОСТАНОВЛЕН' if after else f'ТАКТ {bar+1:02}  ·  ДОЛЯ {last//4+1}  ·  ШАГ {step+1:03}'
        d.rounded_rectangle((53,662,467,689),radius=6,fill=rgba('#101b22',236))
        self.txt(d,(65,668),footer,12,AQUA,'mono')
        self.txt(d,(982,668),f'{min(48,max(0,elapsed/FPS)):05.2f} / 48.00 s',12,LIGHT,'mono','ra')
        self.txt(d,(1051,182),'Восемь тембров' if poster else score.section(bar),23,INK,'serif')
        self.txt(d,(1052,217),'МОТИВ  /  ГАРМОНИЯ  /  РИТМ' if poster else f'{score.BARS[bar].chord}   •   ТАКТ {bar+1:02} ИЗ {len(score.BARS)}',13,MUTED,'mono')
        for voice,v in enumerate(score.VOICES):
            y = 254+voice*47
            j = bisect_right(self.starts[voice],elapsed)-1
            event = self.events[voice][j] if j>=0 else None
            age = elapsed-event[0] if event else 1000
            intensity = signal_strength(age,15) if not poster and not after else 0
            d.rounded_rectangle((1049,y,1383,y+39),radius=6,fill='#15282f',outline=rgba(v.color,58+166*intensity))
            if intensity:
                d.rounded_rectangle((1050,y+1,1382,y+38),radius=6,fill=rgba(v.color,40*intensity))
            d.rounded_rectangle((1058,y+9,1061,y+29),radius=1,fill=v.color)
            self.txt(d,(1073,y+11),v.name,15,INK,'bold')
            self.txt(d,(1369,y+10),label_for(event[1]) if intensity else f'{voice+1:02}',15,v.color if intensity else MUTED,'mono','ra')
            if intensity:
                power=min(87,9+77*intensity*event[1].accent)
                d.rectangle((1268,y+29,1268+power,y+30),fill=rgba(v.color,220*intensity))
        d.line((1050,641,1382,641),fill=STROKE)
        self.txt(d,(1050,653),'ТАКТ',11,MUTED,'bold')
        self.txt(d,(1050,666),f'{bar+1:02} / {len(score.BARS)}' if not poster else f'{len(score.BARS)}',18,LIGHT,'mono')
        self.txt(d,(1383,653),'ГОЛОСОВ ЗА РАЗ',11,MUTED,'bold','ra')
        self.txt(d,(1383,666),f'{max(map(len,score.FRAMES)) if poster else len(score.FRAMES[step]) if not (before or after) else 0} / 8',18,AQUA,'mono','ra')
        cursor = self.roll_x(elapsed)
        if not poster:
            d.rectangle((ROLL[0],ROLL[1],cursor,ROLL[3]),fill=rgba(AQUA,12))
            d.line((cursor,ROLL[1]-5,cursor,ROLL[3]+1),fill=GOLD,width=2)
            if not (before or after):
                for note in score.FRAMES[step]:
                    y=ROLL[1]+note.voice*8+2
                    d.rectangle((self.roll_x(ON[step]),y,self.roll_x(ON[step+1])+1,y+4),fill=score.VOICES[note.voice].color)
        return img


def create(args):
    ff = args.ffmpeg or ffmpeg_path()
    mix = audio_mix(ff,args.assets)
    with tempfile.TemporaryDirectory(prefix='moonspire-organ-') as tmp:
        tmp = Path(tmp)
        solo,film_audio = tmp/'score.wav',tmp/'film.wav'
        write_wav(solo,mix)
        subprocess.run([ff,'-v','error','-y','-i',str(solo),'-codec:a','libmp3lame','-b:a','256k',
                        '-metadata',f'title={score.SONG}','-metadata',f'album={score.TITLE}',
                        '-metadata','artist=Moonspire',str(args.mp3)],check=True)
        write_wav(film_audio,np.pad(mix,((INTRO_FRAMES*RATE//FPS,0),(0,0))))
        print(f'Mixed {len(mix)/RATE:.2f}s, peak {np.max(np.abs(mix)):.3f}',flush=True)
        art = Film(args.schematic,args.assets,args.fonts)
        art.frame(0,poster=True).save(args.poster,quality=94,subsampling=0,optimize=True)
        if args.still_only:
            art.frame(INTRO_FRAMES+ON[16*16]+31).save(tmp/'action.jpg',quality=94)
            shutil.copyfile(tmp/'action.jpg',args.poster.with_name(args.poster.stem+'-playing.jpg'))
            return
        cmd = [ff,'-v','warning','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{SIZE[0]}x{SIZE[1]}',
               '-r',str(FPS),'-i','pipe:0','-i',str(film_audio),'-map','0:v:0','-map','1:a:0',
               '-c:v','libx264','-threads','2','-preset','medium','-crf','18','-pix_fmt','yuv420p',
               '-c:a','aac','-b:a','224k','-movflags','+faststart',str(args.mp4)]
        with subprocess.Popen(cmd,stdin=subprocess.PIPE) as enc:
            try:
                for i in range(INTRO_FRAMES+ON[-1]+TAIL_FRAMES):
                    enc.stdin.write(art.frame(i).tobytes())
                    if i%240==0:
                        print(f'Video frame {i}/{INTRO_FRAMES+ON[-1]+TAIL_FRAMES}',flush=True)
            finally:
                enc.stdin.close()
            if enc.wait()!=0:
                raise RuntimeError('ffmpeg could not encode the synchronized video')
        print(f'{args.mp4}: {DURATION:.2f}s; {args.mp3}',flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('assets',type=Path,help='Minecraft Java 26.3 assets/minecraft directory')
    p.add_argument('--schematic',type=Path,default=design.OUTPUT)
    p.add_argument('--fonts',type=Path,default=FONTS)
    p.add_argument('--poster',type=Path,default=design.POSTER)
    p.add_argument('--mp4',type=Path,default=VIDEO)
    p.add_argument('--mp3',type=Path,default=AUDIO)
    p.add_argument('--ffmpeg',help='FFmpeg executable (system or imageio-ffmpeg otherwise)')
    p.add_argument('--still-only',action='store_true',help='Mix audio and preview two still frames without encoding video')
    create(p.parse_args())


if __name__=='__main__':
    main()
