# Motor50CV - Sistema de Monitoramento Industrial

Sistema completo de monitoramento de motor trifasico de 50cv utilizando OPC UA, MQTT, RabbitMQ e FastAPI.

Desenvolvido como parte do desafio tecnico para demonstracao de conhecimentos em Industria 4.0.


## Indice

1. [Arquitetura](#arquitetura)
2. [Estrutura do Projeto](#estrutura-do-projeto)
3. [Como Executar](#como-executar)
4. [Endpoints e Portas](#endpoints-e-portas)
5. [Documentacao da API](#documentacao-da-api)
6. [Documentacao do Codigo](#documentacao-do-codigo)
7. [Testes](#testes)
8. [Grafana](#grafana)
9. [Banco de Dados](#banco-de-dados)
10. [Desenvolvimento Local](#desenvolvimento-local)


## Arquitetura

```
+-------------------+     +-------------------+     +-------------------+
|   Broker MQTT     |     |     RabbitMQ      |     |      Grafana      |
|   (lse.dev.br)    |     |   (Mensageria)    |     |    (Dashboard)    |
+---------+---------+     +---------+---------+     +---------+---------+
          |                         |                         |
          v                         v                         v
+-------------------+     +-------------------+     +-------------------+
|   MQTT Ingestor   |---->|   OPC UA Server   |<----|    API Service    |
|  (Microsservico)  |     |  (Microsservico)  |     |  (Microsservico)  |
+-------------------+     +-------------------+     +-------------------+
```

### Fluxo de Dados

1. **MQTT Ingestor**: Conecta ao broker MQTT externo, valida os dados recebidos e publica no RabbitMQ
2. **OPC UA Server**: Consome mensagens do RabbitMQ, atualiza variaveis OPC UA, gera alarmes e historiza dados
3. **API Service**: Expoe dados via REST API para consumo do Grafana e outras aplicacoes
4. **Grafana**: Visualiza dados em tempo real e historico atraves da API REST


## Estrutura do Projeto

```
desafio/
├── docker-compose.yml          # Orquestracao dos containers
├── .env                        # Variaveis de ambiente
├── README.md                   # Este arquivo
├── requirements.txt            # Dependencias principais
├── requirements-dev.txt        # Dependencias de desenvolvimento
├── pytest.ini                  # Configuracao do pytest
│
├── services/
│   ├── mqtt_ingestor/          # Microsservico de ingestao MQTT
│   │   ├── main.py             # Ponto de entrada
│   │   ├── mqtt_client.py      # Cliente MQTT assincrono
│   │   ├── rabbitmq_publisher.py # Publisher RabbitMQ
│   │   ├── validators.py       # Validadores Pydantic
│   │   └── config.py           # Configuracoes
│   │
│   ├── opcua_server/           # Microsservico OPC UA Server
│   │   ├── main.py             # Ponto de entrada
│   │   ├── server.py           # Servidor OPC UA
│   │   ├── nodeset.py          # Construtor do nodeset
│   │   ├── alarms.py           # Gerenciador de alarmes
│   │   ├── history_storage.py  # Armazenamento de historico
│   │   ├── rabbitmq_consumer.py # Consumidor RabbitMQ
│   │   └── config.py           # Configuracoes
│   │
│   └── api_service/            # Microsservico API FastAPI
│       ├── main.py             # Ponto de entrada
│       ├── app.py              # Aplicacao FastAPI
│       ├── routes.py           # Rotas da API
│       ├── schemas.py          # Schemas Pydantic
│       ├── services.py         # Camada de servicos
│       └── config.py           # Configuracoes
│
├── tests/                      # Testes unitarios e E2E
│   ├── conftest.py             # Fixtures do pytest
│   ├── test_api.py             # Testes da API
│   ├── test_mqtt_ingestor.py   # Testes do ingestor
│   ├── test_opcua_server.py    # Testes do servidor OPC UA
│   └── test_e2e.py             # Testes end-to-end
│
├── scripts/                    # Scripts auxiliares
│   ├── mqtt_producer.py        # Produtor de dados simulados
│   └── data_generator.py       # Gerador de dados
│
├── grafana/                    # Configuracoes do Grafana
│   ├── dashboards/             # Dashboards JSON
│   └── provisioning/           # Configuracao automatica
│
└── docs/                       # Documentacao gerada
    └── pydoc/                  # Documentacao Pydoc (HTML)
```


## Como Executar

### Pre-requisitos

- Docker e Docker Compose instalados
- Python 3.11+ (para desenvolvimento local)

### Iniciar todos os servicos

```bash
docker-compose up -d
```

### Verificar status dos containers

```bash
docker-compose ps
```

### Visualizar logs

```bash
# Todos os servicos
docker-compose logs -f

# Servico especifico
docker-compose logs -f api-service
docker-compose logs -f opcua-server
docker-compose logs -f mqtt-ingestor
```

### Parar todos os servicos

```bash
docker-compose down

# Para remover volumes tambem
docker-compose down -v
```


## Endpoints e Portas

| Servico | Porta | URL |
|---------|-------|-----|
| API FastAPI | 8000 | http://localhost:8000 |
| Swagger Docs | 8000 | http://localhost:8000/docs |
| ReDoc | 8000 | http://localhost:8000/redoc |
| OPC UA Server | 4840 | opc.tcp://localhost:4840/motor50cv/server |
| RabbitMQ Management | 15672 | http://localhost:15672 |
| Grafana | 3000 | http://localhost:3000 |


## Documentacao da API

A documentacao da API e gerada automaticamente pelo FastAPI e esta disponivel em:

- **Swagger UI (Interativo)**: http://localhost:8000/docs
- **ReDoc (Alternativo)**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Endpoints Disponiveis

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/v1/motor/latest` | Estado atual do motor (tensoes, correntes, potencias, etc) |
| GET | `/api/v1/motor/history/{variable}` | Historico de uma variavel especifica |
| GET | `/api/v1/motor/history/{variable}/statistics` | Estatisticas (min, max, avg) de uma variavel |
| GET | `/api/v1/motor/alarms` | Lista de alarmes (ativos e historico) |
| POST | `/api/v1/motor/alarms/{alarm_id}/acknowledge` | Reconhecer um alarme |
| GET | `/api/v1/motor/variables` | Lista todas as variaveis disponiveis |
| GET | `/api/v1/motor/timeseries/{variable}` | Series temporais para graficos |
| GET | `/health` | Health check da API |

### Variaveis Disponiveis

**Eletricas (com historico):**
- VoltageA, VoltageB, VoltageC (V)
- CurrentA, CurrentB, CurrentC (A)
- PowerActive (W), PowerReactive (VAr), PowerApparent (VA)
- EnergyActive (Wh), EnergyReactive (VArh), EnergyApparent (VAh)
- PowerFactor, Frequency (Hz)

**Ambientais:**
- Temperature, Humidity, CaseTemperature (com historico)

**Vibracao:**
- Axial, Radial (mm/s)


## Documentacao do Codigo

O codigo fonte esta documentado utilizando docstrings no padrao Python. A documentacao pode ser gerada utilizando a ferramenta Pydoc.

### Gerar Documentacao HTML

```bash
# Criar diretorio para documentacao
mkdir -p docs/pydoc

# Gerar documentacao de cada modulo
cd services/api_service && python -m pydoc -w app routes schemas services config
cd ../mqtt_ingestor && python -m pydoc -w main mqtt_client rabbitmq_publisher validators config
cd ../opcua_server && python -m pydoc -w main server nodeset alarms history_storage rabbitmq_consumer config

# Mover arquivos gerados
mv *.html ../../docs/pydoc/
```

### Visualizar Documentacao Interativa

```bash
# Servidor de documentacao local (porta 8080)
python -m pydoc -p 8080
```

Acesse http://localhost:8080 para navegar pela documentacao.

### Padrao de Docstrings

O projeto utiliza docstrings no formato padrao Python:

```python
def funcao_exemplo(param1: str, param2: int = 10) -> dict:
    """
    Descricao breve da funcao.
    
    Descricao mais detalhada se necessario, explicando
    o comportamento e uso da funcao.
    
    Args:
        param1: Descricao do primeiro parametro
        param2: Descricao do segundo parametro (padrao: 10)
        
    Returns:
        Dicionario com os resultados processados
        
    Raises:
        ValueError: Se param1 estiver vazio
        
    Example:
        >>> resultado = funcao_exemplo("teste", 20)
        >>> print(resultado)
        {'status': 'ok'}
    """
    pass
```


## Testes

### Instalar Dependencias de Teste

```bash
pip install -r requirements-dev.txt
```

### Executar Testes

```bash
# Todos os testes
pytest

# Com cobertura de codigo
pytest --cov=services --cov-report=html tests/

# Testes especificos
pytest tests/test_api.py -v
pytest tests/test_mqtt_ingestor.py -v
pytest tests/test_opcua_server.py -v

# Teste E2E (requer containers rodando)
pytest tests/test_e2e.py -v
```

### Relatorio de Cobertura

Apos executar com `--cov-report=html`, abra `htmlcov/index.html` no navegador.


## Grafana

Acesse http://localhost:3000 com:
- **Usuario**: admin
- **Senha**: tpv@2026

### Dashboard Motor50CV

O dashboard pre-configurado inclui:
- Graficos de tensao trifasica (tempo real e historico)
- Graficos de corrente trifasica
- Medidores de potencia ativa/reativa/aparente
- Indicadores de temperatura
- Painel de alarmes ativos


## Banco de Dados

O sistema utiliza **SQLite** para persistencia de dados historicos e alarmes. O banco de dados e gerenciado pelo servico `opcua-server`.

### Localizacao

- **No container**: `/app/data/history.db`
- **Volume Docker**: Persistido automaticamente

### Acessar o Banco de Dados

```bash
# Copiar banco do container para maquina local
docker cp opcua-server:/app/data/history.db ./history.db

# Acessar via sqlite3
sqlite3 history.db
```

### Tabelas Disponiveis

| Tabela | Descricao |
|--------|-----------|
| `alarm_history` | Historico de alarmes gerados |
| `current_values` | Valores atuais das variaveis |
| `variable_history` | Historico geral de variaveis |
| `variable_node_mapping` | Mapeamento variavel -> NodeId OPC UA |
| `history_2_*` | Historico OPC UA por variavel individual |

### Consultas Uteis

```sql
-- Ver alarmes recentes
SELECT * FROM alarm_history ORDER BY timestamp DESC LIMIT 10;

-- Ver valores atuais de todas as variaveis
SELECT * FROM current_values;

-- Ver historico de uma variavel especifica
SELECT * FROM variable_history 
WHERE variable_name = 'VoltageA' 
ORDER BY timestamp DESC LIMIT 10;

-- Contar total de registros de historico
SELECT COUNT(*) FROM variable_history;

-- Ver mapeamento de variaveis para NodeIds
SELECT * FROM variable_node_mapping;

-- Estatisticas de uma variavel
SELECT 
    variable_name,
    MIN(value) as min_value,
    MAX(value) as max_value,
    AVG(value) as avg_value,
    COUNT(*) as total_records
FROM variable_history 
WHERE variable_name = 'VoltageA'
GROUP BY variable_name;
```

### Acesso via API REST

Alternativamente, os dados podem ser acessados via API:

```bash
# Valores atuais
curl http://localhost:8000/api/v1/motor/latest

# Historico de uma variavel (ultima hora)
curl "http://localhost:8000/api/v1/motor/history/VoltageA?hours=1"

# Estatisticas
curl "http://localhost:8000/api/v1/motor/history/VoltageA/statistics?hours=24"

# Alarmes
curl http://localhost:8000/api/v1/motor/alarms
```


## Desenvolvimento Local

### Configurar Ambiente

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Variaveis de Ambiente

Copie o arquivo `.env.example` para `.env` e ajuste conforme necessario:

```bash
cp .env.example .env
```

### Executar Servicos Localmente

```bash
# API Service
cd services/api_service
uvicorn app:app --reload --port 8000

# MQTT Ingestor
cd services/mqtt_ingestor
python main.py

# OPC UA Server
cd services/opcua_server
python main.py
```


## Tecnologias Utilizadas

- **Python 3.11**: Linguagem principal
- **FastAPI**: Framework web para a API REST
- **asyncua**: Biblioteca OPC UA para Python
- **gmqtt**: Cliente MQTT assincrono
- **aio-pika**: Cliente RabbitMQ assincrono
- **Pydantic**: Validacao de dados
- **SQLite**: Armazenamento de historico
- **Docker**: Containerizacao
- **Grafana**: Visualizacao de dados


## Autor: Manuel Moraes

Desenvolvido como parte de desafio tecnico de Industria 4.0.
