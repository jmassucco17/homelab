FROM ghcr.io/jmassucco17/homelab/python-base:latest
COPY common ./common
COPY games/app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
