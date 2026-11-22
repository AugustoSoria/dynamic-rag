FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf

WORKDIR /app

# PyTorch solo para CPU: el paquete por defecto trae CUDA (varios GB que en el servidor no sirven).
# Va en una capa aparte para que cambiar requirements.txt no lo vuelva a descargar.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt .
RUN pip install -r requirements.txt

# El modelo de embeddings se descarga al construir la imagen: el contenedor arranca sin internet
# y sin consultar huggingface.co en cada inicio.
ARG EMBEDDING_MODEL=intfloat/multilingual-e5-small
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL} \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    ANONYMIZED_TELEMETRY=False \
    DATA_DIR=/app/data

COPY app ./app

# Usuario sin privilegios; data/ es donde escribe (PDFs y Chroma), montada como volumen.
RUN useradd --create-home --uid 1000 app && mkdir -p /app/data && chown app:app /app/data
USER app

EXPOSE 8000

# Un solo proceso a propósito: la cola de trabajos y el límite de uso viven en memoria.
# --proxy-headers: la IP real del cliente viene de Caddy en X-Forwarded-For (para el límite por IP).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
