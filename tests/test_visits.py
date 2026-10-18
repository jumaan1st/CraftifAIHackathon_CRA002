import sqlite3
import pytest
import smartgate as sg

@pytest.fixture
def db(tmp_path):
    path=tmp_path/'visits.db'
    sg.initialize(path)
    return path

def event(eid='in1',plate='KA01AB1234',**extra):
    return dict(event_id=eid,number_plate=plate,source='sample',**extra)

def test_round_trip_and_ordered_audit(db):
    sg.process_event(event(),db)
    assert not sg.rows('visits',db)  # authorization is not entry
    sg.record_passage('in1',db)
    sg.record_passage('in1',db)  # duplicate crossing idempotent
    sg.close_gate(db,expected_event_id='in1')
    v=sg.rows('visits',db)[0]
    sg.process_event(event('out1',direction='EXIT',presence_id=v['id']),db)
    sg.record_passage('out1',db)
    sg.close_gate(db,expected_event_id='out1')
    assert sg.rows('visits',db)[0]['exit_time']
    assert [r['event_type'] for r in reversed(sg.rows('logs',db))]==[
        'VEHICLE_DETECTED','ACCESS_DECISION','GATE_OPENED','VEHICLE_ENTERED','GATE_CLOSED',
        'VEHICLE_DETECTED','ACCESS_DECISION','GATE_OPENED','VEHICLE_EXITED','GATE_CLOSED']

def test_exit_without_entry_denied(db):
    with pytest.raises(ValueError,match='No vehicle inside'):
        sg.process_event(event(direction='EXIT'),db)

def test_duplicate_inside_entry_prevented(db):
    sg.process_event(event(),db)
    sg.record_passage('in1',db)
    sg.close_gate(db)
    with pytest.raises(ValueError,match='already inside'):
        sg.process_event(event('in2'),db)

def test_exit_plate_must_match_visit(db):
    sg.process_event(event(),db)
    sg.record_passage('in1',db)
    sg.close_gate(db)
    v=sg.rows('visits',db)[0]
    with pytest.raises(ValueError,match='does not match'):
        sg.process_event(event('out1','WRONG',direction='EXIT',presence_id=v['id']),db)

def test_pending_cannot_cross(db):
    sg.process_event(event(plate=None),db)
    with pytest.raises(ValueError):
        sg.record_passage('in1',db)
    assert not sg.rows('visits',db)

def test_unreadable_approved_visit_can_exit(db):
    sg.process_event(event(plate=None),db)
    sg.resolve('in1',True,1,path=db)
    sg.record_passage('in1',db)
    sg.close_gate(db)
    v=sg.rows('visits',db)[0]
    sg.process_event(event('out1',None,direction='EXIT',presence_id=v['id']),db)
    sg.record_passage('out1',db)
    assert sg.rows('visits',db)[0]['exit_time']

def test_stale_cycle_cannot_close_new_vehicle(db):
    sg.process_event(event(),db)
    sg.close_gate(db)
    sg.process_event(event('in2'),db)
    with pytest.raises(ValueError,match='changed'):
        sg.close_gate(db,expected_event_id='in1')
    assert sg.rows('gate',db)[0]['event_id']=='in2'

def test_existing_database_migrates_without_deleting_history(tmp_path):
    db=tmp_path/'old.db'
    with sqlite3.connect(db) as c:
        c.execute('''CREATE TABLE requests(event_id TEXT PRIMARY KEY,timestamp TEXT NOT NULL,
            tracking_id TEXT,registration_number TEXT,vehicle_type TEXT NOT NULL,source TEXT NOT NULL,
            confidence REAL,visit_type TEXT NOT NULL,apartment_id INTEGER,status TEXT NOT NULL,reason TEXT NOT NULL)''')
        c.execute("INSERT INTO requests VALUES ('old','2026-10-18','1','KA01AB1234','car','sample',NULL,'resident',1,'AUTHORIZED','Old record')")
    sg.initialize(db)
    assert sg.rows('requests',db)[0]['event_id']=='old'
    assert sg.rows('requests',db)[0]['direction']=='ENTRY'
