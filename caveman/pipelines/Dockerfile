FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
ENV SHARED_DATA_PATH=/shared/data
ENV VAULT_BUS_PATH=/vault/bus
ENV PYTHONPATH=/app
CMD ["python", "src/pipeline.py"]
