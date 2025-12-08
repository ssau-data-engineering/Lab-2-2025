from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import PlainTextResponse
import subprocess
import tempfile
import os
from pathlib import Path

app = FastAPI(title="Auto Subtitle API")

@app.post("/transcribe", response_class=PlainTextResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_extension = Path(file.filename).suffix or ".mp4"
            input_path = os.path.join(temp_dir, f"input_video{file_extension}")
            
            content = await file.read()
            with open(input_path, 'wb') as f:
                f.write(content)
            
            cmd = [
                "auto_subtitle",
                input_path,
                "-o", temp_dir,  
                "--output_srt", "true",
                "--srt_only", "true",
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise HTTPException(500, f"Transcription failed: {result.stderr}")
            
            srt_files = [f for f in os.listdir(temp_dir) if f.endswith(".srt")]
            
            srt_path = os.path.join(temp_dir, srt_files[0])
            with open(srt_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            return srt_content
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Processing error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "auto-subtitle-api"}

@app.get("/models")
async def available_models():
    return {"models": ["tiny", "base", "small", "medium", "large"]}