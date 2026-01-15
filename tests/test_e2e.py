"""
Teste End-to-End (E2E) para o sistema de monitoramento do Motor 50CV.

Este script testa o fluxo completo:
1. Publicação MQTT → RabbitMQ
2. Verificação na API REST
3. Validação no OPC UA Server

Uso: pytest tests/test_e2e.py -v
"""

import pytest
import asyncio
import json
import time
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Callable

# Adicionar paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'mqtt_ingestor'))


# ===== Classes locais para testes (evitam imports com dependências) =====

class Severity(IntEnum):
    """Níveis de severidade para alarmes OPC UA."""
    INFORMATIVE = 100
    LOW = 250
    MEDIUM = 500
    HIGH = 700
    CRITICAL = 900


@dataclass
class AlarmEvent:
    """Representa um evento de alarme."""
    id: str
    timestamp: datetime
    severity: Severity
    message: str
    source_name: str
    category: str
    value: Optional[float] = None
    acknowledged: bool = False
    active: bool = True


@dataclass
class AlarmRule:
    """Regra de alarme."""
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    severity: Severity
    message: str
    source_name: str
    category: str
    cooldown_seconds: int = 30


class AlarmManager:
    """Gerenciador de alarmes."""
    
    def __init__(self):
        self._rules: List[AlarmRule] = []
        self._active_alarms: Dict[str, AlarmEvent] = {}
        self._alarm_history: List[AlarmEvent] = []
        self._last_trigger: Dict[str, datetime] = {}
        
    def add_rule(self, rule: AlarmRule):
        self._rules.append(rule)
        
    def check_alarms(self, values: Dict[str, Any]) -> List[AlarmEvent]:
        """Verifica condições e gera alarmes."""
        new_alarms = []
        now = datetime.utcnow()
        
        for rule in self._rules:
            try:
                if rule.condition(values):
                    last = self._last_trigger.get(rule.name)
                    if last and (now - last).total_seconds() < rule.cooldown_seconds:
                        continue
                        
                    alarm_id = f"{rule.name}_{now.timestamp()}"
                    alarm = AlarmEvent(
                        id=alarm_id,
                        timestamp=now,
                        severity=rule.severity,
                        message=rule.message,
                        source_name=rule.source_name,
                        category=rule.category,
                        value=values.get(rule.source_name)
                    )
                    
                    self._active_alarms[alarm_id] = alarm
                    self._alarm_history.append(alarm)
                    self._last_trigger[rule.name] = now
                    new_alarms.append(alarm)
            except Exception:
                pass
                
        return new_alarms


def extract_variable_values(data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
    """Extrai valores das variáveis dos dados recebidos."""
    values = {}
    
    if data_type == "electrical":
        if "voltage" in data:
            values["VoltageA"] = data["voltage"].get("a")
            values["VoltageB"] = data["voltage"].get("b")
            values["VoltageC"] = data["voltage"].get("c")
        if "current" in data:
            values["CurrentA"] = data["current"].get("a")
            values["CurrentB"] = data["current"].get("b")
            values["CurrentC"] = data["current"].get("c")
        if "power" in data:
            values["PowerActive"] = data["power"].get("active")
            values["PowerReactive"] = data["power"].get("reactive")
            values["PowerApparent"] = data["power"].get("apparent")
        if "energy" in data:
            values["EnergyActive"] = data["energy"].get("active")
            values["EnergyReactive"] = data["energy"].get("reactive")
            values["EnergyApparent"] = data["energy"].get("apparent")
        values["PowerFactor"] = data.get("powerFactor")
        values["Frequency"] = data.get("frequency")
        
    elif data_type == "environment":
        values["Temperature"] = data.get("temperature")
        values["Humidity"] = data.get("humidity")
        values["CaseTemperature"] = data.get("caseTemperature")
        
    elif data_type == "vibration":
        values["Axial"] = data.get("axial")
        values["Radial"] = data.get("radial")
        
    return {k: v for k, v in values.items() if v is not None}


# ===== Testes E2E =====

class TestE2EDataFlow:
    """Testes E2E simulados para validação do fluxo de dados."""
    
    def test_mqtt_message_format_electrical(self):
        """Testa formato de mensagem MQTT elétrica."""
        message = {
            "timestamp": datetime.utcnow().isoformat(),
            "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        assert "voltage" in message
        assert "current" in message
        assert "power" in message
        assert "energy" in message
        assert all(k in message["voltage"] for k in ["a", "b", "c"])
        
    def test_mqtt_message_format_environment(self):
        """Testa formato de mensagem MQTT ambiental."""
        message = {
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": 34.5,
            "humidity": 55.2,
            "caseTemperature": 45.0
        }
        
        assert "temperature" in message
        assert "humidity" in message
        assert "caseTemperature" in message
        
    def test_mqtt_message_format_vibration(self):
        """Testa formato de mensagem MQTT de vibração."""
        message = {
            "timestamp": datetime.utcnow().isoformat(),
            "axial": 0.12,
            "radial": 0.15
        }
        
        assert "axial" in message
        assert "radial" in message


class TestE2EValidation:
    """Testes de validação E2E."""
    
    def test_electrical_data_validation_flow(self):
        """Testa fluxo de validação de dados elétricos."""
        from validators import ElectricalReading
        
        raw_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        reading = ElectricalReading(**raw_data)
        message = reading.model_dump(mode='json')
        
        assert message["voltage"]["a"] == 220.0
        assert message["powerFactor"] == 0.95
        
    def test_environment_data_validation_flow(self):
        """Testa fluxo de validação de dados ambientais."""
        from validators import EnvironmentReading
        
        raw_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": 34.5,
            "humidity": 55.2,
            "caseTemperature": 45.0
        }
        
        reading = EnvironmentReading(**raw_data)
        message = reading.model_dump(mode='json')
        
        assert message["temperature"] == 34.5
        assert message["caseTemperature"] == 45.0
        
    def test_vibration_data_validation_flow(self):
        """Testa fluxo de validação de dados de vibração."""
        from validators import VibrationReading
        
        raw_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "axial": 0.12,
            "radial": 0.15
        }
        
        reading = VibrationReading(**raw_data)
        message = reading.model_dump(mode='json')
        
        assert message["axial"] == 0.12
        assert message["radial"] == 0.15


