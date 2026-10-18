"""Local uploaded-video surveillance demo; no physical camera or alarm connection."""
from pathlib import Path
from uuid import uuid4
import hashlib,json,time,io,wave,struct
import cv2
import numpy as np
import pandas as pd
import streamlit as st
import smartgate as sg
from video_ui import detector
from vision.video_service import VideoRun

ROOT=Path(__file__).parent

def soft_alarm_wav(token='preview'):
    """Three short, low-amplitude beeps; token gives each incident a fresh audio URL."""
    rate=22050
    samples=np.zeros(int(rate*1.25),dtype=np.float64)
    length=int(rate*.18)
    envelope=np.sin(np.linspace(0,np.pi,length))**2
    tone=.08*np.sin(2*np.pi*880*np.arange(length)/rate)*envelope
    for start in (.05,.43,.81):
        offset=int(start*rate);samples[offset:offset+length]=tone
    output=io.BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(rate)
        audio.writeframes((samples*32767).astype('<i2').tobytes())
    data=output.getvalue()
    marker=str(token).encode('ascii',errors='ignore')[:64]
    extra=b'JUNK'+struct.pack('<I',len(marker))+marker+b'\0'*(len(marker)%2)
    data=data[:4]+struct.pack('<I',len(data)+len(extra)-8)+data[8:]+extra
    return data

def initialize(path=sg.DB):
    with sg.connect(path) as con:
        con.execute('CREATE TABLE IF NOT EXISTS security_incidents (id TEXT PRIMARY KEY, timestamp TEXT, zone TEXT, trigger TEXT, video_seconds REAL, people INTEGER, motion_percent REAL, backend TEXT, status TEXT)')

def incident(zone,trigger,seconds,people,motion,backend,path=sg.DB):
    initialize(path)
    with sg.connect(path) as con:
        con.execute('INSERT INTO security_incidents VALUES (?,?,?,?,?,?,?,?,?)',
            (uuid4().hex,sg.now(),zone,trigger,seconds,people,motion,backend,'NEW'))

def incidents(path=sg.DB):
    initialize(path)
    with sg.connect(path) as con:
        return [dict(r) for r in con.execute('SELECT * FROM security_incidents ORDER BY timestamp DESC')]

class MotionMonitor:
    def __init__(self):
        self.previous=None
    def measure(self,frame):
        gray=cv2.GaussianBlur(cv2.cvtColor(cv2.resize(frame,(320,180)),cv2.COLOR_BGR2GRAY),(7,7),0)
        if self.previous is None:
            self.previous=gray
            return 0.
        delta=cv2.absdiff(gray,self.previous)
        self.previous=gray
        mask=cv2.threshold(delta,25,255,cv2.THRESH_BINARY)[1]
        return float(np.count_nonzero(mask)*100/mask.size)

def alarm_reason(armed,mode,people,motion,threshold):
    if not armed:return None
    if mode=='People detected' and people:return 'PERSON_DETECTED'
    if mode=='Any movement' and motion>=threshold:return 'MOTION_DETECTED'
    return None

