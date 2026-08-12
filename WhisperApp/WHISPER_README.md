# Whisper 中文机器人语音命令应用

本目录包含一个不依赖 LegoSim 或机器人模拟器的完整 Whisper 应用原型。应用把中文语音转换成文本，再解析为结构化机器人动作 JSON。

## 1. 应用流程

```text
16 kHz 单声道音频
  -> FFmpeg 解码
  -> Whisper log-Mel 频谱
  -> Transformer Encoder
  -> 自回归 Decoder
  -> 繁简转换与文本归一化
  -> 机器人命令解析
  -> JSON 动作
```

当前命令解析器覆盖：

- 前往厨房、客厅或卧室；
- 拿取指定颜色的杯子并放到桌上；
- 左转、右转、前进、后退及米制距离；
- 停止移动；
- 打开客厅或厨房的灯。

这不是通用自然语言机器人规划器。超出上述规则的命令会返回 `intent: unknown`。

## 2. 目录结构

```text
WhisperApp/
├── WHISPER_README.md                 # 本复现文档
├── requirements.txt                  # Whisper 应用最小 Python 依赖
├── transcribe_robot_command.py       # 单条语音识别和命令解析入口
├── robot_command.py                  # 机器人意图与参数解析器
├── run_whisper_benchmark.py          # 五命令准确率与性能基准
├── run_robot_command.sh              # Linux 单命令启动器
├── run_robot_command.ps1             # Windows PowerShell 启动器
├── run_benchmark.sh                  # Linux 批量基准启动器
├── setup_check.py                    # 环境检查
├── runtime_env.py                    # 自动向 PATH 注入 imageio-ffmpeg
├── build_synthetic_corpus.py         # 重新生成合成测试集
├── extract_operator_trace.py         # 单命令模块/张量形状 Trace
├── extract_multi_command_traces.py   # 多命令模块/张量形状 Trace
└── synthetic_zh_robot_commands/
    ├── manifest.jsonl
    └── cmd001–cmd005.{wav,mp3}
```

模型权重、虚拟环境和运行结果不会提交到 Git：

- `models/`：首次运行时由 Whisper 自动下载；
- `.venv/`：本机 Python 环境；
- `results/`：基准输出；
- `traces/`：算子 Trace 输出。

## 3. 已验证环境

服务器验收环境：

- Ubuntu 20.04.6 LTS；
- Python 3.8；
- NVIDIA GPU 与可用 CUDA 驱动；
- PyTorch 2.4.1；
- `openai-whisper==20250625`；
- Whisper `small` 模型。

CPU 模式可运行单条识别和批量基准，但速度通常显著慢于 GPU。复现性能数字时必须记录 GPU 型号、驱动、CUDA、PyTorch、模型和音频集，不能把不同机器的绝对时间直接比较。

## 4. 安装

### 4.1 Ubuntu / Linux

进入本目录：

```bash
cd RobotAPP/WhisperApp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

GPU 环境推荐先安装与驱动匹配的 PyTorch。以下命令复现原验收所用 CUDA 12.1 wheel：

```bash
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

若只使用 CPU：

```bash
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

检查环境：

```bash
python setup_check.py
```

输出应包含 Whisper 安装路径、PyTorch 版本、CUDA 是否可用以及 imageio-ffmpeg 的可执行文件路径。

### 4.2 Windows PowerShell

```powershell
cd RobotAPP\WhisperApp
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
python setup_check.py
```

如果 NVIDIA 驱动不支持 CUDA 12.1，请按 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/)选择对应版本。

## 5. 单条机器人命令复现

Linux：

```bash
./run_robot_command.sh \
  --audio synthetic_zh_robot_commands/cmd003.wav \
  --model small \
  --device auto
```

Windows PowerShell：

```powershell
.\run_robot_command.ps1 `
  --audio synthetic_zh_robot_commands\cmd003.wav `
  --model small `
  --device auto
```

也可以直接运行 Python：

```bash
python transcribe_robot_command.py \
  --audio synthetic_zh_robot_commands/cmd003.wav \
  --model small \
  --model-dir models \
  --device cuda
```

`--device` 可取 `auto`、`cuda` 或 `cpu`。首次运行会下载模型：`tiny` 约 75 MiB，`small` 约 461 MiB。

典型输出结构：

```json
{
  "status": "PASS",
  "model": "small",
  "device": "cuda",
  "text": "向左转，然后向前走两米。",
  "normalized_text": "向左转然后向前走两米",
  "robot_command": {
    "intent": "motion",
    "parameters": {
      "direction": "left",
      "distance_m": 2
    }
  }
}
```

