FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install \
    python-multipart \
    fastapi \
    uvicorn \
    ffmpeg-python \
    git+https://github.com/m1guelpf/auto-subtitle.git

COPY app.py .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]