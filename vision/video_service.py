"""Genuine CPU detections; identity and the physical passage timer remain explicit simulations."""
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock,RLock
from functools import wraps
from uuid import uuid4
import json
import time
import math
import cv2
import smartgate as sg

ROOT=Path(__file__).resolve().parents[1]
VEHICLES={2:'car',3:'motorcycle',5:'bus',7:'truck'}

def synchronized(method):
    @wraps(method)
    def wrapped(self,*args,**kwargs):
        with self.lock:
            return method(self,*args,**kwargs)
    return wrapped

class VehicleDetector:
    name='YOLOv4-tiny / OpenCV DNN CPU'
    source='cpu_vision'
    def __init__(self):
        cv2.setNumThreads(2)
        cfg=ROOT/'models'/'yolov4-tiny.cfg'
        weights=ROOT/'models'/'yolov4-tiny.weights'
        if not cfg.exists() or not weights.exists():
            raise ValueError('Detector assets missing. Run: .venv\\Scripts\\python.exe scripts/download_video_assets.py')
        self.model=cv2.dnn_DetectionModel(str(weights),str(cfg))
        self.model.setInputParams(size=(416,416),scale=1/255,swapRB=True,crop=False)
        self.lock=Lock()

    def detect(self, frame, threshold=.35, class_map=None):
        class_map=VEHICLES if class_map is None else class_map
        with self.lock:
            classes,scores,boxes=self.model.detect(frame,confThreshold=threshold,nmsThreshold=.45)
        return [{'vehicle_type':class_map[int(cid)],'confidence':float(score),'box':[int(x) for x in box]}
                for cid,score,box in zip(classes,scores,boxes) if int(cid) in class_map]

