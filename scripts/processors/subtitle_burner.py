import subprocess
import os
from typing import Tuple

def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> Tuple[bool, str]:
    if not os.path.exists(srt_path):
        return False, f"SRT file not found: {srt_path}"
    if os.path.getsize(srt_path) == 0:
        return False, "SRT file is empty"

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"subtitles={srt_path}:charenc=UTF-8",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-y",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return False, f"FFmpeg failed: {result.stderr}"
        return True, output_path
    except subprocess.TimeoutExpired:
        return False, "FFmpeg timeout (video too long)"
    except Exception as e:
        return False, f"Subprocess error: {str(e)}"