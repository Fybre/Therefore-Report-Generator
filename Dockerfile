FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Python packages
# gcc is needed for compiling bcrypt/cryptography wheels
COPY requirements.txt .
RUN apt-get update && apt-get install -y \
    gcc \
    gosu \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY app/ ./app/
COPY templates/ ./templates/

# Create directories for runtime data (mounted as volumes)
RUN mkdir -p /app/email_templates /app/data

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
