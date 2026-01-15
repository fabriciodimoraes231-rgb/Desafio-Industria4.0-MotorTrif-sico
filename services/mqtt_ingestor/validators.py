"""
Validadores de dados dos sensores.

Este módulo contém funções para validar os dados recebidos dos sensores
do motor trifásico, garantindo integridade e formato correto antes
de enviar para o RabbitMQ.
"""

from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import logging

logger = logging.getLogger(__name__)


class VoltageData(BaseModel):
    """Modelo para dados de tensão trifásica."""
    a: float = Field(..., ge=0, le=500, description="Tensão fase A (V)")
    b: float = Field(..., ge=0, le=500, description="Tensão fase B (V)")
    c: float = Field(..., ge=0, le=500, description="Tensão fase C (V)")


class CurrentData(BaseModel):
    """Modelo para dados de corrente trifásica."""
    a: float = Field(..., ge=0, le=200, description="Corrente fase A (A)")
    b: float = Field(..., ge=0, le=200, description="Corrente fase B (A)")
    c: float = Field(..., ge=0, le=200, description="Corrente fase C (A)")


class PowerData(BaseModel):
    """Modelo para dados de potência."""
    active: float = Field(..., ge=0, description="Potência ativa (W)")
    reactive: float = Field(..., ge=0, description="Potência reativa (VAr)")
    apparent: float = Field(..., ge=0, description="Potência aparente (VA)")


class EnergyData(BaseModel):
    """Modelo para dados de energia."""
    active: float = Field(..., ge=0, description="Energia ativa (Wh)")
    reactive: float = Field(..., ge=0, description="Energia reativa (VArh)")
    apparent: float = Field(..., ge=0, description="Energia aparente (VAh)")


class ElectricalReading(BaseModel):
    """
    Modelo para leitura do sensor elétrico.
    
    Contém todas as variáveis elétricas do motor trifásico:
    tensão, corrente, potência, energia, fator de potência e frequência.
    """
    timestamp: datetime
    voltage: VoltageData
    current: CurrentData
    power: PowerData
    energy: EnergyData
    powerFactor: float = Field(..., ge=0, le=1, alias="powerFactor")
    frequency: float = Field(..., ge=0, le=100)
    
    class Config:
        """Configuração do modelo."""
        populate_by_name = True


class EnvironmentReading(BaseModel):
    """
    Modelo para leitura do sensor ambiental.
    
    Contém temperatura ambiente, umidade e temperatura da carcaça do motor.
    """
    timestamp: datetime
    temperature: float = Field(..., ge=-40, le=100, description="Temperatura ambiente (°C)")
    humidity: float = Field(..., ge=0, le=100, description="Umidade relativa (%)")
    caseTemperature: float = Field(..., ge=-40, le=150, alias="caseTemperature", description="Temperatura da carcaça (°C)")
    
    class Config:
        """Configuração do modelo."""
        populate_by_name = True


class VibrationReading(BaseModel):
    """
    Modelo para leitura do sensor de vibração.
    
    Contém medições de vibração axial e radial do motor.
    """
    timestamp: datetime
    axial: float = Field(..., ge=0, le=100, description="Vibração axial (mm/s)")
    radial: float = Field(..., ge=0, le=100, description="Vibração radial (mm/s)")


def validate_electrical(data: dict[str, Any]) -> Optional[ElectricalReading]:
    """
    Valida dados do sensor elétrico.
    
    Args:
        data: Dicionário com os dados recebidos do sensor elétrico
        
    Returns:
        ElectricalReading se válido, None caso contrário
        
    Example:
        >>> data = {
        ...     "timestamp": "2025-08-08T12:00:00Z",
        ...     "voltage": {"a": 220.0, "b": 221.1, "c": 219.5},
        ...     "current": {"a": 10.5, "b": 10.4, "c": 10.6},
        ...     "power": {"active": 4500, "reactive": 500, "apparent": 4600},
        ...     "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
        ...     "powerFactor": 0.95,
        ...     "frequency": 60.0
        ... }
        >>> result = validate_electrical(data)
        >>> result is not None
        True
    """
    try:
        return ElectricalReading(**data)
    except Exception as e:
        logger.error(f"Erro ao validar dados elétricos: {e}")
        logger.debug(f"Dados recebidos: {data}")
        return None


def validate_environment(data: dict[str, Any]) -> Optional[EnvironmentReading]:
    """
    Valida dados do sensor ambiental.
    
    Args:
        data: Dicionário com os dados recebidos do sensor ambiental
        
    Returns:
        EnvironmentReading se válido, None caso contrário
        
    Example:
        >>> data = {
        ...     "timestamp": "2025-08-08T12:00:00Z",
        ...     "temperature": 34.5,
        ...     "humidity": 55.2,
        ...     "caseTemperature": 62.0
        ... }
        >>> result = validate_environment(data)
        >>> result is not None
        True
    """
    try:
        return EnvironmentReading(**data)
    except Exception as e:
        logger.error(f"Erro ao validar dados ambientais: {e}")
        logger.debug(f"Dados recebidos: {data}")
        return None


def validate_vibration(data: dict[str, Any]) -> Optional[VibrationReading]:
    """
    Valida dados do sensor de vibração.
    
    Args:
        data: Dicionário com os dados recebidos do sensor de vibração
        
    Returns:
        VibrationReading se válido, None caso contrário
        
    Example:
        >>> data = {
        ...     "timestamp": "2025-08-08T12:00:00Z",
        ...     "axial": 0.12,
        ...     "radial": 0.15
        ... }
        >>> result = validate_vibration(data)
        >>> result is not None
        True
    """
    try:
        return VibrationReading(**data)
    except Exception as e:
        logger.error(f"Erro ao validar dados de vibração: {e}")
        logger.debug(f"Dados recebidos: {data}")
        return None


def get_validator_for_topic(topic: str):
    """
    Retorna o validador apropriado para um tópico MQTT.
    
    Args:
        topic: Nome do tópico MQTT
        
    Returns:
        Função validadora correspondente ao tópico
        
    Raises:
        ValueError: Se o tópico não for reconhecido
    """
    validators = {
        "scgdi/motor/electrical": validate_electrical,
        "scgdi/motor/environment": validate_environment,
        "scgdi/motor/vibration": validate_vibration,
    }
    
    if topic not in validators:
        raise ValueError(f"Tópico desconhecido: {topic}")
    
    return validators[topic]
