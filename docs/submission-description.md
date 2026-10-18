# SmartGate AI — Connected Physical AI Security for Communities

**Track:** Track A — PipeGen (Perception)  
**Challenge:** CraftifAI Physical AI Hackathon — Building Systems That See, Decide and Act  
**Submission Form:** https://forms.gle/eJyeCKCG2UH757QZ8  

---

## 1. Problem Statement

Apartment complexes and gated communities rely on fragmented systems: security staff manually check vehicles, maintain handwritten visitor logs, and monitor disjointed CCTV feeds. Vehicle arrivals are disconnected from resident access decisions, completed visits are rarely reconciled with vehicles remaining inside, and corridor security incidents fail to trigger immediate, coordinated responses.

**SmartGate AI** solves this by unifying edge video perception with automated gate control and facility security into a real-time, physical AI operational console.

---

## 2. Solution Architecture & Flow

```
   [Camera Stream / Video Input]
               │
               ▼
┌─────────────────────────────────┐
│     CraftifAI PipeGen Core      │
│  • Decode & Preprocess (640x640)│
│  • YOLO11s FP16 TensorRT Engine │
│  • DeepStream Native Tracker    │
│  • Real-time JSON Metadata Sink │
└────────────────┬────────────────┘
                 │ (Persistent Tracking & Detection Events)
                 ▼
┌─────────────────────────────────┐
│      SmartGate AI Adapter       │
│  • Deduplicate Vehicle Arrivals │
│  • Separate Detector Confidence │
│  • Route Person Detections      │
└────────┬───────────────┬────────┘
         │               │
  (Vehicle Events)  (Person Events)
         │               │
         ▼               ▼
┌─────────────────┐ ┌─────────────────────────────────┐
│ Live Gate Agent │ │ Private Corridor Security & CCTV│
│ • State Engine  │ │ • Zone Intrusion Alerts         │
│ • Resident Appr │ │ • Simulated Safety Light Trigger│
│ • Visit Ledger  │ │ • Incident Audit Timeline       │
└─────────────────┘ └─────────────────────────────────┘
```

---

## 3. Mandatory PipeGen Technical Verification (Track A)

All five mandatory PipeGen stages were completed and verified on hardware:

### 1. Requirements Stage
- **Input:** Single video stream (`parking-entrance.mp4`, H.264, 3840×2160).
- **Specification:** Real-time edge detection and tracking for vehicles (cars, motorcycles, trucks, buses) and persons.
- **Hardware Target:** NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM), NVIDIA Driver 572.60, WSL2 Ubuntu environment (`SmartGate-Ubuntu`).

### 2. Pipeline IR Stage
- **Pipeline Architecture:** Interactive Node Graph comprising:
  `Input (File Decode) → Preprocess (Letterbox/RGB Normalize) → Inference (YOLO11s) → Postprocess (NMS) → Custom Tracking → Output (JSON Metadata Sink)`.
- **Evidence:** Verified node graph screenshot preserved at `docs/pipegen-pir.jpg` and `PipelineIR.json`.

### 3. Model Stage
- **Catalog Model:** YOLO11s (`VehicleDetection` catalog pipeline).
- **ONNX Analysis:** 321 ONNX nodes, 0 unresolved TensorRT nodes.

### 4. Compiler Stage (TensorRT Engine & Benchmarks)
- **Compiler:** TensorRT 10.3.0.
- **Precision:** FP16 (234 FP16 layers, 17 FP32 fallback layers, 1 unknown layer).
- **Compiled Engine:** `pipegen-export/models/yolo11s.fp16.plan` (**27.8 MB**, 252 TensorRT layers).
- **Engine Build Duration:** 77.8 seconds with bounded 1 GB workspace suitable for 4 GB VRAM.
- **Measured Inference Benchmark:**
  - **Inference Latency:** **10.525 ms** mean frame time (trtexec benchmark).
  - **Inference Throughput:** **~95 FPS** (pure model inference speed).
  - **Host ↔ Device Transfer:** 3.166 ms.
  - **GPU Compute Only:** 7.359 ms.
  - **Steady-State Power:** 41.73 W (measured via nvidia-smi).
- **Profile Evidence:** Preserved in `docs/pipegen/ModelStage.json` and `docs/pipegen/yolo11s.fp16.runtime.profile.json`.

### 5. Run Stage (DeepStream Live Execution)
- **Application:** Generated DeepStream 7.1 application with C++ metadata sink parser.
- **Execution:** Ran on `parking-entrance.mp4` processing **1,098 frames over 18.33 seconds**.
- **Metadata Output:** `docs/pipegen/parking-metadata.json` capturing 28 unique object tracks across cars, motorcycles, trucks, and persons.

---

## 4. Deep Integration & Actionable Output

PipeGen is load-bearing in SmartGate AI:

1. **Gate Decision & Access Cycle:**
   - DeepStream metadata is parsed by `vision/pipegen_adapter.py`.
   - Vehicle tracks (e.g., Track 0 Car, Track 5 Motorcycle) trigger entry access requests.
   - **No Fabricated Data:** In compliance with competition rules, YOLO object detection is strictly separated from authorization. Since no dedicated OCR engine is deployed, license plates remain `None` (`PENDING_VERIFICATION`).
   - The arrival triggers simulated intercom notification to residents.
   - Operator / resident authorization releases the simulated barrier, passage is committed to the SQLite visit register, and the barrier closes automatically.

2. **Corridor Security & Incident Timeline:**
   - Person tracks detected by YOLO11s in the video feed trigger zone security alerts.
   - Activates a simulated corridor safety light, plays soft audio alert, and logs the incident with exact timestamp, track ID, and video PTS into the shared SQLite incident database.

---

## 5. Exported Application & Artifacts

The complete exported PipeGen project is included in the submission repository under `pipegen-export/`:
- `run.sh`: Automated launcher script.
- `PipelineIR.json`: Full pipeline intermediate representation.
- `manifest.json` & `README.md`: Build and runtime manifests.
- `models/`: Contains `yolo11s.fp16.plan` (27.8 MB) and `yolo11s.onnx` (38 MB).
- `pipeline/`: C++ metadata parser (`meta_json.cpp`), frame JSON serializer, DeepStream configuration files (`config_det_pgie.txt`, `config_tracker.yml`), and Makefiles.

---

## 6. Implementation Notes & Limitations

- **Tracker Implementation:** The Pipeline IR originally specified ByteTrack; the generated DeepStream pipeline deployed DeepStream's native NvDCF tracker (`config_tracker.yml`). Both maintain stable track IDs across frames.
- **External Video Input:** As noted in the PipeGen export warnings, `parking-entrance.mp4` resides externally to keep repository cloning fast and clean.
- **Simulation Boundary:** Gate actuation, visitor passage timing, and resident intercom decisions are simulated in software. No physical gate motor or RFID hardware was claimed.
