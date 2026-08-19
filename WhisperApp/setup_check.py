import subprocess
import torch
import whisper
from runtime_env import ensure_ffmpeg_on_path

ffmpeg = ensure_ffmpeg_on_path()
print("whisper", whisper.__file__)
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
print("ffmpeg", ffmpeg)
subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL)
print("runtime_check PASS")
