# Dockerfile (для Backend + TG-Bot)

# Используем образ Python нужной версии. 
# ВАЖНО: Укажите здесь версию, совместимую с вашим проектом (например, 3.13)
FROM python:3.13-slim

# Устанавливаем Supervisor для управления процессами
RUN apt-get update && apt-get install -y \
    supervisor \
    ffmpeg

WORKDIR /app

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости с помощью pip
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код, модели и конфиг Supervisor
COPY ./src ./src
COPY ./models ./models
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Создаем директорию для логов, которые будет писать Supervisor
RUN mkdir -p /var/log/supervisor

# Запускаем Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]