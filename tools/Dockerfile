FROM ghcr.io/jmassucco17/homelab/python-base:latest
COPY tools/ ./tools/
CMD ["uvicorn", "tools.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
