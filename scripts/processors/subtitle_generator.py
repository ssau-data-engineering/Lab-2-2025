import requests
from typing import Tuple

def generate_subtitles(audio_path: str, output_srt_path: str, api_url: str) -> Tuple[bool, str]:
    """
    Генерация субтитров через Whisper API
    """
    try:
        with open(audio_path, 'rb') as audio_file:
            files = {'audio_file': audio_file}
            data = {
                'task': 'transcribe',
                'language': 'en',
                'output': 'srt'
            }
            response = requests.post(
                f"{api_url}/asr",
                files=files,
                data=data,
                timeout=300  # 5 минут
            )

        if response.status_code == 200:
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            return True, output_srt_path
        else:
            return False, f"API error: {response.status_code} - {response.text}"
    except Exception as e:
        return False, str(e)