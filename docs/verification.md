# Verification

Verified on 18 October 2026 using Python 3.13.3, Streamlit 1.66.0 and OpenCV 4.14.0.

`python -m pytest -q`: **54 passed**.

Policy and lifecycle coverage includes authorization, denials, resident verification, idempotent events and crossings, entry/exit occupancy, schema migration, stale-cycle protection, all eight pages and the full animated demo.

CUDA coverage includes real YOLOX-s inference and 64 repeated calls from four caller threads to check sustained use. Video coverage includes genuine YOLOv4-tiny CPU vehicle detection on the downloaded Pexels clip, granted and denied video policy, no-detection safety, approval and rejection, pause timing, stop before/after crossing, exit, invalid videos and concurrent frame-read/stop safety. Controller tests use labelled detection stubs; the real-model test loads the original weights and runs inference on the actual sample.

Browser checks verified the built-in footage, actual detection boxes, granted gate-open/entry/gate-close audit, a denied run with no gate opening or passage, pause and the custom-file uploader accepting the original 38.1 MB MP4. The uploaded clip runs through the same local detector/controller. A decoder crash found during stop/read overlap was corrected by serializing each run's decoder and lifecycle operations. Regression tests pass after that change.

Original stock footage is retained for normal video preview. A 960×540, four-frame/sec local derivative reduces CPU analysis cost. Analysis is sampled playback without audio. Plate identities and physical passage timing are explicitly simulated, not inferred.

Downloads and source hashes are recorded in `docs/video-assets.json`; clip/model provenance is in `docs/video-sources.md`. Detection metadata reports are local under `data/video_reports/`, while access events persist in SQLite with source `cpu_vision`.

Still unverified/incomplete: plate OCR, multi-vehicle tracking, native PipeGen export mapping, actual five-stage PipeGen run, TensorRT compilation/speed report and hardware gate actuation. CPU video detection does not replace mandatory Track A PipeGen evidence.

Full CUDA sample verification: `docs/gpu-video-verification.json` records 75 decoded frames per scenario, 71 frames with detections, completed entry and matching exit, and a denied run with no gate opening. These checks use an isolated temporary database and deterministic software timer; they are not camera crossing measurements or PipeGen evidence.

Security extension: eight additional tests pass for disarmed safety, person/motion rules, threshold behavior, motion warm-up/static frames and persistent shared-zone incidents. The complete existing 46-test suite also passed after adding the ninth page and configurable detector class mapping.

Full suite after PipeGen DeepStream metadata integration: **57 passed in 52.80 seconds** (including `tests/test_pipegen_adapter.py`).

PipeGen Track A technical verification:
- 5-stage pipeline run complete (Requirements, Pipeline IR, Model, Compiler, Run).
- YOLO11s FP16 TensorRT engine compiled (`yolo11s.fp16.plan`, 27.8 MB, 252 layers) with measured 10.525 ms inference (~95 FPS).
- DeepStream run executed on `parking-entrance.mp4` (1,098 frames over 18.33 seconds), outputting `parking-metadata.json`.
- Dual-mode adapter in `vision/pipegen_adapter.py` seamlessly maps DeepStream vehicle tracks to SmartGate arrival events and person tracks to the corridor security timeline.
- Complete exported PipeGen project preserved in `pipegen-export/` with runnable `run.sh`.

