FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей системы
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY bot/ ./bot/
COPY .env .env

# Создание директории для кеша
RUN mkdir -p /app/audio_cache /app/logs

# Точка входа
CMD ["python", "-m", "bot.main"]
