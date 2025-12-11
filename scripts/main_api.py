from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.background import BackgroundTasks
import tempfile
from pathlib import Path
import logging

from processors.audio_extractor import extract_audio
from processors.subtitle_burner import burn_subtitles
from processors.downloader import download_video
from processors.subtitle_generator import generate_subtitles
from utils.cleaner import cleanup_temp_files

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Временная директория
TEMP_DIR = "/tmp/video_processing"
Path(TEMP_DIR).mkdir(exist_ok=True)

@app.post("/extract-audio")
async def extract_audio_endpoint(
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(...)
):
    temp_video_path = None
    audio_path = None
    try:
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=Path(video_file.filename).suffix, dir=TEMP_DIR)
        temp_video_path = temp_video.name
        content = await video_file.read()
        with open(temp_video_path, "wb") as f:
            f.write(content)

        audio_filename = f"{Path(temp_video_path).stem}.wav"
        audio_path = f"{TEMP_DIR}/{audio_filename}"

        success, result = extract_audio(temp_video_path, audio_path)
        if not success:
            raise Exception(result)

        background_tasks.add_task(cleanup_temp_files, temp_video_path)
        background_tasks.add_task(cleanup_temp_files, audio_path)

        return FileResponse(audio_path, media_type="audio/wav", filename=audio_filename)
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        if temp_video_path and Path(temp_video_path).exists():
            cleanup_temp_files(temp_video_path)
        if audio_path and Path(audio_path).exists():
            cleanup_temp_files(audio_path)
        return JSONResponse(status_code=500, content={"error": str(e)})