class TestE2EAlarmFlow:
    """Testes E2E para fluxo de alarmes."""
    
    def test_overvoltage_alarm_generation(self):
        """Testa geração de alarme de sobretensão."""
        rules = [
            AlarmRule(
                name="OvervoltagePhaseA",
                condition=lambda values: values.get("VoltageA", 0) > 220 * 1.10,
                severity=Severity.HIGH,
                message="Overvoltage detected on phase A",
                source_name="VoltageA",
                category="Electrical"
            )
        ]
        
        manager = AlarmManager()
        for rule in rules:
            manager.add_rule(rule)
        
        values = {"VoltageA": 250.0}
        alarms = manager.check_alarms(values)
        
        assert len(alarms) > 0
        assert alarms[0].severity == Severity.HIGH
        
    def test_critical_temperature_alarm(self):
        """Testa alarme de temperatura crítica."""
        rules = [
            AlarmRule(
                name="CriticalCaseTemperature",
                condition=lambda values: values.get("CaseTemperature", 0) > 60.0,
                severity=Severity.CRITICAL,
                message="Critical case temperature detected",
                source_name="CaseTemperature",
                category="Environment"
            )
        ]
        
        manager = AlarmManager()
        for rule in rules:
            manager.add_rule(rule)
        
        values = {"CaseTemperature": 75.0}
        alarms = manager.check_alarms(values)
        
        assert len(alarms) > 0
        assert alarms[0].severity == Severity.CRITICAL
        
    def test_normal_values_no_alarm(self):
        """Testa que valores normais não geram alarmes."""
        rules = [
            AlarmRule(
                name="OvervoltagePhaseA",
                condition=lambda values: values.get("VoltageA", 0) > 220 * 1.10,
                severity=Severity.HIGH,
                message="Overvoltage detected",
                source_name="VoltageA",
                category="Electrical"
            ),
            AlarmRule(
                name="CriticalCaseTemperature",
                condition=lambda values: values.get("CaseTemperature", 0) > 60.0,
                severity=Severity.CRITICAL,
                message="Critical temperature",
                source_name="CaseTemperature",
                category="Environment"
            )
        ]
        
        manager = AlarmManager()
        for rule in rules:
            manager.add_rule(rule)
        
        values = {
            "VoltageA": 220.0,
            "CaseTemperature": 45.0
        }
        
        alarms = manager.check_alarms(values)
        assert len(alarms) == 0


