# Образ для приложения SpendSense
FROM python:3.13-slim

# Системные зависимости: tesseract для распознавания чеков (OCR) + русский языковой пакет
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория и каталог для базы данных (SQLite)
WORKDIR /app
RUN mkdir -p /app/data

# Установка зависимостей Python (слой кэшируется отдельно от кода)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода проекта
COPY . .

# Команда запуска бота
CMD ["python", "bot.py"]