@st.fragment(run_every=.3)
def playback():
    state=st.session_state.get('security_video')
    if not state:return
    run=state['run']
    if run.playing and not run.ended:
        try:
            found=detector(state['backend']).detect(run.frame,class_map={0:'person'})
            motion=state['motion'].measure(run.frame)
            state['people']=len(found); state['motion_percent']=motion
            reason=alarm_reason(state['armed'],state['mode'],len(found),motion,state['threshold'])
            if reason and not state['episode']:
                incident(state['zone'],reason,run.source_seconds,len(found),motion,state['backend'])
                state['alerts']+=1
                if state.get('sound',True):state['alarm_audio']=soft_alarm_wav(uuid4().hex)
                state['episode']=True
                state['quiet']=0
            elif not reason:
                state['quiet']+=1
                if state['quiet']>=4:state['episode']=False
            else:state['quiet']=0
            state['alert']=bool(reason)
            image=run.frame.copy()
            for d in found:
                x,y,w,h=d['box']
                cv2.rectangle(image,(x,y),(x+w,y+h),(80,225,160),2)
                cv2.putText(image,f"PERSON {d['confidence']:.0%}",(max(0,x),max(20,y-7)),cv2.FONT_HERSHEY_SIMPLEX,.6,(80,225,160),2)
            state['image']=image
            run.advance_frame()
            if run.ended:
                with run.lock:
                    run.playing=False;run.capture.release()
        except (ValueError,RuntimeError) as exc:
            run.playing=False;run.capture.release();state['error']=str(exc)
    a,b=st.columns([1.7,1])
    with a:
        st.subheader(state['zone']+' · video monitor')
        st.image(state.get('image',run.frame),channels='BGR',width='stretch')
        st.caption(f"Video {run.source_seconds:.1f}s · {state['backend']} · sampled playback up to 4 fps · no audio")
        if not run.playing:st.caption('Playback paused or finished. Saved incidents remain below.')
    with b:
        if state.get('error'):st.error(state['error'])
        elif state.get('alert'):
            st.error('🚨 ALARM TRIGGERED · simulated security response')
        elif state['armed']:st.success('ARMED · monitoring the selected video')
        else:st.info('DISARMED · detections visible; no incident alarm')
        if state.get('sound') and state.get('alarm_audio'):
            st.audio(state['alarm_audio'],format='audio/wav',autoplay=True)
            st.caption('Soft alert · three short beeps per incident. If sound is blocked, press Play above.')
        st.metric('People visible',state.get('people',0))
        st.metric('Frame movement',f"{state.get('motion_percent',0):.1f}%")
        st.metric('Saved alert episodes',state['alerts'])
        lit=state.get('alert',False)
        st.markdown(f"**Safety light:** {'🟡 ON' if lit else '⚪ OFF'} · simulated")
        st.markdown(f"**Security desk:** {'🔴 Attention required' if lit else '🟢 Monitoring'} · simulated")
        st.caption('People detection does not identify a person or determine whether they are authorized. Motion can include shadows or camera shake. Use a fixed camera for a real deployment.')
    history=incidents()
    st.subheader('Shared security incident timeline')
    if history:
        df=pd.DataFrame(history)
        df['timestamp']=pd.to_datetime(df['timestamp'],utc=True).dt.tz_convert('Asia/Kolkata').dt.strftime('%d %b %H:%M:%S')
        st.dataframe(df.drop(columns=['id']),hide_index=True,width='stretch')
        st.download_button('Download security incidents',pd.DataFrame(history).to_csv(index=False),'security-incidents.csv','text/csv')
        pending=[r for r in history if r['status']=='NEW']
        if pending and st.button('Acknowledge recorded alerts'):
            with sg.connect() as con:con.execute("UPDATE security_incidents SET status='ACKNOWLEDGED' WHERE status='NEW'")
            st.rerun(scope='fragment')
    else:st.caption('An armed detection will create the first incident here.')

