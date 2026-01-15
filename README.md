# Motor50CV - Sistema de Monitoramento Industrial (Indústria 4.0)

Sistema completo de monitoramento de motor trifásico de 50cv utilizando OPC UA, MQTT, RabbitMQ e FastAPI.

## 🏗️ Arquitetura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Broker MQTT   │     │    RabbitMQ     │     │     Grafana     │
│  (lse.dev.br)   │     │   (Mensageria)  │     │   (Dashboard)   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  MQTT Ingestor  │────▶│  OPC UA Server  │◀────│   API Service   │
│   (Microsserviço)│     │  (Microsserviço) │     │  (Microsserviço) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## 📁 Estrutura do Projeto

```
desafio/
├── docker-compose.yml          # Orquestração dos containers
├── .env                        # Variáveis de ambiente
├── README.md                   # Este arquivo
├── services/
│   ├── mqtt_ingestor/          # Microsserviço de ingestão MQTT
│   ├── opcua_server/           # Microsserviço OPC UA Server
│   └── api_service/            # Microsserviço API FastAPI
├── tests/                      # Testes unitários e E2E
├── scripts/                    # Scripts auxiliares
└── grafana/                    # Configurações do Grafana
```

## 🚀 Como Executar

### Pré-requisitos
- Docker e Docker Compose instalados
- Python 3.11+ (para desenvolvimento local)

### Iniciar todos os serviços
```bash
docker-compose up -d
```

### Verificar status dos containers
```bash
docker-compose ps
```

### Visualizar logs
```bash
docker-compose logs -f
```

### Parar todos os serviços
```bash
docker-compose down
```

## 🔗 Endpoints e Portas

| Serviço | Porta | URL |
|---------|-------|-----|
| API FastAPI | 8000 | http://localhost:8000 |
| Swagger Docs | 8000 | http://localhost:8000/docs |
| OPC UA Server | 4840 | opc.tcp://localhost:4840/motor50cv/server |
| RabbitMQ Management | 15672 | http://localhost:15672 |
| Grafana | 3000 | http://localhost:3000 |

## 📡 API Endpoints

- `GET /api/v1/motor/latest` - Estado atual do motor
- `GET /api/v1/motor/history/{variable}` - Histórico de uma variável
- `GET /api/v1/motor/alarms` - Histórico de alarmes

## 🧪 Executar Testes

```bash
# Instalar dependências de teste
pip install -r requirements-dev.txt

# Executar testes com cobertura
pytest --cov=services --cov-report=html tests/

# Teste E2E
python tests/test_e2e.py
```

## 📊 Grafana

Acesse http://localhost:3000 com:
- Usuário: `admin`
- Senha: `admin123`

## 📚 Documentação

Gerar documentação com Pydoc:
```bash
python -m pydoc -w services
```

## 🔧 Desenvolvimento Local

```bash
# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 📝 Licença

Este projeto é parte de um desafio técnico para demonstração de conhecimentos em Indústria 4.0.
