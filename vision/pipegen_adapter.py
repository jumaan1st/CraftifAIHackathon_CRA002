"""Strict application contract, not a claim to support every PipeGen export format."""
import json
from smartgate import validate_event

def load_events(payload):
    data = json.loads(payload)
    events = data if isinstance(data,list) else [data]
    if not 1 <= len(events) <= 1000:
        raise ValueError('Upload 1–1000 events.')
    for event in events:
        validate_event(event)
    return events
