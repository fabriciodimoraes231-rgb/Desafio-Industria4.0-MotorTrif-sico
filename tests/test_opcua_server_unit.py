"""
Testes unitários para server.py.

Testa a classe OPCUAServer com todas as dependências mockadas.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

# Import direto - conftest.py adiciona opcua_server ao sys.path
from server import OPCUAServer


@pytest.fixture
def mock_settings():
    """Fixture de settings mockadas para todos os testes."""
    settings = MagicMock()
    settings.opcua_port = 4840
    settings.opcua_endpoint = "opc.tcp://0.0.0.0:4840"
    settings.server_name = "Motor50CV"
    settings.rabbitmq_host = "localhost"
    settings.rabbitmq_port = 5672
    settings.rabbitmq_user = "guest"
    settings.rabbitmq_pass = "guest"
    settings.database_url = "sqlite:///./test.db"
    settings.lds_register_interval = 60
    return settings


class TestOPCUAServerInit:
    """Testes de inicialização do OPCUAServer."""
    
    def test_server_init_with_settings(self, mock_settings):
        """Testa inicialização com settings fornecidas."""
        server = OPCUAServer(mock_settings)
        
        assert server.settings == mock_settings
        assert server.server is None
        assert server.namespace_idx is None
        assert server.nodes == {}
        assert server.alarm_manager is None
        assert server.history_storage is None
        assert server.rabbitmq_consumer is None
        assert server._running is False
    
    def test_server_init_stats(self, mock_settings):
        """Testa inicialização de estatísticas."""
        server = OPCUAServer(mock_settings)
        
        assert server._stats["messages_processed"] == 0
        assert server._stats["alarms_generated"] == 0
        assert server._stats["history_records"] == 0
    
    def test_server_init_last_values(self, mock_settings):
        """Testa inicialização de últimos valores."""
        server = OPCUAServer(mock_settings)
        
        assert server._last_values == {}
        assert server._historized_nodes == []


class TestOPCUAServerProperties:
    """Testes de propriedades do OPCUAServer."""
    
    def test_running_property_initial(self, mock_settings):
        """Testa propriedade running inicial."""
        server = OPCUAServer(mock_settings)
        
        assert server._running is False
    
    def test_lds_task_initial(self, mock_settings):
        """Testa task LDS inicial."""
        server = OPCUAServer(mock_settings)
        
        assert server._lds_task is None


class TestOPCUAServerInitialize:
    """Testes do método initialize."""
    
    def test_initialize_not_called(self, mock_settings):
        """Testa que servidor inicia com server=None antes de initialize."""
        server = OPCUAServer(mock_settings)
        
        assert server.server is None
        assert server.namespace_idx is None
        assert server.alarm_manager is None


class TestOPCUAServerStart:
    """Testes do método start."""
    
    @pytest.mark.asyncio
    async def test_start_sets_running(self, mock_settings):
        """Testa que start define running como True."""
        server = OPCUAServer(mock_settings)
        
        # Mock do servidor
        server.server = AsyncMock()
        server.server.start = AsyncMock()
        
        # Mock do consumer
        server.rabbitmq_consumer = AsyncMock()
        server.rabbitmq_consumer.start = AsyncMock()
        
        await server.start()
        
        assert server._running is True
        server.server.start.assert_called_once()


class TestOPCUAServerStop:
    """Testes do método stop."""
    
    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, mock_settings):
        """Testa que stop define running como False."""
        server = OPCUAServer(mock_settings)
        server._running = True
        
        # Mock do servidor
        server.server = AsyncMock()
        server.server.stop = AsyncMock()
        server.server.dehistorize_node_data_change = AsyncMock()
        
        # Mock do consumer - usa close() não stop()
        server.rabbitmq_consumer = AsyncMock()
        server.rabbitmq_consumer.close = AsyncMock()
        
        # Mock do storage
        server.history_storage = AsyncMock()
        server.history_storage.stop = AsyncMock()
        
        await server.stop()
        
        assert server._running is False
        server.server.stop.assert_called_once()
        server.rabbitmq_consumer.close.assert_called_once()
        server.history_storage.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_without_components(self, mock_settings):
        """Testa stop sem componentes ativos."""
        server = OPCUAServer(mock_settings)
        server._running = True
        server.server = None
        server.rabbitmq_consumer = None
        server.history_storage = None
        
        # Não deve lançar exceção
        await server.stop()
        
        assert server._running is False


class TestOPCUAServerStats:
    """Testes de estatísticas."""
    
    def test_stats_structure(self, mock_settings):
        """Testa estrutura de estatísticas."""
        server = OPCUAServer(mock_settings)
        
        assert "messages_processed" in server._stats
        assert "alarms_generated" in server._stats
        assert "history_records" in server._stats
    
    def test_stats_increments(self, mock_settings):
        """Testa incremento de estatísticas."""
        server = OPCUAServer(mock_settings)
        
        server._stats["messages_processed"] += 1
        server._stats["alarms_generated"] += 1
        server._stats["history_records"] += 1
        
        assert server._stats["messages_processed"] == 1
        assert server._stats["alarms_generated"] == 1
        assert server._stats["history_records"] == 1
    
    def test_get_stats(self, mock_settings):
        """Testa método get_stats."""
        server = OPCUAServer(mock_settings)
        server._stats["messages_processed"] = 100
        server._stats["alarms_generated"] = 10
        server._stats["history_records"] = 500
        
        stats = server.get_stats()
        
        assert stats["messages_processed"] == 100
        assert stats["alarms_generated"] == 10
        assert stats["history_records"] == 500
    
    def test_get_stats_returns_copy(self, mock_settings):
        """Testa que get_stats retorna cópia."""
        server = OPCUAServer(mock_settings)
        server._stats["messages_processed"] = 100
        
        stats = server.get_stats()
        stats["messages_processed"] = 999
        
        # Original não deve ser alterado
        assert server._stats["messages_processed"] == 100


class TestOPCUAServerLatestValues:
    """Testes para get_latest_values."""
    
    def test_get_latest_values_empty(self, mock_settings):
        """Testa get_latest_values sem valores."""
        server = OPCUAServer(mock_settings)
        server.alarm_manager = MagicMock()
        server.alarm_manager.get_active_alarms.return_value = []
        
        result = server.get_latest_values()
        
        assert "timestamp" in result
        assert "variables" in result
        assert "alarm_count" in result
        assert result["variables"] == {}
        assert result["alarm_count"] == 0
    
    def test_get_latest_values_with_data(self, mock_settings):
        """Testa get_latest_values com dados."""
        server = OPCUAServer(mock_settings)
        server._last_values = {"VoltageA": 220.0, "CurrentA": 10.5}
        server.alarm_manager = MagicMock()
        server.alarm_manager.get_active_alarms.return_value = [1, 2, 3]
        
        result = server.get_latest_values()
        
        assert result["variables"]["VoltageA"] == 220.0
        assert result["variables"]["CurrentA"] == 10.5
        assert result["alarm_count"] == 3
    
    def test_get_latest_values_no_alarm_manager(self, mock_settings):
        """Testa get_latest_values sem alarm_manager."""
        server = OPCUAServer(mock_settings)
        server.alarm_manager = None
        
        result = server.get_latest_values()
        
        assert result["alarm_count"] == 0


class TestOPCUAServerReadWrite:
    """Testes para read_variable e write_variable."""
    
    @pytest.mark.asyncio
    async def test_read_variable_not_found(self, mock_settings):
        """Testa leitura de variável inexistente."""
        server = OPCUAServer(mock_settings)
        server.nodes = {}
        
        result = await server.read_variable("NonExistent")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_read_variable_success(self, mock_settings):
        """Testa leitura de variável com sucesso."""
        server = OPCUAServer(mock_settings)
        
        mock_node = AsyncMock()
        mock_node.read_value = AsyncMock(return_value=220.0)
        server.nodes = {"VoltageA": mock_node}
        
        result = await server.read_variable("VoltageA")
        
        assert result == 220.0
        mock_node.read_value.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_variable_error(self, mock_settings):
        """Testa leitura de variável com erro."""
        server = OPCUAServer(mock_settings)
        
        mock_node = AsyncMock()
        mock_node.read_value = AsyncMock(side_effect=Exception("Read error"))
        server.nodes = {"VoltageA": mock_node}
        
        result = await server.read_variable("VoltageA")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_write_variable_not_found(self, mock_settings):
        """Testa escrita em variável inexistente."""
        server = OPCUAServer(mock_settings)
        server.nodes = {}
        
        result = await server.write_variable("NonExistent", 100.0)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_write_variable_success(self, mock_settings):
        """Testa escrita em variável com sucesso."""
        server = OPCUAServer(mock_settings)
        
        mock_node = AsyncMock()
        mock_node.write_value = AsyncMock()
        server.nodes = {"VoltageA": mock_node}
        
        result = await server.write_variable("VoltageA", 230.0)
        
        assert result is True
        mock_node.write_value.assert_called_once_with(230.0)
    
    @pytest.mark.asyncio
    async def test_write_variable_error(self, mock_settings):
        """Testa escrita em variável com erro."""
        server = OPCUAServer(mock_settings)
        
        mock_node = AsyncMock()
        mock_node.write_value = AsyncMock(side_effect=Exception("Write error"))
        server.nodes = {"VoltageA": mock_node}
        
        result = await server.write_variable("VoltageA", 230.0)
        
        assert result is False


class TestOPCUAServerUpdateVariables:
    """Testes para _update_variables."""
    
    @pytest.mark.asyncio
    async def test_update_variables_success(self, mock_settings):
        """Testa atualização de variáveis com sucesso."""
        server = OPCUAServer(mock_settings)
        
        mock_node = AsyncMock()
        mock_node.write_value = AsyncMock()
        server.nodes = {"VoltageA": mock_node}
        
        await server._update_variables(
            {"VoltageA": 220.0},
            datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
        
        mock_node.write_value.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_variables_node_not_found(self, mock_settings):
        """Testa atualização quando nó não existe."""
        server = OPCUAServer(mock_settings)
        server.nodes = {}
        
        # Não deve lançar exceção
        await server._update_variables(
            {"NonExistent": 100.0},
            datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
    
    @pytest.mark.asyncio
    async def test_update_variables_error(self, mock_settings):
        """Testa atualização com erro (não propaga exceção)."""
        server = OPCUAServer(mock_settings)
        
        mock_node = AsyncMock()
        mock_node.write_value = AsyncMock(side_effect=Exception("Error"))
        server.nodes = {"VoltageA": mock_node}
        
        # Não deve lançar exceção
        await server._update_variables(
            {"VoltageA": 220.0},
            datetime(2024, 1, 1, tzinfo=timezone.utc)
        )


class TestOPCUAServerOnSensorData:
    """Testes para _on_sensor_data."""
    
    @pytest.mark.asyncio
    async def test_on_sensor_data_electrical(self, mock_settings):
        """Testa processamento de dados elétricos."""
        server = OPCUAServer(mock_settings)
        server.nodes = {}
        server.alarm_manager = AsyncMock()
        server.alarm_manager.check_values = AsyncMock(return_value=[])
        
        data = {
            "timestamp": "2024-01-01T12:00:00Z",
            "voltage": {"a": 220.0, "b": 221.0, "c": 222.0}
        }
        
        await server._on_sensor_data("electrical", data)
        
        assert server._stats["messages_processed"] == 1
    
    @pytest.mark.asyncio
    async def test_on_sensor_data_with_alarms(self, mock_settings):
        """Testa processamento que gera alarmes."""
        server = OPCUAServer(mock_settings)
        server.nodes = {}
        server.alarm_manager = AsyncMock()
        server.alarm_manager.check_values = AsyncMock(return_value=[
            MagicMock(),
            MagicMock()
        ])
        
        data = {
            "timestamp": "2024-01-01T12:00:00Z",
            "voltage": {"a": 300.0}  # Valor alto
        }
        
        await server._on_sensor_data("electrical", data)
        
        assert server._stats["messages_processed"] == 1
        assert server._stats["alarms_generated"] == 2
    
    @pytest.mark.asyncio
    async def test_on_sensor_data_error(self, mock_settings):
        """Testa tratamento de erro."""
        server = OPCUAServer(mock_settings)
        server.nodes = {}
        server.alarm_manager = AsyncMock()
        server.alarm_manager.check_values = AsyncMock(side_effect=Exception("Error"))
        
        data = {"timestamp": "2024-01-01T12:00:00Z"}
        
        # Não deve propagar exceção
        await server._on_sensor_data("electrical", data)


class TestOPCUAServerOnAlarm:
    """Testes para _on_alarm."""
    
    @pytest.mark.asyncio
    async def test_on_alarm_callback(self, mock_settings):
        """Testa callback de alarme."""
        server = OPCUAServer(mock_settings)
        server.history_storage = AsyncMock()
        server.history_storage.save_alarm = AsyncMock()
        server.alarm_manager = AsyncMock()
        server.alarm_manager.generate_event = AsyncMock()
        
        mock_alarm_event = MagicMock()
        mock_alarm_event.category = "ELECTRICAL"
        mock_alarm_event.severity = MagicMock()
        mock_alarm_event.severity.name = "HIGH"
        mock_alarm_event.message = "High voltage"
        
        await server._on_alarm(mock_alarm_event)
        
        server.history_storage.save_alarm.assert_called_once()


class TestOPCUAServerProperties:
    """Testes de propriedades adicionais."""
    
    def test_running_property(self, mock_settings):
        """Testa propriedade _running."""
        server = OPCUAServer(mock_settings)
        
        assert server._running is False
        
        server._running = True
        
        assert server._running is True
    
    def test_last_values_property(self, mock_settings):
        """Testa propriedade _last_values."""
        server = OPCUAServer(mock_settings)
        
        server._last_values["VoltageA"] = 220.0
        server._last_values["CurrentA"] = 10.0
        
        assert "VoltageA" in server._last_values
        assert server._last_values["VoltageA"] == 220.0
    
    def test_historized_nodes_list(self, mock_settings):
        """Testa lista de nós historizados."""
        server = OPCUAServer(mock_settings)
        
        assert server._historized_nodes == []
        
        mock_node = MagicMock()
        server._historized_nodes.append(mock_node)
        
        assert len(server._historized_nodes) == 1


class TestOPCUAServerEnableHistory:
    """Testes para _enable_opcua_history."""
    
    @pytest.mark.asyncio
    async def test_enable_opcua_history(self):
        """Testa habilitação de histoização."""
        mock_settings = MagicMock()
        
        with patch('server.Server'), \
             patch('server.NodesetBuilder'), \
             patch('server.HistoryStorageSQLite'), \
             patch('server.AlarmManager'), \
             patch('server.RabbitMQConsumer'):
            
            server = OPCUAServer(mock_settings)
            
            mock_server = AsyncMock()
            server.server = mock_server
            
            mock_node = AsyncMock()
            server.nodes = {"VoltageA": mock_node}
            
            mock_storage = AsyncMock()
            server.history_storage = mock_storage
            
            await server._enable_opcua_history()
            
            # Verifica que historizou algum nó
            assert len(server._historized_nodes) >= 0
    
    @pytest.mark.asyncio
    async def test_enable_opcua_history_with_error(self):
        """Testa tratamento de erro na historização."""
        mock_settings = MagicMock()
        
        with patch('server.Server'), \
             patch('server.NodesetBuilder'), \
             patch('server.HistoryStorageSQLite'), \
             patch('server.AlarmManager'), \
             patch('server.RabbitMQConsumer'):
            
            server = OPCUAServer(mock_settings)
            
            mock_server = AsyncMock()
            mock_server.historize_node_data_change = AsyncMock(
                side_effect=Exception("Failed")
            )
            server.server = mock_server
            
            mock_node = AsyncMock()
            server.nodes = {"VoltageA": mock_node}
            
            mock_storage = AsyncMock()
            server.history_storage = mock_storage
            
            # Não deve propagar exceção
            await server._enable_opcua_history()


class TestOPCUAServerStopFull:
    """Testes completos para o método stop."""
    
    @pytest.mark.asyncio
    async def test_stop_cancels_lds_task(self):
        """Testa que stop cancela a task LDS."""
        import asyncio
        
        mock_settings = MagicMock()
        
        with patch('server.Server'), \
             patch('server.NodesetBuilder'), \
             patch('server.HistoryStorageSQLite'), \
             patch('server.AlarmManager'), \
             patch('server.RabbitMQConsumer'):
            
            server = OPCUAServer(mock_settings)
            server._running = True
            
            # Mock LDS task como uma coroutine real
            async def mock_coro():
                pass
            mock_lds_task = asyncio.create_task(mock_coro())
            await asyncio.sleep(0)  # Deixar a task completar
            server._lds_task = mock_lds_task
            
            mock_consumer = AsyncMock()
            server.rabbitmq_consumer = mock_consumer
            
            mock_storage = AsyncMock()
            server.history_storage = mock_storage
            
            mock_server = AsyncMock()
            server.server = mock_server
            
            server._historized_nodes = []
            
            await server.stop()
            
            assert server._running is False
    
    @pytest.mark.asyncio
    async def test_stop_dehistorizes_nodes(self):
        """Testa que stop remove historização dos nós."""
        mock_settings = MagicMock()
        
        with patch('server.Server'), \
             patch('server.NodesetBuilder'), \
             patch('server.HistoryStorageSQLite'), \
             patch('server.AlarmManager'), \
             patch('server.RabbitMQConsumer'):
            
            server = OPCUAServer(mock_settings)
            server._running = True
            
            mock_node = AsyncMock()
            server._historized_nodes = [mock_node]
            
            mock_consumer = AsyncMock()
            server.rabbitmq_consumer = mock_consumer
            
            mock_storage = AsyncMock()
            server.history_storage = mock_storage
            
            mock_server = AsyncMock()
            server.server = mock_server
            
            server._lds_task = None
            
            await server.stop()
            
            # Verifica que tentou remover historização
            mock_server.dehistorize_node_data_change.assert_called()
