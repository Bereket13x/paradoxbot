# Use a lightweight Python image
FROM python:3.10-slim-bookworm

LABEL org.opencontainers.image.title="PARADOX"
LABEL org.opencontainers.image.description="Advanced Telegram Userbot"

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (including lxml build deps + fonts for image plugins)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libzbar0 \
    libxml2-dev \
    libxslt-dev \
    gcc \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python modules
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of your bot's code into the container
COPY . .

# Command to start the bot
CMD ["python3", "main.py"]
