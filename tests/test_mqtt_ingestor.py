"""
Testes unitários para o serviço de ingestão MQTT.

Este módulo contém testes para validadores, cliente MQTT
e publisher RabbitMQ.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'mqtt_ingestor'))

from validators import (
    validate_electrical,
    validate_environment,
    validate_vibration,
    get_validator_for_topic,
    ElectricalReading,
    EnvironmentReading,
    VibrationReading
)


class TestValidators:
    """Testes para os validadores de dados."""
    
    def test_validate_electrical_valid(self):
        """Testa validação de dados elétricos válidos."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "voltage": {"a": 220.0, "b": 221.1, "c": 219.5},
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        result = validate_electrical(data)
        
        assert result is not None
        assert isinstance(result, ElectricalReading)
        assert result.voltage.a == 220.0
        assert result.current.a == 10.5
        assert result.powerFactor == 0.95
        
    def test_validate_electrical_invalid_voltage(self):
        """Testa rejeição de tensão inválida."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "voltage": {"a": 600.0, "b": 221.1, "c": 219.5},  # Tensão acima do limite
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        result = validate_electrical(data)
        assert result is None
        
    def test_validate_electrical_missing_field(self):
        """Testa rejeição com campo faltando."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "voltage": {"a": 220.0, "b": 221.1, "c": 219.5},
            # current faltando
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        result = validate_electrical(data)
        assert result is None
        
    def test_validate_environment_valid(self):
        """Testa validação de dados ambientais válidos."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "temperature": 34.5,
            "humidity": 55.2,
            "caseTemperature": 62.0
        }
        
        result = validate_environment(data)
        
        assert result is not None
        assert isinstance(result, EnvironmentReading)
        assert result.temperature == 34.5
        assert result.humidity == 55.2
        assert result.caseTemperature == 62.0
        
    def test_validate_environment_invalid_humidity(self):
        """Testa rejeição de umidade inválida."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "temperature": 34.5,
            "humidity": 150.0,  # Umidade acima de 100%
            "caseTemperature": 62.0
        }
        
        result = validate_environment(data)
        assert result is None
        
    def test_validate_vibration_valid(self):
        """Testa validação de dados de vibração válidos."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "axial": 0.12,
            "radial": 0.15
        }
        
        result = validate_vibration(data)
        
        assert result is not None
        assert isinstance(result, VibrationReading)
        assert result.axial == 0.12
        assert result.radial == 0.15
        
    def test_validate_vibration_negative_value(self):
        """Testa rejeição de vibração negativa."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "axial": -0.12,  # Valor negativo inválido
            "radial": 0.15
        }
        
        result = validate_vibration(data)
        assert result is None
        
    def test_get_validator_for_topic_electrical(self):
        """Testa obtenção de validador para tópico elétrico."""
        validator = get_validator_for_topic("scgdi/motor/electrical")
        assert validator == validate_electrical
        
    def test_get_validator_for_topic_environment(self):
        """Testa obtenção de validador para tópico ambiental."""
        validator = get_validator_for_topic("scgdi/motor/environment")
        assert validator == validate_environment
        
    def test_get_validator_for_topic_vibration(self):
        """Testa obtenção de validador para tópico de vibração."""
        validator = get_validator_for_topic("scgdi/motor/vibration")
        assert validator == validate_vibration
        
    def test_get_validator_for_topic_unknown(self):
        """Testa exceção para tópico desconhecido."""
        with pytest.raises(ValueError):
            get_validator_for_topic("scgdi/motor/unknown")


class TestElectricalReading:
    """Testes para o modelo ElectricalReading."""
    
    def test_power_factor_range(self):
        """Testa que fator de potência deve estar entre 0 e 1."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "voltage": {"a": 220.0, "b": 221.1, "c": 219.5},
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 1.5,  # Inválido: > 1
            "frequency": 60.0
        }
        
        result = validate_electrical(data)
        assert result is None
        
    def test_frequency_range(self):
        """Testa que frequência deve estar em range válido."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "voltage": {"a": 220.0, "b": 221.1, "c": 219.5},
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 150.0  # Inválido: muito alto
        }
        
        result = validate_electrical(data)
        assert result is None


class TestEnvironmentReading:
    """Testes para o modelo EnvironmentReading."""
    
    def test_temperature_range(self):
        """Testa range de temperatura."""
        # Temperatura muito baixa
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "temperature": -50.0,  # Abaixo do mínimo
            "humidity": 55.2,
            "caseTemperature": 62.0
        }
        result = validate_environment(data)
        assert result is None
        
    def test_case_temperature_high(self):
        """Testa temperatura da carcaça alta (válido mas alarmante)."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "temperature": 34.5,
            "humidity": 55.2,
            "caseTemperature": 80.0  # Alto mas válido
        }
        result = validate_environment(data)
        assert result is not None
        assert result.caseTemperature == 80.0


class TestVibrationReading:
    """Testes para o modelo VibrationReading."""
    
    def test_vibration_high_value(self):
        """Testa vibração alta (válida mas alarmante)."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "axial": 50.0,  # Alto mas dentro do range
            "radial": 50.0
        }
        result = validate_vibration(data)
        assert result is not None
        
    def test_vibration_too_high(self):
        """Testa rejeição de vibração acima do limite."""
        data = {
            "timestamp": "2025-08-08T12:00:00Z",
            "axial": 150.0,  # Acima do limite de 100
            "radial": 0.15
        }
        result = validate_vibration(data)
        assert result is None
