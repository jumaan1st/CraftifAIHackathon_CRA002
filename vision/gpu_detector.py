"""ONNX Runtime CUDA vehicle inference, using OpenCV Zoo's YOLOX model contract.

Pre/postprocessing follows the published OpenCV Zoo YOLOX implementation:
https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_yolox
"""
from pathlib import Path
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
import os,sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
VEHICLES={2:'car',3:'motorcycle',5:'bus',7:'truck'}

class CudaVehicleDetector:
    name='YOLOX-s / ONNX Runtime CUDA'
    source='gpu_vision'

    def __init__(self,provider='CUDAExecutionProvider',profiling=False):
        import onnxruntime as ort
        if provider=='CUDAExecutionProvider':
            self.dll_directories=[]
            if os.name=='nt':
                bins=list((Path(sys.prefix)/'Lib/site-packages/nvidia').glob('*/bin'))
                for folder in bins:
                    self.dll_directories.append(os.add_dll_directory(str(folder)))
                os.environ['PATH']=os.pathsep.join(str(folder) for folder in bins)+os.pathsep+os.environ.get('PATH','')
            ort.preload_dlls(directory='')
            if provider not in ort.get_available_providers():
                raise ValueError('CUDA provider unavailable. Install requirements-gpu.txt.')
        path=ROOT/'models/object_detection_yolox_2022nov.onnx'
        if not path.exists():
            raise ValueError('GPU model missing. Run scripts/download_gpu_model.py.')
        options=ort.SessionOptions()
        options.log_severity_level=3
        options.intra_op_num_threads=2
        options.enable_profiling=profiling
        output=ROOT/'data/gpu_profiles'
        output.mkdir(parents=True,exist_ok=True)
        options.profile_file_prefix=str(output/'onnx-cuda')
        providers=[(provider,{'device_id':0,'gpu_mem_limit':2*1024*1024*1024,
            'arena_extend_strategy':'kSameAsRequested','use_ep_level_unified_stream':True,
            'cudnn_conv_algo_search':'DEFAULT'})] if provider=='CUDAExecutionProvider' else [provider]
        self.session=ort.InferenceSession(str(path),sess_options=options,providers=providers)
        self.session.disable_fallback()
        if provider not in self.session.get_providers():
            raise ValueError('CUDA initialization failed; refusing to label CPU fallback as GPU inference.')
        self.input_name=self.session.get_inputs()[0].name
        self.provider=provider
        self.lock=Lock()
        # Streamlit fragments can use a different OS thread each rerun. Keep CUDA's
        # stream/thread context stable for long videos rather than growing per-thread pools.
        self.worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='smartgate-inference')
        cells=[]; strides=[]
        for stride in (8,16,32):
            y,x=np.mgrid[:640//stride,:640//stride]
            cells.append(np.stack((x,y),axis=-1).reshape(-1,2))
            strides.append(np.full((cells[-1].shape[0],1),stride))
        self.grid=np.concatenate(cells).astype(np.float32)
        self.strides=np.concatenate(strides).astype(np.float32)

    def prepare(self,frame):
        height,width=frame.shape[:2]
        scale=min(640/height,640/width)
        nw,nh=int(width*scale),int(height*scale)
        image=np.full((640,640,3),114,dtype=np.float32)
        image[:nh,:nw]=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),(nw,nh))
        return np.ascontiguousarray(image.transpose(2,0,1)[None]),scale

    def detect(self,frame,threshold=.35,class_map=None):
        class_map=VEHICLES if class_map is None else class_map
        blob,scale=self.prepare(frame)
        with self.lock:
            raw=self.worker.submit(self.session.run,None,{self.input_name:blob}).result()[0][0].copy()
        raw[:,:2]=(raw[:,:2]+self.grid)*self.strides
        raw[:,2:4]=np.exp(raw[:,2:4])*self.strides
        classes=np.argmax(raw[:,5:],axis=1)
        scores=raw[:,4]*raw[np.arange(len(raw)),classes+5]
        selected=np.flatnonzero((scores>=threshold)&np.isin(classes,list(class_map)))
        if not len(selected):return []
        boxes=raw[selected,:4].copy()
        boxes[:,:2]-=boxes[:,2:4]/2
        boxes/=scale
        keep=cv2.dnn.NMSBoxesBatched(boxes.tolist(),scores[selected].tolist(),classes[selected].tolist(),threshold,.45)
        return [{'vehicle_type':class_map[int(classes[selected[i]])],
                 'confidence':float(scores[selected[i]]),'box':[int(x) for x in boxes[i]]} for i in np.asarray(keep).reshape(-1)]
