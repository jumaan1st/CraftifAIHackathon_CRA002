"""Create a narrated product explanation, not a recording of physical hardware."""
from pathlib import Path
import json,subprocess,wave
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
scenes=json.loads((ROOT/'docs/mentor-video-scenes.json').read_text())
out=ROOT/'docs/mentor-video';out.mkdir(exist_ok=True)
voice=[];durations=[]
for i in range(len(scenes)):
    with wave.open(str(out/f'voice-{i}.wav'),'rb') as w:
        params=w.getparams();voice.append(w.readframes(w.getnframes()));durations.append(w.getnframes()/w.getframerate())
with wave.open(str(out/'narration.wav'),'wb') as w:
    w.setparams(params)
    for data in voice:w.writeframes(data)
fontroot=Path('C:/Windows/Fonts')
def font(size,bold=False):return ImageFont.truetype(str(fontroot/('segoeuib.ttf' if bold else 'segoeui.ttf')),size)
output=ROOT/'docs/SmartGate-mentor-explanation.mp4'
cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r','15','-i','-', '-i',str(out/'narration.wav'),'-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-shortest','-movflags','+faststart',str(output)]
process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
for i,(scene,duration) in enumerate(zip(scenes,durations)):
    image=Image.new('RGB',(1280,720),'#0b1625');d=ImageDraw.Draw(image)
    d.rounded_rectangle((38,38,1242,682),radius=24,fill='#10283b',outline='#285063',width=2)
    d.text((82,80),scene['tag'],font=font(20,True),fill='#56dfbd')
    title=scene['title']
    words=title.split();lines=['']
    for word in words:
        candidate=(lines[-1]+' '+word).strip()
        if d.textlength(candidate,font=font(45,True))>1060:lines.append(word)
        else:lines[-1]=candidate
    y=140
    for line in lines:d.text((82,y),line,font=font(45,True),fill='#e6edf6');y+=58
    y=max(y+35,295)
    for n,line in enumerate(scene['body']):
        d.rounded_rectangle((82,y,126,y+44),radius=10,fill='#1f675f')
        d.text((95,y+5),str(n+1),font=font(23,True),fill='#b8ffe7')
        d.text((150,y+3),line,font=font(29),fill='#c2d4e3');y+=77
    d.text((82,595),'PRODUCT EXPLANATION  /  SYNTHETIC NARRATION',font=font(16),fill='#9bb0c5')
    d.text((82,623),'Software prototype. Physical cameras, lights and sirens are not connected.',font=font(16),fill='#9bb0c5')
    for n in range(len(scenes)):
        d.rounded_rectangle((986+n*30,626,1005+n*30,633),radius=3,fill='#56dfbd' if n==i else '#285063')
    image.save(out/f'slide-{i}.png')
    data=image.tobytes()
    for _ in range(round(duration*15)):process.stdin.write(data)
process.stdin.close();code=process.wait()
if code:raise RuntimeError(f'Encoder failed: {code}')
print(output)
