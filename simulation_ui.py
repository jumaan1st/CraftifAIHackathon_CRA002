"""Guided software-only gate simulation, with visuals tied to committed domain events."""
import html
from time import sleep
from uuid import uuid4
import pandas as pd
import streamlit as st
import smartgate as sg

SCENARIOS = {
    'Registered resident': ('KA01AB1234','resident','Active registration → automatic entry'),
    'Unknown vehicle': ('KA09ZZ9999','resident','Unregistered plate → resident verification'),
    'Visitor': ('KA08VS2468','visitor','Visitor → destination resident approval'),
    'Delivery': ('KA07DL4567','delivery','Delivery → destination resident approval'),
    'Revoked registration': ('KA05JK7890','resident','Revoked permission → automatic entry denied'),
    'Unreadable plate': (None,'resident','No plate → manual resident verification'),
}

def scene(phase='CLOSED', plate='', direction='ENTRY', moving=False):
    """Code-native vector scene, not a video or an AI inference visualization."""
    opened = phase in ('OPENING','OPEN','CROSSING')
    angle = -82 if opened else 0
    color = '#4de0ae' if opened else '#f4b667' if phase=='WAITING' else '#a3b5ce'
    label = {'CLOSED':'GATE CLOSED','APPROACH':'VEHICLE APPROACHING','OPENING':'GATE OPENING',
             'OPEN':'GATE OPEN','CROSSING':'VEHICLE CROSSING','CLOSING':'GATE CLOSING',
             'WAITING':'AWAITING RESIDENT','REJECTED':'ACCESS DENIED'}.get(phase,phase)
    start,end = (350,70) if direction=='ENTRY' else (70,350)
    y = end if phase in ('CLOSING',) else start
    vehicle = bool(plate) or phase not in ('CLOSED',)
    if phase=='CLOSED':
        vehicle = False
    animation = f'animation:drive 1.2s ease-in-out forwards;' if moving else ''
    barrier_animation = 'animation:lift .9s ease-in-out forwards;' if phase=='OPENING' else 'animation:lower .9s ease-in-out forwards;' if phase=='CLOSING' else ''
    safe_plate=html.escape(plate or 'UNREADABLE')
    return f'''<!doctype html><html><head><style>
      *{{box-sizing:border-box}} html,body{{overflow:hidden}} body{{margin:0;background:#102237;font-family:Arial,sans-serif;color:#dfeaf7}}
      .wrap{{border:1px solid #284158;border-radius:18px;overflow:hidden;background:#102237}}
      svg{{display:block;width:100%;height:auto;max-height:425px}}
      @keyframes drive{{from{{transform:translate(350px,{start}px)}}to{{transform:translate(350px,{end}px)}}}}
      @keyframes lift{{from{{transform:rotate(0deg)}}to{{transform:rotate(-82deg)}}}}
      @keyframes lower{{from{{transform:rotate(-82deg)}}to{{transform:rotate(0deg)}}}}
      .pill{{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;background:#152e43;font-size:12px;letter-spacing:1.5px}}
    </style></head><body><div class="wrap"><div class="pill"><b style="color:{color}">● {label}</b><span>{'↑ ENTRY' if direction=='ENTRY' else '↓ EXIT'}</span></div>
    <svg role="img" aria-label="Simulated gate: {label}" viewBox="0 0 800 460" xmlns="http://www.w3.org/2000/svg">
      <defs><pattern id="grass" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="4" cy="4" r="1" fill="#21463f"/></pattern>
      <pattern id="stripe" width="35" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(-25)"><rect width="35" height="16" fill="#f1f5f9"/><rect width="17" height="16" fill="#ee7962"/></pattern>
      <filter id="shadow"><feDropShadow dx="0" dy="6" stdDeviation="6" flood-opacity=".3"/></filter></defs>
      <rect width="800" height="460" fill="#14332f"/><rect width="800" height="460" fill="url(#grass)"/>
      <rect x="262" width="276" height="460" fill="#293a4d"/><path d="M274 0V460M526 0V460" stroke="#7891a5" stroke-width="3"/>
      <path d="M400 0V460" stroke="#6c7f91" stroke-width="3" stroke-dasharray="20 20"/>
      <rect x="16" y="30" width="205" height="134" rx="12" fill="#203e50" stroke="#396275"/>
      <text x="38" y="62" fill="#b8d8e5" font-size="12" letter-spacing="2">CEDAR RESIDENCES</text>
      <path d="M40 82h30v22H40zm47 0h30v22H87zm47 0h30v22h-30zm-94 36h30v22H40zm47 0h30v22H87zm47 0h30v22h-30z" fill="#64bcb3" opacity=".6"/>
      <text x="400" y="30" text-anchor="middle" fill="#a4bacb" font-size="12" letter-spacing="3">INSIDE COMMUNITY</text>
      <text x="400" y="442" text-anchor="middle" fill="#a4bacb" font-size="12" letter-spacing="3">APPROACH ROAD</text>
      <rect x="580" y="185" width="170" height="102" rx="12" fill="#1e3b4c" stroke="#3d6275"/>
      <rect x="599" y="204" width="49" height="35" rx="4" fill="#5a919f"/><text x="599" y="265" fill="#b8d8e5" font-size="11" letter-spacing="1">SECURITY CABIN</text>
      <rect x="250" y="283" width="298" height="6" fill="#d8e2e9" opacity=".6"/>
      <circle cx="236" cy="247" r="20" fill="#4a647b"/><rect x="225" y="237" width="25" height="59" rx="5" fill="#7790a6"/>
      <g transform="translate(240 245)"><g style="transform:rotate({angle}deg);transform-origin:0 0;{barrier_animation}"><rect x="0" y="-9" width="300" height="18" rx="5" fill="url(#stripe)" filter="url(#shadow)"/></g></g>
      <circle cx="564" cy="244" r="12" fill="{color}"/><circle cx="564" cy="244" r="21" fill="{color}" opacity=".1"/>
      <text x="40" y="350" fill="#7ab5a4" font-size="11" letter-spacing="2">SOFTWARE SIMULATION</text>
      <text x="40" y="372" fill="#a6c3bd" font-size="11">Gate + vehicle movement</text>
      {f'<g style="transform:translate(350px,{y}px);{animation}" filter="url(#shadow)"><rect width="98" height="85" rx="22" fill="#5bace3"/><rect x="13" y="14" width="72" height="27" rx="8" fill="#163d59"/><rect x="10" y="58" width="78" height="17" rx="4" fill="#edf5fa"/><text x="49" y="70" text-anchor="middle" fill="#193149" font-size="9" font-weight="bold">{safe_plate}</text><rect x="-5" y="18" width="9" height="21" rx="3" fill="#122131"/><rect x="94" y="18" width="9" height="21" rx="3" fill="#122131"/></g>' if vehicle else ''}
    </svg></div></body></html>'''

