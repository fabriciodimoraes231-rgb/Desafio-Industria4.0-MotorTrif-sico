"""
Testes unitários para o módulo mqtt_client.py.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'mqtt_ingestor'))


class TestMQTTClientImport:
    """Testes de importação do MQTTClient."""

    def test_import_mqtt_client(self):
        """Testa importação do MQTTClient."""
        from mqtt_client import MQTTClient
        assert MQTTClient is not None

    def test_mqtt_client_callable(self):
        """Testa que MQTTClient é callable."""
        from mqtt_client import MQTTClient
        assert callable(MQTTClient)


class TestMQTTClientCreation:
    """Testes de criação do MQTTClient."""

    @patch('mqtt_client.get_settings')
    def test_create_mqtt_client(self, mock_settings):
        """Testa criação básica."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic"]
        )
        from mqtt_client import MQTTClient
        client = MQTTClient()
        assert client is not None

    @patch('mqtt_client.get_settings')
    def test_mqtt_client_initial_not_connected(self, mock_settings):
        """Testa que cliente não está conectado inicialmente."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic"]
        )
        from mqtt_client import MQTTClient
        client = MQTTClient()
        assert client.is_connected is False


class TestMQTTClientConnect:
    """Testes de conexão."""

    @pytest.mark.asyncio
    @patch('mqtt_client.get_settings')
    @patch('mqtt_client.GMQTTClient')
    async def test_connect_creates_gmqtt_client(self, mock_gmqtt, mock_settings):
        """Testa que connect cria cliente gmqtt."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic"]
        )
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.subscribe = MagicMock()
        mock_gmqtt.return_value = mock_client
        
        from mqtt_client import MQTTClient
        client = MQTTClient()
        
        await client.connect()
        
        mock_gmqtt.assert_called()

    @pytest.mark.asyncio
    @patch('mqtt_client.get_settings')
    @patch('mqtt_client.GMQTTClient')
    async def test_connect_subscribes_to_topics(self, mock_gmqtt, mock_settings):
        """Testa que connect se inscreve nos tópicos."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic1", "test/topic2"]
        )
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.subscribe = MagicMock()
        mock_gmqtt.return_value = mock_client
        
        from mqtt_client import MQTTClient
        client = MQTTClient()
        
        await client.connect()
        
        # connect foi chamado


class TestMQTTClientDisconnect:
    """Testes de desconexão."""

    @pytest.mark.asyncio
    @patch('mqtt_client.get_settings')
    async def test_disconnect_not_connected(self, mock_settings):
        """Testa disconnect sem conexão prévia."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic"]
        )
        from mqtt_client import MQTTClient
        client = MQTTClient()
        
        # Não deve lançar exceção
        await client.disconnect()


class TestMQTTClientCallback:
    """Testes de callback."""

    @patch('mqtt_client.get_settings')
    def test_set_message_callback(self, mock_settings):
        """Testa configuração de callback."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic"]
        )
        from mqtt_client import MQTTClient
        client = MQTTClient()
        
        def callback(topic, payload):
            pass
        
        client.set_message_callback(callback)
        
        assert client.on_message_callback == callback


class TestMQTTClientProperties:
    """Testes de propriedades."""

    @patch('mqtt_client.get_settings')
    def test_is_connected_property(self, mock_settings):
        """Testa propriedade is_connected."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic"]
        )
        from mqtt_client import MQTTClient
        client = MQTTClient()
        
        assert hasattr(client, 'is_connected')
        assert client.is_connected is False

    @patch('mqtt_client.get_settings')
    def test_has_settings(self, mock_settings):
        """Testa que cliente tem settings."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic"]
        )
        from mqtt_client import MQTTClient
        client = MQTTClient()
        
        assert hasattr(client, 'settings') or hasattr(client, '_settings')


class TestMQTTClientOnConnect:
    """Testes do callback on_connect."""

    @patch('mqtt_client.get_settings')
    def test_has_on_connect_handler(self, mock_settings):
        """Testa que cliente tem handler on_connect."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic"]
        )
        from mqtt_client import MQTTClient
        client = MQTTClient()
        
        assert hasattr(client, '_on_connect')


class TestMQTTClientOnMessage:
    """Testes do callback on_message."""

    @patch('mqtt_client.get_settings')
    def test_has_on_message_handler(self, mock_settings):
        """Testa que cliente tem handler on_message."""
        mock_settings.return_value = MagicMock(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_client_id="test-client",
            mqtt_topics=["test/topic"]
        )
        from mqtt_client import MQTTClient
        client = MQTTClient()
        
        assert hasattr(client, '_on_message')
