# Use an official Python base image
FROM python:3.9-slim

RUN git clone https://github.com/gscafo78/synapsebot.git /app

# Set the working directory
WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Specify the command to run the application
CMD ["python", "rssbot.py"]