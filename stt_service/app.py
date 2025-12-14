import os
import glob
import uuid
import shutil
import subprocess
from flask import Flask, request, jsonify, Response
import logging

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

DATA_DIR = "/app/tmp"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/stt", methods=["POST"])
def stt():
    try:
        if "file" not in request.files:
            return jsonify({"error": "no file field 'file' in multipart"}), 400

        audio_file = request.files["file"]
        model = request.form.get("model", "small")
        lang = request.form.get("lang", "en") 

        os.makedirs(DATA_DIR, exist_ok=True)

        req_id = uuid.uuid4().hex[:8]
        work_dir = DATA_DIR
        os.makedirs(work_dir, exist_ok=True)

        audio_path = os.path.join(work_dir, "audio.wav")
        out_dir = os.path.join(work_dir, "out")
        os.makedirs(out_dir, exist_ok=True)

        audio_file.save(audio_path)

        cmd = [
        "auto_subtitle",
        "--model", model,
        "--language", lang,
        "--output_dir", out_dir,
        "--output_srt", "True",
        "--srt_only", "True",
        audio_path,
        ]


        p = subprocess.run(cmd, capture_output=True, text=True)

        app.logger.info("auto_subtitle rc=%s", p.returncode)
        app.logger.info("auto_subtitle stdout tail=%s", p.stdout[-800:])
        app.logger.info("auto_subtitle stderr tail=%s", p.stderr[-2000:])

        if p.returncode != 0:
            # Вернём в ответ то, что реально сказал auto_subtitle
            return jsonify({
                "error": "auto_subtitle failed",
                "returncode": p.returncode,
                "stdout": p.stdout[-4000:],
                "stderr": p.stderr[-4000:],
                "cmd": cmd,
                "work_dir": work_dir,
            }), 500

        srts = glob.glob(os.path.join(out_dir, "*.srt"))
        if not srts:
            return jsonify({
                "error": "srt not generated",
                "out_dir_listing": os.listdir(out_dir),
                "cmd": cmd,
                "work_dir": work_dir,
            }), 500

        srt_path = srts[0]
        with open(srt_path, "r", encoding="utf-8") as f:
            srt_text = f.read()

        # cleanup (можешь пока закомментировать, чтобы смотреть файлы)
        shutil.rmtree(work_dir, ignore_errors=True)

        return Response(srt_text, mimetype="text/plain; charset=utf-8")

    except Exception as e:
        # Чтобы в docker logs был traceback
        app.logger.exception("STT handler crashed")
        return jsonify({"error": "internal error", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
