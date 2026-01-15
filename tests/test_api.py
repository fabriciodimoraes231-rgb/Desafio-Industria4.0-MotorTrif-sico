"""
Testes unitários para a API FastAPI.

Este módulo contém testes para os endpoints da API REST.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
import asyncio

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'api_service'))

from fastapi.testclient import TestClient
from schemas import (
    AVAILABLE_VARIABLES,
    HISTORIZED_VARIABLES,
    MotorLatestResponse,
    HistoryResponse,
    AlarmsListResponse
)


# Mock do serviço de dados para testes
class MockDataService:
    """Serviço de dados mock para testes."""
    
    def __init__(self):
        self._db = MagicMock()
        self._rabbitmq_conn = MagicMock()
        
    async def get_latest(self):
        return {
            "timestamp": datetime.utcnow(),
            "electrical": {
                "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
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
        
    async def get_history(self, variable, start_time, end_time, limit):
        return {
            "variable": variable,
            "start_time": start_time or datetime.utcnow() - timedelta(hours=24),
            "end_time": end_time or datetime.utcnow(),
            "count": 2,
            "data": [
                {"timestamp": datetime.utcnow().isoformat(), "value": 220.5, "quality": "Good"},
                {"timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat(), "value": 220.3, "quality": "Good"}
            ]
        }
        
    async def get_alarms(self, start_time, end_time, category, active_only, limit):
        return {
            "active_count": 1,
            "total_count": 2,
            "alarms": [
                {
                    "id": "test_alarm_1",
                    "timestamp": datetime.utcnow().isoformat(),
                    "category": "Electrical",
                    "severity": 700,
                    "severity_name": "HIGH",
                    "message": "Overvoltage detected",
                    "source_name": "VoltageA",
                    "value": 250.0,
                    "acknowledged": False
                }
            ]
        }
        
    async def get_statistics(self, variable, hours):
        return {
            "variable": variable,
            "period_hours": hours,
            "min": 218.0,
            "max": 222.0,
            "avg": 220.1,
            "count": 1000
        }
        
    async def acknowledge_alarm(self, alarm_id):
        return True


class TestSchemas:
    """Testes para os schemas da API."""
    
    def test_available_variables(self):
        """Testa lista de variáveis disponíveis."""
        assert "VoltageA" in AVAILABLE_VARIABLES
        assert "VoltageB" in AVAILABLE_VARIABLES
        assert "VoltageC" in AVAILABLE_VARIABLES
        assert "CurrentA" in AVAILABLE_VARIABLES
        assert "CaseTemperature" in AVAILABLE_VARIABLES
        assert "Axial" in AVAILABLE_VARIABLES
        
    def test_historized_variables(self):
        """Testa lista de variáveis com histórico."""
        # Elétricas devem ter histórico
        assert "VoltageA" in HISTORIZED_VARIABLES
        assert "CurrentA" in HISTORIZED_VARIABLES
        assert "PowerActive" in HISTORIZED_VARIABLES
        
        # CaseTemperature deve ter histórico
        assert "CaseTemperature" in HISTORIZED_VARIABLES
        
        # Temperature e Humidity não devem ter histórico
        assert "Temperature" not in HISTORIZED_VARIABLES
        assert "Humidity" not in HISTORIZED_VARIABLES
        
    def test_historized_is_subset_of_available(self):
        """Testa que variáveis com histórico são subconjunto das disponíveis."""
        for var in HISTORIZED_VARIABLES:
            assert var in AVAILABLE_VARIABLES


class TestMotorLatestResponse:
    """Testes para o modelo MotorLatestResponse."""
    
    def test_create_response(self):
        """Testa criação de resposta."""
        data = {
            "timestamp": datetime.utcnow(),
            "electrical": {
                "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
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
        
        # Deve ser possível criar resposta com dados válidos
        response = MotorLatestResponse(**data)
        
        assert response.electrical.voltage.a == 220.0
        assert response.environment.case_temperature == 45.0
        assert response.vibration.axial == 0.12


class TestHistoryResponse:
    """Testes para o modelo HistoryResponse."""
    
    def test_create_response(self):
        """Testa criação de resposta de histórico."""
        data = {
            "variable": "VoltageA",
            "start_time": datetime.utcnow() - timedelta(hours=24),
            "end_time": datetime.utcnow(),
            "count": 100,
            "data": [
                {"timestamp": datetime.utcnow(), "value": 220.5, "quality": "Good"}
            ]
        }
        
        response = HistoryResponse(**data)
        
        assert response.variable == "VoltageA"
        assert response.count == 100
        assert len(response.data) == 1


class TestAlarmsListResponse:
    """Testes para o modelo AlarmsListResponse."""
    
    def test_create_response(self):
        """Testa criação de resposta de alarmes."""
        data = {
            "active_count": 2,
            "total_count": 10,
            "alarms": [
                {
                    "id": "alarm_1",
                    "timestamp": datetime.utcnow(),
                    "category": "Electrical",
                    "severity": 700,
                    "severity_name": "HIGH",
                    "message": "Test alarm",
                    "source_name": "VoltageA",
                    "value": 250.0,
                    "acknowledged": False
                }
            ]
        }
        
        response = AlarmsListResponse(**data)
        
        assert response.active_count == 2
        assert response.total_count == 10
        assert len(response.alarms) == 1


class TestAPIRoutes:
    """Testes para as rotas da API."""
    
    @pytest.fixture
    def mock_service(self):
        """Cria serviço mock."""
        return MockDataService()
        
    def test_variables_endpoint_structure(self):
        """Testa estrutura do endpoint de variáveis."""
        # O endpoint deve retornar estrutura esperada
        expected_categories = ["electrical", "environment", "vibration"]
        
        # Verificar que variáveis estão nas categorias certas
        electrical_vars = [v for v in AVAILABLE_VARIABLES 
                         if v.startswith(("Voltage", "Current", "Power", "Energy", "Frequency"))]
        assert len(electrical_vars) > 0
        
        environment_vars = ["Temperature", "Humidity", "CaseTemperature"]
        for var in environment_vars:
            assert var in AVAILABLE_VARIABLES
            
        vibration_vars = ["Axial", "Radial"]
        for var in vibration_vars:
            assert var in AVAILABLE_VARIABLES


class TestDataValidation:
    """Testes para validação de dados da API."""
    
    def test_voltage_response_validation(self):
        """Testa validação de resposta de tensão."""
        from schemas import VoltageResponse
        
        # Valores válidos
        voltage = VoltageResponse(a=220.0, b=221.0, c=219.0)
        assert voltage.a == 220.0
        
    def test_current_response_validation(self):
        """Testa validação de resposta de corrente."""
        from schemas import CurrentResponse
        
        current = CurrentResponse(a=10.5, b=10.4, c=10.6)
        assert current.a == 10.5
        
    def test_power_response_validation(self):
        """Testa validação de resposta de potência."""
        from schemas import PowerResponse
        
        power = PowerResponse(active=4500, reactive=500, apparent=4600)
        assert power.active == 4500
        
    def test_energy_response_validation(self):
        """Testa validação de resposta de energia."""
        from schemas import EnergyResponse
        
        energy = EnergyResponse(active=10000, reactive=1200, apparent=10200)
        assert energy.active == 10000
        
    def test_environment_response_validation(self):
        """Testa validação de resposta ambiental."""
        from schemas import EnvironmentResponse
        
        env = EnvironmentResponse(
            temperature=34.5,
            humidity=55.2,
            case_temperature=45.0
        )
        assert env.temperature == 34.5
        assert env.case_temperature == 45.0
        
    def test_vibration_response_validation(self):
        """Testa validação de resposta de vibração."""
        from schemas import VibrationResponse
        
        vib = VibrationResponse(axial=0.12, radial=0.15)
        assert vib.axial == 0.12


class TestHealthResponse:
    """Testes para resposta de health check."""
    
    def test_health_response_structure(self):
        """Testa estrutura de resposta de saúde."""
        from schemas import HealthResponse
        
        response = HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            services={
                "database": "connected",
                "rabbitmq": "connected",
                "opcua": "connected"
            }
        )
        
        assert response.status == "healthy"
        assert "database" in response.services
        
    def test_health_response_degraded(self):
        """Testa resposta degradada."""
        from schemas import HealthResponse
        
        response = HealthResponse(
            status="degraded",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            services={
                "database": "connected",
                "rabbitmq": "not_connected",
                "opcua": "connected"
            }
        )
        
        assert response.status == "degraded"
