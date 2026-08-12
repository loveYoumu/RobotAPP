#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>

#include "apis_c.h"

namespace {
constexpr int kWidth = 640;
constexpr int kHeight = 480;
constexpr int kFeatures = 1000;
constexpr int kFeatureBytes = 48;
constexpr int kDatasetFrames = 613;
constexpr int kLbaExecutions = 179;
constexpr int kLbaEdges = 25089;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        std::cerr << "usage: slam_cpu <x> <y>\n";
        return 2;
    }
    const int id_x = std::atoi(argv[1]);
    const int id_y = std::atoi(argv[2]);

    std::vector<std::uint8_t> image(kWidth * kHeight);
    std::vector<std::uint8_t> features(kFeatures * kFeatureBytes);
    for (std::size_t i = 0; i < image.size(); ++i) {
        image[i] = static_cast<std::uint8_t>((i * 17U + i / kWidth) & 0xffU);
    }

    // One detailed representative frame is executed by GPGPU-Sim. The CPU
    // side executes aggregate control/geometry work for the 613-frame dataset.
    InterChiplet::sendMessage(0, 0, id_x, id_y, image.data(), image.size());
    InterChiplet::receiveMessage(
        id_x, id_y, 0, 0, features.data(), features.size());

    std::uint64_t metadata[8] = {
        kDatasetFrames, kWidth, kHeight, kFeatures,
        150, 7422, kLbaExecutions, kLbaEdges};
    std::uint64_t npu_ack[8] = {};
    InterChiplet::sendMessage(0, 3, id_x, id_y, metadata, sizeof(metadata));
    InterChiplet::receiveMessage(id_x, id_y, 0, 3, npu_ack, sizeof(npu_ack));

    volatile double checksum = 0.0;
    for (int frame = 0; frame < kDatasetFrames; ++frame) {
        const double phase = 0.001 * static_cast<double>(frame + 1);
        for (int feature = 0; feature < kFeatures; ++feature) {
            const std::uint8_t descriptor =
                features[(feature * kFeatureBytes + frame) % features.size()];
            checksum += std::sin(phase + feature * 0.0001) *
                        (1.0 + static_cast<double>(descriptor & 7U));
        }
        for (int iteration = 0; iteration < 4; ++iteration) {
            checksum = checksum * 0.999999 + phase * (iteration + 1);
        }
    }

    // Aggregate sparse LBA edge-linearization work; this intentionally models
    // irregular CPU work rather than inventing a dense NPU operation.
    for (int execution = 0; execution < kLbaExecutions; ++execution) {
        for (int edge = 0; edge < kLbaEdges; edge += 8) {
            const double residual =
                (static_cast<double>((edge + execution) % 257) - 128.0) * 1e-4;
            checksum += residual * residual / (1.0 + std::abs(residual));
        }
    }

    std::cout << "SLAM CPU aggregate complete: frames=" << kDatasetFrames
              << " lba=" << kLbaExecutions
              << " checksum=" << checksum
              << " npu_mode=idle_control_only\n";
    return 0;
}
