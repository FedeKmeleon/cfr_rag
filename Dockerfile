# Dockerfile for running locally
# Save the following content in a file named Dockerfile

FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# To build and run the Docker container locally:
# 1. Build the Docker image:
#    docker build -t rag-storage .
# 2. Run the Docker container:
#    docker run -d -p 8000:8000 rag-storage
# 3. Access the endpoints at http://localhost:8000