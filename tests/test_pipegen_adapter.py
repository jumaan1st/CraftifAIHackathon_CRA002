import json
from pathlib import Path
import pytest
import smartgate as sg
from vision.pipegen_adapter import load_events, parse_pipegen_deepstream_metadata

ROOT = Path(__file__).parent.parent

def test_parse_real_deepstream_parking_metadata():
    path = ROOT / 'docs' / 'pipegen' / 'parking-metadata.json'
    assert path.exists(), "Real PipeGen DeepStream metadata must exist"
    data = json.loads(path.read_text(encoding='utf-8'))
    
    parsed = parse_pipegen_deepstream_metadata(data)
    vehicles = parsed['vehicles']
    persons = parsed['persons']
    summary = parsed['summary']
    
    assert summary['total_frames'] == 1098
    assert summary['vehicles_detected'] >= 10
    assert summary['persons_detected'] >= 10
    
    # Check vehicle event structure and validation
    for v in vehicles:
        assert v['source'] == 'pipegen'
        assert v['event_type'] == 'VEHICLE_DETECTED'
        assert v['number_plate'] is None
        assert v['confidence'] is None
        assert 0.0 <= v['detector_confidence'] <= 1.0
        assert v['vehicle_type'] in ('car', 'motorcycle', 'truck', 'bus')
        # Ensure it passes strict SmartGate domain validation
        eid, source, plate, confidence, kind, vtype = sg.validate_event(v)
        assert eid == v['event_id']

def test_load_events_dual_mode():
    # 1. PipeGen frame-based JSON
    pipegen_bytes = (ROOT / 'docs' / 'pipegen' / 'parking-metadata.json').read_bytes()
    pipegen_events = load_events(pipegen_bytes)
    assert len(pipegen_events) >= 10
    assert pipegen_events[0]['source'] == 'pipegen'
    
    # 2. Existing sample event list contract
    sample_bytes = (ROOT / 'data' / 'sample_events.json').read_bytes()
    sample_events = load_events(sample_bytes)
    assert len(sample_events) == 5
    assert sample_events[0]['source'] == 'sample'

def test_pipegen_vehicle_event_process_in_gate(tmp_path):
    db = tmp_path / 'test_gate.db'
    sg.initialize(db)
    
    # Take real Track 0 car arrival
    ev = {
        'event_id': 'pipegen-track0-car-f3',
        'source': 'pipegen',
        'event_type': 'VEHICLE_DETECTED',
        'tracking_id': 0,
        'vehicle_type': 'car',
        'number_plate': None,
        'confidence': None,
        'direction': 'ENTRY',
        'visit_type': 'resident'
    }
    
    # 1. Process event: must be PENDING because plate is unverified
    res = sg.process_event(ev, path=db)
    assert res['status'] == 'PENDING'
    assert 'manual verification required' in res['reason']
    
    with sg.connect(db) as c:
        gate = dict(c.execute('SELECT * FROM gate WHERE id=1').fetchone())
        assert gate['state'] == 'PENDING_VERIFICATION'
        assert gate['event_id'] == 'pipegen-track0-car-f3'
        
    # 2. Operator/Resident grants access
    sg.resolve('pipegen-track0-car-f3', approve=True, apartment_id=1, path=db)
    with sg.connect(db) as c:
        gate = dict(c.execute('SELECT * FROM gate WHERE id=1').fetchone())
        assert gate['state'] == 'OPEN'
        
    # 3. Complete passage
    sg.record_passage('pipegen-track0-car-f3', path=db)
    sg.close_gate(path=db)
    with sg.connect(db) as c:
        gate = dict(c.execute('SELECT * FROM gate WHERE id=1').fetchone())
        assert gate['state'] == 'CLOSED'
        assert gate['event_id'] is None
        visits = [dict(r) for r in c.execute('SELECT * FROM visits').fetchall()]
        assert len(visits) == 1
        assert visits[0]['arrival_event_id'] == 'pipegen-track0-car-f3'
