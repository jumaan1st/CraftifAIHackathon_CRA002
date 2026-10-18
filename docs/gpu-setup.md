# RTX 3050 verification

The laptop GPU is NVIDIA GeForce RTX 3050 Laptop GPU with 4 GB VRAM and NVIDIA driver 572.60. The original shell was a 32-bit process, so Windows system executables must be reached through `C:\Windows\Sysnative` from that shell. The Python environment itself is 64-bit.

Native Windows YOLOX-s FP32 ONNX inference has been verified on the GPU. `docs/gpu-verification.json` records actual CUDA node executions, the model checksum, GPU/CPU timings and the exact measurement scope. The measured means were 40.1 ms CUDA versus 319.9 ms CPU on the same sample frame, with three warm-ups and ten timed iterations. This includes preprocessing, inference and postprocessing; it is not the displayed-video frame rate or a TensorRT/PipeGen report.

Video Gate defaults to **NVIDIA GPU (CUDA)** when this verified evidence is present. CPU remains explicitly selectable. CUDA runtime failures do not silently retry the request as CPU inference. Per-run logs record `gpu_vision` and retain the manually assigned plate identity metadata.

Installation on another compatible Windows GPU machine:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt
.\.venv\Scripts\python.exe scripts/download_gpu_model.py
.\.venv\Scripts\python.exe scripts/verify_gpu.py
```

The Nvidia runtime DLLs are installed in the project environment; the detector adds only those directories to its own process DLL search path. No driver upgrade was needed.

## Competition status

The CUDA app demo and automated tests are ready. The suite currently passes 46 tests, including an actual CUDA vehicle detection test. This does not complete Track A. All five PipeGen stages, a compiled TensorRT engine and PipeGen speed report, its live video run and actionable integration, the exported pipeline and required screenshots still need actual execution and evidence.

Ubuntu setup is complete in a dedicated WSL distribution named `SmartGate-Ubuntu`; existing Docker Desktop data is not reused for PipeGen. The official Ubuntu 22.04 image is checksum-verified using Microsoft's WSL distribution catalog. PipeGen 0.5.1 is installed from the official amd64 Debian package. Docker, NVIDIA container GPU access and X11 have passed verification. The official DeepStream runtime image is downloading. A project-local launcher corrects the vendor check that mistakes Docker stderr warnings for connection failure; it preserves prerequisite checks and restricts container mounts to app, dedicated project/data folders and X11, without host networking or broad /home or /dev mounts.
