FROM python:3.11-slim

WORKDIR /app

# Install build tools for biopython and postgresql client
RUN apt-get update && apt-get install -y gcc postgresql-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# amd64's default torch wheel pulls multi-GB CUDA libs; force CPU-only there.
# arm64 (Apple Silicon Docker) already resolves a CPU-only wheel, so skip.
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "amd64" ]; then \
      pip install --no-cache-dir torch==2.12.0 --index-url https://download.pytorch.org/whl/cpu; \
    fi
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]