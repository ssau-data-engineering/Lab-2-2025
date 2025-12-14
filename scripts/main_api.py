import os
import tempfile
import uuid
import logging
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from processors.audio_extractor import extract_audio
from processors.subtitle_burner import burn_subtitles
from processors.subtitle_generator import generate_subtitles
from utils.cleaner import cleanup_temp_files

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
TEMP_DIR = "/tmp/video_processing"
Path(TEMP_DIR).mkdir(exist_ok=True)


class VideoUrlRequest(BaseModel):
    url: str


def download_video_with_ytdlp(url: str, output_path: str) -> tuple[bool, str]:
    try:
        import yt_dlp
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True, "Download successful"
    except Exception as e:
        return False, f"yt-dlp error: {str(e)}"


def download_video_direct(url: str, output_path: str) -> tuple[bool, str]:
    try:
        import requests
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True, "Direct download successful"
    except Exception as e:
        return False, f"Direct download error: {str(e)}"


@app.post("/extract-audio-from-url")
async def extract_audio_from_url(
    background_tasks: BackgroundTasks,
    request: VideoUrlRequest
):
    temp_video = None
    temp_audio = None
    try:
        unique_id = str(uuid.uuid4())[:8]
        temp_video = f"{TEMP_DIR}/downloaded_video_{unique_id}.mp4"
        temp_audio = f"{TEMP_DIR}/audio_{unique_id}.wav"
        
        logger.info(f"Processing URL: {request.url}")
        
        success = False
        msg = ""
        
        if "youtube.com" in request.url or "youtu.be" in request.url:
            logger.info("Using yt-dlp for YouTube")
            success, msg = download_video_with_ytdlp(request.url, temp_video)
        
        if not success:
            logger.info("Trying direct download")
            success, msg = download_video_direct(request.url, temp_video)
        
        if not success:
            raise HTTPException(status_code=400, detail=f"Video download failed: {msg}")
        
        logger.info(f"Extracting audio to: {temp_audio}")
        success, msg = extract_audio(temp_video, temp_audio)
        if not success:
            raise HTTPException(status_code=500, detail=f"Audio extraction failed: {msg}")
        
        if not os.path.exists(temp_audio):
            raise HTTPException(status_code=500, detail="Audio file not created")
        
        file_size = os.path.getsize(temp_audio)
        logger.info(f"Audio file created, size: {file_size} bytes")
        
        background_tasks.add_task(cleanup_temp_files, temp_video)
        background_tasks.add_task(cleanup_temp_files, temp_audio)
        
        return FileResponse(
            temp_audio, 
            media_type="audio/wav", 
            filename="extracted_audio.wav",
            background=background_tasks
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
        if temp_video and os.path.exists(temp_video):
            cleanup_temp_files(temp_video)
        if temp_audio and os.path.exists(temp_audio):
            cleanup_temp_files(temp_audio)
        return JSONResponse(
            status_code=500, 
            content={"error": f"Internal server error: {str(e)}"}
        )


@app.get("/clear")
async def clear_temp_files():
    success, msg = cleanup_temp_files(TEMP_DIR)
    if success:
        return {"status": "success", "message": msg}
    else:
        raise HTTPException(status_code=500, detail=msg)


@app.post("/burn-subtitles")
async def burn_subtitles_endpoint(
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(...),
    srt_file: UploadFile = File(...)
):
    temp_video = None
    temp_srt = None
    output_path = None
    try:
        video_content = await video_file.read()
        suffix = Path(video_file.filename or "video.mp4").suffix or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=TEMP_DIR) as tmp:
            tmp.write(video_content)
            temp_video = tmp.name

        srt_bytes = await srt_file.read()
        try:
            srt_text = srt_bytes.decode('utf-8')
        except UnicodeDecodeError:
            srt_text = srt_bytes.decode('latin-1', errors='replace')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".srt", dir=TEMP_DIR, mode='w', encoding='utf-8') as tmp:
            tmp.write(srt_text)
            temp_srt = tmp.name

        if not os.path.exists(temp_srt) or os.path.getsize(temp_srt) == 0:
            raise HTTPException(status_code=400, detail="SRT file is empty or invalid")

        output_path = f"{temp_video}_subtitled.mp4"

        success, msg = burn_subtitles(temp_video, temp_srt, output_path)
        if not success:
            raise HTTPException(status_code=500, detail=f"Subtitles burning failed: {msg}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise HTTPException(status_code=500, detail="Output video file is empty")

        background_tasks.add_task(cleanup_temp_files, temp_video)
        background_tasks.add_task(cleanup_temp_files, temp_srt)

        return FileResponse(output_path, media_type="video/mp4", filename="subtitled_video.mp4")

    except Exception as e:
        logger.error(f"Burn subtitles error: {e}", exc_info=True)
        for f in [temp_video, temp_srt, output_path]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/asr")
async def asr(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    task: str = Form("transcribe"),
    language: str = Form("en"),
    output: str = Form("srt")
):
    temp_input_path = None
    temp_audio_path = None
    try:
        suffix = Path(audio_file.filename or "input").suffix or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=TEMP_DIR) as tmp:
            content = await audio_file.read()
            tmp.write(content)
            temp_input_path = tmp.name

        input_path = temp_input_path
        if suffix.lower() in {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}:
            temp_audio_path = f"{temp_input_path}.wav"
            success, msg = extract_audio(temp_input_path, temp_audio_path)
            if not success:
                raise Exception(f"Audio extraction failed: {msg}")
            input_path = temp_audio_path

        success, result = generate_subtitles(
            input_path,
            task=task,
            language=language,
            output_format=output
        )
        if not success:
            raise Exception(result)

        subtitle_path = result 
        filename = Path(subtitle_path).name

        background_tasks.add_task(cleanup_temp_files, temp_input_path)
        if temp_audio_path and Path(temp_audio_path).exists():
            background_tasks.add_task(cleanup_temp_files, temp_audio_path)
        background_tasks.add_task(cleanup_temp_files, subtitle_path)

        return FileResponse(subtitle_path, media_type="text/plain", filename=filename)

    except Exception as e:
        logger.error(f"ASR error: {e}")
        for p in [temp_input_path, temp_audio_path]:
            if p and Path(p).exists():
                cleanup_temp_files(p)
        return JSONResponse(status_code=500, content={"error": str(e)})


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