## 6. 完整五命令基准复现

GPU：

```bash
./run_benchmark.sh small cuda
```

自动选择设备：

```bash
./run_benchmark.sh small auto
```

等价的显式命令：

```bash
python run_whisper_benchmark.py \
  --model small \
  --device cuda \
  --manifest synthetic_zh_robot_commands/manifest.jsonl \
  --model-dir models \
  --output-dir results/small_cuda
```

生成文件：

- `results/small_cuda/predictions.jsonl`：每条命令的识别文本、CER、RTF、结构化动作及显存；
- `results/small_cuda/summary.json`：汇总 CER、命令精确匹配率、总推理时间、RTF、模型哈希和环境信息。

原服务器 `small` 模型验收结果：

| 指标 | 结果 |
|---|---:|
| 命令数 | 5 |
| 总音频长度 | 11.04 s |
| 归一化 CER | 0.0 |
| 结构化命令精确匹配率 | 1.0 |
| 汇总 RTF | 0.533 |
| 峰值 allocated / reserved 显存 | 1094 / 1576 MiB |
| `small.pt` SHA-256 | `9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794` |

这些数值只证明该五条合成命令在原验收服务器上的应用流程正确，不代表真实机器人环境的语音识别准确率。首条推理包含 CUDA 预热影响。

## 7. 重新生成合成测试语音

该步骤需要访问 Microsoft Edge TTS 服务：

```bash
python build_synthetic_corpus.py
```

脚本使用 `zh-CN-XiaoxiaoNeural` 生成五条 MP3，并转为 16 kHz、单声道、PCM S16LE WAV，同时重写相对路径形式的 `manifest.jsonl`。

仓库已经包含验收时使用的音频，因此仅复现推理时不需要重新生成。

## 8. 提取 Whisper 模块和张量形状 Trace

单命令：

```bash
python extract_operator_trace.py \
  --audio synthetic_zh_robot_commands/cmd001.wav \
  --model small \
  --model-dir models \
  --output-dir traces/cmd001
```

五命令：

```bash
python extract_multi_command_traces.py \
  --manifest synthetic_zh_robot_commands/manifest.jsonl \
  --model small \
  --model-dir models \
  --output-dir traces/all_commands
```

这两个 Trace 工具当前按 CUDA/FP16 编写，用于采集 `Linear`、`Conv1d`、`LayerNorm`、`MultiHeadAttention` 和 `ResidualAttentionBlock` 的模块事件及张量形状。它们不是 PyTorch CUDA kernel profiler，也不能替代 Nsight Systems/Compute。

## 9. 验收清单

1. `python setup_check.py` 能导入 Whisper、PyTorch 和 FFmpeg；
2. `cmd003.wav` 能输出非空中文文本；
3. 输出 `robot_command.intent` 为 `motion`；
4. `direction` 为 `left`，`distance_m` 为 `2`；
5. 五命令基准生成 `predictions.jsonl` 和 `summary.json`；
6. 使用 `small` 模型时，五条合成命令应达到接近原服务器的识别结果；性能时间允许因硬件不同而变化；
7. `models/`、`.venv/`、`results/` 和 `traces/` 不应进入 Git 提交。

## 10. 已知限制

- 测试集只有五条 Edge TTS 合成普通话，不覆盖真人、多说话人、口音、远场、混响和机器人噪声；
- 命令解析器是确定性规则，不具备开放词汇规划能力；
- `beam_size=5` 和 `small` 模型偏向准确率，边缘设备可改用 `tiny`，但准确率可能下降；
- 模型权重由 OpenAI Whisper 下载，不包含在本仓库；
- 该目录是完整应用原型，不包含 LegoSim、Sniper、GPGPU-Sim、SCALE-Sim、PopNet、GPUWattch 或 HotSpot。

## 11. 上游软件与许可证

- OpenAI Whisper：[github.com/openai/whisper](https://github.com/openai/whisper)，MIT License；
- PyTorch：[pytorch.org](https://pytorch.org/)；
- OpenCC Python reimplementation：[github.com/yichen0831/opencc-python](https://github.com/yichen0831/opencc-python)；
- Edge TTS：[github.com/rany2/edge-tts](https://github.com/rany2/edge-tts)。

使用和分发时应分别遵守上述项目、模型权重和 TTS 服务的许可证及使用条款。
