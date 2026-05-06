FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
ENV SHARED_KNOWLEDGE_PATH=/shared/knowledge
ENV VAULT_BUS_PATH=/vault/bus
ENV LIBRARIAN_INDEX_PATH=/app/librarian/index
CMD ["python", "main.py"]
