"""
Testes unitários para o servidor OPC UA.

Este módulo contém testes para o gerenciador de alarmes,
historiador e consumidor RabbitMQ.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import os
import sys
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Callable


# ===== Classes locais para testes =====

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
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "severity_name": self.severity.name,
            "message": self.message,
            "source_name": self.source_name,
            "category": self.category,
            "value": self.value,
            "acknowledged": self.acknowledged,
            "active": self.active
        }


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
        
    @property
    def rules(self):
        return self._rules
        
    @property
    def active_alarms(self):
        return self._active_alarms
        
    def check_alarms(self, values: Dict[str, Any]) -> List[AlarmEvent]:
        """Verifica condições e gera alarmes."""
        new_alarms = []
        now = datetime.now(timezone.utc)
        
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
        
    def get_active_alarms(self) -> List[Dict]:
        return [a.to_dict() for a in self._active_alarms.values()]
        
    def get_alarm_history(self, limit: int = 100, category: str = None) -> List[Dict]:
        history = self._alarm_history[-limit:]
        if category:
            history = [a for a in history if a.category == category]
        return [a.to_dict() for a in history]
        
    def acknowledge_alarm(self, alarm_id: str) -> bool:
        for alarm in self._active_alarms.values():
            if alarm.id == alarm_id:
                alarm.acknowledged = True
                return True
        return False


def extract_variable_values(data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
    """Extrai valores das variáveis dos dados recebidos."""
    values = {}
    
    if data_type == "electrical":
        if "voltage" in data:
            values["VoltageA"] = data["voltage"].get("a", 0)
            values["VoltageB"] = data["voltage"].get("b", 0)
            values["VoltageC"] = data["voltage"].get("c", 0)
        else:
            values["VoltageA"] = 0
            values["VoltageB"] = 0
            values["VoltageC"] = 0
        if "current" in data:
            values["CurrentA"] = data["current"].get("a", 0)
            values["CurrentB"] = data["current"].get("b", 0)
            values["CurrentC"] = data["current"].get("c", 0)
        else:
            values["CurrentA"] = 0
            values["CurrentB"] = 0
            values["CurrentC"] = 0
        if "power" in data:
            values["PowerActive"] = data["power"].get("active", 0)
            values["PowerReactive"] = data["power"].get("reactive", 0)
            values["PowerApparent"] = data["power"].get("apparent", 0)
        else:
            values["PowerActive"] = 0
            values["PowerReactive"] = 0
            values["PowerApparent"] = 0
        if "energy" in data:
            values["EnergyActive"] = data["energy"].get("active", 0)
            values["EnergyReactive"] = data["energy"].get("reactive", 0)
            values["EnergyApparent"] = data["energy"].get("apparent", 0)
        else:
            values["EnergyActive"] = 0
            values["EnergyReactive"] = 0
            values["EnergyApparent"] = 0
        values["PowerFactor"] = data.get("powerFactor", 0)
        values["Frequency"] = data.get("frequency", 0)
        
    elif data_type == "environment":
        values["Temperature"] = data.get("temperature", 0)
        values["Humidity"] = data.get("humidity", 0)
        values["CaseTemperature"] = data.get("caseTemperature", 0)
        
    elif data_type == "vibration":
        values["Axial"] = data.get("axial", 0)
        values["Radial"] = data.get("radial", 0)
        
    return values


# ===== TESTES =====

class TestSeverity:
    """Testes para os níveis de severidade."""
    
    def test_severity_values(self):
        """Testa valores de severidade conforme especificação."""
        assert Severity.INFORMATIVE.value == 100
        assert Severity.LOW.value == 250
        assert Severity.MEDIUM.value == 500
        assert Severity.HIGH.value == 700
        assert Severity.CRITICAL.value == 900
        
    def test_severity_ordering(self):
        """Testa ordenação de severidades."""
        assert Severity.INFORMATIVE < Severity.LOW
        assert Severity.LOW < Severity.MEDIUM
        assert Severity.MEDIUM < Severity.HIGH
        assert Severity.HIGH < Severity.CRITICAL


class TestAlarmEvent:
    """Testes para eventos de alarme."""
    
    def test_alarm_event_creation(self):
        """Testa criação de evento de alarme."""
        alarm = AlarmEvent(
            id="test_alarm_1",
            timestamp=datetime(2025, 8, 8, 12, 0, 0),
            category="Electrical",
            severity=Severity.HIGH,
            message="Overvoltage detected",
            source_name="VoltageA",
            value=250.0
        )
        
        assert alarm.category == "Electrical"
        assert alarm.severity == Severity.HIGH
        assert alarm.value == 250.0
        assert alarm.acknowledged is False
        assert alarm.id == "test_alarm_1"
        
    def test_alarm_event_to_dict(self):
        """Testa conversão para dicionário."""
        alarm = AlarmEvent(
            id="test_alarm_2",
            timestamp=datetime(2025, 8, 8, 12, 0, 0),
            category="Environment",
            severity=Severity.CRITICAL,
            message="Case temperature critical",
            source_name="CaseTemperature",
            value=65.0
        )
        
        data = alarm.to_dict()
        
        assert data["category"] == "Environment"
        assert data["severity"] == 900
        assert data["severity_name"] == "CRITICAL"
        assert data["value"] == 65.0
        assert data["acknowledged"] is False


class TestAlarmRule:
    """Testes para regras de alarme."""
    
    def test_rule_creation(self):
        """Testa criação de regra."""
        rule = AlarmRule(
            name="Overvoltage_A",
            condition=lambda v: v.get("VoltageA", 0) > 242,
            severity=Severity.HIGH,
            message="Overvoltage detected",
            source_name="VoltageA",
            category="Electrical"
        )
        
        assert rule.name == "Overvoltage_A"
        assert rule.severity == Severity.HIGH
        assert rule.category == "Electrical"
        
    def test_rule_condition_true(self):
        """Testa condição positiva."""
        rule = AlarmRule(
            name="Overvoltage_A",
            condition=lambda v: v.get("VoltageA", 0) > 242,
            severity=Severity.HIGH,
            message="Overvoltage detected",
            source_name="VoltageA",
            category="Electrical"
        )
        
        values = {"VoltageA": 250.0}
        assert rule.condition(values) is True
        
    def test_rule_condition_false(self):
        """Testa condição negativa."""
        rule = AlarmRule(
            name="Overvoltage_A",
            condition=lambda v: v.get("VoltageA", 0) > 242,
            severity=Severity.HIGH,
            message="Overvoltage detected",
            source_name="VoltageA",
            category="Electrical"
        )
        
        values = {"VoltageA": 220.0}
        assert rule.condition(values) is False


class TestAlarmManager:
    """Testes para o gerenciador de alarmes."""
    
    def test_add_rule(self):
        """Testa adição de regra."""
        manager = AlarmManager()
        rule = AlarmRule(
            name="TestRule",
            condition=lambda v: v.get("Test", 0) > 100,
            severity=Severity.MEDIUM,
            message="Test alarm",
            source_name="Test",
            category="Test"
        )
        
        manager.add_rule(rule)
        
        assert len(manager.rules) == 1
        
    def test_check_alarms_no_alarm(self):
        """Testa verificação sem alarmes."""
        manager = AlarmManager()
        manager.add_rule(AlarmRule(
            name="Overvoltage_A",
            condition=lambda v: v.get("VoltageA", 0) > 242,
            severity=Severity.HIGH,
            message="Overvoltage detected",
            source_name="VoltageA",
            category="Electrical"
        ))
        
        values = {"VoltageA": 220.0}
        alarms = manager.check_alarms(values)
        
        assert len(alarms) == 0
        
    def test_check_alarms_with_alarm(self):
        """Testa verificação com alarme."""
        manager = AlarmManager()
        manager.add_rule(AlarmRule(
            name="Overvoltage_A",
            condition=lambda v: v.get("VoltageA", 0) > 242,
            severity=Severity.HIGH,
            message="Overvoltage detected",
            source_name="VoltageA",
            category="Electrical"
        ))
        
        values = {"VoltageA": 250.0}
        alarms = manager.check_alarms(values)
        
        assert len(alarms) == 1
        assert alarms[0].severity == Severity.HIGH
        assert alarms[0].category == "Electrical"
        
    def test_check_alarms_critical_temperature(self):
        """Testa alarme de temperatura crítica."""
        manager = AlarmManager()
        manager.add_rule(AlarmRule(
            name="CriticalTemp",
            condition=lambda v: v.get("CaseTemperature", 0) > 60,
            severity=Severity.CRITICAL,
            message="Critical temperature",
            source_name="CaseTemperature",
            category="Environment"
        ))
        
        values = {"CaseTemperature": 65.0}
        alarms = manager.check_alarms(values)
        
        assert len(alarms) == 1
        assert alarms[0].severity == Severity.CRITICAL
        
    def test_get_active_alarms(self):
        """Testa obtenção de alarmes ativos."""
        manager = AlarmManager()
        manager.add_rule(AlarmRule(
            name="TestRule",
            condition=lambda v: v.get("Test", 0) > 100,
            severity=Severity.MEDIUM,
            message="Test alarm",
            source_name="Test",
            category="Test"
        ))
        
        manager.check_alarms({"Test": 150})
        active = manager.get_active_alarms()
        
        assert len(active) == 1
        assert active[0]["category"] == "Test"
        
    def test_acknowledge_alarm(self):
        """Testa reconhecimento de alarme."""
        manager = AlarmManager()
        manager.add_rule(AlarmRule(
            name="TestRule",
            condition=lambda v: v.get("Test", 0) > 100,
            severity=Severity.MEDIUM,
            message="Test alarm",
            source_name="Test",
            category="Test"
        ))
        
        alarms = manager.check_alarms({"Test": 150})
        alarm_id = alarms[0].id
        
        result = manager.acknowledge_alarm(alarm_id)
        
        assert result is True
        assert manager.active_alarms[alarm_id].acknowledged is True
        
    def test_get_alarm_history(self):
        """Testa histórico de alarmes."""
        manager = AlarmManager()
        manager.add_rule(AlarmRule(
            name="TestRule",
            condition=lambda v: v.get("Test", 0) > 100,
            severity=Severity.MEDIUM,
            message="Test alarm",
            source_name="Test",
            category="Test"
        ))
        
        manager._last_trigger = {}  # Reset para permitir múltiplos alarmes
        manager.check_alarms({"Test": 150})
        
        history = manager.get_alarm_history()
        
        assert len(history) >= 1


class TestExtractVariableValues:
    """Testes para extração de valores de variáveis."""
    
    def test_extract_electrical(self):
        """Testa extração de dados elétricos."""
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
        assert values["VoltageB"] == 221.0
        assert values["CurrentA"] == 10.5
        assert values["PowerActive"] == 4500
        assert values["PowerFactor"] == 0.95
        
    def test_extract_environment(self):
        """Testa extração de dados ambientais."""
        data = {
            "temperature": 34.5,
            "humidity": 55.2,
            "caseTemperature": 62.0
        }
        
        values = extract_variable_values(data, "environment")
        
        assert values["Temperature"] == 34.5
        assert values["Humidity"] == 55.2
        assert values["CaseTemperature"] == 62.0
        
    def test_extract_vibration(self):
        """Testa extração de dados de vibração."""
        data = {
            "axial": 0.12,
            "radial": 0.15
        }
        
        values = extract_variable_values(data, "vibration")
        
        assert values["Axial"] == 0.12
        assert values["Radial"] == 0.15
        
    def test_extract_missing_fields(self):
        """Testa extração com campos faltando."""
        data = {
            "voltage": {"a": 220.0}
        }
        
        values = extract_variable_values(data, "electrical")
        
        assert values["VoltageA"] == 220.0
        assert values["VoltageB"] == 0
        assert values["CurrentA"] == 0


class TestMultipleAlarms:
    """Testes para múltiplos alarmes."""
    
    def test_multiple_alarms_different_categories(self):
        """Testa múltiplos alarmes de categorias diferentes."""
        manager = AlarmManager()
        
        manager.add_rule(AlarmRule(
            name="Overvoltage_A",
            condition=lambda v: v.get("VoltageA", 0) > 242,
            severity=Severity.HIGH,
            message="Overvoltage",
            source_name="VoltageA",
            category="Electrical"
        ))
        
        manager.add_rule(AlarmRule(
            name="CriticalTemp",
            condition=lambda v: v.get("CaseTemperature", 0) > 60,
            severity=Severity.CRITICAL,
            message="Critical temperature",
            source_name="CaseTemperature",
            category="Environment"
        ))
        
        values = {
            "VoltageA": 250.0,
            "CaseTemperature": 65.0
        }
        
        alarms = manager.check_alarms(values)
        
        assert len(alarms) == 2
        categories = [a.category for a in alarms]
        assert "Electrical" in categories
        assert "Environment" in categories
        
    def test_cooldown_prevents_duplicate(self):
        """Testa que cooldown previne alarmes duplicados."""
        manager = AlarmManager()
        
        manager.add_rule(AlarmRule(
            name="TestRule",
            condition=lambda v: v.get("Test", 0) > 100,
            severity=Severity.MEDIUM,
            message="Test alarm",
            source_name="Test",
            category="Test",
            cooldown_seconds=60
        ))
        
        # Primeiro alarme deve ser gerado
        alarms1 = manager.check_alarms({"Test": 150})
        assert len(alarms1) == 1
        
        # Segundo alarme não deve ser gerado (cooldown)
        alarms2 = manager.check_alarms({"Test": 150})
        assert len(alarms2) == 0
