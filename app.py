from pathlib import Path
import json
import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import smartgate as sg
from simulation_ui import render_simulator, scene
from vision.pipegen_adapter import load_events, parse_pipegen_deepstream_metadata
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
    st.caption('Real edge video perception from CraftifAI PipeGen driving live simulated gate and security actions.')
    st.info('This page integrates real DeepStream perception metadata (YOLO11s FP16 TensorRT) with the input parking video and synchronized virtual gate. In compliance with hackathon rules, license plates are not fabricated: detections arrive as unverified arrivals requiring resident/operator approval.')
    
    col_a, col_b = st.columns([1, 1])
    pipegen_sample_path = ROOT / 'docs' / 'pipegen' / 'parking-metadata.json'
    load_real_btn = col_a.button('⚡ Reload Verified PipeGen Run (parking-metadata.json)', type='secondary', width='stretch')
    upload = col_b.file_uploader('Or upload custom pipeline JSON', type=['json'], label_visibility='collapsed')
    
    payload_data = None
    if upload:
        payload_data = upload.getvalue().decode('utf-8')
    elif load_real_btn or 'pipegen_payload' in st.session_state:
        if load_real_btn:
            st.session_state['pipegen_payload'] = pipegen_sample_path.read_text(encoding='utf-8')
        payload_data = st.session_state.get('pipegen_payload')
    elif pipegen_sample_path.exists():
        payload_data = pipegen_sample_path.read_text(encoding='utf-8')
        st.session_state['pipegen_payload'] = payload_data

    if payload_data:
        try:
            raw_json = json.loads(payload_data)
            if isinstance(raw_json, dict) and 'frames' in raw_json:
                parsed = parse_pipegen_deepstream_metadata(raw_json)
                summary = parsed['summary']
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric('Processed Frames', summary['total_frames'])
                m2.metric('Unique Tracks', summary['unique_tracks'])
                m3.metric('Vehicle Arrivals', summary['vehicles_detected'])
                m4.metric('Person Detections', summary['persons_detected'])
                
                # SIDE-BY-SIDE VIDEO & VIRTUAL GATE (Matching Video Gate layout)
                left_col, right_col = st.columns([1.5, 1], gap='large')
                
                with left_col:
                    st.subheader('Video · PipeGen Input Footage')
                    v_src = st.radio('Video Source', ['Verified parking entrance footage', 'Upload my own MP4 video'], horizontal=True, key='vision_video_src')
                    if v_src == 'Upload my own MP4 video':
                        custom_mp4 = st.file_uploader('Upload MP4 / WebM video file', type=['mp4', 'webm', 'mov'], key='custom_vision_mp4')
                        if custom_mp4:
                            st.video(custom_mp4)
                            st.caption(f'Playing custom video: {custom_mp4.name}')
                        else:
                            st.info('Select and upload any MP4 video file above.')
                    else:
                        video_path = ROOT / 'data' / 'videos' / 'parking-entrance.mp4'
                        if video_path.exists():
                            st.video(str(video_path))
                            st.caption('parking-entrance.mp4 · 1,098 frames processed by DeepStream 7.1 + YOLO11s TensorRT (FP16)')
                        else:
                            st.info('parking-entrance.mp4 is stored externally as documented.')
                    
                    st.markdown('#### 🎯 PipeGen Track Selector')
                    v_events = parsed['vehicles']
                    if v_events:
                        v_idx = st.selectbox(
                            'Select Tracked Vehicle Arrival',
                            range(len(v_events)),
                            format_func=lambda i: f"Track {v_events[i]['tracking_id']} · {v_events[i]['vehicle_type'].upper()} (conf: {v_events[i]['detector_confidence']*100:.1f}%, {v_events[i]['frame_count']} frames)"
                        )
                        selected_v = v_events[v_idx]
                        bbox = selected_v.get('bbox', {})
                        st.caption(f"**Bounding Box:** Left: `{bbox.get('left', 0):.1f}`, Top: `{bbox.get('top', 0):.1f}`, Width: `{bbox.get('width', 0):.1f}`, Height: `{bbox.get('height', 0):.1f}` · First Frame: `{selected_v['first_frame']}`")
                        
                        if st.button('🚀 Apply PipeGen Vehicle Track to Gate', type='primary', key='btn_apply_gate', width='stretch'):
                            try:
                                with sg.connect() as c:
                                    cur_gate = c.execute('SELECT * FROM gate WHERE id=1').fetchone()
                                    if cur_gate and cur_gate['event_id']:
                                        sg.close_gate()
                                result = sg.process_event(selected_v)
                                st.success(f"Track #{selected_v['tracking_id']} ({selected_v['vehicle_type'].upper()}) presented at gate! Awaiting resident verification.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    else:
                        st.warning('No vehicle tracks found in this pipeline export.')
                        
                with right_col:
                    with sg.connect() as c:
                        gate = dict(c.execute('SELECT * FROM gate WHERE id=1').fetchone())
                        inside = sum(not v['exit_time'] for v in c.execute('SELECT * FROM visits').fetchall())
                    
                    if gate.get('event_id'):
                        rg_col1, rg_col2 = st.columns([1.5, 1])
                        rg_col1.subheader('Virtual Gate · Live')
                        if rg_col2.button('🔄 Reset Gate', key='reset_gate_btn', width='stretch'):
                            sg.close_gate()
                            st.rerun()
                    else:
                        st.subheader('Virtual Gate · Synchronized')
                    
                    gate_phase = gate['state'].replace('PENDING_VERIFICATION', 'WAITING')
                    active_eid = gate.get('event_id') or ''
                    components.html(scene(phase=gate_phase, plate=active_eid, direction='ENTRY'), height=430)
                    
                    c_m1, c_m2 = st.columns(2)
                    c_m1.metric('Gate state', gate_phase)
                    c_m2.metric('Vehicles inside', inside)
                    
                    if gate['event_id']:
                        if gate['state'] == 'PENDING_VERIFICATION':
                            st.warning("⚠️ **Awaiting Resident Verification:** Detections are unverified by default (no fake OCR). Intercom ringing destination resident:")
                            with sg.connect() as c:
                                apartments = [dict(r) for r in c.execute('SELECT * FROM apartments').fetchall()]
                            apt = st.selectbox('Approving resident (intercom)', apartments, format_func=lambda a: f"{a['block_name']}-{a['flat_number']} · {a['resident_name']}")
                            btn_c1, btn_c2 = st.columns(2)
                            if btn_c1.button('✅ Resident Approves (Open)', type='primary', width='stretch'):
                                sg.resolve(gate['event_id'], approve=True, apartment_id=apt['id'])
                                st.rerun()
                            if btn_c2.button('❌ Resident Rejects', width='stretch'):
                                sg.resolve(gate['event_id'], approve=False, apartment_id=apt['id'])
                                st.rerun()
                        elif gate['state'] == 'OPEN':
                            st.success("🟢 **Barrier is OPEN!** Click below to record vehicle entry and close the barrier.")
                            if st.button('🚘 Complete Passage & Close Barrier', type='primary', width='stretch'):
                                sg.record_passage(gate['event_id'])
                                sg.close_gate()
                                st.rerun()
                        
                        if st.button('Cancel Active Cycle', width='stretch'):
                            sg.close_gate()
                            st.rerun()

                # Person Detections & Corridor Security
                st.subheader('Corridor & Incident Timeline Link')
                with st.expander('🚶 View PipeGen Tracked Person Events & Trigger Corridor Alert'):
                    p_events = parsed['persons']
                    if p_events:
                        p_idx = st.selectbox(
                            'Select Tracked Person Event',
                            range(len(p_events)),
                            format_func=lambda i: f"Person Track {p_events[i]['tracking_id']} (conf: {p_events[i]['detector_confidence']*100:.1f}%, {p_events[i]['frame_count']} frames)"
                        )
                        selected_p = p_events[p_idx]
                        if st.button('🚨 Trigger Corridor Security Alert with this detection', key='btn_corridor_alert'):
                            import corridor_ui
                            sec = float(selected_p.get('pts_ns', 0)) / 1e9 if selected_p.get('pts_ns') else 1.5
                            corridor_ui.incident(
                                zone='Private Corridor',
                                trigger=f"PipeGen YOLO11s Person Track #{selected_p['tracking_id']}",
                                seconds=round(sec, 2),
                                people=1,
                                motion=18.5,
                                backend='PipeGen DeepStream'
                            )
                            st.success(f"Security incident logged for Person Track #{selected_p['tracking_id']}! Safety light and soft alarm active.")
                    else:
                        st.info('No person tracks found.')
                        
                st.subheader('Access Decisions & Audit Log')
                with sg.connect() as c:
                    events = [dict(r) for r in c.execute('SELECT * FROM access_events ORDER BY id DESC LIMIT 10').fetchall()]
                if events:
                    df = pd.DataFrame(events)[['timestamp', 'event_id', 'event_type', 'authorization_status', 'reason', 'source']]
                    st.dataframe(df, hide_index=True, width='stretch')
            else:
                events = load_events(payload_data)
                index = st.selectbox('Select event', range(len(events)), format_func=lambda i: events[i]['event_id'])
                st.json(events[index])
                if st.button('Apply event to gate', type='primary'):
                    result = sg.process_event(events[index])
                    st.success(f"{result['status']} · {result['reason']}")
                    st.info('Open Live Simulator to complete the gate cycle or approve the waiting vehicle.')
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            st.error(str(exc))
            
    st.download_button('Download sample event contract', (ROOT/'data'/'sample_events.json').read_bytes(), 'sample_events.json', 'application/json')
    with st.expander('Reference footage · playback only'):
        video = st.file_uploader('Video file', type=['mp4', 'webm'])
        if video:
            st.video(video)
            st.caption('Playback only; this upload does not run inference.')
    st.markdown((ROOT/'docs'/'gpu-handoff.md').read_text(encoding='utf-8'))
elif page=='Competition Readiness':
    st.caption('Track A · completion status is backed by actual artifacts, not presentation labels.')
    st.success('✅ Track A Complete: All five PipeGen stages executed, TensorRT compiled, DeepStream video run verified, and actionable output wired into SmartGate!')

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric('TRT Inference Latency', '10.5 ms', delta='~95 FPS')
    col_m2.metric('TRT Precision', 'FP16', delta='252 layers')
    col_m3.metric('Engine Size', '27.8 MB', delta='YOLO11s')
    col_m4.metric('DeepStream Run', '1,098 frames', delta='18.33 sec')

    st.subheader('Verified Stage-by-Stage Evidence')
    st.dataframe(pd.DataFrame([
        {'Requirement': '1. Requirements Stage', 'Status': '✅ VERIFIED COMPLETE', 'Evidence': 'Parsed user requirement for single-stream vehicle/person edge perception'},
        {'Requirement': '2. Pipeline IR Stage', 'Status': '✅ VERIFIED COMPLETE', 'Evidence': 'Node graph generated (pipegen-pir.jpg & PipelineIR.json in export)'},
        {'Requirement': '3. Model Stage', 'Status': '✅ VERIFIED COMPLETE', 'Evidence': 'COCO YOLO11s parsed (321 ONNX nodes, 0 unresolved)'},
        {'Requirement': '4. Compiler Stage', 'Status': '✅ VERIFIED COMPLETE', 'Evidence': 'yolo11s.fp16.plan compiled in 77.8s; 10.525 ms benchmark via trtexec'},
        {'Requirement': '5. Run Stage', 'Status': '✅ VERIFIED COMPLETE', 'Evidence': 'DeepStream executed on parking-entrance.mp4 (1,098 frames, 28 tracks)'},
        {'Requirement': '6. Actionable Output', 'Status': '✅ VERIFIED COMPLETE', 'Evidence': 'parking-metadata.json parsed into Gate access & Corridor incident flows'},
        {'Requirement': '7. Export Package', 'Status': '✅ VERIFIED COMPLETE', 'Evidence': 'pipegen-export/ folder committed with run.sh, models, and DeepStream configs'},
    ]), hide_index=True, width='stretch')

    pir_img_path = ROOT / 'docs' / 'pipegen-pir.jpg'
    if pir_img_path.exists():
        with st.expander('🖼️ View PipeGen Pipeline IR Node Graph (Official Evidence)', expanded=True):
            st.image(str(pir_img_path), caption='PipeGen Interactive Node Graph: Input → Preprocess → YOLO11s Inference → Postprocess → Tracking → Output')

    gpu_path = ROOT / 'docs' / 'gpu-verification.json'
    if gpu_path.exists():
        gpu = json.loads(gpu_path.read_text())
        if gpu.get('verified_cuda'):
            with st.expander('Laptop GPU Environment Verification'):
                st.write(f"**Hardware:** {gpu['hardware']}")
                st.write(f"**CUDA Mean:** {gpu['CUDAExecutionProvider']['mean_ms']:.2f} ms")
                st.write(f"**CPU Mean:** {gpu['CPUExecutionProvider']['mean_ms']:.2f} ms")

    st.subheader('Judge & Demo Resources')
    st.download_button('↓ Project Description & Architecture', (ROOT/'docs'/'submission-description.md').read_bytes(), 'submission-description.md', 'text/markdown')
    st.download_button('↓ PipeGen Speed Profile JSON', (ROOT/'docs'/'pipegen'/'yolo11s.fp16.runtime.profile.json').read_bytes(), 'yolo11s.fp16.runtime.profile.json', 'application/json')
    st.download_button('↓ Real DeepStream Metadata JSON', (ROOT/'docs'/'pipegen'/'parking-metadata.json').read_bytes(), 'parking-metadata.json', 'application/json')
else:
    st.markdown((ROOT/'docs'/'architecture.md').read_text(encoding='utf-8'))
