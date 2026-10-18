"""Download the OpenCV Zoo YOLOX model and its license for optional CUDA inference."""
from pathlib import Path
import hashlib,json,requests
ROOT=Path(__file__).resolve().parents[1]
ASSETS={
 'models/object_detection_yolox_2022nov.onnx':'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx',
 'models/YOLOX-LICENSE':'https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/object_detection_yolox/LICENSE',
}
def main():
 records=[]
 for name,url in ASSETS.items():
  path=ROOT/name
  if not path.exists():
   response=requests.get(url,timeout=(20,120)); response.raise_for_status()
   if len(response.content)>100*1024*1024: raise ValueError('Unexpected model size')
   path.write_bytes(response.content)
  records.append({'path':name,'source':url,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
  print(name,path.stat().st_size,flush=True)
 (ROOT/'docs/gpu-model-assets.json').write_text(json.dumps(records,indent=2))
if __name__=='__main__':main()
