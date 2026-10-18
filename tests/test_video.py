from pathlib import Path
import cv2
import numpy as np
import pytest
import smartgate as sg
from vision.video_service import VideoRun,VehicleDetector,ROOT

class StubDetector:
    def __init__(self,found=True): self.found=found
    def detect(self,frame):
        return [{'vehicle_type':'car','confidence':.92,'box':[10,10,100,100]}] if self.found else []

@pytest.fixture
def video(tmp_path,monkeypatch):
    path=tmp_path/'clip.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(64,48))
    assert writer.isOpened()
    for _ in range(10): writer.write(np.zeros((48,64,3),dtype=np.uint8))
    writer.release()
    monkeypatch.setattr(VideoRun,'save_report',lambda self:None)
    return path

@pytest.fixture
def db(tmp_path):
    path=tmp_path/'db.sqlite'
    sg.initialize(path)
    return path

def test_real_bundled_video_detection():
    sample=ROOT/'data'/'videos'/'parking-entrance.mp4'
    if not sample.exists() or not (ROOT/'models'/'yolov4-tiny.weights').exists():
        pytest.skip('Run scripts/download_video_assets.py to enable real model integration test')
    run=VideoRun(sample,'sample','KA01AB1234')
    try:
        detected=VehicleDetector().detect(run.frame)
        assert any(d['vehicle_type']=='car' and d['confidence']>.5 for d in detected)
    finally: run.capture.release()

def test_video_authorized_opens_passes_closes_once(video,db):
    run=VideoRun(video,'clip','KA01AB1234')
    try:
        run.tick(StubDetector(),clock=0,path=db)
        assert run.phase=='OPENING' and sg.rows('gate',db)[0]['state']=='OPEN'
        run.tick(StubDetector(),clock=1,path=db)
        assert run.phase=='OPEN'
        run.tick(StubDetector(),clock=2,path=db)
        assert run.phase=='CROSSING'
        run.tick(StubDetector(),clock=3.1,path=db)
        assert run.phase=='CLOSING' and len(sg.rows('visits',db))==1
        run.tick(StubDetector(),clock=4.1,path=db)
        run.tick(StubDetector(),clock=5,path=db)
        assert run.phase=='COMPLETE'
        assert sg.rows('gate',db)[0]['state']=='CLOSED'
        assert len(sg.rows('logs',db))==5
        assert sg.rows('logs',db)[0]['source']=='cpu_vision'
    finally: run.capture.release()

def test_denied_video_never_opens(video,db):
    run=VideoRun(video,'clip','KA05JK7890')
    try:
        run.tick(StubDetector(),clock=0,path=db)
        run.tick(StubDetector(),clock=10,path=db)
        assert run.phase=='REJECTED'
        assert sg.rows('gate',db)[0]['state']=='CLOSED'
        assert not sg.rows('visits',db)
        assert not any(x['event_type']=='GATE_OPENED' for x in sg.rows('logs',db))
        assert sg.rows('requests',db)[0]['status']=='DENIED'
    finally: run.capture.release()

def test_no_detection_no_access_attempt(video,db):
    run=VideoRun(video,'clip','KA01AB1234')
    try:
        run.tick(StubDetector(False),clock=0,path=db)
        assert not sg.rows('requests',db)
        assert sg.rows('gate',db)[0]['state']=='CLOSED'
    finally: run.capture.release()

@pytest.mark.parametrize('approve',[True,False])
def test_unknown_video_resident_decision(video,db,approve):
    run=VideoRun(video,'clip',None)
    try:
        run.tick(StubDetector(),clock=0,path=db)
        assert run.phase=='WAITING'
        run.resolve(approve,1,clock=2,path=db)
        run.tick(StubDetector(),clock=7,path=db)
        assert len(sg.rows('visits',db))==(1 if approve else 0)
        assert sg.rows('gate',db)[0]['state']=='CLOSED'
    finally: run.capture.release()

