FROM python:3.12-slim

WORKDIR /app

# System deps for lxml, pymupdf
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install core library first (api depends on it)
COPY core/ /app/core/
RUN pip install --no-cache-dir /app/core

COPY api/ /app/api/
RUN pip install --no-cache-dir /app/api

ENV STORAGE_DIR=/data
ENV PYTHONUNBUFFERED=1
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
