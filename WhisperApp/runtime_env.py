import os
import shutil
from pathlib import Path

import imageio_ffmpeg


def ensure_ffmpeg_on_path():
    """Make imageio-ffmpeg visible to OpenAI Whisper's ffmpeg subprocess."""
    executable = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    runtime_bin = Path(__file__).resolve().parent / ".runtime_bin"
    runtime_bin.mkdir(exist_ok=True)
    command = runtime_bin / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not command.exists():
        try:
            command.symlink_to(executable)
        except OSError:
            shutil.copy2(executable, command)
    if os.name != "nt":
        command.chmod(command.stat().st_mode | 0o111)
    current = os.environ.get("PATH", "")
    directories = current.split(os.pathsep) if current else []
    if str(runtime_bin) not in directories:
        os.environ["PATH"] = str(runtime_bin) + os.pathsep + current
    return command