def test_pause_freezes_gate_timer(video,db):
    run=VideoRun(video,'clip','KA01AB1234')
    try:
        run.tick(StubDetector(),clock=0,path=db)
        run.pause(clock=.5)
        run.tick(StubDetector(),clock=100,path=db)
        assert not sg.rows('visits',db)
        run.resume(clock=100)
        run.tick(StubDetector(),clock=100.1,path=db)
        assert run.phase=='OPENING'
    finally: run.capture.release()

def test_stop_before_crossing_cancels_without_visit(video,db):
    run=VideoRun(video,'clip','KA01AB1234')
    run.tick(StubDetector(),clock=0,path=db)
    run.stop(db)
    assert sg.rows('gate',db)[0]['state']=='CLOSED'
    assert not sg.rows('visits',db)

def test_stop_after_crossing_preserves_visit(video,db):
    run=VideoRun(video,'clip','KA01AB1234')
    run.tick(StubDetector(),clock=0,path=db)
    run.tick(StubDetector(),clock=3.1,path=db)
    run.stop(db)
    assert len(sg.rows('visits',db))==1

def test_video_exit_closes_recorded_visit(video,db):
    entry=VideoRun(video,'clip','KA01AB1234')
    try:
        entry.tick(StubDetector(),clock=0,path=db)
        entry.tick(StubDetector(),clock=5,path=db)
    finally: entry.capture.release()
    visit=sg.rows('visits',db)[0]
    exit_run=VideoRun(video,'clip','KA01AB1234',direction='EXIT',presence_id=visit['id'])
    try:
        exit_run.tick(StubDetector(),clock=10,path=db)
        exit_run.tick(StubDetector(),clock=15,path=db)
        assert sg.rows('visits',db)[0]['exit_time']
    finally: exit_run.capture.release()

def test_invalid_video_is_rejected(tmp_path):
    path=tmp_path/'broken.mp4'
    path.write_bytes(b'not a video')
    with pytest.raises(ValueError,match='decode'):
        VideoRun(path,'broken',None)

def test_stop_and_frame_reads_are_safe_concurrently(video,db):
    from concurrent.futures import ThreadPoolExecutor
    run=VideoRun(video,'clip','KA01AB1234')
    run.tick(StubDetector(),clock=0,path=db)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(run.advance_frame) for _ in range(8)]
        futures.append(pool.submit(run.stop,db))
        for future in futures: future.result()
    assert not run.playing
    assert sg.rows('gate',db)[0]['state']=='CLOSED'

def test_actual_cuda_model_on_verified_laptop():
    import json
    report=ROOT/'docs/gpu-verification.json'
    if not report.exists() or not json.loads(report.read_text()).get('verified_cuda'):
        pytest.skip('Requires verified CUDA laptop and optional GPU dependencies')
    from vision.gpu_detector import CudaVehicleDetector
    run=VideoRun(ROOT/'data/videos/parking-entrance-analysis.mp4','sample',None)
    try:
        detector=CudaVehicleDetector()
        found=detector.detect(run.frame)
        assert 'CUDAExecutionProvider' in detector.session.get_providers()
        assert any(d['vehicle_type']=='car' and d['confidence']>.5 for d in found)
        # Repeated calls arriving from fresh framework threads must not exhaust
        # CUDA's allocator after the first successful frame.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as callers:
            futures=[callers.submit(detector.detect,run.frame) for _ in range(64)]
            assert all(any(d['vehicle_type']=='car' for d in f.result()) for f in futures)
    finally:run.capture.release()

def test_gpu_video_source_is_logged(video,db):
    detection=StubDetector()
    detection.name='Verified GPU test double'
    detection.source='gpu_vision'
    run=VideoRun(video,'clip','KA05JK7890',backend='NVIDIA GPU (CUDA)')
    try:
        run.tick(detection,clock=0,path=db)
        assert all(r['source']=='gpu_vision' for r in sg.rows('logs',db))
    finally:run.capture.release()
