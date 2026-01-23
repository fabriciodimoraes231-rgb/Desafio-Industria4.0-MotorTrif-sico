"""
Testes unitários adicionais para rabbitmq_consumer.py.

Testa a classe RabbitMQConsumer com mocks.
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

# Import direto - conftest.py adiciona opcua_server ao sys.path
from rabbitmq_consumer import RabbitMQConsumer, extract_variable_values


class TestRabbitMQConsumerInit:
    """Testes de inicialização do RabbitMQConsumer."""
    
    def test_consumer_init_with_settings(self):
        """Testa inicialização com settings."""
        mock_settings = MagicMock()
        mock_settings.rabbitmq_host = "localhost"
        mock_settings.rabbitmq_port = 5672
        mock_settings.rabbitmq_user = "admin"
        mock_settings.rabbitmq_pass = "admin123"
        
        consumer = RabbitMQConsumer(mock_settings)
        
        assert consumer.settings == mock_settings
        assert consumer.connection is None
        assert consumer.channel is None
        assert consumer.on_message_callback is None
        assert consumer._consuming is False
    
    def test_consumer_set_message_callback(self):
        """Testa definição de callback de mensagem."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        
        async def my_callback(sensor_type, data):
            pass
        
        consumer.set_message_callback(my_callback)
        
        assert consumer.on_message_callback == my_callback


class TestRabbitMQConsumerClose:
    """Testes de fechamento de conexão."""
    
    @pytest.mark.asyncio
    async def test_close_not_connected(self):
        """Testa close quando não está conectado."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        consumer.connection = None
        
        # Não deve lançar exceção
        await consumer.close()
        
        assert consumer._consuming is False
    
    @pytest.mark.asyncio
    async def test_close_connected(self):
        """Testa close quando está conectado."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        consumer._consuming = True
        
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.close = AsyncMock()
        consumer.connection = mock_connection
        
        await consumer.close()
        
        assert consumer._consuming is False
        mock_connection.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_already_closed(self):
        """Testa close quando conexão já está fechada."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        
        mock_connection = MagicMock()
        mock_connection.is_closed = True
        consumer.connection = mock_connection
        
        # Não deve chamar close
        await consumer.close()
        
        assert consumer._consuming is False


class TestExtractVariableValues:
    """Testes para a função extract_variable_values."""
    
    def test_extract_electrical_values(self):
        """Testa extração de valores elétricos."""
        data = {
            "voltage": {"a": 220.0, "b": 221.0, "c": 219.0},
            "current": {"a": 10.0, "b": 10.5, "c": 9.5},
            "power": {"active": 5000, "reactive": 1000, "apparent": 5100},
            "energy": {"active": 10000, "reactive": 2000, "apparent": 10200},
            "powerFactor": 0.98,
            "frequency": 60.0
        }
        
        values = extract_variable_values("electrical", data)
        
        assert values is not None
        assert "VoltageA" in values
        assert values["VoltageA"] == 220.0
        assert "CurrentA" in values
        assert values["CurrentA"] == 10.0
        assert "PowerActive" in values
        assert values["PowerActive"] == 5000
        assert "PowerFactor" in values
        assert values["PowerFactor"] == 0.98
        assert "Frequency" in values
        assert values["Frequency"] == 60.0
    
    def test_extract_environment_values(self):
        """Testa extração de valores ambientais."""
        data = {
            "temperature": 25.0,
            "humidity": 60.0,
            "caseTemperature": 45.0
        }
        
        values = extract_variable_values("environment", data)
        
        assert values is not None
        assert "Temperature" in values
        assert values["Temperature"] == 25.0
        assert "Humidity" in values
        assert values["Humidity"] == 60.0
        assert "CaseTemperature" in values
        assert values["CaseTemperature"] == 45.0
    
    def test_extract_vibration_values(self):
        """Testa extração de valores de vibração."""
        data = {
            "axial": 0.5,
            "radial": 0.3
        }
        
        values = extract_variable_values("vibration", data)
        
        assert values is not None
        assert "Axial" in values
        assert values["Axial"] == 0.5
        assert "Radial" in values
        assert values["Radial"] == 0.3
    
    def test_extract_unknown_sensor_type(self):
        """Testa extração com tipo de sensor desconhecido."""
        data = {"some": "data"}
        
        values = extract_variable_values("unknown", data)
        
        # Deve retornar dicionário vazio
        assert values == {}
    
    def test_extract_empty_data(self):
        """Testa extração com dados vazios."""
        values = extract_variable_values("electrical", {})
        
        # Deve retornar dicionário vazio ou parcial
        assert isinstance(values, dict)


class TestRabbitMQConsumerProperties:
    """Testes de propriedades do RabbitMQConsumer."""
    
    def test_consuming_property_initial(self):
        """Testa _consuming inicial."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        
        assert consumer._consuming is False
    
    def test_queues_property_initial(self):
        """Testa _queues inicial."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        
        assert consumer._queues == []


class TestRabbitMQConsumerConnect:
    """Testes para o método connect."""
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Testa conexão bem-sucedida."""
        mock_settings = MagicMock()
        mock_settings.rabbitmq_host = "localhost"
        mock_settings.rabbitmq_port = 5672
        mock_settings.rabbitmq_user = "guest"
        mock_settings.rabbitmq_pass = "guest"
        
        consumer = RabbitMQConsumer(mock_settings)
        
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        
        with patch('rabbitmq_consumer.aio_pika') as mock_aio_pika:
            mock_aio_pika.connect_robust = AsyncMock(return_value=mock_connection)
            
            await consumer.connect()
            
            assert consumer.connection == mock_connection
            assert consumer.channel == mock_channel
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Testa falha na conexão."""
        mock_settings = MagicMock()
        mock_settings.rabbitmq_host = "localhost"
        mock_settings.rabbitmq_port = 5672
        mock_settings.rabbitmq_user = "guest"
        mock_settings.rabbitmq_pass = "guest"
        
        consumer = RabbitMQConsumer(mock_settings)
        
        with patch('rabbitmq_consumer.aio_pika') as mock_aio_pika:
            mock_aio_pika.connect_robust = AsyncMock(side_effect=Exception("Connection failed"))
            
            with pytest.raises(ConnectionError):
                await consumer.connect()


class TestRabbitMQConsumerStartConsuming:
    """Testes para o método start_consuming."""
    
    @pytest.mark.asyncio
    async def test_start_consuming_not_connected(self):
        """Testa start_consuming sem conexão."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        consumer.channel = None
        
        with pytest.raises(RuntimeError, match="Não conectado"):
            await consumer.start_consuming()
    
    @pytest.mark.asyncio
    async def test_start_consuming_success(self):
        """Testa início de consumo com sucesso."""
        mock_settings = MagicMock()
        mock_settings.rabbitmq_queue = "motor_readings"
        
        consumer = RabbitMQConsumer(mock_settings)
        
        mock_queue = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)
        
        consumer.channel = mock_channel
        
        await consumer.start_consuming()
        
        assert consumer._consuming is True
        assert mock_queue in consumer._queues


