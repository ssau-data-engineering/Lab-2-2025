import subprocess
import os
from typing import Tuple

def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> Tuple[bool, str]:
    """
    Наложение субтитров на видео
    """
    try:
        filter_complex = (
            f"subtitles='{srt_path}':force_style="
            "'FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF,"
            "OutlineColour=&H000000,BackColour=&H80000000,BorderStyle=4,"
            "Outline=2,Shadow=1,MarginV=30'"
        )
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf', filter_complex,
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-y',  # перезаписать
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False, f"FFmpeg error: {result.stderr}"

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, output_path
        else:
            return False, "Output video not created"
    except Exception as e:
        return False, str(e)