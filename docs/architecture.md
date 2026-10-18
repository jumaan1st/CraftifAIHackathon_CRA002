# SmartGate AI architecture

A Python modular monolith: Streamlit handles presentation, `smartgate.py` owns database transactions and authorization, `vision/video_service.py` runs local CPU or CUDA detections and the video cycle, and `vision/pipegen_adapter.py` validates the external event boundary.

## Data flow

Video → external PipeGen detection / tracking / optional OCR → producer mapping to JSON → event validator → registry lookup → authorization → simulated gate → persistent SQLite audit → dashboard.

The demo supports sample/manual events and a Video Gate mode with real YOLOX-s CUDA or YOLOv4-tiny CPU vehicle detection. An explicitly operator-assigned demo plate links the first detected vehicle to policy; this is not OCR. A timed simulated passage drives the gate and visit record. The processed playback is sampled at up to four frames/sec without audio. The code-native vector scene beside it animates the software barrier. The separate reference uploader in Vision Integration is playback only.

## Data model

- Apartments own multiple vehicles. Registration numbers are normalized and unique.
- Requests have unique producer event IDs, source labels, recognized plate, optional OCR confidence, track ID and current outcome.
- Access events preserve each policy decision, resident verification and gate closure. Their timestamps are UTC receipt times, not camera capture times.
- The singleton gate stores its current state and active request. All decision changes use SQLite transactions. Only one vehicle may occupy a gate cycle at once.
- Visits store a completed entry, apartment, plate and optional departure. An EXIT request references the existing visit. Authorization alone does not create a visit: `record_passage` must execute while the request is authorized and the gate is open. Crossings are idempotent. Duplicate inside entry, exit without entry and mismatched exit plates are rejected.
- Existing schemas upgrade in place, keeping historical audit events. Legacy authorizations are not assumed to be completed passages.

## Guided simulation

`simulation_ui.py` renders a vector road, vehicle and rotating barrier. The sequence opens the barrier, moves the vehicle across, commits passage, lowers the barrier and records closure. Gate and occupancy metrics update during the animation. The full demo runs entry and exit for the same visit. Unknown arrivals wait for an inline resident decision. Rejection keeps the barrier closed and creates no visit. Interrupted authorized cycles can resume. Cancellation before passage creates no occupancy; cancellation after a committed crossing preserves that crossing.

## Authorization

An active registered vehicle receives automatic entry under the demo policy. A plate identifies a vehicle record, not a person. Unknown or unreadable plates require resident verification; supplied confidence below 0.8 cannot automatically authorize entry. Revoked registrations are denied automatic access. Visitor and delivery arrivals always require resident approval even when their plates are registered.

The selected fictional resident represents identity and authority to approve a visit to their apartment. RFID and fingerprint options simulate verification; they collect no biometric data. A mapped resident vehicle must use its mapped apartment to verify. Approval grants one visit and never creates a vehicle registration. Rejection keeps the gate closed. Completion closes the gate and releases the cycle. Cancellation preserves denied/rejected decisions; unresolved pending requests and authorized requests without passage become cancelled.

Stable event IDs prevent replay on dashboard reruns or re-import. An old event cannot reopen the gate. Sample/manual arrivals deliberately generate a new ID for each operator-created arrival.

## Integration contract

The importer accepts one JSON object or an array of 1–1000 objects. Required fields: `event_id` (nonempty string, <=150 characters), `source` (`sample`, `manual`, `cpu_vision`, `gpu_vision`, `pipegen`). Optional fields: `event_type` (`VEHICLE_DETECTED` only), `tracking_id`, `vehicle_type` (`car`, `motorcycle`, `truck`, `bus`), `number_plate` (string or null), `confidence` (plate confidence 0–1 or null), `visit_type` (`resident`, `visitor`, `delivery`), `direction` (`ENTRY` default, or `EXIT`), `presence_id` (positive visit ID, for matching exits including unreadable plates). Local CPU video events use `cpu_vision` and save separate detection reports with explicit manually assigned identity provenance. The video-first-detection identifier marks a single attempt and is not a real tracker ID.

```json
{"event_id":"camera-1-track-42-entry-1","source":"pipegen","event_type":"VEHICLE_DETECTED","tracking_id":42,"vehicle_type":"car","number_plate":null,"confidence":null}
```

Set `source=pipegen` only for an actual external pipeline result. The label is producer-supplied, not independently verified. Do not put a sample plate into an actual detection event. Without OCR, use null and demonstrate manual authorization. Keep the same event ID for retries; generate a new ID for a genuinely new entry. Adapt the real PipeGen export to this contract after inspecting its actual schema; this project does not claim a tested native PipeGen adapter.

## Genuine, simulated and incomplete

Genuine: SQLite persistence, normalization, policy evaluation, deduplication, gate state transitions, forms, JSON validation, audit exports and local YOLOX-s CUDA or YOLOv4-tiny CPU vehicle detections on uploaded/downloaded video frames.

Simulated: sample events, assigned video/sample plate identities, resident identity and consent, RFID, fingerprint, physical passage timing and physical gate. No real resident or biometric data is used.

Incomplete: multi-object tracking, plate OCR, native PipeGen output mapping, external continuous-stream ingestion, hardware deployment and production security. The local video mode associates one manually assigned identity with the first vehicle detected per run. Source labels are not authenticated. This is a local trusted-operator demonstration, not an access-control product.

## Track A evidence still required

The supplied official brief requires all five PipeGen stages (Requirement, Pipeline IR, Model, Compiler, Run), at least one TensorRT engine and its speed report, a pipeline running on actual video input on NVIDIA hardware, actionable output, an export folder, and graph/report screenshots. None of those runs or reports has been generated by this simulator. A real vehicle pipeline feeding authorization events would make PipeGen central to the product. A simulation alone does not establish Track A completion.
