# Multi-stage build for ATDW Data Probe REST API
# Deploy as: docker run -e DATABASE_URL=... -p 8000:8000 atdw-probe-api

FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn[standard]

# Copy source
COPY src/ src/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run the API server
CMD ["uvicorn", "src.api_server:app", "--host", "0.0.0.0", "--port", "8000"]
