[Region: us-west1]
=========================
Using Detected Dockerfile
=========================

context: 06fw-Xt_o

internal
load build definition from Dockerfile
0ms

internal
load metadata for docker.io/library/python:3.11-slim
321ms

auth
library/python:pull token for registry-1.docker.io
0ms

internal
load .dockerignore
0ms

internal
load build context
0ms

2
WORKDIR /app cached
1ms

3
RUN apt-get update && apt-get install -y     gcc     g++     && rm -rf /var/lib/apt/lists/*
10s
Processing triggers for libc-bin (2.41-12+deb13u2) ...

4
COPY requirements.txt .
50ms

5
RUN pip install --no-cache-dir -r requirements.txt
37s
[notice] To update, run: pip install --upgrade pip

6
COPY . .
150ms

auth
sharing credentials for production-us-west2.railway-registry.com
0ms
Build time: 87.30 seconds
 
====================
Starting Healthcheck
====================
Path: /health
Retry window: 1m40s
 
Attempt #1 failed with service unavailable. Continuing to retry for 1m29s
Attempt #2 failed with service unavailable. Continuing to retry for 1m18s
Attempt #3 failed with service unavailable. Continuing to retry for 1m6s
Attempt #4 failed with service unavailable. Continuing to retry for 52s
Attempt #5 failed with service unavailable. Continuing to retry for 34s
Attempt #6 failed with service unavailable. Continuing to retry for 8s
 
1/1 replicas never became healthy!

Healthcheck failed!