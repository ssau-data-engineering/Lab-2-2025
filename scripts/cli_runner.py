import sys
from processors.audio_extractor import extract_audio
from processors.subtitle_burner import burn_subtitles
from processors.downloader import download_video
from processors.subtitle_generator import generate_subtitles
from utils.cleaner import cleanup_temp_files

def main():
    if len(sys.argv) < 2:
        print("Usage: cli_runner.py <command> [args...]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "extract-audio":
        if len(sys.argv) != 4:
            print("Usage: cli_runner.py extract-audio <video_path> <output_path>")
            sys.exit(1)
        video_path = sys.argv[2]
        audio_path = sys.argv[3]
        success, result = extract_audio(video_path, audio_path)
        if success:
            print(f"Audio extracted: {result}")
        else:
            print(f"Error: {result}", file=sys.stderr)
            sys.exit(1)
