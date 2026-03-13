FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Install Python and essential build tools
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app/
    
# install dependencies
RUN pip install --upgrade pip
COPY ./src/requirements.txt /usr/src/app/requirements.txt
COPY ./src/requirements-gpu.txt /usr/src/app/requirements-gpu.txt
RUN pip install  --no-cache-dir -r requirements.txt
RUN pip install  --no-cache-dir -r requirements-gpu.txt --extra-index-url https://download.pytorch.org/whl/cu128

# Copy the app code
COPY . /usr/src/app/

# Run the worker with solo pool for GPU tasks
CMD ["celery", "-A", "src.worker:worker", "worker", "-E", "--loglevel=info", "--pool=solo", "-Q", "queue1"]