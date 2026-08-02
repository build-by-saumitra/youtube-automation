FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg imagemagick espeak-ng espeak-ng-data \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p output cache music data logs

# Expose both FastAPI and Streamlit ports
EXPOSE 8000 8501

# Default: run FastAPI (override for Streamlit)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
