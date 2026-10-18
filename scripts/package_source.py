"""Bundle reproducible SmartGate source and demo assets; exclude user data and installers."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
files=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in {'.py','.md','.txt','.ps1'}]
files.append(ROOT/'.gitignore')
for name in ('assets','docs','models','scripts','tests','vision','.streamlit'):
    files.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.extend((ROOT/'data/videos').glob('*.mp4'))
files.append(ROOT/'data/sample_events.json')
output=ROOT/'SmartGate-AI-source.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as bundle:
    for path in sorted(set(files)):
        if path.is_file():
            bundle.write(path,path.relative_to(ROOT))
print(f'{output}: {output.stat().st_size:,} bytes')
