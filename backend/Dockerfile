FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
# Honor Cloud Run/containers' $PORT (defaults to 8080 locally)
CMD ["sh","-c","uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
