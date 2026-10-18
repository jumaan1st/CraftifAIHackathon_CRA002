"""Video playback controls and a periodically refreshed CPU inference view."""
from pathlib import Path
import hashlib
import json
import pandas as pd
import streamlit as st
import smartgate as sg
from simulation_ui import scene
from vision.video_service import VehicleDetector, VideoRun, annotated_frame, ROOT

@st.cache_resource(show_spinner='Loading AI model and inference runtime (first use only)…')
def detector(backend='CraftifAI PipeGen (YOLO11s TensorRT FP16)'):
    if backend == 'CraftifAI PipeGen (YOLO11s TensorRT FP16)':
        from vision.pipegen_detector import PipeGenVehicleDetector
        return PipeGenVehicleDetector()
    if backend == 'NVIDIA GPU (CUDA)':
        from vision.gpu_detector import CudaVehicleDetector
        return CudaVehicleDetector()
    return VehicleDetector()

@st.fragment(run_every=.3)
def live_video():
    run=st.session_state.get('video_run')
    if not run:
        return
    if run.playing:
        try:
            run.tick(detector(run.backend))
        except Exception as exc:
            run.error=f'Video processing stopped: {exc}'
            run.stop()
    left,right=st.columns([1.8,1],gap='large')
    with left:
        st.subheader('Video · live analysis playback')
        st.image(annotated_frame(run),channels='BGR',width='stretch')
        st.caption(f'{run.filename} · video time {run.source_seconds:.1f}s · sampled at up to 4 frames/sec · {run.backend} · no audio')
        if run.error:
            st.error(run.error)
        elif run.phase=='REJECTED':
            st.error(run.message)
        elif run.phase=='WAITING':
            st.warning('VERIFICATION REQUIRED · gate CLOSED · select a resident to approve or reject')
        elif run.phase=='COMPLETE':
            st.success(run.message)
        else:
            st.info(run.message)
        count=len(run.samples)
        st.caption(f'{count} sampled frames contained vehicles. One access attempt per playback run; identities are not automatically read from the clip.')
    with right:
        st.subheader('Virtual gate · synchronized')
        phase=run.phase if run.phase in ('OPENING','OPEN','CROSSING','CLOSING','WAITING','REJECTED') else 'CLOSED'
        st.iframe(scene(phase,run.plate,run.direction,run.phase=='CROSSING'),height='content',alt='Video-triggered virtual gate')
        st.markdown(f"**Assigned demo plate:** `{run.plate or 'Unreadable / no plate'}`")
        st.caption(f'Real vehicle boxes: {run.detector_name}. Plate identity is operator assigned. Barrier actuation and crossing timing are simulated; no plate OCR or physical gate sensor is connected.')
        if run.phase=='WAITING':
            apartments=sg.rows('apartments')
            request=run.request()
            mapped=request['apartment_id'] if request else None
            options=[a for a in apartments if not mapped or run.visit_type!='resident' or a['id']==mapped]
            apt=st.selectbox('Approving resident',options,format_func=lambda a:f"{a['block_name']}-{a['flat_number']} · {a['resident_name']}",key='video_approver')
            st.caption('These buttons simulate the selected resident’s identity and decision.')
            if st.button('Approve video vehicle',type='primary',width='stretch'):
                run.resolve(True,apt['id'])
                st.rerun(scope='fragment')
            if st.button('Reject video vehicle',width='stretch'):
                run.resolve(False,apt['id'])
                st.rerun(scope='fragment')
        gate=sg.rows('gate')[0]
        inside=sum(not v['exit_time'] for v in sg.rows('visits'))
        st.metric('Gate state',gate['state'].replace('PENDING_VERIFICATION','WAITING'))
        st.metric('Vehicles inside',inside)
    st.subheader('This video’s access log')
    events=[r for r in sg.rows('logs') if r['event_id']==run.request_id]
    if events:
        df=pd.DataFrame(events)[['timestamp','registration_number','event_type','authorization_status','reason']]
        df['timestamp']=pd.to_datetime(df['timestamp'],utc=True).dt.tz_convert('Asia/Kolkata').dt.strftime('%H:%M:%S')
        st.dataframe(df,hide_index=True,width='stretch')
    else:
        st.caption('No access decision until the detector finds a vehicle. The gate remains closed.')
    report=ROOT/'data'/'video_reports'/(run.run_id+'.json')
    if report.exists():
        st.download_button('Download real detection results + demo identity metadata',report.read_bytes(),f'video-{run.run_id}.json','application/json',key='video_report_download')
    if run.playing:
        run.advance_frame()

