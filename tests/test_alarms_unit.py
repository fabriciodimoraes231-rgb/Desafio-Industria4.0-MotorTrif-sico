"""
Testes unitários para alarms.py.

Testa as classes Severity, AlarmEvent, AlarmRule e AlarmManager.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone

# Import direto - conftest.py adiciona opcua_server ao sys.path
from alarms import Severity, AlarmEvent, AlarmRule, AlarmManager


class TestSeverity:
    """Testes para enum Severity."""
    
    def test_severity_values(self):
        """Testa valores dos níveis de severidade."""
        assert Severity.INFORMATIVE == 100
        assert Severity.LOW == 250
        assert Severity.MEDIUM == 500
        assert Severity.HIGH == 700
        assert Severity.CRITICAL == 900
    
    def test_severity_ordering(self):
        """Testa ordenação de severidade."""
        assert Severity.INFORMATIVE < Severity.LOW
        assert Severity.LOW < Severity.MEDIUM
        assert Severity.MEDIUM < Severity.HIGH
        assert Severity.HIGH < Severity.CRITICAL
    
    def test_severity_names(self):
        """Testa nomes das severidades."""
        assert Severity.INFORMATIVE.name == "INFORMATIVE"
        assert Severity.LOW.name == "LOW"
        assert Severity.MEDIUM.name == "MEDIUM"
        assert Severity.HIGH.name == "HIGH"
        assert Severity.CRITICAL.name == "CRITICAL"


class TestAlarmEvent:
    """Testes para dataclass AlarmEvent."""
    
    def test_alarm_event_creation(self):
        """Testa criação de AlarmEvent."""
        now = datetime.now(timezone.utc)
        alarm = AlarmEvent(
            timestamp=now,
            category="Electrical",
            severity=Severity.HIGH,
            message="Overvoltage on phase A",
            source_name="VoltageA",
            value=250.0
        )
        
        assert alarm.timestamp == now
        assert alarm.category == "Electrical"
        assert alarm.severity == Severity.HIGH
        assert alarm.message == "Overvoltage on phase A"
        assert alarm.source_name == "VoltageA"
        assert alarm.value == 250.0
        assert alarm.acknowledged is False
    
    def test_alarm_event_id_generation(self):
        """Testa geração automática de ID."""
        now = datetime.now(timezone.utc)
        alarm = AlarmEvent(
            timestamp=now,
            category="Electrical",
            severity=Severity.HIGH,
            message="Test",
            source_name="VoltageA",
            value=250.0
        )
        
        assert alarm.id is not None
        assert "VoltageA" in alarm.id
    
    def test_alarm_event_custom_id(self):
        """Testa ID customizado."""
        alarm = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.HIGH,
            message="Test",
            source_name="VoltageA",
            value=250.0,
            id="custom-id-123"
        )
        
        assert alarm.id == "custom-id-123"
    
    def test_alarm_event_to_dict(self):
        """Testa conversão para dicionário."""
        now = datetime.now(timezone.utc)
        alarm = AlarmEvent(
            timestamp=now,
            category="Electrical",
            severity=Severity.HIGH,
            message="Overvoltage",
            source_name="VoltageA",
            value=250.0,
            id="alarm-123"
        )
        
        result = alarm.to_dict()
        
        assert result["id"] == "alarm-123"
        assert result["category"] == "Electrical"
        assert result["severity"] == 700  # HIGH value
        assert result["severity_name"] == "HIGH"
        assert result["message"] == "Overvoltage"
        assert result["source_name"] == "VoltageA"
        assert result["value"] == 250.0
        assert result["acknowledged"] is False
    
    def test_alarm_event_acknowledged_true(self):
        """Testa alarme reconhecido."""
        alarm = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.LOW,
            message="Test",
            source_name="VoltageA",
            value=200.0,
            acknowledged=True
        )
        
        assert alarm.acknowledged is True
        assert alarm.to_dict()["acknowledged"] is True


class TestAlarmRule:
    """Testes para AlarmRule."""
    
    def test_alarm_rule_creation(self):
        """Testa criação de AlarmRule."""
        rule = AlarmRule(
            name="Overvoltage_A",
            variable_name="VoltageA",
            category="Electrical",
            severity=Severity.HIGH,
            message_template="Overvoltage: {value:.1f}V",
            condition=lambda v: v > 242
        )
        
        assert rule.name == "Overvoltage_A"
        assert rule.variable_name == "VoltageA"
        assert rule.category == "Electrical"
        assert rule.severity == Severity.HIGH
    
    def test_alarm_rule_evaluate_true(self):
        """Testa avaliação de regra - condição atingida."""
        rule = AlarmRule(
            name="Overvoltage_A",
            variable_name="VoltageA",
            category="Electrical",
            severity=Severity.HIGH,
            message_template="Overvoltage: {value:.1f}V",
            condition=lambda v: v > 242
        )
        
        assert rule.evaluate(250) is True
        assert rule.evaluate(243) is True
    
    def test_alarm_rule_evaluate_false(self):
        """Testa avaliação de regra - condição não atingida."""
        rule = AlarmRule(
            name="Overvoltage_A",
            variable_name="VoltageA",
            category="Electrical",
            severity=Severity.HIGH,
            message_template="Overvoltage: {value:.1f}V",
            condition=lambda v: v > 242
        )
        
        assert rule.evaluate(220) is False
        assert rule.evaluate(242) is False
        assert rule.evaluate(200) is False
    
    def test_alarm_rule_get_message(self):
        """Testa geração de mensagem."""
        rule = AlarmRule(
            name="Overvoltage_A",
            variable_name="VoltageA",
            category="Electrical",
            severity=Severity.HIGH,
            message_template="Overvoltage: {value:.1f}V",
            condition=lambda v: v > 242
        )
        
        message = rule.get_message(250.5)
        assert "250.5" in message
        assert "Overvoltage" in message
    
    def test_alarm_rule_undervoltage(self):
        """Testa regra de subtensão."""
        rule = AlarmRule(
            name="Undervoltage_A",
            variable_name="VoltageA",
            category="Electrical",
            severity=Severity.HIGH,
            message_template="Undervoltage: {value:.1f}V",
            condition=lambda v: v < 198
        )
        
        assert rule.evaluate(190) is True
        assert rule.evaluate(197) is True
        assert rule.evaluate(198) is False
        assert rule.evaluate(220) is False
    
    def test_alarm_rule_overcurrent(self):
        """Testa regra de sobrecorrente."""
        rule = AlarmRule(
            name="Overcurrent_A",
            variable_name="CurrentA",
            category="Electrical",
            severity=Severity.CRITICAL,
            message_template="Overcurrent: {value:.1f}A",
            condition=lambda v: v > 100
        )
        
        assert rule.evaluate(110) is True
        assert rule.evaluate(100) is False
        assert rule.evaluate(50) is False
    
    def test_alarm_rule_overtemperature(self):
        """Testa regra de sobretemperatura."""
        rule = AlarmRule(
            name="Overtemperature",
            variable_name="CaseTemperature",
            category="Environment",
            severity=Severity.HIGH,
            message_template="Overtemperature: {value:.1f}°C",
            condition=lambda v: v > 80
        )
        
        assert rule.evaluate(85) is True
        assert rule.evaluate(80) is False
        assert rule.evaluate(60) is False


class TestAlarmManagerInit:
    """Testes de inicialização do AlarmManager."""
    
    def test_alarm_manager_creation(self):
        """Testa criação do AlarmManager."""
        mock_server = MagicMock()
        mock_nodes = {"VoltageA": MagicMock()}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        assert manager.server == mock_server
        assert manager.nodes == mock_nodes
        assert manager.settings == mock_settings
    
    def test_alarm_manager_empty_nodes(self):
        """Testa criação com nodes vazios."""
        mock_server = MagicMock()
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, {}, mock_settings)
        
        assert manager.nodes == {}


class TestAlarmManagerCheckValues:
    """Testes para check_values do AlarmManager."""
    
    @pytest.mark.asyncio
    async def test_check_values_no_rules(self):
        """Testa check_values sem regras."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        manager.rules = []  # Sem regras
        
        values = {"VoltageA": 250.0}
        alarms = await manager.check_values(values)
        
        assert alarms == []
    
    @pytest.mark.asyncio
    async def test_check_values_normal_values(self):
        """Testa check_values com valores normais."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        manager.rules = [
            AlarmRule(
                name="Overvoltage",
                variable_name="VoltageA",
                category="Electrical",
                severity=Severity.HIGH,
                message_template="Overvoltage: {value:.1f}V",
                condition=lambda v: v > 242
            )
        ]
        manager._active_alarms = {}
        manager._alarm_callback = None
        
        values = {"VoltageA": 220.0}  # Valor normal
        alarms = await manager.check_values(values)
        
        assert alarms == []


class TestAlarmManagerActiveAlarms:
    """Testes para gerenciamento de alarmes ativos."""
    
    def test_get_active_alarms_empty(self):
        """Testa get_active_alarms sem alarmes."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        manager._active_alarms = {}
        
        result = manager.get_active_alarms()
        
        assert result == []
    
    def test_get_active_alarms_with_alarms(self):
        """Testa get_active_alarms com alarmes."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        alarm = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.HIGH,
            message="Test alarm",
            source_name="VoltageA",
            value=250.0
        )
        manager.active_alarms = {"test_rule": alarm}
        
        result = manager.get_active_alarms()
        
        assert len(result) == 1
        assert result[0]["category"] == "Electrical"


class TestAlarmManagerGetAlarmHistory:
    """Testes para get_alarm_history."""
    
    def test_get_alarm_history_empty(self):
        """Testa histórico vazio."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        manager.alarm_history = []
        
        result = manager.get_alarm_history()
        
        assert result == []
    
    def test_get_alarm_history_with_alarms(self):
        """Testa histórico com alarmes."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        alarm1 = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.HIGH,
            message="Test 1",
            source_name="VoltageA",
            value=250.0
        )
        alarm2 = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Environment",
            severity=Severity.MEDIUM,
            message="Test 2",
            source_name="Temperature",
            value=80.0
        )
        manager.alarm_history = [alarm1, alarm2]
        
        result = manager.get_alarm_history()
        
        assert len(result) == 2
    
    def test_get_alarm_history_with_category_filter(self):
        """Testa histórico com filtro de categoria."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        alarm1 = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.HIGH,
            message="Test 1",
            source_name="VoltageA",
            value=250.0
        )
        alarm2 = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Environment",
            severity=Severity.MEDIUM,
            message="Test 2",
            source_name="Temperature",
            value=80.0
        )
        manager.alarm_history = [alarm1, alarm2]
        
        result = manager.get_alarm_history(category="Electrical")
        
        assert len(result) == 1
        assert result[0]["category"] == "Electrical"
    
    def test_get_alarm_history_with_severity_filter(self):
        """Testa histórico com filtro de severidade."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        alarm1 = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.HIGH,
            message="Test 1",
            source_name="VoltageA",
            value=250.0
        )
        alarm2 = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Environment",
            severity=Severity.LOW,
            message="Test 2",
            source_name="Temperature",
            value=30.0
        )
        manager.alarm_history = [alarm1, alarm2]
        
        result = manager.get_alarm_history(severity=Severity.MEDIUM)
        
        assert len(result) == 1
        assert result[0]["severity"] == 700
    
    def test_get_alarm_history_with_limit(self):
        """Testa histórico com limite."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        # Criar 5 alarmes
        manager.alarm_history = [
            AlarmEvent(
                timestamp=datetime.now(timezone.utc),
                category="Electrical",
                severity=Severity.HIGH,
                message=f"Test {i}",
                source_name="VoltageA",
                value=250.0
            ) for i in range(5)
        ]
        
        result = manager.get_alarm_history(limit=2)
        
        assert len(result) == 2


