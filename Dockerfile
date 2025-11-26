FROM n8nio/n8n:latest

USER root

# Установка ffmpeg и curl в Alpine Linux
RUN apk add --no-cache ffmpeg curl

USER node