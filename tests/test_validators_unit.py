"""
Testes unitários completos para os validators do MQTT Ingestor.
"""

import pytest
from datetime import datetime
import sys
import os

# Adicionar caminho do serviço
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'mqtt_ingestor'))

from validators import (
    VoltageData,
    CurrentData,
    PowerData,
    EnergyData,
    ElectricalReading,
    EnvironmentReading,
    VibrationReading,
    validate_electrical,
    validate_environment,
    validate_vibration,
    get_validator_for_topic
)


class TestVoltageData:
    """Testes do validador VoltageData."""

    def test_valid_voltage_data(self):
        """Testa criação com dados válidos."""
        data = VoltageData(a=220.0, b=221.0, c=219.0)
        assert data.a == 220.0
        assert data.b == 221.0
        assert data.c == 219.0

    def test_voltage_zero(self):
        """Testa tensão zero."""
        data = VoltageData(a=0, b=0, c=0)
        assert data.a == 0
        assert data.b == 0
        assert data.c == 0

    def test_voltage_max(self):
        """Testa tensão máxima."""
        data = VoltageData(a=500, b=500, c=500)
        assert data.a == 500
        assert data.b == 500
        assert data.c == 500

    def test_voltage_negative_fails(self):
        """Testa que tensão negativa falha."""
        with pytest.raises(ValueError):
            VoltageData(a=-1, b=220, c=220)

    def test_voltage_above_max_fails(self):
        """Testa que tensão acima do máximo falha."""
        with pytest.raises(ValueError):
            VoltageData(a=501, b=220, c=220)


class TestCurrentData:
    """Testes do validador CurrentData."""

    def test_valid_current_data(self):
        """Testa criação com dados válidos."""
        data = CurrentData(a=10.0, b=10.5, c=9.8)
        assert data.a == 10.0
        assert data.b == 10.5
        assert data.c == 9.8

    def test_current_zero(self):
        """Testa corrente zero."""
        data = CurrentData(a=0, b=0, c=0)
        assert data.a == 0
        assert data.b == 0
        assert data.c == 0

    def test_current_max(self):
        """Testa corrente máxima."""
        data = CurrentData(a=200, b=200, c=200)
        assert data.a == 200
        assert data.b == 200
        assert data.c == 200

    def test_current_negative_fails(self):
        """Testa que corrente negativa falha."""
        with pytest.raises(ValueError):
            CurrentData(a=-1, b=10, c=10)

    def test_current_above_max_fails(self):
        """Testa que corrente acima do máximo falha."""
        with pytest.raises(ValueError):
            CurrentData(a=201, b=10, c=10)


class TestPowerData:
    """Testes do validador PowerData."""

    def test_valid_power_data(self):
        """Testa criação com dados válidos."""
        data = PowerData(active=5000.0, reactive=1000.0, apparent=5100.0)
        assert data.active == 5000.0
        assert data.reactive == 1000.0
        assert data.apparent == 5100.0

    def test_power_zero(self):
        """Testa potência zero."""
        data = PowerData(active=0, reactive=0, apparent=0)
        assert data.active == 0
        assert data.reactive == 0
        assert data.apparent == 0

    def test_reactive_power_negative(self):
        """Testa potência reativa negativa (capacitiva)."""
        data = PowerData(active=5000.0, reactive=-1000.0, apparent=5100.0)
        assert data.reactive == -1000.0

    def test_active_power_negative_fails(self):
        """Testa que potência ativa negativa falha."""
        with pytest.raises(ValueError):
            PowerData(active=-1, reactive=1000, apparent=5100)


class TestEnergyData:
    """Testes do validador EnergyData."""

    def test_valid_energy_data(self):
        """Testa criação com dados válidos."""
        data = EnergyData(active=1000.0, reactive=200.0, apparent=1020.0)
        assert data.active == 1000.0
        assert data.reactive == 200.0
        assert data.apparent == 1020.0

    def test_energy_zero(self):
        """Testa energia zero."""
        data = EnergyData(active=0, reactive=0, apparent=0)
        assert data.active == 0
        assert data.reactive == 0
        assert data.apparent == 0

    def test_energy_negative_fails(self):
        """Testa que energia negativa falha."""
        with pytest.raises(ValueError):
            EnergyData(active=-1, reactive=200, apparent=1020)


