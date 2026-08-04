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

RUN chmod +x start.sh

# Hugging Face Spaces default port
EXPOSE 7860

# Run the startup script
CMD ["./start.sh"]
