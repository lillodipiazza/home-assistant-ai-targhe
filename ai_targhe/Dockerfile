ARG BUILD_FROM
FROM ${BUILD_FROM}

# Dipendenze di sistema per OpenCV e compilazione
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
    python3-dev

# Installa dipendenze Python
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Copia il codice applicativo
COPY app/ /app/

# Copia il modello YOLO pre-addestrato (6MB)
COPY models/best.pt /app/models/best.pt

# Copia lo script di avvio
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
