"""
Testes unitários para o servidor OPC UA usando mocks.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'opcua_server'))


class TestOPCUAServerUnit:
    """Testes de unidade do servidor OPC UA."""
    
    def test_server_import(self):
        """Testa que o módulo pode ser importado."""
        from server import OPCUAServer
        assert OPCUAServer is not None
        
    def test_server_class_exists(self):
        """Testa que a classe existe."""
        from server import OPCUAServer
        assert callable(OPCUAServer)

    def test_server_initial_state(self):
        """Testa estado inicial do servidor."""
        with patch('server.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                opcua_endpoint="opc.tcp://0.0.0.0:4840"
            )
            
            from server import OPCUAServer
            server = OPCUAServer(settings=mock_settings.return_value)
            
            assert server.server is None
            assert server.namespace_idx is None
            assert server.nodes == {}
            assert server._running is False

    def test_server_stats_initial(self):
        """Testa estatísticas iniciais."""
        with patch('server.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                opcua_endpoint="opc.tcp://0.0.0.0:4840"
            )
            
            from server import OPCUAServer
            server = OPCUAServer(settings=mock_settings.return_value)
            
            assert server._stats["messages_processed"] == 0
            assert server._stats["alarms_generated"] == 0
            assert server._stats["history_records"] == 0


class TestOPCUAServerStartStop:
    """Testes de start/stop mockados."""
    
    @pytest.mark.asyncio
    async def test_start_server(self):
        """Testa início do servidor."""
        with patch('server.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                opcua_endpoint="opc.tcp://0.0.0.0:4840"
            )
            
            from server import OPCUAServer
            server = OPCUAServer(settings=mock_settings.return_value)
            
            mock_opcua = AsyncMock()
            server.server = mock_opcua
            server._running = False
            
            # Mockar componentes
            server.rabbitmq_consumer = MagicMock()
            server.rabbitmq_consumer.connect = AsyncMock()
            server._lds_task = None
            
            await server.start()
            
            mock_opcua.start.assert_called_once()
            assert server._running is True

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Testa que start não faz nada se já rodando."""
        with patch('server.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                opcua_endpoint="opc.tcp://0.0.0.0:4840"
            )
            
            from server import OPCUAServer
            server = OPCUAServer(settings=mock_settings.return_value)
            
            mock_opcua = AsyncMock()
            server.server = mock_opcua
            server._running = True
            
            await server.start()
            
            mock_opcua.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_server(self):
        """Testa parada do servidor."""
        with patch('server.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from server import OPCUAServer
            server = OPCUAServer(settings=mock_settings.return_value)
            
            mock_opcua = AsyncMock()
            server.server = mock_opcua
            server._running = True
            server._lds_task = None
            
            server.rabbitmq_consumer = AsyncMock()
            server.history_storage = AsyncMock()
            
            await server.stop()
            
            mock_opcua.stop.assert_called_once()
            assert server._running is False


class TestNodesetBuilder:
    """Testes do NodesetBuilder."""
    
    def test_nodeset_import(self):
        """Testa que o módulo pode ser importado."""
        from nodeset import NodesetBuilder
        assert NodesetBuilder is not None
        
    def test_nodeset_class_exists(self):
        """Testa que a classe existe."""
        from nodeset import NodesetBuilder
        assert callable(NodesetBuilder)


class TestRabbitMQConsumer:
    """Testes do RabbitMQ Consumer."""
    
    def test_consumer_import(self):
        """Testa que o módulo pode ser importado."""
        from rabbitmq_consumer import RabbitMQConsumer
        assert RabbitMQConsumer is not None
        
    def test_extract_variable_values_import(self):
        """Testa que a função de extração pode ser importada."""
        from rabbitmq_consumer import extract_variable_values
        assert callable(extract_variable_values)
        
    def test_extract_electrical_values(self):
        """Testa extração de valores elétricos."""
        from rabbitmq_consumer import extract_variable_values
        
        data = {
            "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
            "current": {"a": 50.0, "b": 51.0, "c": 49.0},
            "power": {"active": 30000, "reactive": 5000, "apparent": 30413},
            "energy": {"active": 1000, "reactive": 100, "apparent": 1005},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        values = extract_variable_values("electrical", data)
        
        assert "VoltageA" in values
        assert values["VoltageA"] == 220.0
        
    def test_extract_environment_values(self):
        """Testa extração de valores ambientais."""
        from rabbitmq_consumer import extract_variable_values
        
        data = {
            "temperature": 35.5,
            "humidity": 60.0,
            "caseTemperature": 45.0
        }
        
        values = extract_variable_values("environment", data)
        
        assert "Temperature" in values
        assert values["Temperature"] == 35.5
        
    def test_extract_vibration_values(self):
        """Testa extração de valores de vibração."""
        from rabbitmq_consumer import extract_variable_values
        
        data = {
            "axial": 0.5,
            "radial": 0.3
        }
        
        values = extract_variable_values("vibration", data)
        
        assert "Axial" in values
        assert values["Axial"] == 0.5


class TestHistoryStorage:
    """Testes do HistoryStorage."""
    
    def test_history_import(self):
        """Testa que o módulo pode ser importado."""
        from history_storage import HistoryStorageSQLite
        assert HistoryStorageSQLite is not None
        
    def test_history_class_exists(self):
        """Testa que a classe existe."""
        from history_storage import HistoryStorageSQLite
        assert callable(HistoryStorageSQLite)
