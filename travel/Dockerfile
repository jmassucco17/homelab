FROM ghcr.io/jmassucco17/homelab/python-base:latest
COPY travel/ ./travel/
RUN mkdir -p /data
CMD ["uvicorn", "travel.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
