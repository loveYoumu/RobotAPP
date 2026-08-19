import argparse
import json
import time
from pathlib import Path

import torch
import whisper
from opencc import OpenCC

from robot_command import parse_robot_command
from runtime_env import ensure_ffmpeg_on_path


def normalize(text):
    import re
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", OpenCC("t2s").convert(text)).lower()


def main():
    ensure_ffmpeg_on_path()
    parser = argparse.ArgumentParser(description="Native Whisper Chinese robot-command prototype")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model", default="small")
    parser.add_argument("--model-dir", default=str(Path(__file__).resolve().parent / "models"))
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    if not Path(args.audio).is_file():
        raise FileNotFoundError(args.audio)
    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else "cpu" if args.device == "auto" else args.device
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested, but CUDA is unavailable")
    start = time.perf_counter()
    model = whisper.load_model(args.model, device=device, download_root=args.model_dir)
    load_s = time.perf_counter() - start
    start = time.perf_counter()
    result = model.transcribe(args.audio, language="zh", task="transcribe", fp16=device == "cuda", temperature=0.0, beam_size=5, condition_on_previous_text=False, verbose=False)
    if device == "cuda":
        torch.cuda.synchronize()
    inference_s = time.perf_counter() - start
    text = result["text"].strip()
    normalized = normalize(text)
    output = {
        "status": "PASS" if text else "FAIL",
        "audio": str(Path(args.audio).resolve()),
        "model": args.model,
        "device": device,
        "text": text,
        "normalized_text": normalized,
        "robot_command": parse_robot_command(normalized),
        "model_load_s": load_s,
        "inference_s": inference_s,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
