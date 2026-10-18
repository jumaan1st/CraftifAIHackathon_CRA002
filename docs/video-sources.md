# Video and model provenance

## Built-in sample

- Title: Urban Parking Scene with Cars and Motorbike.
- Creator: Ivan Chumak.
- Page: https://www.pexels.com/video/urban-parking-scene-with-cars-and-motorbike-37508953/
- License page: https://www.pexels.com/license/
- Local file: `data/videos/parking-entrance.mp4`.
- The page describes cars and a motorbike navigating an urban parking entrance. The downloaded MP4 is about 40 MB. Download URL, size and SHA-256 are in `docs/video-assets.json`.

Pexels permits free use of its videos subject to its license restrictions. Credit is displayed in the app. The footage is not an example of its real participants being granted or denied access to this fictional community. Both policy scenarios reuse the clip with explicitly assigned fictional demo identity. No endorsement by the creator, people or brands shown is implied.

## Detector

Original YOLOv4-tiny Darknet configuration and weights from https://github.com/AlexeyAB/darknet. The setup script uses the repository's configuration and its linked `darknet_yolo_v4_pre/yolov4-tiny.weights` release asset. OpenCV DNN runs the model on CPU. The downloaded model detects COCO vehicle classes (car, motorcycle, bus, truck); it is not a plate OCR model. The repository and model have their own licensing; retain provenance and review those terms when distributing beyond the hackathon prototype.

OpenCV is pinned below version 5 because OpenCV 5 removed its Darknet importer. The working installed build is `opencv-python-headless==4.14.0.94`.

## What the video demonstrates

The first vehicle detection per run triggers a single access attempt. The operator assigns a demo plate and visit type before playback. The selected vehicle's registry permission determines automatic authorization or denial; unknown/visitor/unreadable identities require a fictional resident decision. A software passage timer produces the virtual gate cycle. The video is not edited to make a real barrier open or close.

The selectable native GPU backend uses OpenCV Zoo YOLOX-s FP32 ONNX with ONNX Runtime CUDA. Its model provenance and checksum are recorded in `docs/gpu-model-assets.json` and `docs/gpu-verification.json`; the model license is retained as `models/YOLOX-LICENSE`.

This is real CPU or CUDA detection with simulated identity and physical action. It is not a genuine PipeGen/DeepStream/TensorRT run and does not replace Track A evidence. Continuous multi-vehicle tracking and automatic plate association are not implemented.

## Uploads

User video files are decoded locally and saved as content-addressed files under `data/uploads/`. No cloud upload is used. Accepted extensions: MP4, MOV, AVI and WebM, subject to available decoder support and a 200 MB upload cap. H.264 MP4 is recommended. Source playback has standard video controls; processed analysis uses sampled frames and no audio.

## Built-in corridor sample

Man Walking in the Hallway, cottonbro studio / Pexels: https://www.pexels.com/video/man-walking-in-the-hallway-7599307/ . Stock footage is downloaded locally with a 960x506 H.264 derivative at 4 fps for analysis and preview. Provenance and checksum: `docs/corridor-sample.json`. It depicts ordinary hallway activity, not unauthorized entry. The camera moves in this stock clip, so frame-motion alerts include camera motion; real deployment needs a fixed camera. The generated `corridor-demo.mp4` is a separately labelled synthetic motion-test fallback.