@dataclass
class VideoRun:
    path: Path
    filename: str
    plate: str | None
    visit_type: str='resident'
    direction: str='ENTRY'
    presence_id: int | None=None
    backend: str='CPU'
    run_id: str=field(default_factory=lambda:uuid4().hex)
    playing: bool=True
    ended: bool=False
    phase: str='SCANNING'
    request_id: str | None=None
    activated: float | None=None
    paused_at: float | None=None
    source_seconds: float=0
    detections: list=field(default_factory=list)
    samples: list=field(default_factory=list)
    message: str='Waiting for a detected vehicle'
    passage_saved: bool=False
    frame: object=None
    error: str | None=None
    detector_name: str='YOLOv4-tiny / OpenCV DNN CPU'
    detection_source: str='cpu_vision'
    lock: object=field(default_factory=RLock,repr=False)

    def __post_init__(self):
        self.path=Path(self.path)
        self.capture=cv2.VideoCapture(str(self.path))
        if not self.capture.isOpened():
            self.capture.release()
            raise ValueError('Cannot decode this video. Try an MP4 encoded with H.264.')
        self.fps=float(self.capture.get(cv2.CAP_PROP_FPS)) or 25
        if not 0 < self.fps < 1000:
            self.fps=25
        self.total_frames=int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.next_frame=0
        self.read_frame()
        if self.frame is None:
            self.capture.release()
            raise ValueError('Video contains no readable frames.')

    @synchronized
    def read_frame(self):
        if self.ended:
            return
        if abs(self.capture.get(cv2.CAP_PROP_POS_FRAMES)-self.next_frame)>.5:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES,self.next_frame)
        ok,frame=self.capture.read()
        if not ok:
            self.ended=True
            return
        height,width=frame.shape[:2]
        self.frame=cv2.resize(frame,(960,max(1,round(height*960/width))))
        self.source_seconds=self.next_frame/self.fps
        self.next_frame+=max(1,round(self.fps/4))

    def request(self,path=sg.DB):
        return next((r for r in sg.rows('requests',path) if r['event_id']==self.request_id),None)

    def trigger(self,detection,clock,path):
        event={'event_id':'video-'+self.run_id,'source':self.detection_source,'number_plate':self.plate,
               'visit_type':self.visit_type,'direction':self.direction,'presence_id':self.presence_id,
               'vehicle_type':detection['vehicle_type'],'confidence':None,
               'tracking_id':'video-first-detection'}
        # This is one explicitly operator-assigned identity per run, not per-object OCR or tracking.
        request=sg.process_event(event,path)
        self.request_id=request['event_id']
        self.activated=clock
        self.phase='OPENING' if request['status']=='AUTHORIZED' else 'WAITING' if request['status']=='PENDING' else 'REJECTED'
        self.message=request['reason']

    @synchronized
    def tick(self,detector,clock=None,path=sg.DB):
        if not self.playing:
            return
        clock=time.monotonic() if clock is None else clock
        self.detector_name=getattr(detector,'name','YOLOv4-tiny / OpenCV DNN CPU')
        self.detection_source=getattr(detector,'source','cpu_vision')
        if not self.ended:
            self.detections=detector.detect(self.frame)
            if self.detections:
                self.samples.append({'video_seconds':round(self.source_seconds,2),'detections':self.detections})
                if not self.request_id:
                    try:
                        self.trigger(max(self.detections,key=lambda d:d['box'][2]*d['box'][3]),clock,path)
                    except ValueError as exc:
                        self.error=str(exc)
                        self.playing=False
                        self.phase='CLOSED'
                        return
        if self.request_id and self.phase not in ('COMPLETE','REJECTED','WAITING'):
            request=self.request(path)
            gate=sg.rows('gate',path)[0]
            if not request or gate['event_id']!=self.request_id or request['status']!='AUTHORIZED':
                self.error='This gate cycle changed in another screen. Stop and start a new run.'
                self.playing=False
                return
            elapsed=clock-self.activated
            if elapsed<.9:
                self.phase='OPENING'; self.message='Vehicle detected · authorization granted · opening virtual gate'
            elif elapsed<1.8:
                self.phase='OPEN'; self.message='Gate OPEN · simulated vehicle passage begins'
            elif elapsed<3:
                self.phase='CROSSING'; self.message='Passage timer running · physical crossing is simulated'
            elif elapsed<4:
                if not self.passage_saved:
                    sg.record_passage(self.request_id,path)
                    self.passage_saved=True
                self.phase='CLOSING'; self.message='Visit updated · closing virtual gate'
            else:
                # Handles a slow/inactive browser jumping directly beyond the passage interval.
                if not self.passage_saved:
                    sg.record_passage(self.request_id,path)
                    self.passage_saved=True
                sg.close_gate(path,expected_event_id=self.request_id)
                self.phase='COMPLETE'; self.message='Gate CLOSED · decision and completed visit saved'
        elif self.phase=='REJECTED' and self.request_id:
            gate=sg.rows('gate',path)[0]
            if gate['event_id']==self.request_id:
                sg.close_gate(path,expected_event_id=self.request_id)
            self.message='ACCESS DENIED · virtual gate stays CLOSED · denial saved'
        if self.ended and self.phase!='WAITING' and (not self.request_id or self.phase in ('COMPLETE','REJECTED')):
            self.playing=False
            self.capture.release()
            if not self.request_id:
                self.message='Video finished · no vehicle detected · gate stayed CLOSED'
        self.save_report()

    @synchronized
    def advance_frame(self):
        if self.playing and not self.ended:
            self.read_frame()

    @synchronized
    def resolve(self,approve,apartment_id,clock=None,path=sg.DB):
        if self.phase!='WAITING':
            raise ValueError('This video request is not waiting for approval.')
        sg.resolve(self.request_id,approve,apartment_id,path=path)
        self.activated=time.monotonic() if clock is None else clock
        self.phase='OPENING' if approve else 'REJECTED'
        self.playing=True
        self.paused_at=None

    @synchronized
    def pause(self,clock=None):
        if self.playing:
            self.playing=False
            self.paused_at=time.monotonic() if clock is None else clock

    @synchronized
    def resume(self,clock=None):
        if self.ended and self.phase in ('COMPLETE','REJECTED'):
            return
        clock=time.monotonic() if clock is None else clock
        if self.paused_at is not None and self.activated is not None:
            self.activated+=clock-self.paused_at
        self.paused_at=None
        self.playing=True

    @synchronized
    def stop(self,path=sg.DB):
        gate=sg.rows('gate',path)[0]
        if self.request_id and gate['event_id']==self.request_id:
            sg.close_gate(path,expected_event_id=self.request_id)
        self.playing=False
        self.capture.release()
        self.phase='STOPPED'
        self.message='Playback stopped · gate closed · completed passages preserved'
        self.save_report()

    def save_report(self):
        output=ROOT/'data'/'video_reports'
        output.mkdir(parents=True,exist_ok=True)
        report={'run_id':self.run_id,'filename':self.filename,'event_id':self.request_id,
                'detector':self.detector_name,'backend':self.backend,'source':self.detection_source,'plate_source':'operator-assigned demo identity; no OCR',
                'assigned_plate':self.plate,'direction':self.direction,'phase':self.phase,
                'passage':'software timer, not a measured physical crossing','samples':self.samples}
        (output/(self.run_id+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')

def annotated_frame(run):
    image=run.frame.copy()
    for d in run.detections:
        x,y,w,h=d['box']
        cv2.rectangle(image,(x,y),(x+w,y+h),(80,225,160),2)
        label=f"{d['vehicle_type']} {d['confidence']:.0%}"
        cv2.putText(image,label,(max(0,x),max(20,y-8)),cv2.FONT_HERSHEY_SIMPLEX,.65,(80,225,160),2)
    color=(70,210,130) if run.phase in ('OPENING','OPEN','CROSSING','CLOSING','COMPLETE') else (60,90,240)
    cv2.rectangle(image,(0,0),(image.shape[1],48),(20,30,45),-1)
    gate_label=run.phase if run.phase in ('OPENING','OPEN','CROSSING','CLOSING') else 'CLOSED'
    label=f"VIDEO {run.source_seconds:.1f}s  |  GATE {gate_label}  |  {run.phase}"
    cv2.putText(image,label,(15,31),cv2.FONT_HERSHEY_SIMPLEX,.65,color,2)
    # A labelled software barrier on the footage; this does not alter a real gate.
    height,width=image.shape[:2]
    panel_w=min(290,width-20); panel_h=min(185,height-65)
    x0,y0=width-panel_w-10,height-panel_h-10
    overlay=image.copy()
    cv2.rectangle(overlay,(x0,y0),(width-10,height-10),(25,40,55),-1)
    image=cv2.addWeighted(overlay,.88,image,.12,0)
    elapsed=max(0,time.monotonic()-run.activated) if run.activated is not None else 0
    if run.phase=='OPENING':fraction=min(1,elapsed/.9)
    elif run.phase in ('OPEN','CROSSING'):fraction=1
    elif run.phase=='CLOSING':fraction=max(0,1-(elapsed-3))
    else:fraction=0
    angle=fraction*math.pi/2
    pivot=(x0+40,height-45);length=min(130,panel_w-70,panel_h-65)
    tip=(int(pivot[0]+length*math.cos(angle)),int(pivot[1]-length*math.sin(angle)))
    cv2.putText(image,'VIRTUAL GATE',(x0+13,y0+25),cv2.FONT_HERSHEY_SIMPLEX,.5,(200,230,235),1)
    cv2.rectangle(image,(pivot[0]-9,pivot[1]-12),(pivot[0]+9,height-20),(160,180,195),-1)
    cv2.line(image,pivot,tip,(80,225,160) if fraction>.5 else (90,195,250),10)
    cv2.circle(image,pivot,7,(225,235,240),-1)
    cv2.putText(image,gate_label,(x0+13,height-17),cv2.FONT_HERSHEY_SIMPLEX,.45,(200,230,235),1)
    return image
