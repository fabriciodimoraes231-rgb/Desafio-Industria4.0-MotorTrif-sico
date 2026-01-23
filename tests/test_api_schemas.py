"""
Testes unitários para módulos da API service.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'api_service'))


class TestSchemasImport:
    """Testes de importação dos schemas."""

    def test_import_motor_latest_response(self):
        """Testa importação de MotorLatestResponse."""
        from schemas import MotorLatestResponse
        assert MotorLatestResponse is not None

    def test_import_history_response(self):
        """Testa importação de HistoryResponse."""
        from schemas import HistoryResponse
        assert HistoryResponse is not None

    def test_import_alarms_list_response(self):
        """Testa importação de AlarmsListResponse."""
        from schemas import AlarmsListResponse
        assert AlarmsListResponse is not None

    def test_import_available_variables(self):
        """Testa importação de AVAILABLE_VARIABLES."""
        from schemas import AVAILABLE_VARIABLES
        assert isinstance(AVAILABLE_VARIABLES, (list, tuple, set))

    def test_import_historized_variables(self):
        """Testa importação de HISTORIZED_VARIABLES."""
        from schemas import HISTORIZED_VARIABLES
        assert isinstance(HISTORIZED_VARIABLES, (list, tuple, set))


class TestAvailableVariables:
    """Testes das variáveis disponíveis."""

    def test_voltage_variables_available(self):
        """Testa que variáveis de tensão estão disponíveis."""
        from schemas import AVAILABLE_VARIABLES
        assert 'VoltageA' in AVAILABLE_VARIABLES
        assert 'VoltageB' in AVAILABLE_VARIABLES
        assert 'VoltageC' in AVAILABLE_VARIABLES

    def test_current_variables_available(self):
        """Testa que variáveis de corrente estão disponíveis."""
        from schemas import AVAILABLE_VARIABLES
        assert 'CurrentA' in AVAILABLE_VARIABLES
        assert 'CurrentB' in AVAILABLE_VARIABLES
        assert 'CurrentC' in AVAILABLE_VARIABLES

    def test_power_variables_available(self):
        """Testa que variáveis de potência estão disponíveis."""
        from schemas import AVAILABLE_VARIABLES
        assert 'PowerActive' in AVAILABLE_VARIABLES

    def test_environment_variables_available(self):
        """Testa que variáveis ambientais estão disponíveis."""
        from schemas import AVAILABLE_VARIABLES
        assert 'Temperature' in AVAILABLE_VARIABLES
        assert 'Humidity' in AVAILABLE_VARIABLES

    def test_vibration_variables_available(self):
        """Testa que variáveis de vibração estão disponíveis."""
        from schemas import AVAILABLE_VARIABLES
        assert 'Axial' in AVAILABLE_VARIABLES
        assert 'Radial' in AVAILABLE_VARIABLES


class TestHistorizedVariables:
    """Testes das variáveis historizadas."""

    def test_historized_is_subset(self):
        """Testa que historizadas é subconjunto de disponíveis."""
        from schemas import AVAILABLE_VARIABLES, HISTORIZED_VARIABLES
        for var in HISTORIZED_VARIABLES:
            assert var in AVAILABLE_VARIABLES

    def test_historized_not_empty(self):
        """Testa que há variáveis historizadas."""
        from schemas import HISTORIZED_VARIABLES
        assert len(HISTORIZED_VARIABLES) > 0


class TestResponseSchemas:
    """Testes dos schemas de resposta."""

    def test_motor_latest_response_fields(self):
        """Testa campos do MotorLatestResponse."""
        from schemas import MotorLatestResponse
        fields = MotorLatestResponse.model_fields
        
        assert 'timestamp' in fields
        assert 'electrical' in fields
        assert 'environment' in fields
        assert 'vibration' in fields

    def test_history_response_fields(self):
        """Testa campos do HistoryResponse."""
        from schemas import HistoryResponse
        fields = HistoryResponse.model_fields
        
        assert 'variable' in fields
        assert 'data' in fields

    def test_alarms_list_response_fields(self):
        """Testa campos do AlarmsListResponse."""
        from schemas import AlarmsListResponse
        fields = AlarmsListResponse.model_fields
        
        assert 'alarms' in fields
        assert 'total_count' in fields


class TestElectricalResponse:
    """Testes do ElectricalResponse."""

    def test_electrical_response_import(self):
        """Testa importação do ElectricalResponse."""
        from schemas import ElectricalResponse
        assert ElectricalResponse is not None

    def test_electrical_response_fields(self):
        """Testa campos do ElectricalResponse."""
        from schemas import ElectricalResponse
        fields = ElectricalResponse.model_fields
        
        assert 'voltage' in fields
        assert 'current' in fields


class TestEnvironmentResponse:
    """Testes do EnvironmentResponse."""

    def test_environment_response_import(self):
        """Testa importação do EnvironmentResponse."""
        from schemas import EnvironmentResponse
        assert EnvironmentResponse is not None

    def test_environment_response_fields(self):
        """Testa campos do EnvironmentResponse."""
        from schemas import EnvironmentResponse
        fields = EnvironmentResponse.model_fields
        
        assert 'temperature' in fields
        assert 'humidity' in fields


class TestVibrationResponse:
    """Testes do VibrationResponse."""

    def test_vibration_response_import(self):
        """Testa importação do VibrationResponse."""
        from schemas import VibrationResponse
        assert VibrationResponse is not None

    def test_vibration_response_fields(self):
        """Testa campos do VibrationResponse."""
        from schemas import VibrationResponse
        fields = VibrationResponse.model_fields
        
        assert 'axial' in fields
        assert 'radial' in fields


class TestVoltageResponse:
    """Testes do VoltageResponse."""

    def test_voltage_response_import(self):
        """Testa importação do VoltageResponse."""
        from schemas import VoltageResponse
        assert VoltageResponse is not None

    def test_voltage_response_fields(self):
        """Testa campos do VoltageResponse."""
        from schemas import VoltageResponse
        fields = VoltageResponse.model_fields
        
        assert 'a' in fields
        assert 'b' in fields
        assert 'c' in fields


class TestCurrentResponse:
    """Testes do CurrentResponse."""

    def test_current_response_import(self):
        """Testa importação do CurrentResponse."""
        from schemas import CurrentResponse
        assert CurrentResponse is not None

    def test_current_response_fields(self):
        """Testa campos do CurrentResponse."""
        from schemas import CurrentResponse
        fields = CurrentResponse.model_fields
        
        assert 'a' in fields
        assert 'b' in fields
        assert 'c' in fields


class TestPowerResponse:
    """Testes do PowerResponse."""

    def test_power_response_import(self):
        """Testa importação do PowerResponse."""
        from schemas import PowerResponse
        assert PowerResponse is not None

    def test_power_response_fields(self):
        """Testa campos do PowerResponse."""
        from schemas import PowerResponse
        fields = PowerResponse.model_fields
        
        assert 'active' in fields
        assert 'reactive' in fields
        assert 'apparent' in fields


class TestEnergyResponse:
    """Testes do EnergyResponse."""

    def test_energy_response_import(self):
        """Testa importação do EnergyResponse."""
        from schemas import EnergyResponse
        assert EnergyResponse is not None

    def test_energy_response_fields(self):
        """Testa campos do EnergyResponse."""
        from schemas import EnergyResponse
        fields = EnergyResponse.model_fields
        
        assert 'active' in fields
        assert 'reactive' in fields
        assert 'apparent' in fields


class TestHealthResponse:
    """Testes do HealthResponse."""

    def test_health_response_import(self):
        """Testa importação do HealthResponse."""
        from schemas import HealthResponse
        assert HealthResponse is not None

    def test_health_response_fields(self):
        """Testa campos do HealthResponse."""
        from schemas import HealthResponse
        fields = HealthResponse.model_fields
        
        assert 'status' in fields
        assert 'services' in fields


class TestHistoryDataPointSchema:
    """Testes do HistoryDataPoint."""

    def test_history_data_point_import(self):
        """Testa importação do HistoryDataPoint."""
        from schemas import HistoryDataPoint
        assert HistoryDataPoint is not None

    def test_history_data_point_fields(self):
        """Testa campos do HistoryDataPoint."""
        from schemas import HistoryDataPoint
        fields = HistoryDataPoint.model_fields
        
        assert 'timestamp' in fields
        assert 'value' in fields


class TestAlarmResponse:
    """Testes do AlarmResponse."""

    def test_alarm_response_import(self):
        """Testa importação do AlarmResponse."""
        from schemas import AlarmResponse
        assert AlarmResponse is not None

    def test_alarm_response_fields(self):
        """Testa campos do AlarmResponse."""
        from schemas import AlarmResponse
        fields = AlarmResponse.model_fields
        
        assert 'id' in fields
        assert 'timestamp' in fields
        assert 'category' in fields
        assert 'severity' in fields
        assert 'message' in fields


class TestHistoryStatisticsResponse:
    """Testes do HistoryStatisticsResponse."""

    def test_history_statistics_response_import(self):
        """Testa importação do HistoryStatisticsResponse."""
        from schemas import HistoryStatisticsResponse
        assert HistoryStatisticsResponse is not None

    def test_history_statistics_response_fields(self):
        """Testa campos do HistoryStatisticsResponse."""
        from schemas import HistoryStatisticsResponse
        fields = HistoryStatisticsResponse.model_fields
        
        assert 'variable' in fields
