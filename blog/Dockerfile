FROM ghcr.io/jmassucco17/homelab/python-base:latest
COPY blog/ ./blog/
CMD ["uvicorn", "blog.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
