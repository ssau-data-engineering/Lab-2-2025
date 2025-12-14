FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg wget && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir git+https://github.com/m1guelpf/auto-subtitle.git && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY app.py config.py .

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:5000/docs || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
