FROM n8nio/n8n:latest

USER root
RUN apk add --no-cache ffmpeg python3 py3-pip curl
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && \
    chmod a+rx /usr/local/bin/yt-dlp
RUN python3 -m pip install deep-translator --break-system-packages

USER node