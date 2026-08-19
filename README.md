# RobotAPP

面向 CPU–GPU–NPU 异构芯片仿真的机器人应用工作负载仓库。

当前已整理：

- [SLAM：LegoSim / PopNet / GPUWattch / Sniper / HotSpot 复现说明](readme_SLAM.md)
- [Whisper：中文机器人语音命令完整应用与复现说明](WhisperApp/WHISPER_README.md)
- `WhisperApp/`：Whisper 语音识别、中文命令解析、五命令测试集、基准与算子 Trace 工具
- `SLAM/app/`：可放入 LegoSim 的 SLAM 代表性 CPU、GPU、NPU 端点程序
- `SLAM/architecture/`：TriFold-3D v2 三层架构、节点映射和 PopNet 拓扑
- `SLAM/tools/`：把 GPUWattch 与 Sniper/McPAT 功耗整理为三层 HotSpot 输入的脚本
- `SLAM/results/cluster_20260812/`：已在集群 `SERVER-113` 得到的精简实测结果

仓库不复制 ORB-SLAM3、LegoSim、Sniper、GPGPU-Sim、GPUWattch 或 HotSpot 本体；请分别遵循上游项目的许可证完成安装。
