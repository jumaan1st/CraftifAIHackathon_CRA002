"""Verify actual CUDA execution and record native inference evidence, not PipeGen evidence."""
import sys,json,time,statistics,subprocess,platform,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import cv2
from vision.gpu_detector import CudaVehicleDetector

def main():
    cap=cv2.VideoCapture(str(ROOT/'data/videos/parking-entrance-analysis.mp4'))
    ok,frame=cap.read();cap.release()
    if not ok: raise ValueError('Sample video cannot be read')
    evidence={}
    for provider in ('CUDAExecutionProvider','CPUExecutionProvider'):
        model=CudaVehicleDetector(provider,profiling=provider=='CUDAExecutionProvider')
        for _ in range(3):model.detect(frame)
        times=[]
        for _ in range(10):
            start=time.perf_counter();detections=model.detect(frame)
            times.append((time.perf_counter()-start)*1000)
        evidence[provider]={'mean_ms':statistics.mean(times),'median_ms':statistics.median(times),
                            'iterations':len(times),'detections':detections,'providers':model.session.get_providers()}
        if provider=='CUDAExecutionProvider':
            profile=Path(model.session.end_profiling())
            events=json.loads(profile.read_text())
            counts={}
            for event in events:
                p=event.get('args',{}).get('provider')
                if p:counts[p]=counts.get(p,0)+1
            evidence['profile_node_executions']=counts
            evidence['profile_file']=str(profile.relative_to(ROOT))
            if not counts.get('CUDAExecutionProvider'):
                raise RuntimeError('No CUDA node executions observed; GPU use is not verified')
    info=subprocess.run(['C:/Windows/System32/nvidia-smi.exe','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],capture_output=True,text=True,check=True)
    evidence.update({'verified_cuda':True,'hardware':info.stdout.strip(),'platform':platform.platform(),
        'model':'OpenCV Zoo YOLOX-s FP32 ONNX','model_sha256':hashlib.sha256((ROOT/'models/object_detection_yolox_2022nov.onnx').read_bytes()).hexdigest(),
        'scope':'Native Windows CUDA inference; not a PipeGen run or TensorRT compilation',
        'measurement':'preprocess + inference + postprocess, same sampled video frame, 3 warmups then 10 timed iterations'})
    target=ROOT/'docs/gpu-verification.json'
    target.write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2))
if __name__=='__main__':main()
