# Use Python 3.10 alpine image (smaller)
FROM python:3.10-alpine

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    DATA_PATH=/tmp

# Install build dependencies temporarily
RUN apk add --no-cache --virtual .build-deps gcc musl-dev python3-dev \
    && apk add --no-cache libffi-dev postgresql-dev

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies and remove build deps
RUN pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser -D -u 1000 appuser

# Change ownership of app directory
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]