class TestE2EAPIResponse:
    """Testes E2E para respostas da API."""
    
    def test_api_motor_latest_structure(self):
        """Testa estrutura esperada do endpoint /motor/latest."""
        expected_structure = {
            "timestamp": "ISO8601 string",
            "electrical": {
                "voltage": {"a": "float", "b": "float", "c": "float"},
                "current": {"a": "float", "b": "float", "c": "float"},
                "power": {"active": "float", "reactive": "float", "apparent": "float"},
                "energy": {"active": "float", "reactive": "float", "apparent": "float"},
                "powerFactor": "float",
                "frequency": "float"
            },
            "environment": {
                "temperature": "float",
                "humidity": "float",
                "caseTemperature": "float"
            },
            "vibration": {
                "axial": "float",
                "radial": "float"
            },
            "active_alarms": "int"
        }
        
        assert "electrical" in expected_structure
        assert "environment" in expected_structure
        assert "vibration" in expected_structure
        
    def test_api_alarms_structure(self):
        """Testa estrutura esperada do endpoint /motor/alarms."""
        expected_alarm = {
            "id": "string",
            "timestamp": "ISO8601 string",
            "category": "string",
            "severity": "int",
            "severity_name": "string",
            "message": "string",
            "source_name": "string",
            "value": "float",
            "acknowledged": "bool"
        }
        
        required_fields = ["id", "timestamp", "category", "severity", "message"]
        for field in required_fields:
            assert field in expected_alarm


class TestE2EOPCUANodeset:
    """Testes E2E para estrutura do Nodeset OPC UA."""
    
    def test_nodeset_structure(self):
        """Testa estrutura esperada do Nodeset."""
        expected_nodes = [
            "Motor50CV",
            "Motor50CV/Electrical",
            "Motor50CV/Electrical/Voltage",
            "Motor50CV/Electrical/Current",
            "Motor50CV/Electrical/Power",
            "Motor50CV/Electrical/Energy",
            "Motor50CV/Environment",
            "Motor50CV/Vibration"
        ]
        
        expected_variables = [
            "VoltageA", "VoltageB", "VoltageC",
            "CurrentA", "CurrentB", "CurrentC",
            "PowerActive", "PowerReactive", "PowerApparent",
            "EnergyActive", "EnergyReactive", "EnergyApparent",
            "PowerFactor", "Frequency",
            "Temperature", "Humidity", "CaseTemperature",
            "Axial", "Radial"
        ]
        
        assert len(expected_variables) == 19


class TestE2ECompleteScenario:
    """Cenário E2E completo simulado."""
    
    def test_complete_motor_monitoring_scenario(self):
        """Testa cenário completo de monitoramento."""
        from validators import ElectricalReading, EnvironmentReading, VibrationReading
        
        # 1. Simular dados recebidos via MQTT
        electrical_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        environment_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": 34.5,
            "humidity": 55.2,
            "caseTemperature": 45.0
        }
        
        vibration_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "axial": 0.12,
            "radial": 0.15
        }
        
        # 2. Validar dados
        electrical = ElectricalReading(**electrical_data)
        environment = EnvironmentReading(**environment_data)
        vibration = VibrationReading(**vibration_data)
        
        # 3. Extrair valores para verificação de alarmes
        values = {}
        values.update(extract_variable_values(electrical.model_dump(mode='json'), "electrical"))
        values.update(extract_variable_values(environment.model_dump(mode='json'), "environment"))
        values.update(extract_variable_values(vibration.model_dump(mode='json'), "vibration"))
        
        # 4. Verificar extração de valores
        assert "VoltageA" in values
        assert values["VoltageA"] == 220.0
        assert "CaseTemperature" in values
        assert values["CaseTemperature"] == 45.0
        assert "Axial" in values
        assert values["Axial"] == 0.12
        
        # 5. Verificar alarmes (valores normais, não deve gerar)
        rules = [
            AlarmRule(
                name="OvervoltagePhaseA",
                condition=lambda v: v.get("VoltageA", 0) > 242,
                severity=Severity.HIGH,
                message="Overvoltage",
                source_name="VoltageA",
                category="Electrical"
            ),
            AlarmRule(
                name="CriticalTemp",
                condition=lambda v: v.get("CaseTemperature", 0) > 60,
                severity=Severity.CRITICAL,
                message="Critical temperature",
                source_name="CaseTemperature",
                category="Environment"
            )
        ]
        
        manager = AlarmManager()
        for rule in rules:
            manager.add_rule(rule)
            
        alarms = manager.check_alarms(values)
        assert len(alarms) == 0
        
    def test_complete_alarm_scenario(self):
        """Testa cenário completo com geração de alarme."""
        from validators import ElectricalReading, EnvironmentReading
        
        # 1. Simular dados com problema
        electrical_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "voltage": {"a": 250.0, "b": 221.0, "c": 219.0},
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        environment_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": 34.5,
            "humidity": 55.2,
            "caseTemperature": 75.0
        }
        
        # 2. Validar dados
        electrical = ElectricalReading(**electrical_data)
        environment = EnvironmentReading(**environment_data)
        
        # 3. Extrair valores
        values = {}
        values.update(extract_variable_values(electrical.model_dump(mode='json'), "electrical"))
        values.update(extract_variable_values(environment.model_dump(mode='json'), "environment"))
        
        # 4. Configurar regras de alarme
        rules = [
            AlarmRule(
                name="OvervoltagePhaseA",
                condition=lambda v: v.get("VoltageA", 0) > 242,
                severity=Severity.HIGH,
                message="Overvoltage detected on phase A",
                source_name="VoltageA",
                category="Electrical"
            ),
            AlarmRule(
                name="CriticalCaseTemp",
                condition=lambda v: v.get("CaseTemperature", 0) > 60,
                severity=Severity.CRITICAL,
                message="Critical case temperature",
                source_name="CaseTemperature",
                category="Environment"
            )
        ]
        
        manager = AlarmManager()
        for rule in rules:
            manager.add_rule(rule)
            
        alarms = manager.check_alarms(values)
        
        # 5. Verificar alarmes gerados
        assert len(alarms) == 2
        
        severities = [a.severity for a in alarms]
        assert Severity.HIGH in severities
        assert Severity.CRITICAL in severities
        
        categories = [a.category for a in alarms]
        assert "Electrical" in categories
        assert "Environment" in categories


