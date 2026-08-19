import argparse
import hashlib
import json
import os
import platform
import re
import time
from pathlib import Path

import jiwer
import psutil
import torch
import whisper
from opencc import OpenCC
from robot_command import parse_robot_command
from runtime_env import ensure_ffmpeg_on_path

OPENCC = OpenCC("t2s")


def normalize_zh(text):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", OPENCC.convert(text)).lower()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    ensure_ffmpeg_on_path()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="small")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    model_dir = Path(args.model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    records = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]
    for item in records:
        audio = Path(item["audio"])
        if not audio.is_absolute():
            item["audio"] = str((manifest_path.parent / audio).resolve())

    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else "cpu" if args.device == "auto" else args.device
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested, but CUDA is unavailable")
    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    load_start = time.perf_counter()
    model = whisper.load_model(args.model, device=device, download_root=str(model_dir))
    if device == "cuda":
        torch.cuda.synchronize()
    model_load_s = time.perf_counter() - load_start

    process = psutil.Process(os.getpid())
    predictions = []
    references = []
    hypotheses = []
    for index, item in enumerate(records):
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        rss_before = process.memory_info().rss
        start = time.perf_counter()
        result = model.transcribe(
            item["audio"],
            language="zh",
            task="transcribe",
            fp16=device == "cuda",
            temperature=0.0,
            beam_size=5,
            condition_on_previous_text=False,
            verbose=False,
        )
        if device == "cuda":
            torch.cuda.synchronize()
        latency = time.perf_counter() - start
        hypothesis = result["text"].strip()
        reference_norm = normalize_zh(item["reference"])
        hypothesis_norm = normalize_zh(hypothesis)
        reference_command = parse_robot_command(reference_norm)
        hypothesis_command = parse_robot_command(hypothesis_norm)
        command_exact_match = reference_command == hypothesis_command
        sample_cer = jiwer.cer(reference_norm, hypothesis_norm)
        prediction = dict(item)
        prediction.update({
            "hypothesis": hypothesis,
            "reference_normalized": reference_norm,
            "hypothesis_normalized": hypothesis_norm,
            "reference_command": reference_command,
            "hypothesis_command": hypothesis_command,
            "command_exact_match": command_exact_match,
            "cer": sample_cer,
            "latency_s": latency,
            "rtf": latency / item["duration_s"],
            "gpu_peak_allocated_mb": torch.cuda.max_memory_allocated() / 1024**2 if device == "cuda" else 0.0,
            "gpu_peak_reserved_mb": torch.cuda.max_memory_reserved() / 1024**2 if device == "cuda" else 0.0,
            "rss_before_mb": rss_before / 1024**2,
            "rss_after_mb": process.memory_info().rss / 1024**2,
            "is_first_inference": index == 0,
        })
        predictions.append(prediction)
        references.append(reference_norm)
        hypotheses.append(hypothesis_norm)
        print(json.dumps(prediction, ensure_ascii=False), flush=True)

    total_audio = sum(item["duration_s"] for item in predictions)
    total_latency = sum(item["latency_s"] for item in predictions)
    model_files = sorted(model_dir.glob(f"{args.model}*.pt"))
    summary = {
        "prototype_status": "PASS" if all(item["hypothesis"] for item in predictions) else "FAIL",
        "model": args.model,
        "device": device,
        "gpu_name": torch.cuda.get_device_name(0) if device == "cuda" else None,
        "torch_version": torch.__version__,
        "whisper_module": whisper.__file__,
        "python": platform.python_version(),
        "model_load_s": model_load_s,
        "samples": len(predictions),
        "total_audio_s": total_audio,
        "total_inference_s": total_latency,
        "aggregate_rtf": total_latency / total_audio,
        "mean_latency_s": total_latency / len(predictions),
        "aggregate_cer": jiwer.cer(references, hypotheses),
        "command_exact_match_rate": sum(item["command_exact_match"] for item in predictions) / len(predictions),
        "max_gpu_peak_allocated_mb": max(item["gpu_peak_allocated_mb"] for item in predictions),
        "max_gpu_peak_reserved_mb": max(item["gpu_peak_reserved_mb"] for item in predictions),
        "model_files": [{"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in model_files],
    }
    with (output_dir / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for item in predictions:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
