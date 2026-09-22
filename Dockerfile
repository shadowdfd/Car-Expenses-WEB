FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# copy requirements and install
COPY requirements.txt /app/
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# copy application
COPY . /app

# create data directory for SQLite database
RUN mkdir -p /app/data

# Копируем скрипты инициализации и entrypoint
COPY init_db.py /app/
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# Используем entrypoint для автоматической инициализации БД
ENTRYPOINT ["/app/entrypoint.sh"]
