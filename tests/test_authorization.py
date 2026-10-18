import sqlite3
import pytest
import smartgate as sg
from vision.pipegen_adapter import load_events

@pytest.fixture
def db(tmp_path):
    path=tmp_path/'test.db'
    sg.initialize(path)
    return path

def event(plate='KA01AB1234',**extra):
    return dict(event_id='e1',source='sample',number_plate=plate,**extra)

def test_seed_and_normalization(db):
    assert len(sg.rows('apartments',db))==5
    assert len(sg.rows('vehicles',db))==5
    r=sg.process_event(event('ka 01-ab 1234'),db)
    assert (r['status'],r['apartment_id'])==('AUTHORIZED',1)
    assert sg.rows('gate',db)[0]['state']=='OPEN'

@pytest.mark.parametrize('plate,confidence,status',[
    ('KA09ZZ9999',None,'PENDING'),(None,None,'PENDING'),
    ('KA01AB1234',.4,'PENDING'),('KA05JK7890',None,'DENIED')])
def test_no_automatic_entry(db,plate,confidence,status):
    assert sg.process_event(event(plate,confidence=confidence),db)['status']==status
    assert sg.rows('gate',db)[0]['state']!='OPEN'

@pytest.mark.parametrize('approve,expected,state',[(True,'AUTHORIZED','OPEN'),(False,'REJECTED','CLOSED')])
def test_resident_resolution_persists(db,approve,expected,state):
    sg.process_event(event('UNKNOWN'),db)
    sg.resolve('e1',approve,2,path=db)
    assert sg.rows('requests',db)[0]['status']==expected
    assert sg.rows('gate',db)[0]['state']==state
    assert len(sg.rows('logs',db))==(4 if approve else 3)
    assert len(sg.rows('vehicles',db))==5
    with pytest.raises(ValueError):
        sg.resolve('e1',True,2,path=db)

def test_dedup_cannot_reopen_gate(db):
    sg.process_event(event(),db)
    sg.close_gate(db)
    sg.process_event(event(),db)
    assert len(sg.rows('requests',db))==1
    assert len(sg.rows('logs',db))==4
    assert sg.rows('gate',db)[0]['state']=='CLOSED'

def test_one_vehicle_per_cycle(db):
    sg.process_event(event(),db)
    e=event('UNKNOWN'); e['event_id']='e2'
    with pytest.raises(ValueError):
        sg.process_event(e,db)
    assert len(sg.rows('requests',db))==1

def test_visitor_requires_approval_even_if_registered(db):
    assert sg.process_event(event(visit_type='visitor'),db)['status']=='PENDING'
    sg.resolve('e1',True,3,path=db)
    assert sg.rows('requests',db)[0]['apartment_id']==3

def test_revoked_vehicle_separate_verification(db):
    sg.process_event(event('KA05JK7890'),db)
    with pytest.raises(ValueError):
        sg.resolve('e1',True,1,path=db)
    sg.resolve('e1',True,5,path=db)
    assert sg.rows('gate',db)[0]['state']=='OPEN'
    assert sg.rows('vehicles',db)[4]['is_active']==0

def test_cancel_cannot_later_approve(db):
    sg.process_event(event(None),db)
    sg.close_gate(db)
    with pytest.raises(ValueError):
        sg.resolve('e1',True,1,path=db)

def test_unique_normalized_registry(db):
    with pytest.raises(sqlite3.IntegrityError):
        sg.add_vehicle('ka 01 ab 1234','car',1,path=db)
    with pytest.raises(sqlite3.IntegrityError):
        sg.add_vehicle('KA09ZZ9999','car',900,path=db)

@pytest.mark.parametrize('payload',['null','[1]','[]','{"event_id":"x","source":"ocr"}',
    '{"event_id":"x","source":"sample","confidence":1.5}',
    '{"event_id":"x","source":"sample","confidence":NaN}'])
def test_invalid_contract(payload):
    with pytest.raises(ValueError):
        load_events(payload)