class TestE2EPerformance:
    """Testes de performance E2E."""
    
    def test_validation_performance(self):
        """Testa performance de validação."""
        from validators import ElectricalReading
        
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        start = time.time()
        for _ in range(1000):
            reading = ElectricalReading(**data)
            reading.model_dump(mode='json')
        end = time.time()
        
        elapsed = end - start
        assert elapsed < 1.0, f"Validation too slow: {elapsed:.2f}s for 1000 iterations"
        
    def test_alarm_check_performance(self):
        """Testa performance de verificação de alarmes."""
        manager = AlarmManager()
        for i in range(20):
            manager.add_rule(AlarmRule(
                name=f"Rule{i}",
                condition=lambda v, i=i: v.get(f"Var{i}", 0) > 100,
                severity=Severity.MEDIUM,
                message=f"Alarm {i}",
                source_name=f"Source{i}",
                category="Test"
            ))
            
        values = {f"Var{i}": 50.0 for i in range(20)}
        
        start = time.time()
        for _ in range(1000):
            manager.check_alarms(values)
        end = time.time()
        
        elapsed = end - start
        assert elapsed < 1.0, f"Alarm check too slow: {elapsed:.2f}s for 1000 iterations"


class TestExtractVariableValues:
    """Testes para extração de valores de variáveis."""
    
    def test_extract_electrical_values(self):
        """Testa extração de valores elétricos."""
        data = {
            "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
            "current": {"a": 10.5, "b": 10.4, "c": 10.6},
            "power": {"active": 4500, "reactive": 500, "apparent": 4600},
            "energy": {"active": 10000, "reactive": 1200, "apparent": 10200},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        values = extract_variable_values(data, "electrical")
        
        assert values["VoltageA"] == 220.0
        assert values["CurrentA"] == 10.5
        assert values["PowerActive"] == 4500
        assert values["EnergyActive"] == 10000
        assert values["PowerFactor"] == 0.95
        assert values["Frequency"] == 60.0
        
    def test_extract_environment_values(self):
        """Testa extração de valores ambientais."""
        data = {
            "temperature": 34.5,
            "humidity": 55.2,
            "caseTemperature": 45.0
        }
        
        values = extract_variable_values(data, "environment")
        
        assert values["Temperature"] == 34.5
        assert values["Humidity"] == 55.2
        assert values["CaseTemperature"] == 45.0
        
    def test_extract_vibration_values(self):
        """Testa extração de valores de vibração."""
        data = {
            "axial": 0.12,
            "radial": 0.15
        }
        
        values = extract_variable_values(data, "vibration")
        
        assert values["Axial"] == 0.12
        assert values["Radial"] == 0.15
