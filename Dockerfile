FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY skillos/ ./skillos/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Install Python dependencies
RUN pip install --no-cache-dir -e "."

# Create non-root user
RUN useradd -m -u 1000 skillos && chown -R skillos:skillos /app
USER skillos

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run application
CMD ["python", "-m", "skillos"]
