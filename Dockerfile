FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Expose FastAPI default port
EXPOSE 8000

# Run the FastAPI app
CMD ["uvicorn", "dashboard.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
