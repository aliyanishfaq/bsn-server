# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the unzipped IfcOpenShell folder to the container's site-packages
#COPY ifcopenshell /usr/local/lib/python3.11/site-packages/ifcopenshell

# Install necessary dependencies
RUN apt-get update && apt-get install -y gcc

# Install any additional dependencies specified in requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port that the app runs on
EXPOSE 8000

# Define environment variables
ENV UVICORN_APP=server:combined_asgi_app
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000
ENV UVICORN_RELOAD=True

# Run the application
CMD ["uvicorn", "server:combined_asgi_app", "--host", "0.0.0.0", "--port", "8000", "--reload"]