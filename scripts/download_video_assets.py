"""Fetch the known demo clip and original detector weights, never user-supplied URLs."""
from pathlib import Path
import hashlib
import json
import requests

ROOT=Path(__file__).resolve().parents[1]
ASSETS={
    'data/videos/corridor-stock.mp4':'https://videos.pexels.com/video-files/7599307/7599307-uhd_2732_1440_25fps.mp4',
    'models/yolov4-tiny.cfg':'https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg',
    'models/yolov4-tiny.weights':'https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v4_pre/yolov4-tiny.weights',
    'data/videos/parking-entrance.mp4':'https://videos.pexels.com/video-files/37508953/15891531_3840_2160_60fps.mp4',
}
def main():
    manifest=[]
    for name,url in ASSETS.items():
        destination=ROOT/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():
            temp=destination.with_suffix(destination.suffix+'.part')
            with requests.get(url,stream=True,timeout=(20,120)) as response:
                response.raise_for_status()
                count=0
                with temp.open('wb') as f:
                    for chunk in response.iter_content(1024*1024):
                        count+=len(chunk)
                        if count>250*1024*1024:
                            raise ValueError('Asset exceeded the download size limit')
                        f.write(chunk)
            temp.replace(destination)
        manifest.append({'path':name,'url':url,'bytes':destination.stat().st_size,
                         'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
        print(name,destination.stat().st_size,flush=True)
    (ROOT/'docs'/'video-assets.json').write_text(json.dumps(manifest,indent=2))
    prepare_analysis_video()

def prepare_analysis_video():
    """Small local derivative for CPU analysis; keep the original for native playback."""
    import cv2
    cv2.setNumThreads(2)
    source=ROOT/'data/videos/parking-entrance.mp4'
    target=ROOT/'data/videos/parking-entrance-analysis.mp4'
    if target.exists():
        return
    cap=cv2.VideoCapture(str(source))
    fps=cap.get(cv2.CAP_PROP_FPS)
    total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not cap.isOpened() or fps<=0:
        raise ValueError('Cannot decode downloaded video')
    writer=cv2.VideoWriter(str(target),cv2.VideoWriter_fourcc(*'mp4v'),4,(960,540))
    if not writer.isOpened():
        cap.release()
        raise ValueError('Cannot create CPU analysis proxy')
    try:
        for frame_number in range(0,total,max(1,round(fps/4))):
            cap.set(cv2.CAP_PROP_POS_FRAMES,frame_number)
            ok,frame=cap.read()
            if not ok: break
            writer.write(cv2.resize(frame,(960,540)))
    finally:
        writer.release()
        cap.release()
    print('CPU analysis proxy ready',target.stat().st_size,flush=True)
if __name__=='__main__':
    main()
