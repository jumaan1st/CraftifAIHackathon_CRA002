from pathlib import Path
import json
import sqlite3
import pandas as pd
import streamlit as st
import smartgate as sg
from simulation_ui import render_simulator
from vision.pipegen_adapter import load_events
from video_ui import render_video
from corridor_ui import render_security

ROOT=Path(__file__).parent
st.set_page_config(page_title='SmartGate AI · Gate simulation',page_icon='🚦',layout='wide')
sg.initialize()
st.markdown('''<style>
.stApp {background:#0b1625;color:#e6edf6}
.block-container {padding-top:2rem;padding-bottom:2rem;max-width:1550px}
[data-testid="stMetric"] {background:#12283b;border:1px solid #254259;border-radius:14px;padding:15px 18px}
[data-testid="stMetricLabel"] {color:#a9becf}
[data-testid="stMetricValue"] {font-size:1.8rem}
[data-testid="stSidebar"] {background:#102033;border-right:1px solid #263c51}
h1,h2,h3 {letter-spacing:-.035em} h1 {font-size:2.5rem!important}
.eyebrow {color:#56dfbd;font-size:11px;letter-spacing:3px;font-weight:700;margin:8px 0}
.stButton>button {border-radius:10px;min-height:46px}
.stCaption {color:#a5b9ca} [data-testid="stAlert"] {border-radius:12px}
</style>''',unsafe_allow_html=True)

with st.sidebar:
    st.markdown('## 🚦 SmartGate AI')
    st.caption('SEE. VERIFY. MOVE.')
    st.divider()
    page=st.radio('Workspace',['Live Simulator','Video Gate','Private Corridor & CCTV','Overview','Vehicle Registry','Access Logs','Vision Integration','Competition Readiness','Architecture'],label_visibility='collapsed',key='workspace')
    st.divider()
    st.markdown('**DEMO ENVIRONMENT**')
    st.caption('Cedar Residences · Bengaluru')
    st.caption('Animated software gate. Fictional vehicles and residents. Sample plates are not OCR results.')
    st.markdown('🟢 **SQLite audit connected**')
    st.caption('Video Gate: CUDA / CPU vehicle detection · plates manually assigned')

st.markdown('<div class="eyebrow">SMARTGATE AI / COMMUNITY ACCESS</div>',unsafe_allow_html=True)
st.title(page if page!='Live Simulator' else 'A smarter welcome. A safer gate.')
apartments=sg.rows('apartments')
vehicles=sg.rows('vehicles')
requests=sg.rows('requests')
logs=sg.rows('logs')
visits=sg.rows('visits')
apt_map={a['id']:f"{a['block_name']}-{a['flat_number']} · {a['resident_name']}" for a in apartments}

if page=='Live Simulator':
    def open_video():
        st.session_state['workspace']='Video Gate'
    st.button('🎬 Open Video Gate · use footage or upload your own',on_click=open_video)
    render_simulator(apartments)
elif page=='Video Gate':
    render_video()
elif page=='Private Corridor & CCTV':
    render_security()
elif page=='Overview':
    st.caption('An operational summary of recorded visits and access decisions.')
    cols=st.columns(4)
    for col,label,value in zip(cols,['Vehicles inside','Completed entries','Completed exits','Pending decisions'],[
        sum(not v['exit_time'] for v in visits),len(visits),sum(bool(v['exit_time']) for v in visits),
        sum(r['status']=='PENDING' for r in requests)]):
        col.metric(label,value)
    st.subheader('Visit register')
    if visits:
        st.dataframe(pd.DataFrame(visits),hide_index=True,width='stretch')
    else:
        st.info('Open Live Simulator and press Play full entry + exit demo to create your first complete visit.')
    st.subheader('How it works')
    st.markdown('**Detect → Check → Authorize → Open → Cross → Close → Record**')
    st.write('A registered vehicle follows the demo entry policy. Unknown, visitor, delivery and unreadable arrivals wait behind a closed barrier for a fictional resident’s decision. Only completed crossings affect occupancy. Exit closes the original visit.')
    st.caption('Permission is not proof of entry. Audit decisions and completed crossings are stored separately.')
