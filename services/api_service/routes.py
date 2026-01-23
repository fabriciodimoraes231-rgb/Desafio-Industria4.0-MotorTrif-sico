"""
Rotas da API REST do motor 50CV.

Este modulo define todos os endpoints da API REST para consulta
de dados do motor trifasico 50CV. Os endpoints seguem o padrao
RESTful e retornam dados em formato JSON.

Endpoints:
    GET /api/v1/motor/latest: Estado atual do motor
    GET /api/v1/motor/history/{variable}: Historico de uma variavel
    GET /api/v1/motor/history/{variable}/statistics: Estatisticas de uma variavel
    GET /api/v1/motor/alarms: Lista de alarmes
    POST /api/v1/motor/alarms/{alarm_id}/acknowledge: Reconhecer alarme
    GET /api/v1/motor/variables: Lista variaveis disponiveis
    GET /api/v1/motor/timeseries/{variable}: Series temporais para graficos
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends

from schemas import (
    MotorLatestResponse,
    HistoryResponse,
    HistoryStatisticsResponse,
    AlarmsListResponse,
    AlarmResponse,
    AVAILABLE_VARIABLES,
    HISTORIZED_VARIABLES
)
from services import DataService, get_data_service

router = APIRouter(prefix="/api/v1/motor", tags=["motor"])


@router.get("/latest", response_model=MotorLatestResponse)
async def get_latest(service: DataService = Depends(get_data_service)):
    """
    Retorna o estado atual do motor.
    
    Retorna todas as medicoes atuais do motor, incluindo parametros
    eletricos, ambientais, de vibracao e numero de alarmes ativos.
    
    Returns:
        MotorLatestResponse: Estado completo do motor
        
    Example:
        GET /api/v1/motor/latest
        
        Response:
        {
            "timestamp": "2026-01-23T10:30:00Z",
            "electrical": {"voltage": {"a": 220.5, "b": 219.8, "c": 220.1}, ...},
            "environment": {"temperature": 25.5, ...},
            "vibration": {"axial": 0.5, "radial": 0.3},
            "active_alarms": 0
        }
    """
    data = await service.get_latest()
    return data


@router.get("/history/{variable}", response_model=HistoryResponse)
async def get_history(
    variable: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(
        None,
        description="Fim do periodo (ISO 8601). Padrao: agora"
    ),
    limit: int = Query(
        1000,
        ge=1,
        le=10000
    ),
    service: DataService = Depends(get_data_service)
):
    """
    Retorna o historico de uma variavel.
    
    Consulta o historico de valores de uma variavel especifica
    em um determinado periodo de tempo.
    
    Args:
        variable: Nome da variavel (ex: VoltageA, CurrentB, PowerActive)
        start_time: Inicio do periodo (ISO 8601). Padrao: 1 hora atras
        end_time: Fim do periodo (ISO 8601). Padrao: agora
        limit: Numero maximo de registros (1-10000). Padrao: 1000
        
    Returns:
        HistoryResponse: Lista de pontos de dados historicos
        
    Raises:
        HTTPException 404: Variavel nao encontrada
        HTTPException 400: Variavel nao possui historico habilitado
        
    Example:
        GET /api/v1/motor/history/VoltageA?limit=100
    """
    if variable not in AVAILABLE_VARIABLES:
        raise HTTPException(
            status_code=404,
            detail=f"Variavel '{variable}' nao encontrada. Variaveis disponiveis: {AVAILABLE_VARIABLES}"
        )
        
    # Verificar se variável tem histórico
    if variable not in HISTORIZED_VARIABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Variavel '{variable}' nao possui historico habilitado. Variaveis com historico: {HISTORIZED_VARIABLES}"
        )
        
    data = await service.get_history(variable, start_time, end_time, limit)
    return data


@router.get("/history/{variable}/statistics", response_model=HistoryStatisticsResponse)
async def get_statistics(
    variable: str,
    hours: int = Query(24, ge=1, le=720),
    service: DataService = Depends(get_data_service)
):
    """
    Retorna estatisticas de uma variavel.
    
    Calcula estatisticas agregadas (minimo, maximo, media) de uma
    variavel em um determinado periodo.
    
    Args:
        variable: Nome da variavel
        hours: Periodo em horas para o calculo (1-720). Padrao: 24
        
    Returns:
        HistoryStatisticsResponse: Estatisticas da variavel
        
    Raises:
        HTTPException 400: Variavel nao possui historico habilitado
        
    Example:
        GET /api/v1/motor/history/VoltageA/statistics?hours=24
    """
    if variable not in HISTORIZED_VARIABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Variavel '{variable}' nao possui historico habilitado"
        )
        
    data = await service.get_statistics(variable, hours)
    return data


@router.get("/alarms", response_model=AlarmsListResponse)
async def get_alarms(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    category: Optional[str] = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    service: DataService = Depends(get_data_service)
):
    """
    Retorna historico de alarmes.
    
    Lista alarmes gerados pelo sistema, com opcoes de filtro por
    periodo, categoria e status.
    
    Args:
        start_time: Inicio do periodo (ISO 8601)
        end_time: Fim do periodo (ISO 8601)
        category: Filtrar por categoria (Electrical, Environment, Vibration)
        active_only: Se True, retorna apenas alarmes nao reconhecidos
        limit: Numero maximo de registros (1-1000). Padrao: 100
        
    Returns:
        AlarmsListResponse: Lista de alarmes
        
    Raises:
        HTTPException 400: Categoria invalida
        
    Example:
        GET /api/v1/motor/alarms?category=Electrical&active_only=true
    """
    valid_categories = ["Electrical", "Environment", "Vibration"]
    if category and category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Categoria invalida. Categorias validas: {valid_categories}"
        )
        
    data = await service.get_alarms(start_time, end_time, category, active_only, limit)
    return data


@router.post("/alarms/{alarm_id}/acknowledge")
async def acknowledge_alarm(
    alarm_id: str,
    service: DataService = Depends(get_data_service)
):
    """
    Reconhece um alarme.
    
    Marca um alarme como reconhecido pelo operador. Alarmes reconhecidos
    nao sao contabilizados como ativos.
    
    Args:
        alarm_id: Identificador unico do alarme
        
    Returns:
        dict: Mensagem de confirmacao
        
    Raises:
        HTTPException 404: Alarme nao encontrado
        
    Example:
        POST /api/v1/motor/alarms/2026-01-23T10:30:00_VoltageA/acknowledge
    """
    success = await service.acknowledge_alarm(alarm_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Alarme '{alarm_id}' nao encontrado"
        )
        
    return {"message": "Alarme reconhecido com sucesso", "alarm_id": alarm_id}


@router.get("/variables")
async def list_variables():
    """
    Lista todas as variaveis disponiveis.
    
    Retorna a lista completa de variaveis disponiveis para consulta,
    separadas por categoria e indicando quais possuem historico.
    
    Returns:
        dict: Dicionario com listas de variaveis por categoria
        
    Example:
        GET /api/v1/motor/variables
        
        Response:
        {
            "all_variables": ["VoltageA", "VoltageB", ...],
            "historized_variables": ["VoltageA", ...],
            "categories": {
                "electrical": [...],
                "environment": [...],
                "vibration": [...]
            }
        }
    """
    return {
        "all_variables": AVAILABLE_VARIABLES,
        "historized_variables": HISTORIZED_VARIABLES,
        "categories": {
            "electrical": [
                "VoltageA", "VoltageB", "VoltageC",
                "CurrentA", "CurrentB", "CurrentC",
                "PowerActive", "PowerReactive", "PowerApparent",
                "EnergyActive", "EnergyReactive", "EnergyApparent",
                "PowerFactor", "Frequency"
            ],
            "environment": ["Temperature", "Humidity", "CaseTemperature"],
            "vibration": ["Axial", "Radial"]
        }
    }


@router.get("/timeseries/{variable}")
async def get_timeseries(
    variable: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    service: DataService = Depends(get_data_service)
):
    """
    Retorna series temporais para graficos.
    
    Endpoint otimizado para consumo pelo Grafana e outras ferramentas
    de visualizacao. Retorna dados no formato [valor, timestamp_ms].
    
    Args:
        variable: Nome da variavel
        start_time: Inicio do periodo (ISO 8601). Padrao: 1 hora atras
        end_time: Fim do periodo (ISO 8601). Padrao: agora
        limit: Numero maximo de pontos (1-5000). Padrao: 500
        
    Returns:
        dict: Dados no formato de time series
        {
            "target": "VoltageA",
            "datapoints": [[220.5, 1674470400000], ...]
        }
        
    Raises:
        HTTPException 400: Variavel nao possui historico
        
    Example:
        GET /api/v1/motor/timeseries/VoltageA
    """
    if variable not in HISTORIZED_VARIABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Variavel '{variable}' nao possui historico"
        )
        
    end_time = end_time or datetime.now(timezone.utc)
    start_time = start_time or (end_time - timedelta(hours=1))
    
    data = await service.get_history(variable, start_time, end_time, limit)
    
    # Formatar para time series - timestamp em milissegundos epoch
    datapoints = []
    for point in data.get("data", []):
        ts = point["timestamp"]
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        else:
            dt = ts
        ts_ms = int(dt.timestamp() * 1000)
        datapoints.append([point["value"], ts_ms])
    
    # Ordenar por timestamp crescente
    datapoints.sort(key=lambda x: x[1])
    
    return {
        "target": variable,
        "datapoints": datapoints
    }
