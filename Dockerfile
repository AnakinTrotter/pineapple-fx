FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY data/ ./data/
COPY static/ ./static/
COPY run.py .

# Environment variables (can be overridden at runtime)
ENV PINEAPPLE_HOST=0.0.0.0
ENV PINEAPPLE_PORT=8000
ENV PINEAPPLE_DEBUG=false
# Admin API key - pass via: docker run -e PINEAPPLE_ADMIN_KEY=your-key
# If not set, a random key is generated and logged at startup
ENV PINEAPPLE_ADMIN_KEY=""

# Expose the port
EXPOSE 8000

# Run the application
CMD ["python", "run.py"]
