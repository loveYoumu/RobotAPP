# SLAM 异构芯片仿真与热仿真复现说明

## 1. 这里上传的是什么

本目录不是完整 ORB-SLAM3 源码镜像，而是我们为 LegoSim 构造的、可追踪通信与功耗的 **SLAM 代表性工作负载**：

- CPU：613 帧跟踪控制、特征消费、位姿迭代和 179 次局部 BA 的稀疏边线性化近似；
- GPU：一帧 640×480 图像的图像金字塔、FAST-like 角点和 BRIEF-like 描述子；
- NPU：作为三层目标架构中的真实端点保留，但经典 ORB-SLAM3 没有神经网络算子，因此只做控制握手，动态功耗设为 0；
- NoC：通过 LegoSim/InterChiplet 和 PopNet 记录 CPU↔GPU、CPU↔NPU 的消息及延迟；
- 功耗/温度：GPUWattch 组件级 trace + Sniper/McPAT CPU 总功耗，经 `slam_trifold_v2_thermal.py` 映射为三层 HotSpot 输入。

因此，仓库中的结果用于架构设计空间探索，不等价于逐指令运行完整 ORB-SLAM3，也不能当作流片签核数据。

## 2. 目录

```text
SLAM/
├── app/                  # LegoSim 三个端点、Makefile 与 YAML
├── architecture/         # TriFold-3D v2 参数、PopNet 图和节点/链路表
├── tools/                # 功耗 trace → 三层 HotSpot 输入
├── integration/          # 与 π0.5、Whisper 联合应用的接口约定
└── results/cluster_20260812/
                           # 小型、可审阅的集群实测结果
```

## 3. 前置条件

以下路径均用占位符表示；不要照搬原开发者的家目录。

```bash
export LEGOSIM_ROOT=/path/to/LEGOSIM_MICRO
export HOTSPOT_ROOT=/path/to/HotSpot
export ROBOTAPP_ROOT=/path/to/RobotAPP
export GPGPUSIM_CONFIG=release
```

需要已有可工作的 LegoSim（含 InterChiplet、PopNet、Sniper、GPGPU-Sim/GPUWattch）、CUDA 工具链和 HotSpot。目标仓库目前未声明许可证，所以没有复制这些第三方工程，也没有提交模型权重、数据集、密码、密钥和大体积原始 trace。

## 4. 把 SLAM 工作负载放入 LegoSim

保持 `artifact/slam` 这一层级，因为 NPU 端点引用 `$LEGOSIM_ROOT/interchiplet/includes/pipe_comm.h`：

```bash
mkdir -p "$LEGOSIM_ROOT/artifact/slam/target_architecture_v2"
cp "$ROBOTAPP_ROOT"/SLAM/app/slam_cpu.cpp "$LEGOSIM_ROOT/artifact/slam/"
cp "$ROBOTAPP_ROOT"/SLAM/app/slam_gpu.cu  "$LEGOSIM_ROOT/artifact/slam/"
cp "$ROBOTAPP_ROOT"/SLAM/app/slam_npu.cpp "$LEGOSIM_ROOT/artifact/slam/"
cp "$ROBOTAPP_ROOT"/SLAM/app/Makefile      "$LEGOSIM_ROOT/artifact/slam/makefile"
cp "$ROBOTAPP_ROOT"/SLAM/app/slam_trifold_v2_static.yml \
   "$LEGOSIM_ROOT/artifact/slam/target_architecture_v2/"
cp "$ROBOTAPP_ROOT"/SLAM/architecture/trifold_v2_baseline.gv \
   "$LEGOSIM_ROOT/artifact/slam/target_architecture_v2/"
```

编译：

```bash
cd "$LEGOSIM_ROOT"
source ./setup_env.sh              # 若你的 LegoSim 使用其他环境脚本，请替换
make -C artifact/slam clean_all
make -C artifact/slam -j"$(nproc)"
```

## 5. 先跑不带 GPU 热回灌的基线

```bash
cd "$LEGOSIM_ROOT/artifact/slam"
export SIMULATOR_ROOT="$LEGOSIM_ROOT"
export BENCHMARK_ROOT="$LEGOSIM_ROOT/artifact/slam"
../../interchiplet/bin/interchiplet \
  ./target_architecture_v2/slam_trifold_v2_static.yml -w 6 -f 4 -t 1
```

正常情况下应生成 `bench.txt`、`delayInfo.txt`、各进程日志和 `proc_r*_p*_t*` 目录。三个逻辑端点是：GPU `(0,0)`、NPU `(0,3)`、CPU `(5,5)`；完整 36 节点物理解释见 `SLAM/architecture/trifold_v2_node_map.csv`。

