FROM ghcr.io/jmassucco17/homelab/python-base:latest
COPY common ./common
COPY blog/app ./app
COPY blog/posts ./posts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
