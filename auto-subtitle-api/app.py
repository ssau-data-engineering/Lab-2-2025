# whisper-service/app.py
import os
import tempfile
import subprocess
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)


@app.route('/transcribe', methods=['POST'])
def handle_transcription():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    video_file = request.files['file']
    if video_file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    with tempfile.TemporaryDirectory() as temp_dir:
        # Сохраняем загруженное видео
        file_extension = os.path.splitext(video_file.filename)[1] or ".mp4"
        input_video_path = os.path.join(temp_dir, f"video_input{file_extension}")
        video_file.save(input_video_path)

        # Запускаем процесс транскрибации
        transcription_result = subprocess.run([
            "/usr/local/bin/auto_subtitle",
            input_video_path,
            "-o", temp_dir,
            "--output_srt", "true",
            "--srt_only", "true",
        ], capture_output=True, text=True)

        if transcription_result.returncode != 0:
            return jsonify({
                "error": "Transcription process failed",
                "details": transcription_result.stderr,
                "output": transcription_result.stdout
            }), 500

        # Ищем сгенерированный файл субтитров
        found_srt_files = [f for f in os.listdir(temp_dir) if f.endswith(".srt")]
        if not found_srt_files:
            return jsonify({"error": "Subtitle file was not created"}), 500

        srt_file_path = os.path.join(temp_dir, found_srt_files[0])
        return send_file(
            srt_file_path, 
            mimetype='text/plain', 
            as_attachment=True, 
            download_name='transcribed_subtitles.srt'
        )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)