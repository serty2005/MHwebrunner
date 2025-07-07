FROM python:3.11-slim-buster

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/MHwebrunner

WORKDIR /opt/MHwebrunner

RUN mkdir -p /opt/MHwebrunner/logs

COPY requirements.txt .

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Команда для запуска приложения с помощью Uvicorn
# --host 0.0.0.0 делает приложение доступным извне контейнера
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
