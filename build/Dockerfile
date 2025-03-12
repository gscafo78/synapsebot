# Use an official Python base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements.txt file into the working directory
COPY ../requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the working directory
COPY ../setting_example.json .
COPY ../rssbot.py ./main.py

# Specify the command to run the application
CMD ["python", "main.py"]