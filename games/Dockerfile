FROM ghcr.io/jmassucco17/homelab/python-base:latest
COPY games/ ./games/
CMD ["uvicorn", "games.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
