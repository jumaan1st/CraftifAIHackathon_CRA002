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

def test_pipegen_corridor_security_integration(tmp_path):
    from video_ui import detector
    det = detector('CraftifAI PipeGen (YOLO11s TensorRT FP16)')
    assert det.name == 'CraftifAI PipeGen YOLO11s (TensorRT FP16)'
    
    # Test person detection on sample frame
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    found_persons = det.detect(frame, class_map={0: 'person'})
    assert isinstance(found_persons, list)
    
    # Verify incident recording with PipeGen backend
    db = tmp_path / 'security_pipegen.db'
    incident('Private Corridor', 'PERSON_DETECTED', 3.5, 1, 2.4, 'CraftifAI PipeGen (YOLO11s TensorRT FP16)', db)
    rows = incidents(db)
    assert len(rows) == 1
    assert rows[0]['backend'] == 'CraftifAI PipeGen (YOLO11s TensorRT FP16)'
    assert rows[0]['zone'] == 'Private Corridor'
    assert rows[0]['trigger'] == 'PERSON_DETECTED'
