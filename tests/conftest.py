"""
Configuração do pytest para os testes do Motor50CV.

Este módulo contém fixtures e configurações compartilhadas.
"""

import pytest
import sys
import os
from datetime import datetime

# Adicionar paths dos serviços ao PYTHONPATH
SERVICES_PATH = os.path.join(os.path.dirname(__file__), '..', 'services')
sys.path.insert(0, os.path.join(SERVICES_PATH, 'mqtt_ingestor'))
sys.path.insert(0, os.path.join(SERVICES_PATH, 'opcua_server'))
sys.path.insert(0, os.path.join(SERVICES_PATH, 'api_service'))


@pytest.fixture
def sample_electrical_data():
    """Dados elétricos de exemplo para testes."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
        "current": {"a": 10.5, "b": 10.4, "c": 10.6},
        "power": {"active": 4500, "reactive": 500, "apparent": 4600},
        "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
        "powerFactor": 0.95,
        "frequency": 60.0
    }


@pytest.fixture
def sample_environment_data():
    """Dados ambientais de exemplo para testes."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "temperature": 34.5,
        "humidity": 55.2,
        "caseTemperature": 45.0
    }


@pytest.fixture
def sample_vibration_data():
    """Dados de vibração de exemplo para testes."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "axial": 0.12,
        "radial": 0.15
    }


@pytest.fixture
def overvoltage_electrical_data():
    """Dados elétricos com sobretensão para testes."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "voltage": {"a": 250.0, "b": 221.0, "c": 219.0},  # Fase A com sobretensão
        "current": {"a": 10.5, "b": 10.4, "c": 10.6},
        "power": {"active": 4500, "reactive": 500, "apparent": 4600},
        "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
        "powerFactor": 0.95,
        "frequency": 60.0
    }


@pytest.fixture
def critical_temperature_environment_data():
    """Dados ambientais com temperatura crítica para testes."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "temperature": 34.5,
        "humidity": 55.2,
        "caseTemperature": 75.0  # Temperatura crítica >60°C
    }


@pytest.fixture
def mqtt_topics():
    """Tópicos MQTT configurados."""
    return {
        "electrical": "motor50cv/electrical",
        "environment": "motor50cv/environment",
        "vibration": "motor50cv/vibration"
    }
