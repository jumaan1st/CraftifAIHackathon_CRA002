"""Inspect public vendor download-page assets. No browser credentials are accessed."""
from pathlib import Path
import re,requests
from urllib.parse import urljoin
root=Path(__file__).resolve().parents[1]/'data/setup/pipegen-public'
root.mkdir(parents=True,exist_ok=True)
url='https://developer.craftifai.com/products/pipegen'
r=requests.get(url,timeout=30);r.raise_for_status()
(root/'page.html').write_text(r.text,encoding='utf-8')
for i,src in enumerate(re.findall(r'<script[^>]+src=["\']([^"\']+)',r.text)):
 target=urljoin(url,src)
 if not target.startswith('https://developer.craftifai.com/'):continue
 data=requests.get(target,timeout=30);data.raise_for_status()
 (root/f'bundle-{i}.js').write_text(data.text,encoding='utf-8')
 print('Public script',target,'bytes',len(data.content),flush=True)
