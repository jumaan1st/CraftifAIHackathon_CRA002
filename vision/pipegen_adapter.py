"""PipeGen adapter for both contract events and real DeepStream metadata."""
import json
from smartgate import validate_event

def parse_pipegen_deepstream_metadata(data):
    """
    Parse real DeepStream metadata JSON output from PipeGen (e.g., parking-metadata.json).
    Extracts persistent object tracks, deduplicates arrivals, and generates:
    - vehicle events: strictly compatible with SmartGate's access and gate engine
    - person events: for corridor security and incident monitoring
    """
    if not isinstance(data, dict) or 'frames' not in data:
        raise ValueError("Invalid PipeGen metadata: expected JSON object with 'frames' list.")

    frames = data.get('frames', [])
    tracks = {}
    for fr in frames:
        frame_idx = fr.get('frame', 0)
        pts_ns = fr.get('pts_ns', 0)
        for obj in fr.get('objects', []):
            tid = obj.get('id')
            if tid is None:
                continue
            lbl = obj.get('label', 'unknown').lower()
            conf = float(obj.get('confidence', 0.0))
            bbox = obj.get('bbox', {})
            tracker_conf = float(obj.get('tracker_confidence', 0.0))

            if tid not in tracks:
                tracks[tid] = {
                    'track_id': tid,
                    'label': lbl,
                    'first_frame': frame_idx,
                    'pts_ns': pts_ns,
                    'count': 1,
                    'max_conf': conf,
                    'sample_bbox': bbox,
                    'tracker_confidence': tracker_conf
                }
            else:
                tracks[tid]['count'] += 1
                if conf > tracks[tid]['max_conf']:
                    tracks[tid]['max_conf'] = conf
                    tracks[tid]['sample_bbox'] = bbox
                    if tracker_conf > 0:
                        tracks[tid]['tracker_confidence'] = tracker_conf

    vehicle_events = []
    person_events = []

    for tid in sorted(tracks.keys()):
        t = tracks[tid]
        lbl = t['label']
        ff = t['first_frame']

        # Map COCO classes to SmartGate vehicle types
        if lbl in ('car', 'motorcycle', 'truck', 'bus'):
            event = {
                'event_id': f"pipegen-track{tid}-{lbl}-f{ff}",
                'source': 'pipegen',
                'event_type': 'VEHICLE_DETECTED',
                'tracking_id': int(tid),
                'vehicle_type': lbl,
                'number_plate': None,
                'confidence': None,  # Plate confidence is null; YOLO detector confidence is separate
                'detector_confidence': round(t['max_conf'], 4),
                'tracker_confidence': round(t['tracker_confidence'], 4),
                'frame_count': t['count'],
                'first_frame': ff,
                'pts_ns': t['pts_ns'],
                'bbox': t['sample_bbox'],
                'direction': 'ENTRY',
                'visit_type': 'resident'
            }
            validate_event(event)
            vehicle_events.append(event)
        elif lbl == 'person':
            person_events.append({
                'event_id': f"pipegen-person-track{tid}-f{ff}",
                'source': 'pipegen',
                'event_type': 'PERSON_DETECTED',
                'tracking_id': int(tid),
                'first_frame': ff,
                'pts_ns': t['pts_ns'],
                'detector_confidence': round(t['max_conf'], 4),
                'tracker_confidence': round(t['tracker_confidence'], 4),
                'frame_count': t['count'],
                'bbox': t['sample_bbox']
            })

    summary = {
        'total_frames': len(frames),
        'unique_tracks': len(tracks),
        'vehicles_detected': len(vehicle_events),
        'persons_detected': len(person_events),
        'min_confidence': data.get('min_confidence', 0.0),
        'pipeline': data.get('pipeline', 'video_json_export')
    }

    return {
        'vehicles': vehicle_events,
        'persons': person_events,
        'summary': summary
    }

def load_events(payload):
    """
    Accepts either raw PipeGen DeepStream metadata or standard event lists.
    Returns a list of validated events for the SmartGate access engine.
    """
    if isinstance(payload, bytes):
        payload = payload.decode('utf-8')
    data = json.loads(payload)

    # Check if this is real DeepStream frame-by-frame metadata from PipeGen
    if isinstance(data, dict) and 'frames' in data:
        parsed = parse_pipegen_deepstream_metadata(data)
        if not parsed['vehicles']:
            raise ValueError('PipeGen metadata processed, but no vehicle tracks (cars/motorcycles/trucks) were found.')
        return parsed['vehicles']

    events = data if isinstance(data, list) else [data]
    if not 1 <= len(events) <= 1000:
        raise ValueError('Upload 1–1000 events.')
    for event in events:
        validate_event(event)
    return events
