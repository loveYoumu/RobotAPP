import asyncio
import json
import subprocess
import wave
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "synthetic_zh_robot_commands"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = "zh-CN-XiaoxiaoNeural"
COMMANDS = [
    ("cmd001", "请前往厨房"),
    ("cmd002", "把红色杯子拿到桌子上"),
    ("cmd003", "向左转然后向前走两米"),
    ("cmd004", "停止移动"),
    ("cmd005", "打开客厅的灯"),
]

async def main():
    DATA.mkdir(parents=True, exist_ok=True)
    records = []
    for sample_id, text in COMMANDS:
        mp3 = DATA / f"{sample_id}.mp3"
        wav = DATA / f"{sample_id}.wav"
        await edge_tts.Communicate(text, VOICE).save(str(mp3))
        subprocess.run([
            str(FFMPEG), "-y", "-loglevel", "error", "-i", str(mp3),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)
        ], check=True)
        with wave.open(str(wav), "rb") as handle:
            duration = handle.getnframes() / float(handle.getframerate())
            assert handle.getframerate() == 16000 and handle.getnchannels() == 1
        records.append({
            "id": sample_id,
            "audio": wav.name,
            "reference": text,
            "duration_s": round(duration, 6),
            "source": "edge-tts",
            "voice": VOICE,
        })
    with (DATA / "manifest.jsonl").open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(records, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