class TestElectricalReading:
    """Testes do validador ElectricalReading."""

    def get_valid_electrical_data(self):
        """Retorna dados elétricos válidos."""
        return {
            'timestamp': datetime.now(),
            'voltage': {'a': 220.0, 'b': 221.0, 'c': 219.0},
            'current': {'a': 10.0, 'b': 10.5, 'c': 9.8},
            'power': {'active': 5000.0, 'reactive': 1000.0, 'apparent': 5100.0},
            'energy': {'active': 1000.0, 'reactive': 200.0, 'apparent': 1020.0},
            'powerFactor': 0.85,
            'frequency': 60.0
        }

    def test_valid_electrical_reading(self):
        """Testa criação com dados válidos."""
        data = self.get_valid_electrical_data()
        reading = ElectricalReading(**data)
        assert reading.powerFactor == 0.85
        assert reading.frequency == 60.0

    def test_power_factor_zero(self):
        """Testa fator de potência zero."""
        data = self.get_valid_electrical_data()
        data['powerFactor'] = 0
        reading = ElectricalReading(**data)
        assert reading.powerFactor == 0

    def test_power_factor_one(self):
        """Testa fator de potência unitário."""
        data = self.get_valid_electrical_data()
        data['powerFactor'] = 1.0
        reading = ElectricalReading(**data)
        assert reading.powerFactor == 1.0

    def test_power_factor_above_one_fails(self):
        """Testa que fator de potência acima de 1 falha."""
        data = self.get_valid_electrical_data()
        data['powerFactor'] = 1.1
        with pytest.raises(ValueError):
            ElectricalReading(**data)

    def test_frequency_zero(self):
        """Testa frequência zero."""
        data = self.get_valid_electrical_data()
        data['frequency'] = 0
        reading = ElectricalReading(**data)
        assert reading.frequency == 0

    def test_frequency_max(self):
        """Testa frequência máxima."""
        data = self.get_valid_electrical_data()
        data['frequency'] = 100
        reading = ElectricalReading(**data)
        assert reading.frequency == 100

    def test_frequency_above_max_fails(self):
        """Testa que frequência acima do máximo falha."""
        data = self.get_valid_electrical_data()
        data['frequency'] = 101
        with pytest.raises(ValueError):
            ElectricalReading(**data)


class TestEnvironmentReading:
    """Testes do validador EnvironmentReading."""

    def get_valid_environment_data(self):
        """Retorna dados ambientais válidos."""
        return {
            'timestamp': datetime.now(),
            'temperature': 25.0,
            'humidity': 60.0,
            'caseTemperature': 45.0
        }

    def test_valid_environment_reading(self):
        """Testa criação com dados válidos."""
        data = self.get_valid_environment_data()
        reading = EnvironmentReading(**data)
        assert reading.temperature == 25.0
        assert reading.humidity == 60.0
        assert reading.caseTemperature == 45.0

    def test_temperature_min(self):
        """Testa temperatura mínima."""
        data = self.get_valid_environment_data()
        data['temperature'] = -40
        reading = EnvironmentReading(**data)
        assert reading.temperature == -40

    def test_temperature_max(self):
        """Testa temperatura máxima."""
        data = self.get_valid_environment_data()
        data['temperature'] = 100
        reading = EnvironmentReading(**data)
        assert reading.temperature == 100

    def test_temperature_below_min_fails(self):
        """Testa que temperatura abaixo do mínimo falha."""
        data = self.get_valid_environment_data()
        data['temperature'] = -41
        with pytest.raises(ValueError):
            EnvironmentReading(**data)

    def test_temperature_above_max_fails(self):
        """Testa que temperatura acima do máximo falha."""
        data = self.get_valid_environment_data()
        data['temperature'] = 101
        with pytest.raises(ValueError):
            EnvironmentReading(**data)

    def test_humidity_zero(self):
        """Testa umidade zero."""
        data = self.get_valid_environment_data()
        data['humidity'] = 0
        reading = EnvironmentReading(**data)
        assert reading.humidity == 0

    def test_humidity_max(self):
        """Testa umidade máxima."""
        data = self.get_valid_environment_data()
        data['humidity'] = 100
        reading = EnvironmentReading(**data)
        assert reading.humidity == 100

    def test_humidity_above_max_fails(self):
        """Testa que umidade acima do máximo falha."""
        data = self.get_valid_environment_data()
        data['humidity'] = 101
        with pytest.raises(ValueError):
            EnvironmentReading(**data)

    def test_case_temperature_min(self):
        """Testa temperatura da carcaça mínima."""
        data = self.get_valid_environment_data()
        data['caseTemperature'] = -40
        reading = EnvironmentReading(**data)
        assert reading.caseTemperature == -40

    def test_case_temperature_max(self):
        """Testa temperatura da carcaça máxima."""
        data = self.get_valid_environment_data()
        data['caseTemperature'] = 150
        reading = EnvironmentReading(**data)
        assert reading.caseTemperature == 150


