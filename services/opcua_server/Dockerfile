FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Criar diretório de dados
RUN mkdir -p /app/data

# Copiar código fonte
COPY . .

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expor porta OPC UA
EXPOSE 4840

# Comando de execução
CMD ["python", "-m", "main"]