## 6. 开启功耗与温度回灌

本仓库 YAML 默认不写死任何用户路径。若要复现实验中的 GPUWattch 温度配置，将 YAML 中 GPU 项补上：

```yaml
pre_copy: "$GPU_POWER_CONFIG_DIR/*"
```

并设置：

```bash
export GPU_POWER_CONFIG_DIR=/path/to/gpgpusim_temperature_feedback_config
```

不同 LegoSim 版本对 `pre_copy` 的环境变量/通配符展开方式可能不同；若不展开，请先把该目录中的配置文件复制到 GPU 进程工作目录。不要把旧实验中的绝对路径原样复制。

运行结束后选择 GPUWattch 组件 trace：

```bash
find . -name 'gpgpusim_power_trace_report*.log.gz' -print
python3 "$ROBOTAPP_ROOT/SLAM/tools/slam_trifold_v2_thermal.py" \
  --gpu-trace /path/to/gpgpusim_power_trace_report.log.gz \
  --output-dir /tmp/slam_trifold_hotspot \
  --gpu-cycles 4583843 \
  --cpu-cycles 36017916
```

脚本输出三层 floorplan、`trifold_v2_3d.lcf`、`trifold_v2_3d.ptrace`、功耗摘要和模型假设。随后在输出目录运行 HotSpot；参数名以你安装的版本为准：

```bash
cd /tmp/slam_trifold_hotspot
"$HOTSPOT_ROOT/hotspot" \
  -c "$HOTSPOT_ROOT/hotspot.config" \
  -p trifold_v2_3d.ptrace \
  -steady_file trifold_v2.steady \
  -model_type grid \
  -grid_layer_file trifold_v2_3d.lcf
```

温度回灌的含义是：把 HotSpot 得到的块温度转换为下一轮 GPGPU-Sim/GPUWattch 的温度相关配置，再重复 LegoSim。回灌必须记录轮次、输入 trace、峰值温度和周期差；不能只修改一个温度数字后声称已收敛。当前仓库保存的是验证过的第一套静态拓扑结果，未声称完成硅级闭环收敛。

## 7. 已验证的集群数据（2026-08-12）

运行机器为 `SERVER-113`。完整静态 SLAM 重复两轮：

| 指标 | 第 1 轮 | 第 2 轮/汇总 |
|---|---:|---:|
| LegoSim 完成状态 | 0 | 0 |
| 应用周期 | 36,051,220 | 36,017,916 |
| 周期差 | — | 0.092465% |
| 详细热 trace 行数 | — | 4,365 |
| 平均封装功耗 | — | 57.7748 W |
| 原始瞬时峰值功耗 | — | 732.990248 W |
| 稳态最高温度 | — | 72.71 °C，T2 GPU control |
| 瞬态最高温度 | — | 84.05 °C，T2 GPU control |
| trace 最后一行最高温度 | — | 73.73 °C，T0 HBM/system |

原始峰值功耗来自 GTX480 XML 近似下的 GPUWattch trace，明显高于本架构 160 W 封装约束，不能直接解释成目标芯片真实峰值。这里保留它是为了让结果可追溯，而不是美化数据。精简原始字段见 `SLAM/results/cluster_20260812/`。

## 8. 与 π0.5、Whisper 的联合接口

联合流水线建议为：SLAM 输出位姿/地图状态，Whisper 输出语言 token，π0.5 消费三路 RGB、机器人状态和语言 token，输出 `[B,50,32]` 动作序列。π0.5 已知接口写在 `SLAM/integration/pi05_interface_v1.yaml`。三者联跑前还需要同学提供：

- 可执行入口与精确版本/commit；
- 模型权重和数据集的获取方式（不要提交权重到本仓库）；
- 单次推理命令、硬件/精度、warm-up 和 profiling 输出；
- 张量 dtype、布局、时间戳与同步策略；
- 可复现的小样本输入和期望输出校验值。

## 9. 可复现性边界

- `SLAM/app` 是从真实 ORB-SLAM3 profiling 量级抽取的架构工作负载，不是完整 SLAM 二进制；
- CPU 功耗使用 Sniper/McPAT 汇总，GPU 使用 GPUWattch 组件 trace；NPU 对经典 ORB-SLAM3 为 0 W 动态功耗；
- 三层 floorplan、背景功耗、CPU active/idle 拆分是公开在脚本中的工程假设；
- 热仿真结果依赖 HotSpot 配置、材料参数、散热边界和 trace 时间步；复现实验时必须把这些文件与结果一起归档。