class TestVibrationReading:
    """Testes do validador VibrationReading."""

    def get_valid_vibration_data(self):
        """Retorna dados de vibração válidos."""
        return {
            'timestamp': datetime.now(),
            'axial': 0.5,
            'radial': 0.3
        }

    def test_valid_vibration_reading(self):
        """Testa criação com dados válidos."""
        data = self.get_valid_vibration_data()
        reading = VibrationReading(**data)
        assert reading.axial == 0.5
        assert reading.radial == 0.3

    def test_vibration_zero(self):
        """Testa vibração zero."""
        data = self.get_valid_vibration_data()
        data['axial'] = 0
        data['radial'] = 0
        reading = VibrationReading(**data)
        assert reading.axial == 0
        assert reading.radial == 0

    def test_vibration_max(self):
        """Testa vibração máxima."""
        data = self.get_valid_vibration_data()
        data['axial'] = 100
        data['radial'] = 100
        reading = VibrationReading(**data)
        assert reading.axial == 100
        assert reading.radial == 100

    def test_vibration_negative_fails(self):
        """Testa que vibração negativa falha."""
        data = self.get_valid_vibration_data()
        data['axial'] = -1
        with pytest.raises(ValueError):
            VibrationReading(**data)

    def test_vibration_above_max_fails(self):
        """Testa que vibração acima do máximo falha."""
        data = self.get_valid_vibration_data()
        data['axial'] = 101
        with pytest.raises(ValueError):
            VibrationReading(**data)


class TestValidateElectrical:
    """Testes da função validate_electrical."""

    def test_validate_valid_data(self):
        """Testa validação de dados válidos."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'voltage': {'a': 220.0, 'b': 221.0, 'c': 219.0},
            'current': {'a': 10.0, 'b': 10.5, 'c': 9.8},
            'power': {'active': 5000.0, 'reactive': 1000.0, 'apparent': 5100.0},
            'energy': {'active': 1000.0, 'reactive': 200.0, 'apparent': 1020.0},
            'powerFactor': 0.85,
            'frequency': 60.0
        }
        result = validate_electrical(data)
        assert result is not None
        assert isinstance(result, ElectricalReading)

    def test_validate_invalid_data(self):
        """Testa validação de dados inválidos."""
        data = {'invalid': 'data'}
        result = validate_electrical(data)
        assert result is None

    def test_validate_empty_data(self):
        """Testa validação de dados vazios."""
        result = validate_electrical({})
        assert result is None


class TestValidateEnvironment:
    """Testes da função validate_environment."""

    def test_validate_valid_data(self):
        """Testa validação de dados válidos."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'temperature': 25.0,
            'humidity': 60.0,
            'caseTemperature': 45.0
        }
        result = validate_environment(data)
        assert result is not None
        assert isinstance(result, EnvironmentReading)

    def test_validate_invalid_data(self):
        """Testa validação de dados inválidos."""
        data = {'invalid': 'data'}
        result = validate_environment(data)
        assert result is None

    def test_validate_empty_data(self):
        """Testa validação de dados vazios."""
        result = validate_environment({})
        assert result is None


class TestValidateVibration:
    """Testes da função validate_vibration."""

    def test_validate_valid_data(self):
        """Testa validação de dados válidos."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'axial': 0.5,
            'radial': 0.3
        }
        result = validate_vibration(data)
        assert result is not None
        assert isinstance(result, VibrationReading)

    def test_validate_invalid_data(self):
        """Testa validação de dados inválidos."""
        data = {'invalid': 'data'}
        result = validate_vibration(data)
        assert result is None

    def test_validate_empty_data(self):
        """Testa validação de dados vazios."""
        result = validate_vibration({})
        assert result is None


class TestGetValidatorForTopic:
    """Testes da função get_validator_for_topic."""

    def test_electrical_topic(self):
        """Testa tópico elétrico."""
        validator = get_validator_for_topic("scgdi/motor/electrical")
        assert validator == validate_electrical

    def test_environment_topic(self):
        """Testa tópico ambiental."""
        validator = get_validator_for_topic("scgdi/motor/environment")
        assert validator == validate_environment

    def test_vibration_topic(self):
        """Testa tópico de vibração."""
        validator = get_validator_for_topic("scgdi/motor/vibration")
        assert validator == validate_vibration

    def test_unknown_topic_raises(self):
        """Testa que tópico desconhecido lança exceção."""
        with pytest.raises(ValueError):
            get_validator_for_topic("unknown/topic")

    def test_empty_topic_raises(self):
        """Testa que tópico vazio lança exceção."""
        with pytest.raises(ValueError):
            get_validator_for_topic("")