def render_security():
    initialize()
    corridor_path=ROOT/'data/videos/corridor-analysis.mp4'
    if not corridor_path.exists():corridor_path=ROOT/'data/videos/corridor-stock.mp4'
    st.caption('One connected smart housing demo: corridor surveillance, parking CCTV and a shared security desk.')
    st.info('Upload a video, arm monitoring and watch real person / frame-motion detection trigger a visual alarm, simulated safety light and persistent incident record. Physical cameras, sirens and notifications are not connected.')
    a,b=st.columns(2)
    zone=a.selectbox('Camera zone',['Private Corridor','Parking CCTV'])
    backend=b.selectbox('Security inference hardware',['NVIDIA GPU (CUDA)','CPU'])
    source=st.radio('Security footage',['Built-in corridor sample','Uploaded video','Use existing parking sample'],horizontal=True)
    upload=None
    if source=='Uploaded video':
        upload=st.file_uploader('Choose your corridor or parking video',type=['mp4','mov','avi','webm'],key='security_upload')
        st.caption('1. Choose a video below. 2. Set your alarm trigger. 3. Press Start security monitoring.')
        if upload is None:st.info('Upload a video here to enable Start security monitoring.')
    selection=(zone,source,upload.name if upload else None,upload.size if upload else None)
    previous=st.session_state.get('security_video')
    if previous and previous.get('selection')!=selection:
        previous['run'].pause()
        with previous['run'].lock:previous['run'].capture.release()
        st.session_state.pop('security_video',None)
    st.markdown('[Hallway sample by cottonbro studio · Pexels](https://www.pexels.com/video/man-walking-in-the-hallway-7599307/) · [License](https://www.pexels.com/license/)')
    st.caption('Stock footage illustrates detection only; it does not imply unauthorized activity by the people shown.')
    if source=='Built-in corridor sample':
        st.caption('Real hallway footage by cottonbro studio / Pexels, downloaded locally. Use Start security monitoring to run detection and save alerts.')
    if source.startswith('Use'):
        st.caption('The sample is parking footage, not a private corridor. Upload a fixed-camera corridor video for that scenario.')
    a,b,c=st.columns([1,1.3,1])
    armed=a.toggle('Arm night security · demo',value=True)
    mode=b.selectbox('Alarm trigger',['People detected','Any movement'],index=1 if source=='Built-in corridor sample' else 0)
    threshold=c.slider('Movement sensitivity · minimum %',.5,20.,2.,.5)
    st.caption('Night mode is manually simulated here. A production installation would use a configured schedule and resident-controlled zones. Video stays on this computer; no face recognition is used.')
    sound=st.toggle('Soft alarm sound',value=True)
    if st.button('🔈 Test soft alarm'):
        st.audio(soft_alarm_wav(uuid4().hex),format='audio/wav',autoplay=True)
    controls=st.columns(3)
    if controls[0].button('▶ Start security monitoring',type='primary',disabled=source=='Uploaded video' and upload is None,width='stretch'):
        try:
            detector(backend)
            old=st.session_state.get('security_video')
            if old:
                old['run'].pause()
                with old['run'].lock:old['run'].capture.release()
            path=corridor_path if source=='Built-in corridor sample' else ROOT/'data/videos/parking-entrance-analysis.mp4'
            if source=='Uploaded video':
                raw=upload.getvalue()
                if len(raw)>200*1024*1024:raise ValueError('Choose a video under 200 MB.')
                path=ROOT/'data/uploads'/(hashlib.sha256(raw).hexdigest()+Path(upload.name).suffix.lower())
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            st.session_state['security_video']={'run':VideoRun(path,path.name,None),'backend':backend,'zone':zone,'armed':armed,'mode':mode,'threshold':threshold,'motion':MotionMonitor(),'episode':False,'quiet':0,'alerts':0,'sound':sound,'alarm_audio':None,'selection':selection}
        except (ValueError,RuntimeError) as exc:st.error(str(exc))
    state=st.session_state.get('security_video')
    if controls[1].button('Ⅱ Pause monitoring',disabled=not state,width='stretch'):state['run'].pause()
    if controls[2].button('▶ Resume monitoring',disabled=not state,width='stretch'):state['run'].resume()
    if state:
        state.update(armed=armed,mode=mode,threshold=threshold,sound=sound)
        if not sound:state['alarm_audio']=None
        playback()
    elif source=='Built-in corridor sample':
        st.video(str(corridor_path))
        st.caption('Preview playback does not trigger an alarm. Select Start security monitoring to analyze the frames and save incidents.')
    elif source=='Uploaded video' and upload:st.video(upload)
    explanation=ROOT/'docs/SmartGate-mentor-explanation.mp4'
    if explanation.exists():
        with st.expander('Play mentor explanation video'):
            st.video(str(explanation))
            st.download_button('Download explanation video',explanation.read_bytes(),'SmartGate-mentor-explanation.mp4','video/mp4')
    with st.expander('Mentor explanation · connected smart housing'):
        st.markdown('''**Gate:** a detected vehicle starts an authorization workflow and records entry / exit.

**Corridor:** armed person or movement detection creates an incident and switches on a simulated safety light.

**Parking:** the same monitoring module covers another camera zone, with incidents in the same security timeline.

**Business model:** offer apartment associations one local security console, priced per community with optional per-camera support. Pilot with a small installation; measure missed alerts, false alarms and guard response time before making savings claims.

**Next hardware step:** connect approved cameras and an MQTT light / siren through a home automation hub. That physical integration is a roadmap item, not implemented in this demo.''')
