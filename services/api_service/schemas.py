"""
Schemas Pydantic para a API.

Este módulo define os modelos de dados para requisições
e respostas da API REST.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============== Modelos de Dados Elétricos ==============

class VoltageResponse(BaseModel):
    """Resposta com dados de tensão trifásica."""
    a: float = Field(..., description="Tensão fase A (V)")
    b: float = Field(..., description="Tensão fase B (V)")
    c: float = Field(..., description="Tensão fase C (V)")
    
    class Config:
        json_schema_extra = {
            "example": {"a": 220.0, "b": 221.1, "c": 219.5}
        }


class CurrentResponse(BaseModel):
    """Resposta com dados de corrente trifásica."""
    a: float = Field(..., description="Corrente fase A (A)")
    b: float = Field(..., description="Corrente fase B (A)")
    c: float = Field(..., description="Corrente fase C (A)")
    
    class Config:
        json_schema_extra = {
            "example": {"a": 10.5, "b": 10.4, "c": 10.6}
        }


class PowerResponse(BaseModel):
    """Resposta com dados de potência."""
    active: float = Field(..., description="Potência ativa (W)")
    reactive: float = Field(..., description="Potência reativa (VAr)")
    apparent: float = Field(..., description="Potência aparente (VA)")
    
    class Config:
        json_schema_extra = {
            "example": {"active": 4500, "reactive": 500, "apparent": 4600}
        }


class EnergyResponse(BaseModel):
    """Resposta com dados de energia."""
    active: float = Field(..., description="Energia ativa (Wh)")
    reactive: float = Field(..., description="Energia reativa (VArh)")
    apparent: float = Field(..., description="Energia aparente (VAh)")
    
    class Config:
        json_schema_extra = {
            "example": {"active": 10000, "reactive": 1200, "apparent": 10200}
        }


class ElectricalResponse(BaseModel):
    """Resposta completa de dados elétricos."""
    voltage: VoltageResponse
    current: CurrentResponse
    power: PowerResponse
    energy: EnergyResponse
    power_factor: float = Field(..., alias="powerFactor", description="Fator de potência")
    frequency: float = Field(..., description="Frequência (Hz)")
    
    class Config:
        populate_by_name = True


# ============== Modelos de Dados Ambientais ==============

class EnvironmentResponse(BaseModel):
    """Resposta com dados ambientais."""
    temperature: float = Field(..., description="Temperatura ambiente (°C)")
    humidity: float = Field(..., description="Umidade relativa (%)")
    case_temperature: float = Field(..., alias="caseTemperature", description="Temperatura da carcaça (°C)")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {"temperature": 34.5, "humidity": 55.2, "caseTemperature": 62.0}
        }


# ============== Modelos de Dados de Vibração ==============

class VibrationResponse(BaseModel):
    """Resposta com dados de vibração."""
    axial: float = Field(..., description="Vibração axial (mm/s)")
    radial: float = Field(..., description="Vibração radial (mm/s)")
    
    class Config:
        json_schema_extra = {
            "example": {"axial": 0.12, "radial": 0.15}
        }


# ============== Modelo de Estado Completo ==============

class MotorLatestResponse(BaseModel):
    """
    Resposta com estado completo atual do motor.
    
    Retorna os últimos valores conhecidos de todas as variáveis
    do motor 50CV.
    """
    timestamp: datetime = Field(..., description="Data/hora da leitura")
    electrical: ElectricalResponse
    environment: EnvironmentResponse
    vibration: VibrationResponse
    active_alarms: int = Field(..., description="Número de alarmes ativos")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-08-08T12:00:00Z",
                "electrical": {
                    "voltage": {"a": 220.0, "b": 221.1, "c": 219.5},
                    "current": {"a": 10.5, "b": 10.4, "c": 10.6},
                    "power": {"active": 4500, "reactive": 500, "apparent": 4600},
                    "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
                    "powerFactor": 0.95,
                    "frequency": 60.0
                },
                "environment": {
                    "temperature": 34.5,
                    "humidity": 55.2,
                    "caseTemperature": 45.0
                },
                "vibration": {
                    "axial": 0.12,
                    "radial": 0.15
                },
                "active_alarms": 0
            }
        }


# ============== Modelos de Histórico ==============

class HistoryDataPoint(BaseModel):
    """Ponto de dado histórico."""
    timestamp: datetime = Field(..., description="Data/hora do registro")
    value: float = Field(..., description="Valor registrado")
    quality: str = Field(default="Good", description="Qualidade do dado")
    
    class Config:
        json_schema_extra = {
            "example": {"timestamp": "2025-08-08T12:00:00Z", "value": 220.5, "quality": "Good"}
        }


class HistoryResponse(BaseModel):
    """Resposta com dados históricos de uma variável."""
    variable: str = Field(..., description="Nome da variável")
    start_time: datetime = Field(..., description="Início do período")
    end_time: datetime = Field(..., description="Fim do período")
    count: int = Field(..., description="Número de registros retornados")
    data: List[HistoryDataPoint] = Field(..., description="Dados históricos")
    
    class Config:
        json_schema_extra = {
            "example": {
                "variable": "VoltageA",
                "start_time": "2025-08-07T12:00:00Z",
                "end_time": "2025-08-08T12:00:00Z",
                "count": 2,
                "data": [
                    {"timestamp": "2025-08-08T12:00:00Z", "value": 220.5, "quality": "Good"},
                    {"timestamp": "2025-08-08T11:55:00Z", "value": 220.3, "quality": "Good"}
                ]
            }
        }


class HistoryStatisticsResponse(BaseModel):
    """Resposta com estatísticas de uma variável."""
    variable: str = Field(..., description="Nome da variável")
    period_hours: int = Field(..., description="Período em horas")
    min: Optional[float] = Field(None, description="Valor mínimo")
    max: Optional[float] = Field(None, description="Valor máximo")
    avg: Optional[float] = Field(None, description="Valor médio")
    count: int = Field(..., description="Número de registros")


# ============== Modelos de Alarmes ==============

class AlarmResponse(BaseModel):
    """Resposta com dados de um alarme."""
    id: str = Field(..., description="ID único do alarme")
    timestamp: datetime = Field(..., description="Data/hora do alarme")
    category: str = Field(..., description="Categoria (Electrical, Environment, Vibration)")
    severity: int = Field(..., description="Severidade (100-900)")
    severity_name: str = Field(..., description="Nome da severidade")
    message: str = Field(..., description="Mensagem do alarme")
    source_name: str = Field(..., description="Variável fonte")
    value: float = Field(..., description="Valor que disparou o alarme")
    acknowledged: bool = Field(..., description="Se foi reconhecido")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "2025-08-08T12:00:00_CaseTemperature",
                "timestamp": "2025-08-08T12:00:00Z",
                "category": "Environment",
                "severity": 900,
                "severity_name": "CRITICAL",
                "message": "Case temperature critical: 62.0°C",
                "source_name": "CaseTemperature",
                "value": 62.0,
                "acknowledged": False
            }
        }


class AlarmsListResponse(BaseModel):
    """Resposta com lista de alarmes."""
    active_count: int = Field(..., description="Número de alarmes ativos")
    total_count: int = Field(..., description="Total de alarmes no período")
    alarms: List[AlarmResponse] = Field(..., description="Lista de alarmes")


# ============== Modelos de Health Check ==============

class HealthResponse(BaseModel):
    """Resposta de health check."""
    status: str = Field(..., description="Status do serviço (healthy, degraded, unhealthy)")
    timestamp: datetime = Field(..., description="Data/hora da verificação")
    version: str = Field(..., description="Versão da API")
    services: Dict[str, str] = Field(..., description="Status dos serviços dependentes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-08-08T12:00:00Z",
                "version": "1.0.0",
                "services": {
                    "database": "connected",
                    "rabbitmq": "connected",
                    "opcua": "connected"
                }
            }
        }


# ============== Variáveis Disponíveis ==============

AVAILABLE_VARIABLES = [
    # Elétricas
    "VoltageA", "VoltageB", "VoltageC",
    "CurrentA", "CurrentB", "CurrentC",
    "PowerActive", "PowerReactive", "PowerApparent",
    "EnergyActive", "EnergyReactive", "EnergyApparent",
    "PowerFactor", "Frequency",
    # Ambientais
    "Temperature", "Humidity", "CaseTemperature",
    # Vibração
    "Axial", "Radial"
]

# Variáveis com histórico habilitado
HISTORIZED_VARIABLES = [
    "VoltageA", "VoltageB", "VoltageC",
    "CurrentA", "CurrentB", "CurrentC",
    "PowerActive", "PowerReactive", "PowerApparent",
    "EnergyActive", "EnergyReactive", "EnergyApparent",
    "PowerFactor", "Frequency",
    "CaseTemperature"
]
