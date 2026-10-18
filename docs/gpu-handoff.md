# PipeGen execution checklist for the laptop or mentor GPU machine

## Goal to paste into PipeGen

Build an apartment entrance vehicle perception pipeline from a real video file. Detect cars, motorcycles, buses and trucks; track vehicles with persistent track IDs. Generate JSON metadata for vehicle arrivals at the entrance. Produce one event per vehicle arrival, not an authorization event per frame. Compile at least one supported model to TensorRT, retain its actual speed report, and generate a runnable DeepStream export. Use a supported curated detector/tracker. Plate detection and OCR are optional: if unsupported or unreliable, leave number_plate null. Do not synthesize plates or confidence values. Keep model classes, chosen precision, video source, hardware and output configuration visible for the demo.

## Required run sequence

1. Confirm the installed PipeGen version and a compatible NVIDIA GPU / Jetson environment using the organizer's current instructions. Sign in to CraftifAI yourself.
2. Complete Requirement → Pipeline IR → Model → Compiler → Run in PipeGen. Save the actual stage outputs.
3. Save the PIR graph screenshot, compiled TensorRT engine, PipeGen speed report screenshot and complete export directory.
4. Run the pipeline on a real video file, USB/CSI camera or RTSP feed. A video file is allowed by the supplied official problem statement.
5. Inspect the actual JSON format. Map a real tracked vehicle event to the application contract below. This mapping must follow the actual export, which is not yet available here.
6. Transfer the JSON to this laptop, open Vision Integration, select the event and Apply event to gate. In Live Simulator, approve any unreadable plate as a simulated resident, and complete vehicle passage.
7. Record the running GPU pipeline and this resulting application action. Include source code, exported pipeline, hardware/model/precision details and screenshots in the submission.

## Application boundary

```json
{"event_id":"camera1-track42-entrance1","source":"pipegen","event_type":"VEHICLE_DETECTED","tracking_id":42,"vehicle_type":"car","number_plate":null,"confidence":null,"direction":"ENTRY","visit_type":"resident"}
```

The detector/track ID must come from the actual pipeline. Keep event_id stable on retries and unique for a new arrival. Set source to pipegen only for actual pipeline output. Confidence means plate-reading confidence, not detector confidence. Do not insert a sample plate into a real detection event. Without plate OCR, demonstrate detection triggering verification, then simulated resident authorization opening the software gate.

The app currently imports JSON files; a continuous stream bridge and native PipeGen schema conversion are not implemented. Make the real perception event trigger the access workflow during judging so PipeGen is central to the demonstration.

## Evidence inventory

- GPU / Jetson model, PipeGen version, video input and actual model name.
- Five-stage run artifacts and PIR graph screenshot.
- TensorRT precision and actual PipeGen speed report. Report only measured results.
- Generated export folder including run instructions.
- Real output JSON and corresponding SmartGate audit export.
- Demo recording showing pipeline output driving the gate workflow.
- Judge-accessible repository URL containing app source and pipeline export.

No physical gate or firmware bonus is claimed. Do not claim INT8 optimization or a closed-loop hardware bonus unless actually completed and evidenced.
