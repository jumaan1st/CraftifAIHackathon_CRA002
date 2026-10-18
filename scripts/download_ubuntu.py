"""Get the supported Ubuntu 22.04 WSL image from Microsoft's signed distribution catalog."""
from pathlib import Path
import requests,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
metadata=requests.get('https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json',timeout=30)
metadata.raise_for_status()
item=next(d for d in metadata.json()['ModernDistributions']['Ubuntu'] if d['Name']=='Ubuntu-22.04')['Amd64Url']
target=ROOT/'data/setup/ubuntu-22.04.wsl'
target.parent.mkdir(parents=True,exist_ok=True)
if not target.exists():
 response=requests.get(item['Url'],stream=True,timeout=(30,120));response.raise_for_status()
 temp=target.with_suffix('.part')
 count=0
 with temp.open('wb') as f:
  for chunk in response.iter_content(1024*1024):
   f.write(chunk);count+=len(chunk)
   if count%(50*1024*1024)==0:print('Ubuntu downloaded MB',count//1024//1024,flush=True)
 temp.replace(target)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
if digest!=item['Sha256']:raise ValueError('Ubuntu image checksum mismatch')
(ROOT/'docs/ubuntu-image.json').write_text(json.dumps(dict(item,actual_sha256=digest),indent=2))
print('Ubuntu image verified',target,flush=True)
