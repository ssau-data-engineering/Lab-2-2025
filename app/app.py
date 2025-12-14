from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import tempfile
import subprocess
import shutil
from pathlib import Path
from datetime import timedelta
import os
import requests
import srt
from transformers import pipeline

app = FastAPI()

FFMPEG_TIMEOUT_SEC = 10 * 60
AUDIO_SAMPLE_RATE = "16000"
AUDIO_CHANNELS = "1"

OUTPUT_DIR = Path("temp_outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "openai/whisper-base")
whisper_pipe = pipeline(
    "automatic-speech-recognition",
    model=WHISPER_MODEL,
    device="cpu",
)

HF_API_KEY = os.environ.get("HF_API_KEY", "")
HF_TR_MODEL_URL = os.environ.get(
    "HF_TR_MODEL_URL",
    "https://router.huggingface.co/v1/chat/completions"
)

HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}",
    "Content-Type": "application/json",
}


def _save_upload_to_disk(upload: UploadFile, dst: Path) -> None:
    with dst.open("wb") as f:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


def _format_srt_time(seconds: float) -> timedelta:
    return timedelta(seconds=max(0.0, float(seconds)))


def extract_audio_ffmpeg(input_video: Path, output_wav: Path) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-vn",
        "-ac", AUDIO_CHANNELS,
        "-ar", AUDIO_SAMPLE_RATE,
        str(output_wav),
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=FFMPEG_TIMEOUT_SEC,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-3000:])


@app.post("/extract-audio")
async def extract_audio(file: UploadFile = File(...)):
    workdir = Path(tempfile.mkdtemp(prefix="job_"))
    try:
        suffix = Path(file.filename or "input.mp4").suffix or ".mp4"
        input_path = workdir / f"input{suffix}"
        tmp_audio = workdir / "audio.wav"

        with input_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        if input_path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        try:
            extract_audio_ffmpeg(input_path, tmp_audio)
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="ffmpeg timeout")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ffmpeg failed: {e}")

        if not tmp_audio.exists() or tmp_audio.stat().st_size == 0:
            raise HTTPException(status_code=500, detail="audio.wav was not created")

        out_name = f"audio_{next(tempfile._get_candidate_names())}.wav"
        out_path = OUTPUT_DIR / out_name
        shutil.move(str(tmp_audio), str(out_path))

        return FileResponse(
            path=str(out_path),
            media_type="audio/wav",
            filename="audio.wav",
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@app.post("/stt-whisper")
async def stt_whisper(file: UploadFile = File(...)):
    workdir = Path(tempfile.mkdtemp(prefix="job_stt_"))
    try:
        suffix = Path(file.filename or "audio.wav").suffix or ".wav"
        audio_path = workdir / f"audio{suffix}"

        _save_upload_to_disk(file, audio_path)

        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded audio is empty")

        try:
            result = whisper_pipe(
                str(audio_path),
                return_timestamps=True,
                chunk_length_s=30,
                stride_length_s=5,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Whisper failed: {e}")

        chunks = result.get("chunks") or []
        if not chunks:
            text = (result.get("text") or "").strip()
            if not text:
                raise HTTPException(status_code=500, detail="No speech recognized")
            subs = [srt.Subtitle(index=1, start=timedelta(0), end=timedelta(seconds=5), content=text)]
        else:
            subs = []
            idx = 1
            for seg in chunks:
                ts = seg.get("timestamp")
                if not ts or ts[0] is None or ts[1] is None:
                    continue
                start = _format_srt_time(ts[0])
                end = _format_srt_time(ts[1])
                text = (seg.get("text") or "").strip()
                if not text:
                    continue
                subs.append(srt.Subtitle(index=idx, start=start, end=end, content=text))
                idx += 1
            if not subs:
                raise HTTPException(status_code=500, detail="No timestamped segments produced")

        srt_text = srt.compose(subs)

        out_name = f"subs_en_{next(tempfile._get_candidate_names())}.srt"
        out_path = OUTPUT_DIR / out_name
        out_path.write_text(srt_text, encoding="utf-8")

        return FileResponse(
            path=str(out_path),
            filename="subs_en.srt",
            media_type="text/plain; charset=utf-8",
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@app.post("/translate-srt")
async def translate_srt(file: UploadFile = File(...)):
    if not (file.filename or "").endswith(".srt"):
        raise HTTPException(status_code=400, detail="Expected .srt file")

    en_text = (await file.read()).decode("utf-8", errors="replace")

    payload = {
        "model": os.environ.get("HF_TR_MODEL", "deepseek-ai/DeepSeek-V3.2:novita"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional subtitle translator. "
                    "Translate subtitles from English to Russian. "
                    "Keep original SRT format strictly. "
                    "Do not add comments. Do not change timestamps. "
                    "Only translate text lines."
                ),
            },
            {"role": "user", "content": en_text},
        ],
        "temperature": 0.0,
        "max_tokens": 6000,
        "stream": False,
    }

    try:
        resp = requests.post(HF_TR_MODEL_URL, headers=HEADERS, json=payload, timeout=180)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HF request failed: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"HF API error: {resp.status_code} {resp.text}")

    data = resp.json()
    try:
        ru_text = data["choices"][0]["message"]["content"]
    except Exception:
        raise HTTPException(status_code=500, detail=f"Unexpected HF response: {data}")

    out_name = f"subs_ru_{next(tempfile._get_candidate_names())}.srt"
    out_path = OUTPUT_DIR / out_name
    out_path.write_text(ru_text, encoding="utf-8")

    return FileResponse(
        str(out_path),
        filename="subs_ru.srt",
        media_type="text/plain; charset=utf-8",
    )


@app.post("/burn-subs")
async def burn_subs(subs: UploadFile = File(...), video: UploadFile = File(...)):
    workdir = Path(tempfile.mkdtemp(prefix="job_burn_"))
    video_path = workdir / "input.mp4"
    subs_path = workdir / "subs.srt"
    out_path = workdir / "out.mp4"

    try:
        with video_path.open("wb") as f:
            while True:
                chunk = await video.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        with subs_path.open("wb") as f:
            f.write(await subs.read())

        if video_path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="Video file is empty")
        if subs_path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="Subs file is empty")

        vf = (
            "subtitles=subs.srt"
            ":charenc=UTF-8"
            ":force_style='FontName=DejaVuSans,Fontsize=20,Outline=1,Shadow=1,MarginV=40'"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", "input.mp4",
            "-vf", vf,
            "-c:a", "copy",
            "out.mp4",
        ]

        proc = subprocess.run(
            cmd,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=FFMPEG_TIMEOUT_SEC,
        )

        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"ffmpeg failed:\n{proc.stderr[-2000:]}")

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise HTTPException(status_code=500, detail="out.mp4 was not created")

        return FileResponse(
            path=str(out_path),
            media_type="video/mp4",
            filename="result.mp4",
        )

    finally:
        shutil.rmtree(workdir, ignore_errors=True)