def draw(slot, phase, plate='', direction='ENTRY', moving=False):
    with slot.container():
        st.iframe(scene(phase,plate,direction,moving),height='content',alt='Animated software gate and vehicle movement')

def update_metrics(metrics, state):
    visits=sg.rows('visits')
    values=[state,sum(not v['exit_time'] for v in visits),len(visits),sum(bool(v['exit_time']) for v in visits)]
    for box,label,value in zip(metrics,['Gate','Vehicles inside','Completed entries','Completed exits'],values):
        box.metric(label,value)

def cycle(request, slot, status, progress, metrics):
    """Animate only an authorized request; passage and closure are persistent operations."""
    eid=request['event_id']
    direction=request['direction']
    plate=request['registration_number']
    st.session_state['last_direction']=direction
    if request['completed_at']:
        sg.close_gate(expected_event_id=eid)
        return
    for phase,message,value,delay in [
        ('OPENING','Permission granted · lifting barrier',.35,1.1),
        ('OPEN','Gate is OPEN · vehicle may proceed',.5,.9),
        ('CROSSING',f"Vehicle {'entering' if direction=='ENTRY' else 'exiting'} · crossing sensor active",.7,1.4)]:
        status.info(message)
        progress.progress(value)
        metrics[0].metric('Gate','OPENING' if phase=='OPENING' else 'OPEN')
        draw(slot,phase,plate,direction,phase=='CROSSING')
        sleep(delay)
    sg.record_passage(eid)
    update_metrics(metrics,'CLOSING')
    status.info('Passage recorded · lowering barrier')
    progress.progress(.9)
    draw(slot,'CLOSING',plate,direction)
    sleep(1.1)
    sg.close_gate(expected_event_id=eid)
    update_metrics(metrics,'CLOSED')
    draw(slot,'CLOSED',direction=direction)
    progress.progress(1.0)
    status.success(f"{'Entry' if direction=='ENTRY' else 'Exit'} complete · gate CLOSED · all events saved")
    sleep(.5)

