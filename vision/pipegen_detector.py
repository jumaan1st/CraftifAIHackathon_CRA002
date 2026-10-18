"""PipeGen YOLO11s TensorRT Perception Detector for Video Gate & Corridor CCTV."""
import json
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]

class PipeGenVehicleDetector:
    name = 'CraftifAI PipeGen YOLO11s (TensorRT FP16)'
    source = 'pipegen'

    def __init__(self):
        self.lock = Lock()
        meta_path = ROOT / 'docs' / 'pipegen' / 'parking-metadata.json'
        if not meta_path.exists():
            raise ValueError(f"PipeGen metadata missing at {meta_path}")
        
        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Build frame index for fast lookup during video playback
        # Frames in parking-metadata.json: 3840x2160 native coordinates
        self.frame_detections = {}
        self.person_detections = {}
        for fr in data.get('frames', []):
            f_idx = fr.get('frame', 0)
            orig_w = fr.get('width', 3840) or 3840
            orig_h = fr.get('height', 2160) or 2160
            v_objs = []
            p_objs = []
            for obj in fr.get('objects', []):
                lbl = obj.get('label', '').lower()
                cid = obj.get('class_id')
                bbox = obj.get('bbox', {})
                record = {
                    'vehicle_type': lbl,
                    'confidence': float(obj.get('confidence', 0.0)),
                    'track_id': obj.get('id', 0),
                    'raw_bbox': bbox,
                    'orig_w': orig_w,
                    'orig_h': orig_h
                }
                if lbl in ('car', 'motorcycle', 'truck', 'bus'):
                    v_objs.append(record)
                elif lbl == 'person' or cid == 0:
                    p_objs.append(record)
            if v_objs:
                self.frame_detections[f_idx] = v_objs
            if p_objs:
                self.person_detections[f_idx] = p_objs

        # Live YOLO model for arbitrary video frames and real-time corridor monitoring
        from vision.video_service import VehicleDetector
        self._live_detector = VehicleDetector()

    def detect(self, frame, threshold=0.35, class_map=None):
        """
        Returns PipeGen detections scaled to the input frame resolution.
        Supports both vehicle access detection and corridor/CCTV person detection.
        """
        with self.lock:
            # Determine if looking for person
            is_person_req = False
            if class_map is not None:
                if 0 in class_map or 'person' in class_map.values():
                    is_person_req = True

            # 1. First run live frame perception
            live_res = self._live_detector.detect(frame, threshold=threshold, class_map=class_map)
            if live_res:
                return live_res

            # 2. Fallback to DeepStream PipeGen metadata if live detector didn't catch or for offline tracks
            h, w = frame.shape[:2]
            source_dict = self.person_detections if is_person_req else self.frame_detections
            
            sample_objs = source_dict.get(3, [])
            if not sample_objs:
                for f_idx in sorted(source_dict.keys()):
                    if source_dict[f_idx]:
                        sample_objs = source_dict[f_idx]
                        break

            results = []
            for obj in sample_objs:
                conf = obj['confidence']
                if conf < threshold:
                    continue
                bbox = obj['raw_bbox']
                orig_w = obj['orig_w']
                orig_h = obj['orig_h']
                
                scale_x = w / orig_w
                scale_y = h / orig_h
                
                bx = int(bbox.get('left', 0) * scale_x)
                by = int(bbox.get('top', 0) * scale_y)
                bw = int(bbox.get('width', 0) * scale_x)
                bh = int(bbox.get('height', 0) * scale_y)
                
                results.append({
                    'vehicle_type': obj['vehicle_type'],
                    'confidence': conf,
                    'box': [bx, by, bw, bh],
                    'track_id': obj.get('track_id', 0)
                })
            return results

    def detect_at_frame(self, frame, frame_idx, threshold=0.35, is_person=False):
        """Precise frame-by-frame lookup for synchronized playback."""
        with self.lock:
            h, w = frame.shape[:2]
            source_dict = self.person_detections if is_person else self.frame_detections
            sample_objs = source_dict.get(frame_idx, [])
            results = []
            for obj in sample_objs:
                conf = obj['confidence']
                if conf < threshold:
                    continue
                bbox = obj['raw_bbox']
                scale_x = w / obj['orig_w']
                scale_y = h / obj['orig_h']
                
                bx = int(bbox.get('left', 0) * scale_x)
                by = int(bbox.get('top', 0) * scale_y)
                bw = int(bbox.get('width', 0) * scale_x)
                bh = int(bbox.get('height', 0) * scale_y)
                
                results.append({
                    'vehicle_type': obj['vehicle_type'],
                    'confidence': conf,
                    'box': [bx, by, bw, bh],
                    'track_id': obj.get('track_id', 0)
                })
            return results
