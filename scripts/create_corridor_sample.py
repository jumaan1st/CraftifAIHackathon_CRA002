"""Generate an explicitly synthetic corridor clip for frame-motion demonstrations."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import math,subprocess,json
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'data/videos/corridor-demo.mp4'
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
base=Image.new('RGB',(960,540),'#7c8387');d=ImageDraw.Draw(base)
d.polygon([(0,0),(960,0),(600,190),(360,190)],fill='#bfc7cc')
d.polygon([(0,540),(960,540),(600,320),(360,320)],fill='#777b7d')
d.polygon([(0,0),(360,190),(360,320),(0,540)],fill='#d9d9d0')
d.polygon([(960,0),(600,190),(600,320),(960,540)],fill='#c2c7c6')
d.rectangle((360,190,600,320),fill='#8e9b9f');d.rectangle((435,202,525,319),fill='#465d65')
for x,y,w,h in [(35,115,100,300),(230,180,55,165),(815,115,100,300),(675,180,55,165)]:
 d.rectangle((x,y,x+w,y+h),fill='#52616b',outline='#344954',width=5)
 d.ellipse((x+w-16,y+h//2,x+w-9,y+h//2+7),fill='#ddc36b')
for y,width in [(360,160),(415,275),(490,430)]:d.line((480-width,y,480+width,y),fill='#a5a7a3',width=2)
d.rectangle((380,45,580,63),fill='#ffffe7');d.rectangle((431,125,529,137),fill='#ffffe7')
cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s','960x540','-r','12','-i','-','-an','-c:v','libx264','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(p)]
proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
for n in range(216):
 t=n/12;im=base.copy();d=ImageDraw.Draw(im)
 if 3<t<13:
  x=int(115+(t-3)*70);y=335
  step=math.sin(t*8)*19
  d.ellipse((x-18,y-155,x+18,y-119),fill='#b08c74')
  d.rounded_rectangle((x-28,y-120,x+28,y-25),radius=15,fill='#213b63')
  d.line((x-13,y-25,x-17+step,y+55),fill='#263443',width=18)
  d.line((x+13,y-25,x+17-step,y+55),fill='#263443',width=18)
  d.line((x-26,y-100,x-42-step,y-37),fill='#2f4c75',width=13)
  d.line((x+26,y-100,x+42+step,y-37),fill='#2f4c75',width=13)
 d.rectangle((0,0,960,34),fill='#102033');d.text((14,5),'CORRIDOR CAMERA / GENERATED MOTION DEMO',font=font,fill='#d8f6ed')
 d.rectangle((0,506,960,540),fill='#102033');d.text((14,512),'Synthetic animation • real frame-motion analysis • not recorded CCTV',font=font,fill='#b8cad7')
 proc.stdin.write(im.tobytes())
proc.stdin.close();assert proc.wait()==0
(ROOT/'docs/corridor-sample.json').write_text(json.dumps({'file':str(p.relative_to(ROOT)),'type':'Generated animation, not recorded CCTV','duration_seconds':18,'purpose':'Motion alarm demonstration; person detection accuracy on this animation is not asserted','creator':'SmartGate demo renderer'},indent=2))
print(p)
