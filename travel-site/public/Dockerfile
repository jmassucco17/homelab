FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --user-group python

# Set appropriate permissions
RUN chown -R python:python /app
USER python

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]