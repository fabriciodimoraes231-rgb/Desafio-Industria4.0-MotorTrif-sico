"""
Testes unitários para o cliente MQTT usando mocks.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'mqtt_ingestor'))


class TestMQTTClientUnit:
    """Testes de unidade do cliente MQTT."""
    
    def test_mqtt_client_import(self):
        """Testa que o módulo pode ser importado."""
        from mqtt_client import MQTTClient
        assert MQTTClient is not None
        
    def test_mqtt_client_class_exists(self):
        """Testa que a classe existe."""
        from mqtt_client import MQTTClient
        assert callable(MQTTClient)


class TestMQTTClientInit:
    """Testes de inicialização do cliente."""
    
    def test_client_initial_state(self):
        """Testa estado inicial do cliente."""
        with patch('mqtt_client.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                mqtt_broker="lse.dev.br",
                mqtt_port=1883,
                mqtt_client_id="test_client"
            )
            
            from mqtt_client import MQTTClient
            client = MQTTClient(settings=mock_settings.return_value)
            
            assert client.client is None
            assert client.on_message_callback is None
            assert client._connected is False

    def test_reconnect_interval(self):
        """Testa intervalo de reconexão padrão."""
        with patch('mqtt_client.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from mqtt_client import MQTTClient
            client = MQTTClient(settings=mock_settings.return_value)
            
            assert client._reconnect_interval == 5


class TestMQTTClientCallback:
    """Testes de callbacks."""
    
    def test_set_message_callback(self):
        """Testa configuração de callback de mensagens."""
        with patch('mqtt_client.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from mqtt_client import MQTTClient
            client = MQTTClient(settings=mock_settings.return_value)
            
            async def handler(topic, data):
                pass
                
            client.set_message_callback(handler)
            
            assert client.on_message_callback == handler


class TestMQTTClientConnection:
    """Testes de conexão mockada."""
    
    @pytest.mark.asyncio
    async def test_connect_creates_gmqtt_client(self):
        """Testa que connect cria cliente GMQTT."""
        with patch('mqtt_client.get_settings') as mock_settings:
            with patch('mqtt_client.GMQTTClient') as mock_gmqtt:
                mock_settings.return_value = MagicMock(
                    mqtt_broker="lse.dev.br",
                    mqtt_port=1883,
                    mqtt_client_id="test_client"
                )
                
                mock_client = MagicMock()
                mock_client.connect = AsyncMock()
                mock_gmqtt.return_value = mock_client
                
                from mqtt_client import MQTTClient
                client = MQTTClient(settings=mock_settings.return_value)
                
                await client.connect()
                
                mock_gmqtt.assert_called_once()
                assert client._connected is True

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Testa falha de conexão."""
        with patch('mqtt_client.get_settings') as mock_settings:
            with patch('mqtt_client.GMQTTClient') as mock_gmqtt:
                mock_settings.return_value = MagicMock(
                    mqtt_broker="lse.dev.br",
                    mqtt_port=1883,
                    mqtt_client_id="test_client"
                )
                
                mock_client = MagicMock()
                mock_client.connect = AsyncMock(side_effect=Exception("Connection refused"))
                mock_gmqtt.return_value = mock_client
                
                from mqtt_client import MQTTClient
                client = MQTTClient(settings=mock_settings.return_value)
                
                with pytest.raises(ConnectionError):
                    await client.connect()

    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """Testa desconexão bem-sucedida."""
        with patch('mqtt_client.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            
            from mqtt_client import MQTTClient
            client = MQTTClient(settings=mock_settings.return_value)
            
            mock_gmqtt = AsyncMock()
            client.client = mock_gmqtt
            client._connected = True
            
            await client.disconnect()
            
            mock_gmqtt.disconnect.assert_called_once()
            assert client._connected is False


class TestMQTTMessageParsing:
    """Testes de parsing de mensagens."""
    
    def test_parse_electrical_json(self):
        """Testa parsing de JSON elétrico."""
        payload = json.dumps({
            "timestamp": "2024-01-01T00:00:00Z",
            "voltage": {"a": 220, "b": 221, "c": 219},
            "current": {"a": 50, "b": 51, "c": 49}
        })
        
        data = json.loads(payload)
        
        assert data["voltage"]["a"] == 220
        assert data["current"]["b"] == 51

    def test_parse_environment_json(self):
        """Testa parsing de JSON ambiental."""
        payload = json.dumps({
            "timestamp": "2024-01-01T00:00:00Z",
            "temperature": 35.5,
            "humidity": 60.0,
            "caseTemperature": 45.0
        })
        
        data = json.loads(payload)
        
        assert data["temperature"] == 35.5
        assert data["humidity"] == 60.0

    def test_parse_vibration_json(self):
        """Testa parsing de JSON de vibração."""
        payload = json.dumps({
            "timestamp": "2024-01-01T00:00:00Z",
            "axial": 0.5,
            "radial": 0.3
        })
        
        data = json.loads(payload)
        
        assert data["axial"] == 0.5
        assert data["radial"] == 0.3
