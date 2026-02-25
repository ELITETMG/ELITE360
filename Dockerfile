# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install system dependencies required by GDAL, GEOS, PROJ (used by Fiona/Shapely)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables expected by Fiona
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV PROJ_DIR=/usr

WORKDIR /app

# Copy the full source first so `pip install .` has package code available
COPY . .

# Install pip build tools and project dependencies from pyproject.toml
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . gunicorn "uvicorn[standard]"

# Render injects $PORT at runtime; default to 10000 for local testing
ENV PORT=10000

EXPOSE 10000

CMD gunicorn main:app \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT} \
    --workers 2 \
    --timeout 120
