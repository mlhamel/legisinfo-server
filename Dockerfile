FROM python:3.12-slim AS builder

WORKDIR /app

# Install curl to download buf CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install buf CLI for code generation
RUN BIN="/usr/local/bin" && \
    VERSION="1.30.0" && \
    curl -sSL \
    "https://github.com/bufbuild/buf/releases/download/v${VERSION}/buf-$(uname -s)-$(uname -m)" \
    -o "${BIN}/buf" && \
    chmod +x "${BIN}/buf"

# Set up python environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv for fast package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project definitions
COPY pyproject.toml ./
# Create dummy folder to satisfy hatchling package layout check during build
RUN mkdir -p src/legisinfo_server && touch src/legisinfo_server/__init__.py

# Sync/install dependencies
RUN uv pip install --system --no-cache .

# Copy Protobuf and Buf configs
COPY proto/ proto/
COPY buf.yaml buf.gen.yaml ./

# Run Buf to generate ConnectRPC code stubs
RUN buf generate

# Now copy the remaining source code
COPY src/ src/


# Create the final runtime image
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LEGISINFO_DATA_PATH=/data

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy python site-packages and generated/source files from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

EXPOSE 8000

# Mount scraped data volume on /data
VOLUME ["/data"]

CMD ["uvicorn", "legisinfo_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
