#include <cstdint>
#include <cstdio>
#include <cstdlib>

#include "apis_cu.h"
#include "cuda_runtime.h"

namespace {
constexpr int kWidth = 640;
constexpr int kHeight = 480;
constexpr int kFeatures = 1000;
constexpr int kFeatureBytes = 48;
}

__global__ void pyramid_downsample(
    const std::uint8_t *input, std::uint8_t *half, int width, int height) {
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width / 2 || y >= height / 2) return;
    const int source = (2 * y) * width + 2 * x;
    half[y * (width / 2) + x] = static_cast<std::uint8_t>(
        (input[source] + input[source + 1] +
         input[source + width] + input[source + width + 1]) / 4);
}

__global__ void fast_like(
    const std::uint8_t *image, std::uint8_t *corner, int width, int height) {
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x < 3 || y < 3 || x >= width - 3 || y >= height - 3) return;
    const int index = y * width + x;
    const int center = image[index];
    int score = 0;
    score += abs(center - image[index - 3]);
    score += abs(center - image[index + 3]);
    score += abs(center - image[index - 3 * width]);
    score += abs(center - image[index + 3 * width]);
    score += abs(center - image[index - 2 * width - 2]);
    score += abs(center - image[index + 2 * width + 2]);
    score += abs(center - image[index - 2 * width + 2]);
    score += abs(center - image[index + 2 * width - 2]);
    corner[index] = static_cast<std::uint8_t>(score > 160 ? 1 : 0);
}

__global__ void brief_like(
    const std::uint8_t *image, const std::uint8_t *corner,
    std::uint8_t *features, int width, int height) {
    const int feature = blockIdx.x * blockDim.x + threadIdx.x;
    if (feature >= kFeatures) return;
    const int x = 16 + (feature * 37) % (width - 32);
    const int y = 16 + (feature * 53) % (height - 32);
    const int base = feature * kFeatureBytes;
    features[base + 0] = static_cast<std::uint8_t>(x & 0xff);
    features[base + 1] = static_cast<std::uint8_t>((x >> 8) & 0xff);
    features[base + 2] = static_cast<std::uint8_t>(y & 0xff);
    features[base + 3] = static_cast<std::uint8_t>((y >> 8) & 0xff);
    for (int byte = 4; byte < kFeatureBytes; ++byte) {
        std::uint8_t descriptor = 0;
        for (int bit = 0; bit < 8; ++bit) {
            const int dx1 = ((byte * 7 + bit * 3) % 21) - 10;
            const int dy1 = ((byte * 5 + bit * 11) % 21) - 10;
            const int dx2 = ((byte * 13 + bit * 2) % 21) - 10;
            const int dy2 = ((byte * 3 + bit * 17) % 21) - 10;
            descriptor |= (image[(y + dy1) * width + x + dx1] <
                           image[(y + dy2) * width + x + dx2]) << bit;
        }
        features[base + byte] = descriptor ^ corner[y * width + x];
    }
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    const int id_x = std::atoi(argv[1]);
    const int id_y = std::atoi(argv[2]);

    std::uint8_t *image = nullptr;
    std::uint8_t *half = nullptr;
    std::uint8_t *corner = nullptr;
    std::uint8_t *features = nullptr;
    cudaMalloc(&image, kWidth * kHeight);
    cudaMalloc(&half, (kWidth / 2) * (kHeight / 2));
    cudaMalloc(&corner, kWidth * kHeight);
    cudaMalloc(&features, kFeatures * kFeatureBytes);

    receiveMessage(id_x, id_y, 5, 5, image, kWidth * kHeight);
    const dim3 threads(16, 16);
    const dim3 full_grid((kWidth + 15) / 16, (kHeight + 15) / 16);
    const dim3 half_grid((kWidth / 2 + 15) / 16, (kHeight / 2 + 15) / 16);
    pyramid_downsample<<<half_grid, threads>>>(image, half, kWidth, kHeight);
    fast_like<<<full_grid, threads>>>(image, corner, kWidth, kHeight);
    brief_like<<<(kFeatures + 127) / 128, 128>>>(
        image, corner, features, kWidth, kHeight);
    cudaDeviceSynchronize();
    sendMessage(5, 5, id_x, id_y, features, kFeatures * kFeatureBytes);

    cudaFree(features);
    cudaFree(corner);
    cudaFree(half);
    cudaFree(image);
    std::printf("SLAM GPU representative ORB frame complete\n");
    return 0;
}
