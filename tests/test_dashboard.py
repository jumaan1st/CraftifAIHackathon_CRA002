from pathlib import Path
from streamlit.testing.v1 import AppTest
import smartgate as sg
import simulation_ui

def setup_app(tmp_path,monkeypatch):
    path=tmp_path/'ui.db'
    for name in ('initialize','rows','add_vehicle','process_event','resolve','close_gate','record_passage'):
        original=getattr(sg,name)
        def wrapped(*args,_fn=original,**kwargs):
            return _fn(*args,**dict(kwargs,path=path))
        monkeypatch.setattr(sg,name,wrapped)
    monkeypatch.setattr(simulation_ui,'sleep',lambda _:None)
    app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=20)
    return app.run()

def click(app,label):
    next(b for b in app.button if b.label==label).click().run(timeout=20)
    assert not app.exception, str(app.exception)

def test_all_pages_render(tmp_path,monkeypatch):
    app=setup_app(tmp_path,monkeypatch)
    for page in ['Live Simulator','Video Gate','Private Corridor & CCTV','Overview','Vehicle Registry','Access Logs','Vision Integration','Competition Readiness','Architecture']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, str(app.exception)

def test_full_demo(tmp_path,monkeypatch):
    app=setup_app(tmp_path,monkeypatch)
    click(app,'▶ Play full entry + exit demo')
    assert sg.rows('gate')[0]['state']=='CLOSED'
    visits=sg.rows('visits')
    assert len(visits)==1 and visits[0]['exit_time']
    types=[x['event_type'] for x in sg.rows('logs')]
    assert types.count('GATE_OPENED')==2
    assert types.count('GATE_CLOSED')==2
    assert types.count('VEHICLE_ENTERED')==types.count('VEHICLE_EXITED')==1
    assert len(types)==10

def test_registered_entry_then_exit(tmp_path,monkeypatch):
    app=setup_app(tmp_path,monkeypatch)
    click(app,'Start entry')
    assert len([v for v in sg.rows('visits') if not v['exit_time']])==1
    next(r for r in app.radio if r.label=='Movement').set_value('Exit').run()
    click(app,'Start exit')
    assert sg.rows('gate')[0]['state']=='CLOSED'
    assert sg.rows('visits')[0]['exit_time']

import pytest
@pytest.mark.parametrize('approve',[True,False])
def test_unknown_approval_or_rejection(tmp_path,monkeypatch,approve):
    app=setup_app(tmp_path,monkeypatch)
    app.selectbox[0].set_value('Unknown vehicle').run()
    click(app,'Start entry')
    assert sg.rows('gate')[0]['state']=='PENDING_VERIFICATION'
    assert not sg.rows('visits')
    click(app,'Approve visit & open gate' if approve else 'Reject visit · keep gate closed')
    assert sg.rows('gate')[0]['state']=='CLOSED'
    assert len(sg.rows('visits'))==(1 if approve else 0)
    assert sg.rows('requests')[0]['status']==('AUTHORIZED' if approve else 'REJECTED')
