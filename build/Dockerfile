# Use an official Python base image
FROM python:3.11.2-slim

# Install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Clone the repository
RUN git clone https://github.com/gscafo78/synapsebot.git /app

# Set the working directory
WORKDIR /app

# Install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

VOLUME /app
# Specify the command to run the application
CMD ["python", "rssbot.py"]