"""
Schemas Pydantic para a API REST.

Este modulo define todos os modelos de dados utilizados pela API REST
do Motor 50CV. Os schemas sao utilizados para validacao de entrada,
serializacao de saida e geracao automatica de documentacao OpenAPI.

Classes:
    VoltageResponse: Modelo de tensao trifasica
    CurrentResponse: Modelo de corrente trifasica
    PowerResponse: Modelo de potencia (ativa, reativa, aparente)
    EnergyResponse: Modelo de energia acumulada
    ElectricalResponse: Dados eletricos completos do motor
    EnvironmentResponse: Dados ambientais (temperatura, umidade)
    VibrationResponse: Dados de vibracao do motor
    MotorLatestResponse: Estado completo atual do motor
    HistoryDataPoint: Ponto de dado historico individual
    HistoryResponse: Resposta de consulta de historico
    HistoryStatisticsResponse: Estatisticas de uma variavel
    AlarmResponse: Dados de um alarme individual
    AlarmsListResponse: Lista de alarmes
    HealthResponse: Resposta do health check

Constants:
    AVAILABLE_VARIABLES: Lista de todas as variaveis disponiveis
    HISTORIZED_VARIABLES: Lista de variaveis com historico habilitado
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class VoltageResponse(BaseModel):
    """
    Modelo de tensao trifasica.
    
    Representa as tensoes das tres fases do motor em Volts.
    
    Attributes:
        a: Tensao da fase A em Volts
        b: Tensao da fase B em Volts
        c: Tensao da fase C em Volts
    """
    a: float
    b: float
    c: float


class CurrentResponse(BaseModel):
    """
    Modelo de corrente trifasica.
    
    Representa as correntes das tres fases do motor em Amperes.
    
    Attributes:
        a: Corrente da fase A em Amperes
        b: Corrente da fase B em Amperes
        c: Corrente da fase C em Amperes
    """
    a: float
    b: float
    c: float


class PowerResponse(BaseModel):
    """
    Modelo de potencia.
    
    Representa as potencias ativa, reativa e aparente do motor.
    
    Attributes:
        active: Potencia ativa em Watts (W)
        reactive: Potencia reativa em Volt-Amperes reativos (VAr)
        apparent: Potencia aparente em Volt-Amperes (VA)
    """
    active: float
    reactive: float
    apparent: float


class EnergyResponse(BaseModel):
    """
    Modelo de energia acumulada.
    
    Representa as energias ativa, reativa e aparente acumuladas.
    
    Attributes:
        active: Energia ativa acumulada em Watt-hora (Wh)
        reactive: Energia reativa acumulada em Volt-Ampere-hora reativo (VArh)
        apparent: Energia aparente acumulada em Volt-Ampere-hora (VAh)
    """
    active: float
    reactive: float
    apparent: float


class ElectricalResponse(BaseModel):
    """
    Dados eletricos completos do motor.
    
    Agrupa todos os parametros eletricos do motor em uma estrutura unica.
    
    Attributes:
        voltage: Tensoes trifasicas (V)
        current: Correntes trifasicas (A)
        power: Potencias (W, VAr, VA)
        energy: Energias acumuladas (Wh, VArh, VAh)
        power_factor: Fator de potencia (0 a 1)
        frequency: Frequencia da rede em Hertz (Hz)
    """
    voltage: VoltageResponse
    current: CurrentResponse
    power: PowerResponse
    energy: EnergyResponse
    power_factor: float = Field(..., alias="powerFactor")
    frequency: float
    
    class Config:
        populate_by_name = True


class EnvironmentResponse(BaseModel):
    """
    Dados ambientais.
    
    Representa as medicoes de temperatura e umidade do ambiente
    e temperatura da carcaca do motor.
    
    Attributes:
        temperature: Temperatura ambiente em graus Celsius
        humidity: Umidade relativa do ar em porcentagem (%)
        case_temperature: Temperatura da carcaca do motor em graus Celsius
    """
    temperature: float
    humidity: float
    case_temperature: float = Field(..., alias="caseTemperature")
    
    class Config:
        populate_by_name = True


class VibrationResponse(BaseModel):
    """
    Dados de vibracao do motor.
    
    Representa as medicoes de vibracao nos eixos axial e radial.
    
    Attributes:
        axial: Vibracao no eixo axial em mm/s
        radial: Vibracao no eixo radial em mm/s
    """
    axial: float
    radial: float


# ============== Modelo de Estado Completo ==============

class MotorLatestResponse(BaseModel):
    """
    Estado completo atual do motor.
    
    Agrega todas as medicoes atuais do motor em uma unica resposta,
    incluindo dados eletricos, ambientais, de vibracao e alarmes.
    
    Attributes:
        timestamp: Data/hora da ultima atualizacao
        electrical: Dados eletricos completos
        environment: Dados ambientais
        vibration: Dados de vibracao
        active_alarms: Numero de alarmes ativos
    """
    timestamp: datetime
    electrical: ElectricalResponse
    environment: EnvironmentResponse
    vibration: VibrationResponse
    active_alarms: int


class HistoryDataPoint(BaseModel):
    """
    Ponto de dado historico individual.
    
    Representa um unico ponto de dado no historico de uma variavel.
    
    Attributes:
        timestamp: Data/hora do registro (formato ISO 8601)
        value: Valor numerico da variavel
        quality: Qualidade do dado (Good, Bad, Uncertain)
    """
    timestamp: str
    value: float
    quality: str = "Good"


class HistoryResponse(BaseModel):
    """
    Resposta de consulta de historico.
    
    Retorna o historico de uma variavel em um periodo de tempo.
    
    Attributes:
        variable: Nome da variavel consultada
        start_time: Inicio do periodo consultado
        end_time: Fim do periodo consultado
        count: Numero de pontos retornados
        data: Lista de pontos de dados historicos
    """
    variable: str
    start_time: datetime
    end_time: datetime
    count: int
    data: List[HistoryDataPoint]


class HistoryStatisticsResponse(BaseModel):
    """
    Estatisticas de uma variavel.
    
    Retorna estatisticas agregadas (minimo, maximo, media) de uma
    variavel em um determinado periodo.
    
    Attributes:
        variable: Nome da variavel
        period_hours: Periodo em horas para o calculo
        min: Valor minimo no periodo
        max: Valor maximo no periodo
        avg: Valor medio no periodo
        count: Numero de amostras no periodo
    """
    variable: str
    period_hours: int
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    count: int


class AlarmResponse(BaseModel):
    """
    Dados de um alarme individual.
    
    Representa um alarme gerado pelo sistema de monitoramento.
    
    Attributes:
        id: Identificador unico do alarme
        timestamp: Data/hora da ocorrencia
        category: Categoria do alarme (Electrical, Environment, Vibration)
        severity: Nivel de severidade numerico (100-900)
        severity_name: Nome do nivel (INFORMATIVE, LOW, MEDIUM, HIGH, CRITICAL)
        message: Mensagem descritiva do alarme
        source_name: Nome da variavel que gerou o alarme
        value: Valor que disparou o alarme
        acknowledged: Se o alarme foi reconhecido
    """
    id: str
    timestamp: datetime
    category: str
    severity: int
    severity_name: str
    message: str
    source_name: str
    value: float
    acknowledged: bool


class AlarmsListResponse(BaseModel):
    """
    Lista de alarmes.
    
    Retorna uma lista de alarmes com contadores de ativos e total.
    
    Attributes:
        active_count: Numero de alarmes ativos (nao reconhecidos)
        total_count: Numero total de alarmes retornados
        alarms: Lista de alarmes
    """
    active_count: int
    total_count: int
    alarms: List[AlarmResponse]


class HealthResponse(BaseModel):
    """
    Resposta do health check.
    
    Indica o estado de saude da API e seus servicos dependentes.
    
    Attributes:
        status: Status geral (healthy, degraded, unhealthy)
        timestamp: Data/hora da verificacao
        version: Versao da API
        services: Status de cada servico dependente
    """
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]


# ============== Constantes ==============

AVAILABLE_VARIABLES = [
    "VoltageA", "VoltageB", "VoltageC",
    "CurrentA", "CurrentB", "CurrentC",
    "PowerActive", "PowerReactive", "PowerApparent",
    "EnergyActive", "EnergyReactive", "EnergyApparent",
    "PowerFactor", "Frequency",
    "Temperature", "Humidity", "CaseTemperature",
    "Axial", "Radial"
]
"""Lista de todas as variaveis disponiveis para consulta."""

HISTORIZED_VARIABLES = [
    "VoltageA", "VoltageB", "VoltageC",
    "CurrentA", "CurrentB", "CurrentC",
    "PowerActive", "PowerReactive", "PowerApparent",
    "EnergyActive", "EnergyReactive", "EnergyApparent",
    "PowerFactor", "Frequency",
    "CaseTemperature"
]
"""Lista de variaveis que possuem historico habilitado."""
