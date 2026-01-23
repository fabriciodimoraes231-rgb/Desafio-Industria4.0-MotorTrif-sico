"""
Testes unitários para o RabbitMQ Publisher usando mocks.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'mqtt_ingestor'))


class TestRabbitMQPublisherUnit:
    """Testes de unidade do RabbitMQ Publisher."""
    
    def test_publisher_import(self):
        """Testa que o módulo pode ser importado."""
        from rabbitmq_publisher import RabbitMQPublisher
        assert RabbitMQPublisher is not None
        
    def test_publisher_class_exists(self):
        """Testa que a classe existe."""
        from rabbitmq_publisher import RabbitMQPublisher
        assert callable(RabbitMQPublisher)


class TestRabbitMQPublisherConnection:
    """Testes de conexão mockada."""
    
    @pytest.mark.asyncio
    async def test_connect_calls_aio_pika(self):
        """Testa que connect usa aio_pika."""
        with patch('rabbitmq_publisher.aio_pika') as mock_pika:
            with patch('rabbitmq_publisher.get_settings') as mock_settings:
                mock_settings.return_value = MagicMock(
                    rabbitmq_host="localhost",
                    rabbitmq_port=5672,
                    rabbitmq_user="guest",
                    rabbitmq_pass="guest",
                    rabbitmq_exchange="test",
                    rabbitmq_queue="test"
                )
                
                mock_conn = AsyncMock()
                mock_channel = AsyncMock()
                mock_exchange = AsyncMock()
                mock_queue = AsyncMock()
                
                mock_conn.channel.return_value = mock_channel
                mock_channel.declare_exchange.return_value = mock_exchange
                mock_channel.declare_queue.return_value = mock_queue
                mock_pika.connect_robust = AsyncMock(return_value=mock_conn)
                mock_pika.ExchangeType = MagicMock()
                
                from rabbitmq_publisher import RabbitMQPublisher
                publisher = RabbitMQPublisher()
                
                await publisher.connect()
                
                mock_pika.connect_robust.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_requires_connection(self):
        """Testa que publish requer conexão."""
        with patch('rabbitmq_publisher.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from rabbitmq_publisher import RabbitMQPublisher
            publisher = RabbitMQPublisher()
            publisher._connected = False
            
            with pytest.raises(RuntimeError):
                await publisher.publish("test", {"data": 1})

    @pytest.mark.asyncio
    async def test_publish_with_mock_exchange(self):
        """Testa publicação com exchange mockado."""
        with patch('rabbitmq_publisher.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from rabbitmq_publisher import RabbitMQPublisher
            publisher = RabbitMQPublisher()
            
            mock_exchange = AsyncMock()
            publisher.exchange = mock_exchange
            publisher._connected = True
            
            await publisher.publish("electrical", {"voltage": 220})
            
            mock_exchange.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_mock_connection(self):
        """Testa fechamento com conexão mockada."""
        with patch('rabbitmq_publisher.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from rabbitmq_publisher import RabbitMQPublisher
            publisher = RabbitMQPublisher()
            
            mock_conn = AsyncMock()
            mock_conn.is_closed = False
            publisher.connection = mock_conn
            publisher._connected = True
            
            await publisher.close()
            
            mock_conn.close.assert_called_once()
            assert publisher._connected is False

    def test_is_connected_property(self):
        """Testa propriedade is_connected."""
        with patch('rabbitmq_publisher.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from rabbitmq_publisher import RabbitMQPublisher
            publisher = RabbitMQPublisher()
            
            # Não conectado
            publisher.connection = None
            publisher._connected = False
            assert publisher.is_connected is False
            
            # Conexão fechada
            mock_conn = MagicMock()
            mock_conn.is_closed = True
            publisher.connection = mock_conn
            publisher._connected = True
            assert publisher.is_connected is False
            
            # Conectado
            mock_conn.is_closed = False
            assert publisher.is_connected is True

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """Testa health check quando não conectado."""
        with patch('rabbitmq_publisher.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from rabbitmq_publisher import RabbitMQPublisher
            publisher = RabbitMQPublisher()
            publisher._connected = False
            
            result = await publisher.health_check()
            assert result is False