class TestAlarmManagerAcknowledgeAlarm:
    """Testes para acknowledge_alarm."""
    
    def test_acknowledge_alarm_success(self):
        """Testa reconhecimento de alarme com sucesso."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        alarm = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.HIGH,
            message="Test",
            source_name="VoltageA",
            value=250.0,
            id="alarm-123"
        )
        manager.active_alarms = {"test_rule": alarm}
        
        result = manager.acknowledge_alarm("alarm-123")
        
        assert result is True
        assert alarm.acknowledged is True
    
    def test_acknowledge_alarm_not_found(self):
        """Testa reconhecimento de alarme não encontrado."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        manager.active_alarms = {}
        
        result = manager.acknowledge_alarm("nonexistent")
        
        assert result is False


class TestAlarmManagerClearHistory:
    """Testes para clear_history."""
    
    def test_clear_history(self):
        """Testa limpeza do histórico."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        alarm = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.HIGH,
            message="Test",
            source_name="VoltageA",
            value=250.0
        )
        manager.alarm_history = [alarm]
        
        manager.clear_history()
        
        assert len(manager.alarm_history) == 0


class TestAlarmManagerGenerateEvent:
    """Testes para generate_event."""
    
    @pytest.mark.asyncio
    async def test_generate_event_success(self):
        """Testa geração de evento com sucesso."""
        mock_server = AsyncMock()
        mock_event_generator = AsyncMock()
        mock_event_generator.event = MagicMock()
        mock_server.get_event_generator = AsyncMock(return_value=mock_event_generator)
        mock_server.nodes = MagicMock()
        
        mock_nodes = {"Motor50CV": MagicMock()}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        alarm = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.HIGH,
            message="Test",
            source_name="VoltageA",
            value=250.0
        )
        
        await manager.generate_event(alarm)
        
        mock_event_generator.trigger.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_event_error(self):
        """Testa tratamento de erro na geração de evento."""
        mock_server = AsyncMock()
        mock_server.get_event_generator = AsyncMock(side_effect=Exception("Error"))
        mock_server.nodes = MagicMock()
        
        mock_nodes = {"Motor50CV": MagicMock()}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        alarm = AlarmEvent(
            timestamp=datetime.now(timezone.utc),
            category="Electrical",
            severity=Severity.HIGH,
            message="Test",
            source_name="VoltageA",
            value=250.0
        )
        
        # Não deve propagar exceção
        await manager.generate_event(alarm)


class TestAlarmManagerSetAlarmCallback:
    """Testes para set_alarm_callback."""
    
    def test_set_alarm_callback(self):
        """Testa definição de callback."""
        mock_server = MagicMock()
        mock_nodes = {}
        mock_settings = MagicMock()
        
        manager = AlarmManager(mock_server, mock_nodes, mock_settings)
        
        callback = MagicMock()
        manager.set_alarm_callback(callback)
        
        assert manager._on_alarm_callback == callback