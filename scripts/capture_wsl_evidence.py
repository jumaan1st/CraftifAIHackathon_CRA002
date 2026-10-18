"""Save actual WSL/container/X11 verification, without claiming a PipeGen run."""
from pathlib import Path
from datetime import datetime,timezone
import subprocess,json
ROOT=Path(__file__).resolve().parents[1]
commands={
 'ubuntu':'cat /etc/os-release',
 'docker':'docker version --format "{{.Server.Version}}"',
 'toolkit':'nvidia-ctk --version',
 'container_gpu':'docker run --rm --gpus all ubuntu:22.04 nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader',
 'x11':'xdpyinfo -display :0 | head -n 8',
 'linux_user':'id',
}
record={'collected_at':datetime.now(timezone.utc).isoformat(),'distribution':'SmartGate-Ubuntu',
        'scope':'Environment prerequisites only; PipeGen stages and TensorRT are not completed','checks':{}}
for name,command in commands.items():
 r=subprocess.run(['C:/Windows/System32/wsl.exe','-d','SmartGate-Ubuntu','-u','smartgate','--','bash','-lc',command],capture_output=True,timeout=45)
 record['checks'][name]={'command':command,'exit_code':r.returncode,'stdout':r.stdout.decode('utf-8',errors='replace').strip(),'stderr':r.stderr.decode('utf-8',errors='replace').strip()}
 print(name,'PASS' if r.returncode==0 else 'FAIL',flush=True)
(ROOT/'docs/environment-verification.json').write_text(json.dumps(record,indent=2))
