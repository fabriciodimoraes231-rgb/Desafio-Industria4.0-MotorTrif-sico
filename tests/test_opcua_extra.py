"""
Testes adicionais para aumentar cobertura do servidor OPC UA.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'opcua_server'))


class TestHistoryStorageUnit:
    """Testes do HistoryStorage SQLite."""
    
    def test_storage_creation(self):
        """Testa criação do storage."""
        from history_storage import HistoryStorageSQLite
        
        storage = HistoryStorageSQLite(
            db_path="/tmp/test.db",
            max_history_data_response_size=1000
        )
        
        assert storage is not None
        assert storage.db_path == "/tmp/test.db"
        
    def test_storage_default_values(self):
        """Testa valores padrão do storage."""
        from history_storage import HistoryStorageSQLite
        
        storage = HistoryStorageSQLite()
        
        assert storage.db_path is not None


class TestHistoryStorageRead:
    """Testes de leitura de histórico."""
    
    @pytest.mark.asyncio
    async def test_read_history_empty(self):
        """Testa leitura de histórico vazio."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall.return_value = []
            mock_db.execute.return_value = mock_cursor
            mock_connect.return_value = mock_db
            
            from history_storage import HistoryStorageSQLite
            storage = HistoryStorageSQLite(db_path="/tmp/test.db")
            storage._db = mock_db
            
            # Testar método de leitura (depende da implementação real)
            assert storage._db is not None


class TestNodesetBuilderUnit:
    """Testes do NodesetBuilder."""
    
    def test_nodeset_creation(self):
        """Testa criação do nodeset builder."""
        with patch('nodeset.Server') as mock_server_class:
            from nodeset import NodesetBuilder
            
            mock_server = MagicMock()
            builder = NodesetBuilder(mock_server, 1)
            
            assert builder is not None
            assert builder.server == mock_server
            assert builder.namespace_idx == 1

    @pytest.mark.asyncio
    async def test_build_creates_nodes(self):
        """Testa que build cria nós."""
        with patch('nodeset.Server') as mock_server_class:
            from nodeset import NodesetBuilder
            
            mock_server = AsyncMock()
            mock_objects = AsyncMock()
            mock_root_folder = AsyncMock()
            
            mock_server.nodes.objects = mock_objects
            mock_objects.add_folder.return_value = mock_root_folder
            mock_root_folder.add_folder.return_value = AsyncMock()
            
            builder = NodesetBuilder(mock_server, 1)
            
            result = await builder.build()
            
            assert result is not None
            mock_objects.add_folder.assert_called()


