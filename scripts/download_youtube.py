import sys
from pytube import YouTube

url = sys.argv[1]
yt = YouTube(url)
stream = yt.streams.filter(file_extension='mp4', progressive=True).first()
stream.download(output_path='/tmp', filename='input.mp4')
print(f"Downloaded: {url}")