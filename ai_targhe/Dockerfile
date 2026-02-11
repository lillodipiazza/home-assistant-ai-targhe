# Default per build locale; il Supervisor passa BUILD_FROM da build.yaml
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.21
FROM ${BUILD_FROM}

# Dipendenze di sistema per OpenCV, Tesseract OCR e compilazione
RUN apk add --no-cache \
    libstdc++ \
    libgcc \
    libffi-dev \
    jpeg-dev \
    zlib-dev \
    libpng-dev \
    openblas-dev \
    g++ \
    gcc \
    musl-dev \
    python3-dev \
    tesseract-ocr \
    tesseract-ocr-data-ita \
    tesseract-ocr-data-eng

# Installa dipendenze Python
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Copia il codice applicativo
COPY app/ /app/

# Copia modelli YOLO (usare best.onnx; vedi scripts/export_onnx.py per esportare da best.pt)
COPY models/ /app/models/

# Copia lo script di avvio
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
