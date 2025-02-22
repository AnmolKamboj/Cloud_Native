# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port Flask will run on
EXPOSE 8080

# Set environment variables
ENV FLASK_APP=mainapp.py
ENV FLASK_ENV=production

# Run the Flask application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "mainapp:app"]