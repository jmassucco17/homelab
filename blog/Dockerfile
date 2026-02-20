FROM python:3.12-slim
WORKDIR /app
COPY blog/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY blog/app ./app
COPY blog/posts ./posts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
