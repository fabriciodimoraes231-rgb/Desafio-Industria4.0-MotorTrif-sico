"""
Validadores de dados dos sensores.

Este modulo define os modelos Pydantic para validacao dos dados
recebidos dos sensores do motor trifasico via MQTT.

Os validadores garantem que os dados estejam dentro dos limites
fisicamente plaussiveis antes de serem processados pelo sistema.

Classes:
    VoltageData: Validador de tensao trifasica (0-500V)
    CurrentData: Validador de corrente trifasica (0-200A)
    PowerData: Validador de potencia
    EnergyData: Validador de energia acumulada
    ElectricalReading: Leitura completa do sensor eletrico
    EnvironmentReading: Leitura do sensor ambiental
    VibrationReading: Leitura do sensor de vibracao

Functions:
    validate_electrical: Valida dados do sensor eletrico
    validate_environment: Valida dados do sensor ambiental
    validate_vibration: Valida dados do sensor de vibracao
    get_validator_for_topic: Retorna o validador apropriado para um topico
"""

from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
import logging

logger = logging.getLogger(__name__)


class VoltageData(BaseModel):
    """
    Validador de tensao trifasica.
    
    Valida que as tensoes estejam entre 0 e 500 Volts.
    
    Attributes:
        a: Tensao da fase A (0-500V)
        b: Tensao da fase B (0-500V)
        c: Tensao da fase C (0-500V)
    """
    a: float = Field(..., ge=0, le=500)
    b: float = Field(..., ge=0, le=500)
    c: float = Field(..., ge=0, le=500)


class CurrentData(BaseModel):
    """
    Validador de corrente trifasica.
    
    Valida que as correntes estejam entre 0 e 200 Amperes.
    
    Attributes:
        a: Corrente da fase A (0-200A)
        b: Corrente da fase B (0-200A)
        c: Corrente da fase C (0-200A)
    """
    a: float = Field(..., ge=0, le=200)
    b: float = Field(..., ge=0, le=200)
    c: float = Field(..., ge=0, le=200)


class PowerData(BaseModel):
    """
    Validador de dados de potencia.
    
    Attributes:
        active: Potencia ativa em Watts (>= 0)
        reactive: Potencia reativa em VAr (pode ser negativa)
        apparent: Potencia aparente em VA (>= 0)
    """
    active: float = Field(..., ge=0)
    reactive: float
    apparent: float = Field(..., ge=0)


class EnergyData(BaseModel):
    """
    Validador de dados de energia acumulada.
    
    Attributes:
        active: Energia ativa em Wh (>= 0)
        reactive: Energia reativa em VArh (>= 0)
        apparent: Energia aparente em VAh (>= 0)
    """
    active: float = Field(..., ge=0)
    reactive: float = Field(..., ge=0)
    apparent: float = Field(..., ge=0)


class ElectricalReading(BaseModel):
    """
    Leitura completa do sensor eletrico.
    
    Modelo para validacao de uma leitura completa do sensor
    de parametros eletricos do motor.
    
    Attributes:
        timestamp: Data/hora da leitura
        voltage: Tensoes trifasicas
        current: Correntes trifasicas
        power: Potencias (ativa, reativa, aparente)
        energy: Energias acumuladas
        powerFactor: Fator de potencia (0-1)
        frequency: Frequencia em Hz (0-100)
    """
    timestamp: datetime
    voltage: VoltageData
    current: CurrentData
    power: PowerData
    energy: EnergyData
    powerFactor: float = Field(..., ge=0, le=1, alias="powerFactor")
    frequency: float = Field(..., ge=0, le=100)
    
    model_config = ConfigDict(populate_by_name=True)


class EnvironmentReading(BaseModel):
    """
    Leitura do sensor ambiental.
    
    Modelo para validacao de dados de temperatura e umidade.
    
    Attributes:
        timestamp: Data/hora da leitura
        temperature: Temperatura ambiente (-40 a 100C)
        humidity: Umidade relativa (0-100%)
        caseTemperature: Temperatura da carcaca (-40 a 150C)
    """
    timestamp: datetime
    temperature: float = Field(..., ge=-40, le=100)
    humidity: float = Field(..., ge=0, le=100)
    caseTemperature: float = Field(..., ge=-40, le=150, alias="caseTemperature")
    
    model_config = ConfigDict(populate_by_name=True)


class VibrationReading(BaseModel):
    """
    Leitura do sensor de vibracao.
    
    Modelo para validacao de dados de vibracao do motor.
    
    Attributes:
        timestamp: Data/hora da leitura
        axial: Vibracao no eixo axial (0-100 mm/s)
        radial: Vibracao no eixo radial (0-100 mm/s)
    """
    timestamp: datetime
    axial: float = Field(..., ge=0, le=100)
    radial: float = Field(..., ge=0, le=100)


def validate_electrical(data: dict[str, Any]) -> Optional[ElectricalReading]:
    """
    Valida dados do sensor eletrico.
    
    Args:
        data: Dicionario com os dados brutos do sensor
        
    Returns:
        ElectricalReading se valido, None caso contrario
    """
    try:
        return ElectricalReading(**data)
    except Exception as e:
        logger.error(f"Erro ao validar dados eletricos: {e}")
        logger.debug(f"Dados recebidos: {data}")
        return None


def validate_environment(data: dict[str, Any]) -> Optional[EnvironmentReading]:
    """
    Valida dados do sensor ambiental.
    
    Args:
        data: Dicionario com os dados brutos do sensor
        
    Returns:
        EnvironmentReading se valido, None caso contrario
    """
    try:
        return EnvironmentReading(**data)
    except Exception as e:
        logger.error(f"Erro ao validar dados ambientais: {e}")
        logger.debug(f"Dados recebidos: {data}")
        return None


def validate_vibration(data: dict[str, Any]) -> Optional[VibrationReading]:
    """
    Valida dados do sensor de vibracao.
    
    Args:
        data: Dicionario com os dados brutos do sensor
        
    Returns:
        VibrationReading se valido, None caso contrario
    """
    try:
        return VibrationReading(**data)
    except Exception as e:
        logger.error(f"Erro ao validar dados de vibracao: {e}")
        logger.debug(f"Dados recebidos: {data}")
        return None


def get_validator_for_topic(topic: str):
    """
    Retorna o validador apropriado para um topico MQTT.
    
    Mapeia topicos MQTT para suas funcoes de validacao correspondentes.
    
    Args:
        topic: Nome do topico MQTT
        
    Returns:
        Funcao de validacao para o topico
        
    Raises:
        ValueError: Se o topico nao for reconhecido
        
    Example:
        >>> validator = get_validator_for_topic("scgdi/motor/electrical")
        >>> reading = validator(data)
    """
    validators = {
        "scgdi/motor/electrical": validate_electrical,
        "scgdi/motor/environment": validate_environment,
        "scgdi/motor/vibration": validate_vibration,
    }
    
    if topic not in validators:
        raise ValueError(f"Topico desconhecido: {topic}")
    
    return validators[topic]