def render_video():
    st.caption('Play vehicle footage → detect a vehicle → apply the selected access policy → operate the virtual gate → save the log.')
    st.info('Vehicle detection runs on your selected backend. Choose a demo identity to demonstrate permission granted or denied; the application does not read the video’s number plate.')
    gpu_report=ROOT/'docs/gpu-verification.json'
    verified=json.loads(gpu_report.read_text()).get('verified_cuda',False) if gpu_report.exists() else False
    backend_options = ['CraftifAI PipeGen (YOLO11s TensorRT FP16)', 'NVIDIA GPU (CUDA)', 'CPU']
    backend = st.selectbox('Perception engine & hardware', backend_options, index=0)
    if backend == 'CraftifAI PipeGen (YOLO11s TensorRT FP16)':
        st.success('⚡ PipeGen Perception: Catalog YOLO11s (FP16 TensorRT, 10.5 ms inference latency, 27.8 MB engine) running DeepStream 7.1 detections.')
    elif verified and backend == 'NVIDIA GPU (CUDA)':
        report = json.loads(gpu_report.read_text())
        st.caption(f"Verified GPU: {report['hardware']} · native CUDA YOLOX-s baseline.")
    st.caption('Backend changes apply when you start a new playback run.')
    old=st.session_state.get('video_run')
    source=st.radio('Video source',['Online sample · downloaded locally','Upload my own video'],horizontal=True)
    sample=ROOT/'data'/'videos'/'parking-entrance.mp4'
    upload=None
    if source=='Upload my own video':
        upload=st.file_uploader('Choose MP4, MOV, AVI or WebM',type=['mp4','mov','avi','webm'],key='gate_video_upload')
        st.caption('Choose your video, select Entry or Exit and an access test, then press Play video & run gate. H.264 MP4 is recommended.')
    else:
        st.markdown('[Parking-entrance footage by Ivan Chumak · Pexels](https://www.pexels.com/video/urban-parking-scene-with-cars-and-motorbike-37508953/) · [License](https://www.pexels.com/license/)')
        st.caption('The same real footage can test both policies. “Granted” and “denied” describe our chosen demo identity, not a label supplied by the video owner.')
        if not sample.exists():
            st.warning('Sample not downloaded. Run scripts/download_video_assets.py, or upload your own video.')
    selection=(source,upload.name if upload else None,upload.size if upload else None)
    if old and getattr(old,'selection',None)!=selection:
        old.stop()
        st.session_state.pop('video_run',None)
        old=None
    a,b=st.columns(2)
    movement=a.selectbox('Movement',['Entry','Exit'],key='video_direction')
    assigned=None
    presence_id=None
    kind='resident'
    if movement=='Entry':
        profile=b.selectbox('Access test',['Access given · active resident','Access denied · revoked registration','Unknown vehicle · resident decides','Visitor · resident decides','Unreadable plate · resident decides'])
        if profile.startswith('Access given'):
            vehicles=[v for v in sg.rows('vehicles') if v['is_active']]
            selected=st.selectbox('Assign registered demo plate',vehicles,format_func=lambda v:f"{v['registration_number']} · {v['resident_name']}")
            assigned=selected['registration_number']
        elif profile.startswith('Access denied'):
            revoked=[v for v in sg.rows('vehicles') if not v['is_active']]
            if revoked:
                assigned=revoked[0]['registration_number']
                st.caption(f"Assigned revoked demo plate: {assigned}. The gate will remain closed after detection.")
            else:
                st.error('No revoked vehicle exists in the registry.')
        elif profile.startswith('Unknown'):
            assigned='KA09ZZ9999'
        elif profile.startswith('Visitor'):
            assigned='KA08VS2468'; kind='visitor'
    else:
        inside=[v for v in sg.rows('visits') if not v['exit_time']]
        if inside:
            selected=b.selectbox('Vehicle leaving',inside,format_func=lambda v:f"{v['registration_number'] or 'Unreadable vehicle'} · visit #{v['id']}")
            assigned=selected['registration_number']; presence_id=selected['id']
        else:
            b.info('No vehicle inside. Complete an entry first.')
    controls=st.columns(4)
    available=(source.startswith('Online') and sample.exists()) or upload is not None
    if movement=='Exit' and not presence_id:
        available=False
    if controls[0].button('▶ Play video & run gate',type='primary',width='stretch',disabled=not available):
        gate=sg.rows('gate')[0]
        owned=old and old.request_id==gate['event_id']
        if gate['event_id'] and not owned:
            st.error('A gate cycle is already active in Live Simulator. Complete or cancel it before running a video.')
        elif movement=='Entry' and assigned and any(v['registration_number']==assigned and not v['exit_time'] for v in sg.rows('visits')):
            st.error('This demo vehicle is already inside. Select Exit or choose another registered plate.')
        else:
            try:
                if old:
                    old.stop()
                proxy=ROOT/'data'/'videos'/'parking-entrance-analysis.mp4'
                path=proxy if proxy.exists() else sample
                name='Pexels parking entrance'
                if upload:
                    raw=upload.getvalue()
                    if len(raw)>200*1024*1024:
                        raise ValueError('Choose a video under 200 MB.')
                    path=ROOT/'data'/'uploads'/(hashlib.sha256(raw).hexdigest()+Path(upload.name).suffix.lower())
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(raw)
                    name=Path(upload.name).name
                detector(backend)  # fail before opening a decoder or creating an access attempt
                st.session_state['video_run']=VideoRun(path,name,assigned,kind,movement.upper(),presence_id,backend=backend)
                st.session_state['video_run'].selection=selection
            except (ValueError,RuntimeError) as exc:
                st.error(str(exc))
    run=st.session_state.get('video_run')
    if controls[1].button('Ⅱ Pause',width='stretch',disabled=not run or not run.playing):
        run.pause()
    if controls[2].button('▶ Resume',width='stretch',disabled=not run or run.playing or run.phase=='STOPPED'):
        run.resume()
    if controls[3].button('■ Stop & close',width='stretch',disabled=not run):
        run.stop()
    if run:
        live_video()
    else:
        st.subheader('Video preview')
        if upload:
            st.video(upload)
        elif sample.exists():
            st.video(str(sample))
        st.caption('Press Play video & run gate above to start the processed playback and access decision. Preview playback alone does not actuate the gate.')
