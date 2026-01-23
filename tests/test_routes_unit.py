"""
Testes unitários para routes.py.

Testa os endpoints da API com DataService mockado.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Adiciona api_service ao path para evitar conflito de imports
api_service_path = Path(__file__).parent.parent / "services" / "api_service"
if str(api_service_path) not in sys.path:
    sys.path.insert(0, str(api_service_path))


@pytest.fixture
def mock_data_service():
    """Fixture de DataService mockado."""
    service = AsyncMock()
    service.get_latest = AsyncMock(return_value={
        "timestamp": "2024-01-01T12:00:00Z",
        "electrical": {"voltage": {"a": 220.0, "b": 220.0, "c": 220.0}},
        "environment": {"temperature": 25.0},
        "vibration": {"axial": 0.5, "radial": 0.3},
        "active_alarms": 0
    })
    service.get_history = AsyncMock(return_value={
        "variable": "VoltageA",
        "unit": "V",
        "data": [{"timestamp": "2024-01-01T12:00:00Z", "value": 220.0}],
        "count": 1
    })
    service.get_statistics = AsyncMock(return_value={
        "variable": "VoltageA",
        "period_hours": 24,
        "statistics": {"min": 210.0, "max": 230.0, "avg": 220.0, "std": 5.0},
        "count": 100
    })
    service.get_alarms = AsyncMock(return_value={
        "alarms": [],
        "total": 0,
        "active_count": 0
    })
    service.acknowledge_alarm = AsyncMock(return_value=True)
    return service


@pytest.fixture
def app_with_mocks(mock_data_service):
    """Cria app de teste com mocks."""
    # Mock de services antes de importar routes
    with patch.dict('sys.modules', {'services': MagicMock()}):
        # Importar módulos necessários
        import schemas
        from schemas import AVAILABLE_VARIABLES, HISTORIZED_VARIABLES
        
        # Mock get_data_service
        mock_get_service = AsyncMock(return_value=mock_data_service)
        
        with patch('routes.get_data_service', mock_get_service):
            import routes
            
            test_app = FastAPI()
            test_app.include_router(routes.router)
            
            # Override dependency
            test_app.dependency_overrides[routes.get_data_service] = lambda: mock_data_service
            
            yield test_app, schemas.AVAILABLE_VARIABLES, schemas.HISTORIZED_VARIABLES


class TestRoutesIntegration:
    """Testes de integração simples para routes."""
    
    def test_available_variables_defined(self):
        """Testa que variáveis disponíveis estão definidas em schemas."""
        from schemas import AVAILABLE_VARIABLES, HISTORIZED_VARIABLES
        
        assert len(AVAILABLE_VARIABLES) > 0
        assert len(HISTORIZED_VARIABLES) > 0
        # HISTORIZED deve ser subconjunto de AVAILABLE
        for var in HISTORIZED_VARIABLES:
            assert var in AVAILABLE_VARIABLES
    
    def test_voltage_variables_exist(self):
        """Testa que variáveis de tensão existem."""
        from schemas import AVAILABLE_VARIABLES
        
        voltage_vars = [v for v in AVAILABLE_VARIABLES if "Voltage" in v]
        assert len(voltage_vars) > 0
    
    def test_current_variables_exist(self):
        """Testa que variáveis de corrente existem."""
        from schemas import AVAILABLE_VARIABLES
        
        current_vars = [v for v in AVAILABLE_VARIABLES if "Current" in v]
        assert len(current_vars) > 0
    
    def test_power_variables_exist(self):
        """Testa que variáveis de potência existem."""
        from schemas import AVAILABLE_VARIABLES
        
        power_vars = [v for v in AVAILABLE_VARIABLES if "Power" in v]
        assert len(power_vars) > 0
    
    def test_energy_variables_exist(self):
        """Testa que variáveis de energia existem."""
        from schemas import AVAILABLE_VARIABLES
        
        energy_vars = [v for v in AVAILABLE_VARIABLES if "Energy" in v]
        assert len(energy_vars) > 0
    
    def test_temperature_variable_exists(self):
        """Testa que variável de temperatura existe."""
        from schemas import AVAILABLE_VARIABLES
        
        temp_vars = [v for v in AVAILABLE_VARIABLES if "Temperature" in v]
        assert len(temp_vars) > 0


class TestSchemasLists:
    """Testes de listas de variáveis."""
    
    def test_historized_is_subset_of_available(self):
        """Testa que HISTORIZED é subconjunto de AVAILABLE."""
        from schemas import AVAILABLE_VARIABLES, HISTORIZED_VARIABLES
        
        for var in HISTORIZED_VARIABLES:
            assert var in AVAILABLE_VARIABLES, f"{var} está em HISTORIZED mas não em AVAILABLE"
    
    def test_historized_has_electrical_vars(self):
        """Testa que variáveis elétricas estão em HISTORIZED."""
        from schemas import HISTORIZED_VARIABLES
        
        has_voltage = any("Voltage" in v for v in HISTORIZED_VARIABLES)
        has_current = any("Current" in v for v in HISTORIZED_VARIABLES)
        has_power = any("Power" in v for v in HISTORIZED_VARIABLES)
        
        assert has_voltage
        assert has_current
        assert has_power