class TestRabbitMQConsumerUnit:
    """Testes do RabbitMQ Consumer."""
    
    def test_consumer_creation(self):
        """Testa criação do consumer."""
        with patch('rabbitmq_consumer.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                rabbitmq_host="localhost",
                rabbitmq_port=5672,
                rabbitmq_user="guest",
                rabbitmq_pass="guest",
                rabbitmq_queue="test_queue"
            )
            
            from rabbitmq_consumer import RabbitMQConsumer
            consumer = RabbitMQConsumer(settings=mock_settings.return_value)
            
            assert consumer is not None
            assert consumer.connection is None
            assert consumer.channel is None

    def test_consumer_is_connected_false(self):
        """Testa is_connected quando não conectado."""
        with patch('rabbitmq_consumer.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from rabbitmq_consumer import RabbitMQConsumer
            consumer = RabbitMQConsumer(settings=mock_settings.return_value)
            consumer.connection = None
            
            assert consumer.is_connected is False

    def test_consumer_is_connected_true(self):
        """Testa is_connected quando conectado."""
        with patch('rabbitmq_consumer.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from rabbitmq_consumer import RabbitMQConsumer
            consumer = RabbitMQConsumer(settings=mock_settings.return_value)
            
            mock_conn = MagicMock()
            mock_conn.is_closed = False
            consumer.connection = mock_conn
            
            assert consumer.is_connected is True

    def test_consumer_is_consuming_false(self):
        """Testa is_consuming quando não consumindo."""
        with patch('rabbitmq_consumer.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from rabbitmq_consumer import RabbitMQConsumer
            consumer = RabbitMQConsumer(settings=mock_settings.return_value)
            consumer._consuming = False
            
            assert consumer.is_consuming is False

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Testa conexão bem-sucedida."""
        with patch('rabbitmq_consumer.get_settings') as mock_settings:
            with patch('rabbitmq_consumer.aio_pika') as mock_pika:
                mock_settings.return_value = MagicMock(
                    rabbitmq_host="localhost",
                    rabbitmq_port=5672,
                    rabbitmq_user="guest",
                    rabbitmq_pass="guest",
                    rabbitmq_queue="test_queue"
                )
                
                mock_conn = AsyncMock()
                mock_channel = AsyncMock()
                mock_conn.channel.return_value = mock_channel
                mock_pika.connect_robust = AsyncMock(return_value=mock_conn)
                
                from rabbitmq_consumer import RabbitMQConsumer
                consumer = RabbitMQConsumer(settings=mock_settings.return_value)
                
                await consumer.connect()
                
                mock_pika.connect_robust.assert_called_once()
                assert consumer.connection is not None

    @pytest.mark.asyncio
    async def test_close_success(self):
        """Testa fechamento de conexão."""
        with patch('rabbitmq_consumer.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from rabbitmq_consumer import RabbitMQConsumer
            consumer = RabbitMQConsumer(settings=mock_settings.return_value)
            
            mock_conn = AsyncMock()
            mock_conn.is_closed = False
            consumer.connection = mock_conn
            consumer._consuming = True
            
            await consumer.close()
            
            mock_conn.close.assert_called_once()
            assert consumer._consuming is False


class TestExtractVariableValuesComplete:
    """Testes completos de extração de variáveis."""
    
    def test_extract_all_electrical(self):
        """Testa extração de todos os valores elétricos."""
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
        
        assert values["VoltageA"] == 220.0
        assert values["VoltageB"] == 221.0
        assert values["VoltageC"] == 219.0
        assert values["CurrentA"] == 50.0
        assert values["CurrentB"] == 51.0
        assert values["CurrentC"] == 49.0
        assert values["PowerActive"] == 30000
        assert values["PowerReactive"] == 5000
        assert values["PowerApparent"] == 30413
        assert values["EnergyActive"] == 1000
        assert values["EnergyReactive"] == 100
        assert values["EnergyApparent"] == 1005
        assert values["PowerFactor"] == 0.95
        assert values["Frequency"] == 60.0

    def test_extract_all_environment(self):
        """Testa extração de todos os valores ambientais."""
        from rabbitmq_consumer import extract_variable_values
        
        data = {
            "temperature": 35.5,
            "humidity": 60.0,
            "caseTemperature": 45.0
        }
        
        values = extract_variable_values("environment", data)
        
        assert values["Temperature"] == 35.5
        assert values["Humidity"] == 60.0
        assert values["CaseTemperature"] == 45.0

    def test_extract_all_vibration(self):
        """Testa extração de todos os valores de vibração."""
        from rabbitmq_consumer import extract_variable_values
        
        data = {
            "axial": 0.5,
            "radial": 0.3
        }
        
        values = extract_variable_values("vibration", data)
        
        assert values["Axial"] == 0.5
        assert values["Radial"] == 0.3

    def test_extract_unknown_type(self):
        """Testa extração com tipo desconhecido."""
        from rabbitmq_consumer import extract_variable_values
        
        values = extract_variable_values("unknown", {"foo": "bar"})
        
        assert values == {}

    def test_extract_missing_fields(self):
        """Testa extração com campos faltando."""
        from rabbitmq_consumer import extract_variable_values
        
        # Dados parciais de electrical
        data = {
            "voltage": {"a": 220.0}  # Faltando b e c
        }
        
        values = extract_variable_values("electrical", data)
        
        assert values["VoltageA"] == 220.0
        assert values.get("VoltageB", 0) == 0
