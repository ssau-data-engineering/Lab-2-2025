FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    torchaudio==2.2.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir --no-deps \
    git+https://github.com/openai/whisper.git

RUN pip install --no-cache-dir --no-deps \
    git+https://github.com/m1guelpf/auto-subtitle.git

RUN pip install --no-cache-dir flask ffmpeg-python tqdm tiktoken numba
RUN pip install -U "numpy<2"

RUN mkdir /app/tmp && \
    chmod 777 /app/tmp

COPY app.py .

EXPOSE 8001

CMD ["python", "app.py"]
