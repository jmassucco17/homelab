FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY blog/app ./app
COPY blog/blog_posts ./blog_posts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
