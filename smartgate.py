"""Persistent simulation domain. No inference or physical hardware is performed here."""
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).parent / 'data' / 'smartgate.db'

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def normalize(plate):
    return re.sub(r'[^A-Z0-9]', '', (plate or '').upper())

@contextmanager
def connect(path=DB):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        with con:
            yield con
    finally:
        con.close()

def initialize(path=DB):
    with connect(path) as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS apartments (
          id INTEGER PRIMARY KEY, block_name TEXT NOT NULL, flat_number TEXT NOT NULL,
          resident_name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS vehicles (
          id INTEGER PRIMARY KEY, registration_number TEXT NOT NULL UNIQUE,
          vehicle_type TEXT NOT NULL, apartment_id INTEGER NOT NULL REFERENCES apartments(id),
          is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)));
        CREATE TABLE IF NOT EXISTS requests (
          event_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, tracking_id TEXT,
          registration_number TEXT, vehicle_type TEXT NOT NULL, source TEXT NOT NULL,
          confidence REAL, visit_type TEXT NOT NULL, apartment_id INTEGER REFERENCES apartments(id),
          status TEXT NOT NULL, reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS access_events (
          id INTEGER PRIMARY KEY, event_id TEXT NOT NULL REFERENCES requests(event_id),
          timestamp TEXT NOT NULL, tracking_id TEXT, registration_number TEXT,
          apartment_id INTEGER REFERENCES apartments(id), event_type TEXT NOT NULL,
          authorization_status TEXT NOT NULL, authorization_method TEXT NOT NULL,
          reason TEXT NOT NULL, source TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS gate (
          id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL, event_id TEXT,
          reason TEXT NOT NULL);
        INSERT OR IGNORE INTO gate VALUES (1,'CLOSED',NULL,'Ready for the next vehicle');
        CREATE TABLE IF NOT EXISTS visits (
          id INTEGER PRIMARY KEY, arrival_event_id TEXT NOT NULL UNIQUE REFERENCES requests(event_id),
          registration_number TEXT, apartment_id INTEGER REFERENCES apartments(id),
          vehicle_type TEXT NOT NULL, entry_time TEXT NOT NULL, exit_time TEXT,
          exit_event_id TEXT UNIQUE REFERENCES requests(event_id));
        ''')
        # Non-destructive migration for existing demos and their audit history.
        columns = {r['name'] for r in c.execute('PRAGMA table_info(requests)')}
        for name, definition in [('direction', "TEXT NOT NULL DEFAULT 'ENTRY'"),
                                 ('presence_id', 'INTEGER REFERENCES visits(id)'),
                                 ('completed_at', 'TEXT')]:
            if name not in columns:
                c.execute(f'ALTER TABLE requests ADD COLUMN {name} {definition}')
        for i, (block, flat, name) in enumerate([
            ('A','101','Asha Rao'),('A','202','Dev Mehta'),('B','103','Mira Sen'),
            ('B','204','Kabir Das'),('C','301','Leela Nair')], 1):
            c.execute('INSERT OR IGNORE INTO apartments VALUES (?,?,?,?)', (i,block,flat,name))
        for i, plate in enumerate(['KA01AB1234','KA02CD5678','KA03EF9012','KA04GH3456','KA05JK7890'],1):
            c.execute('INSERT OR IGNORE INTO vehicles VALUES (?,?,?,?,?)',
                      (i,plate,'motorcycle' if i==3 else 'car',i,0 if i==5 else 1))

def rows(table, path=DB):
    queries = {
        'apartments': 'SELECT * FROM apartments ORDER BY id',
        'vehicles': '''SELECT v.*,a.block_name,a.flat_number,a.resident_name FROM vehicles v
                       JOIN apartments a ON a.id=v.apartment_id ORDER BY v.id''',
        'requests': 'SELECT * FROM requests ORDER BY timestamp DESC, rowid DESC',
        'logs': '''SELECT e.*,a.block_name,a.flat_number,a.resident_name FROM access_events e
                  LEFT JOIN apartments a ON a.id=e.apartment_id ORDER BY e.id DESC''',
        'gate': 'SELECT * FROM gate WHERE id=1',
        'visits': '''SELECT v.*,a.block_name,a.flat_number,a.resident_name FROM visits v
                     LEFT JOIN apartments a ON a.id=v.apartment_id ORDER BY v.id DESC'''}
    with connect(path) as c:
        return [dict(r) for r in c.execute(queries[table])]

def add_vehicle(plate, vehicle_type, apartment_id, active=True, path=DB):
    plate = normalize(plate)
    if not 5 <= len(plate) <= 15:
        raise ValueError('Enter a registration with 5–15 letters and digits.')
    if vehicle_type not in ('car','motorcycle','truck','bus'):
        raise ValueError('Unsupported vehicle type')
    with connect(path) as c:
        c.execute('INSERT INTO vehicles(registration_number,vehicle_type,apartment_id,is_active) VALUES (?,?,?,?)',
                  (plate,vehicle_type,apartment_id,int(active)))

def validate_event(event):
    if not isinstance(event, dict):
        raise ValueError('Each event must be a JSON object.')
    eid = event.get('event_id')
    if not isinstance(eid,str) or not eid.strip() or len(eid)>150:
        raise ValueError('A stable, nonempty event_id (max 150 characters) is required.')
    source = event.get('source')
    if source not in ('sample','manual','pipegen','cpu_vision','gpu_vision'):
        raise ValueError('source must be sample, manual, cpu_vision, gpu_vision or pipegen.')
    plate = event.get('number_plate')
    if plate is not None and not isinstance(plate,str):
        raise ValueError('number_plate must be a string or null.')
    confidence = event.get('confidence')
    if confidence is not None and (isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not 0<=confidence<=1):
        raise ValueError('confidence must be between 0 and 1 or null.')
    kind = event.get('visit_type','resident')
    if kind not in ('resident','visitor','delivery'):
        raise ValueError('visit_type must be resident, visitor or delivery.')
    if event.get('event_type','VEHICLE_DETECTED') != 'VEHICLE_DETECTED':
        raise ValueError('Only VEHICLE_DETECTED events are supported.')
    vehicle_type = event.get('vehicle_type','car')
    if vehicle_type not in ('car','motorcycle','truck','bus'):
        raise ValueError('Unsupported vehicle_type.')
    if event.get('direction','ENTRY') not in ('ENTRY','EXIT'):
        raise ValueError('direction must be ENTRY or EXIT.')
    if event.get('presence_id') is not None and (type(event['presence_id']) is not int or event['presence_id'] < 1):
        raise ValueError('presence_id must be a positive integer.')
    return eid, source, normalize(plate), confidence, kind, vehicle_type

def log(c, request, status, method, reason, apartment_id, event_type='ACCESS_DECISION'):
    c.execute('''INSERT INTO access_events(event_id,timestamp,tracking_id,registration_number,
        apartment_id,event_type,authorization_status,authorization_method,reason,source)
        VALUES (?,?,?,?,?,?,?,?,?,?)''',
        (request['event_id'],now(),request['tracking_id'],request['registration_number'],
         apartment_id,event_type,status,method,reason,request['source']))

def process_event(event, path=DB):
    eid, source, plate, confidence, kind, vehicle_type = validate_event(event)
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        existing = c.execute('SELECT * FROM requests WHERE event_id=?',(eid,)).fetchone()
        if existing:
            return dict(existing)
        gate = c.execute('SELECT * FROM gate WHERE id=1').fetchone()
        if gate['event_id'] is not None:
            raise ValueError('Complete or close the current gate cycle before processing another vehicle.')
        vehicle = c.execute('SELECT * FROM vehicles WHERE registration_number=?',(plate,)).fetchone()
        apartment = vehicle['apartment_id'] if vehicle else None
        direction = event.get('direction','ENTRY')
        presence_id = event.get('presence_id')
        if direction == 'EXIT':
            presence = c.execute('SELECT * FROM visits WHERE id=? AND exit_time IS NULL',(presence_id,)).fetchone() if presence_id else c.execute(
                'SELECT * FROM visits WHERE registration_number=? AND exit_time IS NULL ORDER BY id DESC LIMIT 1',(plate,)).fetchone()
            if not presence:
                raise ValueError('No vehicle inside matches this exit. Simulate an entry first.')
            if plate != (presence['registration_number'] or ''):
                raise ValueError('Exit plate does not match the selected vehicle inside.')
            presence_id, apartment = presence['id'], presence['apartment_id']
            status, reason = 'AUTHORIZED', 'Recorded vehicle inside cleared for simulated exit'
        elif plate and c.execute('SELECT 1 FROM visits WHERE registration_number=? AND exit_time IS NULL',(plate,)).fetchone():
            raise ValueError('This vehicle is already inside. Choose Exit to complete its visit.')
        elif not plate or (confidence is not None and confidence < .8):
            status, reason = 'PENDING', 'Plate Not Recognized: manual verification required'
        elif kind != 'resident':
            status, reason = 'PENDING', f'{kind.title()} requires destination resident approval'
        elif vehicle and vehicle['is_active']:
            status, reason = 'AUTHORIZED', 'Active registered vehicle permitted by demo entry policy'
        elif vehicle:
            status, reason = 'DENIED', 'Vehicle registration revoked; separate resident verification required'
        else:
            status, reason = 'PENDING', 'Unknown vehicle: resident verification required'
        c.execute('''INSERT INTO requests(event_id,timestamp,tracking_id,registration_number,vehicle_type,
          source,confidence,visit_type,apartment_id,status,reason,direction,presence_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (eid,now(),str(event.get('tracking_id','—')),plate,vehicle_type,source,confidence,kind,apartment,status,reason,direction,presence_id))
        request = dict(c.execute('SELECT * FROM requests WHERE event_id=?',(eid,)).fetchone())
        log(c,request,'DETECTED','SIMULATOR' if source in ('sample','manual') else 'VISION',
            f'{direction.title()} vehicle presented at gate',apartment,'VEHICLE_DETECTED')
        log(c,request,status,'REGISTRY' if status=='AUTHORIZED' else 'POLICY',reason,apartment)
        state = 'OPEN' if status=='AUTHORIZED' else 'PENDING_VERIFICATION' if status=='PENDING' else 'CLOSED'
        c.execute('UPDATE gate SET state=?,event_id=?,reason=? WHERE id=1',(state,eid,reason))
        if status == 'AUTHORIZED':
            log(c,request,'OPEN','GATE_SIMULATOR','Authorization released the barrier',apartment,'GATE_OPENED')
        return request

def resolve(event_id, approve, apartment_id, method='Resident approval (simulated)', path=DB):
    if method not in ('Resident approval (simulated)','RFID (simulated)','Fingerprint (simulated)'):
        raise ValueError('Unsupported verification method')
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM requests WHERE event_id=?',(event_id,)).fetchone()
        if not row or row['status'] not in ('PENDING','DENIED'):
            raise ValueError('This request is no longer awaiting verification.')
        gate = c.execute('SELECT * FROM gate WHERE id=1').fetchone()
        if gate['event_id'] != event_id:
            raise ValueError('Only the current gate request may be resolved.')
        apt = c.execute('SELECT * FROM apartments WHERE id=?',(apartment_id,)).fetchone()
        if not apt:
            raise ValueError('Select the resident who is authorizing this visit.')
        if row['visit_type']=='resident' and row['apartment_id'] and row['apartment_id']!=apartment_id:
            raise ValueError('Registered resident vehicle requires its mapped apartment to verify.')
        status = 'AUTHORIZED' if approve else 'REJECTED'
        reason = f"{apt['resident_name']} ({apt['block_name']}-{apt['flat_number']}) {'approved' if approve else 'rejected'} this visit; simulated identity and consent"
        c.execute('UPDATE requests SET status=?,reason=?,apartment_id=? WHERE event_id=?',
                  (status,reason,apartment_id,event_id))
        log(c,dict(row),status,method,reason,apartment_id,'RESIDENT_VERIFICATION')
        if approve:
            log(c,dict(row),'OPEN','GATE_SIMULATOR','Resident approval released the barrier',apartment_id,'GATE_OPENED')
        c.execute('UPDATE gate SET state=?,reason=? WHERE id=1',('OPEN' if approve else 'CLOSED',reason))

def record_passage(event_id, path=DB):
    """Commit an actual simulated crossing once; authorization alone is not a crossing."""
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM requests WHERE event_id=?',(event_id,)).fetchone()
        if not row:
            raise ValueError('Unknown request.')
        if row['completed_at']:
            return
        gate = c.execute('SELECT * FROM gate WHERE id=1').fetchone()
        if gate['event_id'] != event_id or gate['state'] != 'OPEN' or row['status'] != 'AUTHORIZED':
            raise ValueError('Passage requires the current vehicle to be authorized and the gate open.')
        stamp = now()
        if row['direction'] == 'ENTRY':
            if row['registration_number'] and c.execute('SELECT 1 FROM visits WHERE registration_number=? AND exit_time IS NULL',(row['registration_number'],)).fetchone():
                raise ValueError('Vehicle is already inside.')
            c.execute('''INSERT INTO visits(arrival_event_id,registration_number,apartment_id,vehicle_type,entry_time)
                         VALUES (?,?,?,?,?)''',(event_id,row['registration_number'],row['apartment_id'],row['vehicle_type'],stamp))
        else:
            changed = c.execute('UPDATE visits SET exit_time=?,exit_event_id=? WHERE id=? AND exit_time IS NULL',
                                (stamp,event_id,row['presence_id'])).rowcount
            if not changed:
                raise ValueError('This visit has already exited.')
        c.execute('UPDATE requests SET completed_at=? WHERE event_id=?',(stamp,event_id))
        log(c,dict(row),'COMPLETED','GATE_SIMULATOR',
            'Vehicle entered the community' if row['direction']=='ENTRY' else 'Vehicle exited the community',
            row['apartment_id'],'VEHICLE_ENTERED' if row['direction']=='ENTRY' else 'VEHICLE_EXITED')

def close_gate(path=DB, expected_event_id=None):
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        gate = c.execute('SELECT * FROM gate WHERE id=1').fetchone()
        if expected_event_id is not None and gate['event_id'] != expected_event_id:
            raise ValueError('The active gate cycle changed; refresh before continuing.')
        if gate['event_id']:
            request = dict(c.execute('SELECT * FROM requests WHERE event_id=?',(gate['event_id'],)).fetchone())
            if request['status'] == 'PENDING':
                c.execute("UPDATE requests SET status='CANCELLED',reason='Operator closed this verification cycle' WHERE event_id=?",(gate['event_id'],))
            if request['status']=='AUTHORIZED' and not request['completed_at']:
                c.execute("UPDATE requests SET status='CANCELLED',reason='Cycle cancelled before vehicle passage' WHERE event_id=?",(gate['event_id'],))
            log(c,request,'CLOSED','GATE_SIMULATOR','Barrier closed after passage' if request['completed_at'] else 'Barrier closed; no passage recorded',request['apartment_id'],'GATE_CLOSED')
        c.execute("UPDATE gate SET state='CLOSED',event_id=NULL,reason='Ready for the next vehicle' WHERE id=1")
