# Use the official Python image as the base image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file to the working directory
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code to the working directory
COPY . .

# Expose the port on which the FastAPI application will run
EXPOSE 8002

# Run the Celery worker and FastAPI application when the container starts
CMD celery -A celery_worker worker --loglevel=info --concurrency=1 & uvicorn main:app --host 0.0.0.0 --port 8000
