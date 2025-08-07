# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Create non-root user for security
RUN groupadd --gid 1000 veeva && \
    useradd --uid 1000 --gid veeva --shell /bin/bash --create-home veeva

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /root/.local /home/veeva/.local

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=veeva:veeva . .

# Create necessary directories
RUN mkdir -p logs reports/validation reports/monitoring data/database config && \
    chown -R veeva:veeva logs reports data config

# Set environment variables
ENV PATH=/home/veeva/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV VEEVA_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python python/main.py status || exit 1

# Switch to non-root user
USER veeva

# Default command - keep container running for interactive use
CMD ["tail", "-f", "/dev/null"]