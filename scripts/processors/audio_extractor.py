import subprocess
import os
from typing import Tuple

def extract_audio(video_path: str, audio_path: str) -> Tuple[bool, str]:
    """
    Извлечение аудиодорожки из видео
    """
    try:
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            '-y', 
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False, f"FFmpeg error: {result.stderr}"

        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            return True, audio_path
        else:
            return False, "Audio file not created"
    except Exception as e:
        return False, str(e)