class TestRabbitMQConsumerProcessMessage:
    """Testes para _process_message."""
    
    @pytest.mark.asyncio
    async def test_process_message_with_callback(self):
        """Testa processamento de mensagem com callback."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        
        callback = AsyncMock()
        consumer.set_message_callback(callback)
        
        # Mock mensagem
        message_data = {"_sensor_type": "electrical", "data": "test"}
        mock_message = AsyncMock()
        mock_message.body = json.dumps(message_data).encode()
        mock_message.process = MagicMock(return_value=AsyncMock())
        
        # Simular context manager
        class MockContextManager:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
        
        mock_message.process = MagicMock(return_value=MockContextManager())
        
        await consumer._process_message(mock_message)
        
        callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_message_json_error(self):
        """Testa processamento com JSON inválido."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        
        mock_message = AsyncMock()
        mock_message.body = b"invalid json"
        
        class MockContextManager:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
        
        mock_message.process = MagicMock(return_value=MockContextManager())
        
        # Não deve lançar exceção
        await consumer._process_message(mock_message)


class TestRabbitMQConsumerConsumeSpecificQueue:
    """Testes para consume_specific_queue."""
    
    @pytest.mark.asyncio
    async def test_consume_specific_queue_not_connected(self):
        """Testa consume_specific_queue sem conexão."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        consumer.channel = None
        
        with pytest.raises(RuntimeError, match="Não conectado"):
            await consumer.consume_specific_queue("electrical")
    
    @pytest.mark.asyncio
    async def test_consume_specific_queue_success(self):
        """Testa consumo de fila específica com sucesso."""
        mock_settings = MagicMock()
        mock_settings.rabbitmq_queue = "motor_readings"
        
        consumer = RabbitMQConsumer(mock_settings)
        
        mock_queue = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)
        
        consumer.channel = mock_channel
        
        await consumer.consume_specific_queue("electrical")
        
        assert mock_queue in consumer._queues
    
    @pytest.mark.asyncio
    async def test_consume_specific_queue_error(self):
        """Testa erro ao consumir fila específica."""
        mock_settings = MagicMock()
        mock_settings.rabbitmq_queue = "motor_readings"
        
        consumer = RabbitMQConsumer(mock_settings)
        
        mock_channel = AsyncMock()
        mock_channel.declare_queue = AsyncMock(side_effect=Exception("Queue error"))
        
        consumer.channel = mock_channel
        
        # Não deve lançar exceção, apenas logar
        await consumer.consume_specific_queue("electrical")


class TestRabbitMQConsumerIsConnectedProperty:
    """Testes para propriedade is_connected."""
    
    def test_is_connected_true(self):
        """Testa is_connected quando conectado."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        
        mock_connection = MagicMock()
        mock_connection.is_closed = False
        consumer.connection = mock_connection
        
        assert consumer.is_connected is True
    
    def test_is_connected_false_no_connection(self):
        """Testa is_connected sem conexão."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        consumer.connection = None
        
        assert consumer.is_connected is False
    
    def test_is_connected_false_closed(self):
        """Testa is_connected com conexão fechada."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        
        mock_connection = MagicMock()
        mock_connection.is_closed = True
        consumer.connection = mock_connection
        
        assert consumer.is_connected is False


class TestRabbitMQConsumerIsConsumingProperty:
    """Testes para propriedade is_consuming."""
    
    def test_is_consuming_true(self):
        """Testa is_consuming quando consumindo."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        consumer._consuming = True
        
        assert consumer.is_consuming is True
    
    def test_is_consuming_false(self):
        """Testa is_consuming quando não consumindo."""
        mock_settings = MagicMock()
        consumer = RabbitMQConsumer(mock_settings)
        consumer._consuming = False
        
        assert consumer.is_consuming is False