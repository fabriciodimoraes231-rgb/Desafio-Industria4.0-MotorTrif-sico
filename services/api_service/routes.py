"""
Rotas da API para dados do motor.

Este módulo define os endpoints REST para consulta de dados
do motor 50CV.
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


@router.get(
    "/latest",
    response_model=MotorLatestResponse,
    summary="Estado atual do motor",
    description="Retorna o último estado conhecido do motor, incluindo todas as variáveis elétricas, ambientais e de vibração."
)
async def get_latest(
    service: DataService = Depends(get_data_service)
):
    """
    Retorna o estado atual do motor.
    
    Returns:
        MotorLatestResponse: Estado completo com todas as variáveis
        
    Example:
        GET /api/v1/motor/latest
    """
    data = await service.get_latest()
    return data


@router.get(
    "/history/{variable}",
    response_model=HistoryResponse,
    summary="Histórico de uma variável",
    description="Retorna os dados históricos de uma variável específica com filtros de tempo."
)
async def get_history(
    variable: str,
    start_time: Optional[datetime] = Query(
        None,
        description="Início do período (ISO 8601). Padrão: 24 horas atrás"
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="Fim do período (ISO 8601). Padrão: agora"
    ),
    limit: int = Query(
        1000,
        ge=1,
        le=10000,
        description="Número máximo de registros"
    ),
    service: DataService = Depends(get_data_service)
):
    """
    Retorna histórico de uma variável.
    
    Args:
        variable: Nome da variável (ex: VoltageA, CurrentB, CaseTemperature)
        start_time: Início do período
        end_time: Fim do período
        limit: Máximo de registros
        
    Returns:
        HistoryResponse: Dados históricos da variável
        
    Raises:
        HTTPException: Se variável não existe ou não tem histórico
        
    Example:
        GET /api/v1/motor/history/VoltageA?limit=100
    """
    # Validar variável
    if variable not in AVAILABLE_VARIABLES:
        raise HTTPException(
            status_code=404,
            detail=f"Variável '{variable}' não encontrada. Variáveis disponíveis: {AVAILABLE_VARIABLES}"
        )
        
    # Verificar se variável tem histórico
    if variable not in HISTORIZED_VARIABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Variável '{variable}' não possui histórico habilitado. Variáveis com histórico: {HISTORIZED_VARIABLES}"
        )
        
    data = await service.get_history(variable, start_time, end_time, limit)
    return data


@router.get(
    "/history/{variable}/statistics",
    response_model=HistoryStatisticsResponse,
    summary="Estatísticas de uma variável",
    description="Retorna estatísticas (min, max, média) de uma variável em um período."
)
async def get_statistics(
    variable: str,
    hours: int = Query(
        24,
        ge=1,
        le=720,
        description="Período em horas para cálculo das estatísticas"
    ),
    service: DataService = Depends(get_data_service)
):
    """
    Retorna estatísticas de uma variável.
    
    Args:
        variable: Nome da variável
        hours: Período em horas (1-720)
        
    Returns:
        HistoryStatisticsResponse: Estatísticas da variável
        
    Example:
        GET /api/v1/motor/history/VoltageA/statistics?hours=24
    """
    if variable not in HISTORIZED_VARIABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Variável '{variable}' não possui histórico habilitado"
        )
        
    data = await service.get_statistics(variable, hours)
    return data


@router.get(
    "/alarms",
    response_model=AlarmsListResponse,
    summary="Histórico de alarmes",
    description="Retorna o histórico de alarmes com filtros opcionais."
)
async def get_alarms(
    start_time: Optional[datetime] = Query(
        None,
        description="Início do período. Padrão: 7 dias atrás"
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="Fim do período. Padrão: agora"
    ),
    category: Optional[str] = Query(
        None,
        description="Filtrar por categoria (Electrical, Environment, Vibration)"
    ),
    active_only: bool = Query(
        False,
        description="Retornar apenas alarmes não reconhecidos"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Número máximo de registros"
    ),
    service: DataService = Depends(get_data_service)
):
    """
    Retorna histórico de alarmes.
    
    Args:
        start_time: Início do período
        end_time: Fim do período
        category: Filtrar por categoria
        active_only: Apenas alarmes ativos
        limit: Máximo de registros
        
    Returns:
        AlarmsListResponse: Lista de alarmes
        
    Example:
        GET /api/v1/motor/alarms?category=Electrical&active_only=true
    """
    # Validar categoria se fornecida
    valid_categories = ["Electrical", "Environment", "Vibration"]
    if category and category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Categoria inválida. Categorias válidas: {valid_categories}"
        )
        
    data = await service.get_alarms(start_time, end_time, category, active_only, limit)
    return data


@router.post(
    "/alarms/{alarm_id}/acknowledge",
    summary="Reconhecer alarme",
    description="Marca um alarme como reconhecido."
)
async def acknowledge_alarm(
    alarm_id: str,
    service: DataService = Depends(get_data_service)
):
    """
    Reconhece um alarme.
    
    Args:
        alarm_id: ID do alarme a reconhecer
        
    Returns:
        Mensagem de sucesso
        
    Raises:
        HTTPException: Se alarme não encontrado
        
    Example:
        POST /api/v1/motor/alarms/2025-08-08T12:00:00_CaseTemperature/acknowledge
    """
    success = await service.acknowledge_alarm(alarm_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Alarme '{alarm_id}' não encontrado"
        )
        
    return {"message": "Alarme reconhecido com sucesso", "alarm_id": alarm_id}


@router.get(
    "/variables",
    summary="Listar variáveis disponíveis",
    description="Retorna a lista de todas as variáveis disponíveis para consulta."
)
async def list_variables():
    """
    Lista todas as variáveis disponíveis.
    
    Returns:
        Dicionário com variáveis e suas propriedades
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


@router.get(
    "/timeseries/{variable}",
    summary="Séries temporais para Grafana",
    description="Retorna dados históricos formatados como time series para visualização em Grafana."
)
async def get_timeseries(
    variable: str,
    start_time: Optional[datetime] = Query(
        None,
        description="Início do período (ISO 8601). Padrão: 1 hora atrás"
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="Fim do período (ISO 8601). Padrão: agora"
    ),
    limit: int = Query(
        500,
        ge=1,
        le=5000,
        description="Número máximo de pontos"
    ),
    service: DataService = Depends(get_data_service)
):
    """
    Retorna séries temporais para gráficos.
    
    Args:
        variable: Nome da variável
        start_time: Início do período
        end_time: Fim do período
        limit: Máximo de pontos
        
    Returns:
        Lista de pontos [timestamp, valor] para gráficos
    """
    if variable not in HISTORIZED_VARIABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Variável '{variable}' não possui histórico"
        )
        
    end_time = end_time or datetime.now(timezone.utc)
    start_time = start_time or (end_time - timedelta(hours=1))
    
    data = await service.get_history(variable, start_time, end_time, limit)
    
    # Formatar para time series
    return {
        "target": variable,
        "datapoints": [
            [point["value"], point["timestamp"]]
            for point in reversed(data.get("data", []))
        ]
    }
