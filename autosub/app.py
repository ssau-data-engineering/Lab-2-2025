from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import subprocess
import os
import logging
from pathlib import Path

from config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_MODEL,
    DEFAULT_PORT,
    DEFAULT_HOST,
    SUPPORTED_MODELS,
    AUTO_SUBTITLE_CMD,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


class TranscribeRequest(BaseModel):
    input_file: str = Field(..., description="Path to the input audio file")
    output_dir: str = Field(default=DEFAULT_OUTPUT_DIR, description="Output directory for SRT file")
    model: str = Field(default=DEFAULT_MODEL, description="Whisper model to use")


def validate_request(request: TranscribeRequest) -> None:
    if not os.path.exists(request.input_file):
        raise HTTPException(
            status_code=404,
            detail=f"Input file not found: {request.input_file}"
        )
    
    if not os.path.isfile(request.input_file):
        raise HTTPException(
            status_code=400,
            detail=f"Input path is not a file: {request.input_file}"
        )
    
    if request.model not in SUPPORTED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model: {request.model}. Supported models: {', '.join(SUPPORTED_MODELS)}"
        )
    
    output_path = Path(request.output_dir)
    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Cannot create output directory {request.output_dir}: {str(e)}"
            )


def build_transcription_command(input_file: str, output_dir: str, model: str) -> list[str]:
    return [
        AUTO_SUBTITLE_CMD,
        input_file,
        "--output_srt", "True",
        "--output_dir", output_dir,
        "--model", model
    ]


def run_transcription(command: list[str]) -> subprocess.CompletedProcess:
    logger.info(f"Executing command: {' '.join(command)}")
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False
    )


@app.post("/transcribe")
async def transcribe(request: TranscribeRequest):
    validate_request(request)
    
    logger.info(
        f"Starting transcription for {request.input_file} "
        f"using model {request.model}, output to {request.output_dir}"
    )
    
    try:
        command = build_transcription_command(
            request.input_file,
            request.output_dir,
            request.model
        )
        process = run_transcription(command)
        
        if process.returncode != 0:
            error_msg = process.stderr or "Unknown error"
            logger.error(f"Transcription failed with return code {process.returncode}: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": "Transcription failed",
                    "return_code": process.returncode,
                    "stdout": process.stdout,
                    "stderr": process.stderr
                }
            )
        
        logger.info("Transcription completed successfully")
        return {
            "status": "success",
            "message": "Transcription successful",
            "stdout": process.stdout,
            "stderr": process.stderr
        }
        
    except HTTPException:
        raise
    except subprocess.SubprocessError as e:
        logger.error(f"Subprocess error during transcription: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Subprocess execution failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during transcription: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)