elif page=='Vehicle Registry':
    st.caption('Fictional apartment directory and vehicle entry permissions.')
    display=pd.DataFrame(vehicles)
    display['Permission']=display['is_active'].map({1:'Active',0:'Revoked'})
    st.dataframe(display[['registration_number','vehicle_type','block_name','flat_number','resident_name','Permission']],hide_index=True,width='stretch')
    st.subheader('Add a demo vehicle')
    with st.form('registry',clear_on_submit=True):
        a,b=st.columns(2)
        plate=a.text_input('Registration number',placeholder='KA06MN2468')
        vehicle_type=b.selectbox('Vehicle type',['car','motorcycle','truck','bus'])
        apt=st.selectbox('Apartment / resident',list(apt_map),format_func=apt_map.get)
        active=st.checkbox('Active entry permission',value=True)
        if st.form_submit_button('Save vehicle',type='primary'):
            try:
                sg.add_vehicle(plate,vehicle_type,apt,active)
                st.rerun()
            except (ValueError,sqlite3.IntegrityError) as exc:
                st.error('This registration already exists or the apartment is invalid.' if isinstance(exc,sqlite3.IntegrityError) else str(exc))
    with st.expander('Apartment directory'):
        st.dataframe(pd.DataFrame(apartments),hide_index=True,width='stretch')
elif page=='Access Logs':
    st.caption('Every arrival, access decision, barrier opening, crossing and closure.')
    left,right=st.columns(2)
    timezone=left.selectbox('Display timezone',['Asia/Kolkata','UTC'])
    plate_filter=right.text_input('Find a plate',placeholder='KA01AB1234')
    a,b,c=st.columns(3)
    status=a.multiselect('Result',sorted({r['authorization_status'] for r in logs}))
    types=b.multiselect('Activity',sorted({r['event_type'] for r in logs}))
    direction=c.multiselect('Movement',['ENTRY','EXIT'])
    directions={r['event_id']:r['direction'] for r in requests}
    filtered=[dict(r,direction=directions.get(r['event_id'],'ENTRY')) for r in logs if
        (not status or r['authorization_status'] in status) and
        (not types or r['event_type'] in types) and
        (not direction or directions.get(r['event_id'],'ENTRY') in direction) and
        sg.normalize(plate_filter) in (r['registration_number'] or '')]
    df=pd.DataFrame(filtered)
    if not df.empty:
        shown=df.copy()
        shown['timestamp']=pd.to_datetime(shown['timestamp'],utc=True).dt.tz_convert(timezone).dt.strftime('%d %b %Y · %H:%M:%S')
        st.dataframe(shown[['timestamp','direction','registration_number','event_type','authorization_status','reason','source']],hide_index=True,width='stretch')
    else:
        st.info('No matching events. Run a gate simulation or adjust these filters.')
    st.caption(f'{len(filtered)} matching audit events · downloads preserve UTC timestamps and event IDs')
    a,b=st.columns(2)
    a.download_button('↓ Download audit CSV',df.to_csv(index=False),'smartgate-audit.csv','text/csv',width='stretch')
    b.download_button('↓ Download audit JSON',json.dumps(filtered,indent=2),'smartgate-audit.json','application/json',width='stretch')
elif page=='Vision Integration':
    st.caption('The same authorization and gate services can consume real external vision events.')
    st.info('This page imports external pipeline events. Video Gate separately runs local CPU vehicle detection. Neither mode includes plate OCR; imported source labels are producer claims, not independent proof of inference.')
    upload=st.file_uploader('Load pipeline JSON events',type=['json'])
    if upload:
        try:
            events=load_events(upload.getvalue())
            index=st.selectbox('Select event',range(len(events)),format_func=lambda i:events[i]['event_id'])
            st.json(events[index])
            if st.button('Apply event to gate',type='primary'):
                result=sg.process_event(events[index])
                st.success(f"{result['status']} · {result['reason']}")
                st.info('Open Live Simulator to complete the gate cycle or approve the waiting vehicle.')
        except (ValueError,UnicodeError) as exc:
            st.error(str(exc))
    st.download_button('Download sample event contract',(ROOT/'data'/'sample_events.json').read_bytes(),'sample_events.json','application/json')
    with st.expander('Reference footage · playback only'):
        video=st.file_uploader('Video file',type=['mp4','webm'])
        if video:
            st.video(video)
            st.caption('Playback only; this upload does not run inference.')
    st.markdown((ROOT/'docs'/'gpu-handoff.md').read_text(encoding='utf-8'))
