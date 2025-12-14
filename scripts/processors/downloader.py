import requests
import yt_dlp
from typing import Tuple

def download_video(url: str, output_path: str) -> Tuple[bool, str]:
    try:
        if 'youtube.com' in url or 'youtu.be' in url:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': output_path,
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        else:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        return True, output_path
    except Exception as e:
        return False, str(e)