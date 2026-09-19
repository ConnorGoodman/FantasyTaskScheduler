FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ftscheduler ./ftscheduler
COPY config.example.yml ./config.example.yml

ENTRYPOINT ["python", "-m", "ftscheduler", "--config", "/app/config.yml"]