def new_event(plate,kind='resident',direction='ENTRY',presence_id=None,source='sample'):
    return {'event_id':'sim-'+uuid4().hex,'source':source,'number_plate':plate,'visit_type':kind,
            'direction':direction,'presence_id':presence_id,'tracking_id':uuid4().hex[:6],'vehicle_type':'car'}

def render_simulator(apartments):
    gate=sg.rows('gate')[0]
    requests=sg.rows('requests')
    visits=sg.rows('visits')
    inside=[v for v in visits if not v['exit_time']]
    current=next((r for r in requests if r['event_id']==gate['event_id']),None)
    last=st.session_state.get('cycle_result')
    st.caption('Choose a scenario, then watch the entire gate cycle. Every decision and crossing is saved automatically.')
    cols=st.columns(4)
    metrics=[col.empty() for col in cols]
    update_metrics(metrics,gate['state'].replace('PENDING_VERIFICATION','WAITING'))
    st.write('')
    left,right=st.columns([1.65,1],gap='large')
    with left:
        st.subheader('Live gate simulation')
        slot=st.empty()
        phase='OPEN' if gate['state']=='OPEN' else 'WAITING' if gate['state']=='PENDING_VERIFICATION' else 'REJECTED' if current else 'CLOSED'
        draw(slot,phase,current['registration_number'] if current else '',current['direction'] if current else st.session_state.get('last_direction','ENTRY'))
        status=st.empty()
        progress=st.empty()
        if last and not current:
            status.success(last)
        elif current:
            status.warning(current['reason'])
        else:
            status.info('Ready · barrier closed · choose Entry or Exit to begin')
        st.caption('① Arrival  →  ② Authorization  →  ③ Gate opens  →  ④ Vehicle passes  →  ⑤ Gate closes & log saves')
    with right:
        st.subheader('Run your scenario')
        if not current:
            movement=st.radio('Movement',['Entry','Exit'],horizontal=True)
            event=None
            if movement=='Entry':
                scenario=st.selectbox('Who is arriving?',list(SCENARIOS)+['Custom plate'])
                if scenario=='Custom plate':
                    plate=st.text_input('Vehicle registration',placeholder='KA01AB1234')
                    kind=st.selectbox('Visit type',['resident','visitor','delivery'])
                    event=new_event(plate,kind,source='manual')
                else:
                    plate,kind,hint=SCENARIOS[scenario]
                    st.caption(hint)
                    st.code(plate or 'Plate unreadable',language=None)
                    event=new_event(plate,kind)
            elif inside:
                selected=st.selectbox('Vehicle leaving',range(len(inside)),format_func=lambda i:f"{inside[i]['registration_number'] or 'Unidentified vehicle'} · visit #{inside[i]['id']}")
                visit=inside[selected]
                event=new_event(visit['registration_number'],direction='EXIT',presence_id=visit['id'])
                st.caption('Only a vehicle recorded inside can exit. Its departure updates the same visit.')
            else:
                st.info('No vehicles inside yet. Run an entry or the full demo first.')
            start=st.button(f"Start {movement.lower()}",type='primary',width='stretch',disabled=event is None)
            if start:
                try:
                    status.info('Vehicle approaching · checking access policy')
                    draw(slot,'APPROACH',event['number_plate'],event['direction'])
                    sleep(.8)
                    request=sg.process_event(event)
                    if request['status']=='AUTHORIZED':
                        cycle(request,slot,status,progress,metrics)
                        st.session_state['cycle_result']=f"{movement} complete — {request['registration_number'] or 'verified visitor'} · gate closed · audit saved"
                    else:
                        st.session_state.pop('cycle_result',None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            st.divider()
            st.markdown('**Presenting to judges?**')
            st.caption('One click runs a registered vehicle in and back out. Two complete open → pass → close cycles, with persistent logs.')
            candidates=[v for v in sg.rows('vehicles') if v['is_active'] and v['registration_number'] not in {x['registration_number'] for x in inside}]
            if st.button('▶ Play full entry + exit demo',width='stretch',disabled=not candidates):
                try:
                    plate=candidates[0]['registration_number']
                    request=sg.process_event(new_event(plate))
                    cycle(request,slot,status,progress,metrics)
                    status.info('Vehicle is now inside · preparing its exit')
                    sleep(.8)
                    visit=next(v for v in sg.rows('visits') if v['arrival_event_id']==request['event_id'])
                    request=sg.process_event(new_event(plate,direction='EXIT',presence_id=visit['id']))
                    cycle(request,slot,status,progress,metrics)
                    st.session_state['cycle_result']=f'Demo complete — {plate} entered and exited · gate closed twice · audit saved'
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if not candidates:
                st.caption('All active registered vehicles are inside. Simulate an exit to make one available for the full demo.')
        else:
            st.markdown(f"### {current['registration_number'] or 'Plate unreadable'}")
            st.write(f"**{current['direction']}** · {current['visit_type'].title()} · {current['status']}")
            apt_map={a['id']:f"{a['block_name']}-{a['flat_number']} · {a['resident_name']}" for a in apartments}
            st.caption('Mapped apartment: '+apt_map.get(current['apartment_id'],'Not registered'))
            if current['status'] in ('PENDING','DENIED'):
                st.warning('Barrier stays CLOSED until a resident approves this visit.')
                allowed=[current['apartment_id']] if current['visit_type']=='resident' and current['apartment_id'] else list(apt_map)
                apt=st.selectbox('Resident / destination apartment',allowed,format_func=apt_map.get)
                method=st.selectbox('Verification method',['Resident approval (simulated)','RFID (simulated)','Fingerprint (simulated)'])
                st.caption('The buttons below simulate this fictional resident’s identity and decision. They do not collect biometrics or register a new vehicle.')
                approve=st.button('Approve visit & open gate',type='primary',width='stretch')
                reject=st.button('Reject visit · keep gate closed',width='stretch')
                if approve or reject:
                    try:
                        sg.resolve(current['event_id'],approve,apt,method)
                        if approve:
                            updated=next(r for r in sg.rows('requests') if r['event_id']==current['event_id'])
                            cycle(updated,slot,status,progress,metrics)
                            st.session_state['cycle_result']='Resident-approved entry complete · gate closed · visit and logs saved'
                        else:
                            draw(slot,'REJECTED',current['registration_number'])
                            status.error('Resident rejected the request · gate remains CLOSED · decision saved')
                            sleep(.9)
                            sg.close_gate(expected_event_id=current['event_id'])
                            st.session_state['cycle_result']='Visit rejected · no vehicle entered · gate stayed closed · decision saved'
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            elif current['status']=='AUTHORIZED':
                st.info('Authorized cycle is waiting to finish. Resume to record passage and close the gate.')
                if st.button('Resume vehicle passage & close',type='primary',width='stretch'):
                    cycle(current,slot,status,progress,metrics)
                    st.session_state['cycle_result']='Cycle completed · gate closed · audit saved'
                    st.rerun()
            if st.button('Cancel / clear current cycle',width='stretch'):
                sg.close_gate(expected_event_id=current['event_id'])
                st.session_state['cycle_result']='Cycle cleared · gate closed · no unrecorded passage added'
                st.rerun()
    st.divider()
    a,b=st.columns([1.5,1])
    with a:
        st.subheader('Live activity log')
        recent=sg.rows('logs')[:12]
        if recent:
            data=pd.DataFrame(recent)[['timestamp','registration_number','event_type','authorization_status']]
            data['timestamp']=pd.to_datetime(data['timestamp'],utc=True).dt.tz_convert('Asia/Kolkata').dt.strftime('%H:%M:%S')
            data.columns=['Time (IST)','Plate','Activity','Result']
            st.dataframe(data,hide_index=True,width='stretch')
        else:
            st.info('Your first gate cycle will appear here, step by step.')
        st.caption('The full history and CSV/JSON downloads are available in Access Logs.')
    with b:
        st.subheader('Currently inside')
        current_inside=[v for v in sg.rows('visits') if not v['exit_time']]
        if current_inside:
            st.dataframe(pd.DataFrame([{'Plate':v['registration_number'] or f"Unidentified · #{v['id']}",
                'Apartment':f"{v['block_name'] or '—'}-{v['flat_number'] or '—'}",'Entry (UTC)':v['entry_time']} for v in current_inside]),hide_index=True,width='stretch')
        else:
            st.info('No vehicles inside. Completed exits remove vehicles from this list.')
