from pathlib import Path
import numpy as np
import pytest
from corridor_ui import MotionMonitor,alarm_reason,incident,incidents

@pytest.mark.parametrize('armed,mode,people,motion,expected',[
    (False,'People detected',1,20,None),
    (False,'Any movement',0,20,None),
    (True,'People detected',1,0,'PERSON_DETECTED'),
    (True,'People detected',0,20,None),
    (True,'Any movement',0,3,'MOTION_DETECTED'),
    (True,'Any movement',0,1,None),
])
def test_armed_security_policy(armed,mode,people,motion,expected):
    assert alarm_reason(armed,mode,people,motion,2)==expected

def test_motion_warmup_static_and_change():
    monitor=MotionMonitor()
    frame=np.zeros((180,320,3),dtype=np.uint8)
    assert monitor.measure(frame)==0
    assert monitor.measure(frame)==0
    changed=frame.copy();changed[20:100,20:100]=255
    assert monitor.measure(changed)>2
    assert monitor.measure(changed)==0

def test_security_incident_persists_without_gate_event(tmp_path):
    db=tmp_path/'security.db'
    incident('Private Corridor','PERSON_DETECTED',2.,1,3.,'CPU',db)
    incident('Parking CCTV','MOTION_DETECTED',4.,0,5.,'CPU',db)
    rows=incidents(db)
    assert {r['zone'] for r in rows}=={'Private Corridor','Parking CCTV'}
    assert all(r['status']=='NEW' for r in rows)
    assert len({r['id'] for r in rows})==2
