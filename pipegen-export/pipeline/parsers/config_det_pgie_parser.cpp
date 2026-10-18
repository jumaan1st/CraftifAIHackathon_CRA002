// Custom detection (bbox) parser (generated).
// Scaffold validates the output layer and exposes the raw tensor(s); the DECODE
// block (per-model) populates `objectList` with NvDsInferObjectDetectionInfo.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "nvdsinfer_custom_impl.h"

extern "C" bool ParseConfigDetPgie(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList);

CHECK_CUSTOM_PARSE_FUNC_PROTOTYPE(ParseConfigDetPgie);

extern "C" bool ParseConfigDetPgie(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList)
{
    if (outputLayersInfo.empty()) return false;
    auto const& layer0 = outputLayersInfo[0];

    const unsigned numClasses = detectionParams.numClassesConfigured;
    const float netW = static_cast<float>(networkInfo.width);
    const float netH = static_cast<float>(networkInfo.height);
    const float* data = static_cast<const float*>(layer0.buffer);

    static bool logged = false;
    if (!logged) {
        logged = true;
        fprintf(stderr, "[YOLO11s_det] first call: layer=%s numDims=%d "
                "networkInput=%.0fx%.0f numClasses=%u outputs=%zu\n",
                layer0.layerName ? layer0.layerName : "?",
                layer0.inferDims.numDims, netW, netH, numClasses,
                outputLayersInfo.size());
    }

    // ==== BEGIN GENERATED DECODE ====
    // Engine output shape: 1x84x8400 → after batch strip: numDims=2, d={84,8400}
    // Layout: [84][numAnchors] where 84 = 4 box coords (cx,cy,w,h) + 80 class scores
    // Scores are post-sigmoid probabilities from ultralytics YOLO11 export.

    const unsigned int featureDim = layer0.inferDims.d[0]; // 84
    const unsigned int numAnchors = layer0.inferDims.d[1]; // 8400

    // Sanity: featureDim should equal 4 + numClasses
    if (featureDim != 4u + numClasses) {
        fprintf(stderr, "[YOLO11s_det] ERROR: featureDim=%u != 4+numClasses=%u\n",
                featureDim, 4u + numClasses);
        return false;
    }

    // Target class IDs to keep: 0(person),2(car),3(motorcycle),5(bus),7(truck)
    static const int targetIds[] = {0, 2, 3, 5, 7};
    static const int numTargets = 5;

    for (unsigned int a = 0; a < numAnchors; ++a) {
        // data is laid out as [featureDim][numAnchors], i.e. row-major with
        // row = feature index, col = anchor index.
        float cx = data[0 * numAnchors + a];
        float cy = data[1 * numAnchors + a];
        float bw = data[2 * numAnchors + a];
        float bh = data[3 * numAnchors + a];

        // Find best class score (scores are already post-sigmoid)
        float maxScore = 0.0f;
        unsigned int bestClassId = 0;
        for (unsigned int c = 0; c < numClasses; ++c) {
            float s = data[(4 + c) * numAnchors + a];
            if (s > maxScore) {
                maxScore = s;
                bestClassId = c;
            }
        }

        // Per-class threshold
        float thr = (bestClassId < detectionParams.perClassPreclusterThreshold.size())
                     ? detectionParams.perClassPreclusterThreshold[bestClassId]
                     : 0.3f;

        if (maxScore < thr) continue;

        // Filter: keep only target class IDs
        bool isTarget = false;
        for (int t = 0; t < numTargets; ++t) {
            if (static_cast<int>(bestClassId) == targetIds[t]) {
                isTarget = true;
                break;
            }
        }
        if (!isTarget) continue;

        // cx,cy,bw,bh are in network-input pixel coords already
        float left = cx - bw * 0.5f;
        float top  = cy - bh * 0.5f;

        // Clamp to network input
        left = std::max<float>(0.0f, std::min<float>(left, netW));
        top  = std::max<float>(0.0f, std::min<float>(top,  netH));
        float right  = std::max<float>(0.0f, std::min<float>(cx + bw * 0.5f, netW));
        float bottom = std::max<float>(0.0f, std::min<float>(cy + bh * 0.5f, netH));

        float w = right - left;
        float h = bottom - top;

        // Drop degenerate boxes
        if (w <= 1.0f || h <= 1.0f) continue;

        NvDsInferObjectDetectionInfo obj;
        obj.classId = bestClassId;
        obj.left = left;
        obj.top = top;
        obj.width = w;
        obj.height = h;
        obj.detectionConfidence = maxScore;
        objectList.push_back(obj);
    }
    // ==== END GENERATED DECODE ====
    return true;
}