"""
Testes unitários para o RabbitMQ Publisher.

Estes testes usam mocks para simular conexões com RabbitMQ,
cobrindo a lógica de publicação sem precisar de infraestrutura.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
import json

# Adicionar path do serviço
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'mqtt_ingestor'))


class TestRabbitMQPublisherInit:
    """Testes de inicialização do publisher."""
    
    @patch('rabbitmq_publisher.get_settings')
    def test_publisher_creation(self, mock_settings):
        """Testa criação do publisher."""
        mock_settings.return_value = MagicMock(
            rabbitmq_host="localhost",
            rabbitmq_port=5672,
            rabbitmq_user="guest",
            rabbitmq_pass="guest",
            rabbitmq_exchange="motor_exchange",
            rabbitmq_queue="motor_readings"
        )
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        assert publisher is not None
        assert publisher.connection is None
        assert publisher.channel is None
        assert publisher.exchange is None
        assert publisher._connected is False
        
    @patch('rabbitmq_publisher.get_settings')
    def test_publisher_with_custom_settings(self, mock_settings):
        """Testa publisher com settings customizadas."""
        custom_settings = MagicMock(
            rabbitmq_host="custom-host",
            rabbitmq_port=5673
        )
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher(settings=custom_settings)
        
        assert publisher.settings == custom_settings


class TestRabbitMQPublisherConnect:
    """Testes de conexão com RabbitMQ."""
    
    @pytest.mark.asyncio
    @patch('aio_pika.connect_robust')
    @patch('rabbitmq_publisher.get_settings')
    async def test_connect_success(self, mock_settings, mock_connect):
        """Testa conexão bem-sucedida com RabbitMQ."""
        mock_settings.return_value = MagicMock(
            rabbitmq_host="localhost",
            rabbitmq_port=5672,
            rabbitmq_user="guest",
            rabbitmq_pass="guest",
            rabbitmq_exchange="motor_exchange",
            rabbitmq_queue="motor_readings"
        )
        
        mock_conn = AsyncMock()
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()
        mock_queue = AsyncMock()
        
        mock_conn.channel.return_value = mock_channel
        mock_channel.declare_exchange.return_value = mock_exchange
        mock_channel.declare_queue.return_value = mock_queue
        mock_connect.return_value = mock_conn
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        await publisher.connect()
        
        # Verifica que conectou
        mock_connect.assert_called_once()
        assert publisher._connected is True
        assert publisher.connection is not None
        
    @pytest.mark.asyncio
    @patch('aio_pika.connect_robust')
    @patch('rabbitmq_publisher.get_settings')
    async def test_connect_failure(self, mock_settings, mock_connect):
        """Testa falha de conexão com RabbitMQ."""
        mock_settings.return_value = MagicMock(
            rabbitmq_host="localhost",
            rabbitmq_port=5672,
            rabbitmq_user="guest",
            rabbitmq_pass="guest",
            rabbitmq_exchange="motor_exchange",
            rabbitmq_queue="motor_readings"
        )
        
        mock_connect.side_effect = Exception("Connection refused")
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        with pytest.raises(ConnectionError):
            await publisher.connect()
            
    @pytest.mark.asyncio
    @patch('aio_pika.connect_robust')
    @patch('rabbitmq_publisher.get_settings')
    async def test_connect_declares_queues(self, mock_settings, mock_connect):
        """Testa que connect declara as filas corretamente."""
        mock_settings.return_value = MagicMock(
            rabbitmq_host="localhost",
            rabbitmq_port=5672,
            rabbitmq_user="guest",
            rabbitmq_pass="guest",
            rabbitmq_exchange="motor_exchange",
            rabbitmq_queue="motor_readings"
        )
        
        mock_conn = AsyncMock()
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()
        mock_queue = AsyncMock()
        
        mock_conn.channel.return_value = mock_channel
        mock_channel.declare_exchange.return_value = mock_exchange
        mock_channel.declare_queue.return_value = mock_queue
        mock_connect.return_value = mock_conn
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        await publisher.connect()
        
        # Verifica que declarou exchange e filas
        mock_channel.declare_exchange.assert_called_once()
        assert mock_channel.declare_queue.call_count >= 1


class TestRabbitMQPublisherClose:
    """Testes de fechamento de conexão."""
    
    @pytest.mark.asyncio
    @patch('rabbitmq_publisher.get_settings')
    async def test_close_connection(self, mock_settings):
        """Testa fechamento de conexão."""
        mock_settings.return_value = MagicMock(
            rabbitmq_host="localhost",
            rabbitmq_port=5672
        )
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        # Simular conexão aberta
        mock_conn = AsyncMock()
        mock_conn.is_closed = False
        publisher.connection = mock_conn
        publisher._connected = True
        
        await publisher.close()
        
        mock_conn.close.assert_called_once()
        assert publisher._connected is False
        
    @pytest.mark.asyncio
    @patch('rabbitmq_publisher.get_settings')
    async def test_close_already_closed(self, mock_settings):
        """Testa close quando já está fechado."""
        mock_settings.return_value = MagicMock(
            rabbitmq_host="localhost"
        )
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        # Sem conexão ativa
        publisher.connection = None
        publisher._connected = False
        
        # Não deve lançar exceção
        await publisher.close()


class TestRabbitMQPublisherPublish:
    """Testes de publicação de mensagens."""
    
    @pytest.mark.asyncio
    @patch('rabbitmq_publisher.get_settings')
    async def test_publish_not_connected(self, mock_settings):
        """Testa publish quando não está conectado."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        publisher._connected = False
        
        with pytest.raises(RuntimeError):
            await publisher.publish("electrical", {"voltage": 220})
            
    @pytest.mark.asyncio
    @patch('rabbitmq_publisher.get_settings')
    async def test_publish_success(self, mock_settings):
        """Testa publicação bem-sucedida."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        # Simular conexão
        mock_exchange = AsyncMock()
        publisher.exchange = mock_exchange
        publisher._connected = True
        
        data = {"voltage": {"a": 220, "b": 221, "c": 219}}
        await publisher.publish("electrical", data)
        
        # Verifica que publicou
        mock_exchange.publish.assert_called_once()
        
    @pytest.mark.asyncio
    @patch('rabbitmq_publisher.get_settings')
    async def test_publish_with_pydantic_model(self, mock_settings):
        """Testa publicação com modelo Pydantic."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        mock_exchange = AsyncMock()
        publisher.exchange = mock_exchange
        publisher._connected = True
        
        # Simular modelo Pydantic
        mock_model = MagicMock()
        mock_model.model_dump.return_value = {"voltage": 220}
        
        await publisher.publish("electrical", mock_model)
        
        mock_model.model_dump.assert_called_once()
        mock_exchange.publish.assert_called_once()
        
    @pytest.mark.asyncio
    @patch('rabbitmq_publisher.get_settings')
    async def test_publish_with_custom_routing_key(self, mock_settings):
        """Testa publicação com routing key customizada."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        mock_exchange = AsyncMock()
        publisher.exchange = mock_exchange
        publisher._connected = True
        
        await publisher.publish("electrical", {"data": 1}, routing_key="custom.key")
        
        # Verifica routing key na chamada
        call_args = mock_exchange.publish.call_args
        assert call_args.kwargs.get('routing_key') == "custom.key"


class TestRabbitMQPublisherHealthCheck:
    """Testes de health check."""
    
    @pytest.mark.asyncio
    @patch('rabbitmq_publisher.get_settings')
    async def test_health_check_connected(self, mock_settings):
        """Testa health check quando conectado."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        mock_conn = AsyncMock()
        mock_conn.is_closed = False
        mock_channel = AsyncMock()
        
        publisher.connection = mock_conn
        publisher.channel = mock_channel
        publisher._connected = True
        
        result = await publisher.health_check()
        
        assert result is True
        
    @pytest.mark.asyncio
    @patch('rabbitmq_publisher.get_settings')
    async def test_health_check_not_connected(self, mock_settings):
        """Testa health check quando não está conectado."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        publisher._connected = False
        
        result = await publisher.health_check()
        
        assert result is False
        
    @pytest.mark.asyncio
    @patch('rabbitmq_publisher.get_settings')
    async def test_health_check_exception(self, mock_settings):
        """Testa health check com exceção."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        mock_conn = AsyncMock()
        mock_conn.is_closed = False
        mock_channel = AsyncMock()
        mock_channel.declare_queue.side_effect = Exception("Error")
        
        publisher.connection = mock_conn
        publisher.channel = mock_channel
        publisher._connected = True
        
        result = await publisher.health_check()
        
        assert result is False


class TestRabbitMQPublisherIsConnected:
    """Testes da propriedade is_connected."""
    
    @patch('rabbitmq_publisher.get_settings')
    def test_is_connected_true(self, mock_settings):
        """Testa is_connected quando conectado."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        mock_conn = MagicMock()
        mock_conn.is_closed = False
        
        publisher.connection = mock_conn
        publisher._connected = True
        
        assert publisher.is_connected is True
        
    @patch('rabbitmq_publisher.get_settings')
    def test_is_connected_false_no_connection(self, mock_settings):
        """Testa is_connected sem conexão."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        publisher.connection = None
        publisher._connected = False
        
        assert publisher.is_connected is False
        
    @patch('rabbitmq_publisher.get_settings')
    def test_is_connected_false_closed(self, mock_settings):
        """Testa is_connected com conexão fechada."""
        mock_settings.return_value = MagicMock()
        
        from rabbitmq_publisher import RabbitMQPublisher
        publisher = RabbitMQPublisher()
        
        mock_conn = MagicMock()
        mock_conn.is_closed = True
        
        publisher.connection = mock_conn
        publisher._connected = True
        
        assert publisher.is_connected is False
