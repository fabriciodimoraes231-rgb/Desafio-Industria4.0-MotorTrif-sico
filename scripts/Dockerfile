FROM python:3.11-slim

WORKDIR /app

# Instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar script
COPY mqtt_producer.py .

# Variáveis de ambiente padrão
ENV MQTT_HOST=lse.dev.br
ENV MQTT_PORT=1883
ENV ALARM_RATE=0.1
ENV INTERVAL=2.0
ENV PYTHONUNBUFFERED=1

# Executar producer
CMD ["python", "mqtt_producer.py"]