elif page=='Competition Readiness':
    st.caption('Track A · completion status is backed by actual artifacts, not presentation labels.')
    st.success('Application demo ready: animated entry + exit, resident decisions, visit register and persistent audit exports.')
    gpu_path=ROOT/'docs/gpu-verification.json'
    if gpu_path.exists():
        gpu=json.loads(gpu_path.read_text())
        if gpu.get('verified_cuda'):
            st.success('Laptop GPU verified: '+gpu['hardware'])
            a,b,c=st.columns(3)
            gpu_ms=gpu['CUDAExecutionProvider']['mean_ms']
            cpu_ms=gpu['CPUExecutionProvider']['mean_ms']
            a.metric('CUDA mean',f'{gpu_ms:.1f} ms')
            b.metric('CPU mean · same model',f'{cpu_ms:.1f} ms')
            c.metric('Measured speed ratio',f'{cpu_ms/gpu_ms:.1f}×')
            st.caption(gpu['measurement']+'. Native CUDA evidence; this is not a PipeGen speed report or TensorRT engine.')
            st.download_button('Download verified CUDA evidence',gpu_path.read_bytes(),'gpu-verification.json','application/json')
    setup_path=ROOT/'docs/pipegen-installation.json'
    if setup_path.exists():
        setup=json.loads(setup_path.read_text())
        st.info(f"PipeGen {setup['installed_version']} installed in {setup['distribution']} · runtime: {setup['runtime_status']}.")
    playback_path=ROOT/'docs/gpu-video-verification.json'
    if playback_path.exists() and json.loads(playback_path.read_text()).get('passed'):
        st.success('Full CUDA sample checks passed: entry, matching exit and access denied; 75 decoded frames per scenario. Gate timing and identities remain simulated.')
    st.warning('Track A technical requirements are still incomplete until the real GPU run and its evidence are collected.')
    st.dataframe(pd.DataFrame([
        {'Requirement':'All five PipeGen stages','Status':'Needs real run','Evidence':'Requirement → PIR → Model → Compiler → Run'},
        {'Requirement':'TensorRT compilation','Status':'Needs real run','Evidence':'Engine and PipeGen speed report'},
        {'Requirement':'Video pipeline on NVIDIA GPU / Jetson','Status':'Needs real run','Evidence':'Live video-file or camera demonstration'},
        {'Requirement':'Actionable output','Status':'App ready; real integration unverified','Evidence':'Real JSON events drive gate authorization and logs'},
        {'Requirement':'Source + PipeGen export folder','Status':'App source ready; export missing','Evidence':'Repository URL and actual generated export'},
        {'Requirement':'Graph + speed screenshots','Status':'Not collected','Evidence':'Real PIR graph and speed report screenshots'},
    ]),hide_index=True,width='stretch')
    st.subheader('Your next move')
    st.write('Run PipeGen in the prepared laptop Ubuntu environment, using the brief in Vision Integration. Feed its real JSON output into this app, complete the gate cycle, then collect the graph, speed report, export folder and demo recording.')
    st.download_button('↓ PipeGen execution brief',(ROOT/'docs'/'gpu-handoff.md').read_bytes(),'smartgate-gpu-handoff.md','text/markdown')
    st.download_button('↓ Judge presentation script',(ROOT/'docs'/'pitch.md').read_bytes(),'smartgate-pitch.md','text/markdown')
    with st.expander('Read the 90-second pitch'):
        st.markdown((ROOT/'docs'/'pitch.md').read_text(encoding='utf-8'))
else:
    st.markdown((ROOT/'docs'/'architecture.md').read_text(encoding='utf-8'))
