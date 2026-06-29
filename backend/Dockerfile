FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
# PyTorch se instala desde el indice CUDA oficial para que BGE pueda usar GPU
# cuando Docker expone una GPU NVIDIA. Sin GPU, EMBEDDING_DEVICE=auto cae a CPU.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu130 torch==2.11.0 \
    && pip install --no-cache-dir ".[ai]"

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
